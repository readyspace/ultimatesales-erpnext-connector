#!/usr/bin/env python3
"""Run unchanged pinned Marketplace rules and retain sanitized source evidence.

Includes explicit installed-test targets that Semgrep otherwise ignores by
default. Never suppress findings, upload source, or retain raw source snippets.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / ".reference-source/marketplace/validation/semgrep-rules"
# Explicit test paths bypass Semgrep's default test-directory exclusion.
# Discover future modules too, so adding a helper cannot silently evade the scan.
TARGETS = ["ultimatesales_connector"] + sorted(
    str(path.relative_to(ROOT))
    for path in (ROOT / "ultimatesales_connector/tests").rglob("*.py")
    if path.name != "__init__.py"
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot():
    return {str(path.relative_to(ROOT)): digest(path)
            for path in (ROOT / "ultimatesales_connector").rglob("*")
            if path.is_file() and path.suffix in {".py", ".js", ".json"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semgrep", default=shutil.which("semgrep"))
    parser.add_argument("--rules-directory", type=Path, default=RULES)
    parser.add_argument("--report", type=Path, default=ROOT / "docs/upstream/security-scan.json")
    args = parser.parse_args()
    if not args.semgrep:
        parser.error("Install the scanner locally or pass --semgrep; no scan has run.")
    sys.path.insert(0, str(ROOT / "tools"))
    from fetch_security_rules import load_manifest, verify_rules_directory
    # Retain the supplied path so verification can detect symlink components.
    rules = args.rules_directory.absolute()
    try:
        manifest = load_manifest()
        rules_before = verify_rules_directory(manifest, rules)
    except (ValueError, OSError):
        parser.error("Pinned rules are missing, changed or unsafe. Fetch and verify the unchanged rules first.")
    before = snapshot()
    command = [str(Path(args.semgrep).resolve()), "scan", "--config", str(rules),
               "--json", "--quiet", "--metrics=off", "--disable-version-check",
               "--no-git-ignore", *TARGETS]
    with tempfile.TemporaryDirectory(prefix="us-security-") as directory:
        environment = dict(os.environ)
        environment.update({"SEMGREP_SETTINGS_FILE": str(Path(directory) / "settings.yml"),
                            "SEMGREP_LOG_FILE": str(Path(directory) / "scanner.log"),
                            "OTEL_SDK_DISABLED": "true"})
        try:
            import certifi
            environment["SSL_CERT_FILE"] = certifi.where()
            environment["REQUESTS_CA_BUNDLE"] = certifi.where()
        except ImportError:
            pass
        result = subprocess.run(command, cwd=ROOT, env=environment,
                                text=True, capture_output=True, timeout=300, check=False)
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        raise SystemExit("Scanner failed without JSON. No successful scan evidence was written.")
    after = snapshot()
    rules_after = {}
    rule_verification_errors = []
    try:
        manifest_after = load_manifest()
        rules_after = verify_rules_directory(manifest_after, rules)
        rules_stable = manifest_after == manifest and rules_after == rules_before
    except (ValueError, OSError):
        rules_stable = False
    if not rules_stable:
        rule_verification_errors.append("pinned_rules_not_stable_during_scan")
    findings = []
    for finding in payload.get("results", []):
        extra = finding.get("extra", {})
        metadata = extra.get("metadata", {})
        severity = extra.get("severity", "INFO")
        blocking = metadata.get("is_blocking") is True or severity in {"ERROR", "CRITICAL", "HIGH"}
        path = finding["path"]
        findings.append({"rule": finding["check_id"].rsplit(".", 1)[-1],
                         "path": path, "line": finding["start"]["line"],
                         "severity": severity, "blocking": blocking,
                         "test_only": "/tests/" in path,
                         "internal_only": bool(metadata.get("is_internal_only"))})
    errors = [{"code": error.get("code"), "level": error.get("level"),
               "path": error.get("path"), "type": str(error.get("type"))}
              for error in payload.get("errors", [])]
    scan_paths = payload.get("paths", {}).get("scanned", [])
    stable = before == after
    missing_test_targets = sorted(set(TARGETS[1:]) - set(scan_paths))
    blocking = [finding for finding in findings if finding["blocking"]]
    report = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if result.returncode in (0, 1) and not blocking and not errors
                  and stable and rules_stable and scan_paths and not missing_test_targets else "FAIL",
        "scanner_version": payload.get("version"), "scanner_exit_code": result.returncode,
        "validator_repository": "https://github.com/frappe/marketplace",
        "validator_commit": "cb1a58adfacbe9d8e0e4a4d5c7d1ef7786a05e6a",
        "command": ["semgrep", *command[1:3], "<VERIFIED_PINNED_RULES>", *command[4:]],
        "targets": TARGETS, "source_stable_during_scan": stable,
        "missing_explicit_test_targets": missing_test_targets,
        "scanned_file_count": len(scan_paths), "finding_count": len(findings),
        "blocking_count": len(blocking),
        "production_blocking_count": sum(not finding["test_only"] for finding in blocking),
        "test_only_blocking_count": sum(finding["test_only"] for finding in blocking),
        "errors": errors, "findings": findings,
        "scanned_file_sha256": {path: after[path] for path in scan_paths if path in after},
        "rules_sha256": rules_before,
        "verified_rules_sha256_after_scan": rules_after,
        "rules_manifest": "docs/upstream/security-rules-manifest.json",
        "unchanged_pinned_rules_verified": rules_stable,
        "rules_verification_errors": rule_verification_errors,
        "limitations": ["Static local scan only; no Marketplace submission/reviewer approval.",
                        "No installed-site permission, live-account or worker execution evidence.",
                        "TOML metadata is checked separately by packaging and upstream dependency validators."],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status']}: {len(scan_paths)} scanned files; {len(findings)} findings; "
          f"{len(blocking)} blocking ({report['production_blocking_count']} production, "
          f"{report['test_only_blocking_count']} installed-test-only); {len(errors)} errors; "
          f"pinned rules {'PASS' if rules_stable else 'FAIL'}.")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
