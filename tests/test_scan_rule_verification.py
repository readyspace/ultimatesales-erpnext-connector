"""Mocked scanner checks with synthetic rules; no vendor source or network calls."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def scan_harness(monkeypatch, tmp_path):
    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location("scan_rule_fetcher", root / "tools/fetch_security_rules.py")
    fetcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fetcher)
    rules = tmp_path / "rules"
    entries = []
    for relative in sorted(fetcher.RULE_PATHS):
        body = ("synthetic scanner rule: " + relative + "\n").encode()
        path = rules / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        entries.append({"path": relative, "url": fetcher.RAW_PREFIX + relative,
                        "sha256": fetcher.sha256(body)})
    manifest = {"schema_version": 1, "repository": fetcher.REPOSITORY, "commit": fetcher.COMMIT,
                "source_prefix": fetcher.SOURCE_PREFIX, "files": entries}
    manifest_path = tmp_path / "manifest.json"
    manifest_body = (json.dumps(manifest, indent=2) + "\n").encode()
    manifest_path.write_bytes(manifest_body)
    monkeypatch.setattr(fetcher, "MANIFEST_SHA256", fetcher.sha256(manifest_body))
    load_manifest = fetcher.load_manifest
    monkeypatch.setattr(fetcher, "load_manifest", lambda: load_manifest(manifest_path))
    monkeypatch.setitem(sys.modules, "fetch_security_rules", fetcher)
    spec = importlib.util.spec_from_file_location("scan_rule_wrapper", root / "tooling/environments/scan-security.py")
    wrapper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wrapper)
    monkeypatch.setattr(wrapper, "ROOT", tmp_path)
    targets = ["ultimatesales_connector", "ultimatesales_connector/tests/test_synthetic.py"]
    monkeypatch.setattr(wrapper, "TARGETS", targets)
    for relative in ["ultimatesales_connector/domain.py", targets[1]]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Synthetic scanner target\n", encoding="utf-8")
    report_path = tmp_path / "scan.json"
    return SimpleNamespace(wrapper=wrapper, fetcher=fetcher, rules=rules, manifest=manifest_path,
                           report=report_path, tmp_path=tmp_path)


def invoke(harness, monkeypatch, directory=None):
    monkeypatch.setattr(sys, "argv", ["scan-security.py", "--semgrep", "/synthetic/semgrep",
                                     "--rules-directory", str(directory or harness.rules),
                                     "--report", str(harness.report)])
    return harness.wrapper.main()


def scanner_response(harness):
    payload = {"results": [], "errors": [], "version": "synthetic-offline",
               "paths": {"scanned": ["ultimatesales_connector/domain.py",
                                      "ultimatesales_connector/tests/test_synthetic.py"]}}
    return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")


def mutate_cache(harness, change):
    rule = harness.rules / sorted(harness.fetcher.RULE_PATHS)[0]
    if change == "changed":
        rule.write_bytes(b"changed synthetic rule")
    elif change == "missing":
        rule.unlink()
    elif change == "extra":
        (harness.rules / "unexpected.yml").write_bytes(b"extra synthetic rule")
    elif change == "rule_symlink":
        target = harness.tmp_path / "outside.yml"
        target.write_bytes(rule.read_bytes())
        rule.unlink()
        rule.symlink_to(target)
    elif change == "manifest_changed":
        harness.manifest.write_bytes(harness.manifest.read_bytes() + b" ")


@pytest.mark.parametrize("change", ["changed", "missing", "extra", "rule_symlink", "manifest_changed"])
def test_invalid_pinned_rules_never_launch_scanner(scan_harness, monkeypatch, change):
    mutate_cache(scan_harness, change)
    monkeypatch.setattr(scan_harness.wrapper.subprocess, "run",
                        lambda *_, **__: pytest.fail("Scanner launched for invalid rules"))
    with pytest.raises(SystemExit) as error:
        invoke(scan_harness, monkeypatch)
    assert error.value.code == 2
    assert not scan_harness.report.exists()


def test_supplied_rules_directory_symlink_is_rejected_before_resolution(scan_harness, monkeypatch):
    alias = scan_harness.tmp_path / "rules-alias"
    alias.symlink_to(scan_harness.rules, target_is_directory=True)
    monkeypatch.setattr(scan_harness.wrapper.subprocess, "run",
                        lambda *_, **__: pytest.fail("Scanner launched through a symlink"))
    with pytest.raises(SystemExit) as error:
        invoke(scan_harness, monkeypatch, alias)
    assert error.value.code == 2
    assert not scan_harness.report.exists()


@pytest.mark.parametrize("change", ["changed", "missing", "extra", "rule_symlink", "manifest_changed"])
def test_mutating_rules_during_scan_prevents_pass_and_records_safe_failure(scan_harness, monkeypatch, change):
    calls = []

    def scanner(command, **kwargs):
        calls.append(command)
        mutate_cache(scan_harness, change)
        return scanner_response(scan_harness)

    monkeypatch.setattr(scan_harness.wrapper.subprocess, "run", scanner)
    assert invoke(scan_harness, monkeypatch) == 1
    report = json.loads(scan_harness.report.read_text())
    assert len(calls) == 1
    assert report["status"] == "FAIL"
    assert report["unchanged_pinned_rules_verified"] is False
    assert report["rules_verification_errors"] == ["pinned_rules_not_stable_during_scan"]
    assert len(report["rules_sha256"]) == 12
    assert report["verified_rules_sha256_after_scan"] == {}
    assert report["errors"] == [] and report["blocking_count"] == 0
    assert report["source_stable_during_scan"] is True
    assert "changed synthetic rule" not in scan_harness.report.read_text()


def test_unchanged_rules_verify_before_and_after_successful_scan(scan_harness, monkeypatch):
    commands = []

    def scanner(command, **kwargs):
        commands.append(command)
        assert command[command.index("--config") + 1] == str(scan_harness.rules)
        assert "--no-git-ignore" in command
        assert command[-2:] == scan_harness.wrapper.TARGETS
        return scanner_response(scan_harness)

    monkeypatch.setattr(scan_harness.wrapper.subprocess, "run", scanner)
    assert invoke(scan_harness, monkeypatch) == 0
    report = json.loads(scan_harness.report.read_text())
    assert len(commands) == 1 and report["status"] == "PASS"
    assert report["unchanged_pinned_rules_verified"] is True
    assert report["rules_verification_errors"] == []
    assert len(report["rules_sha256"]) == 12
    assert report["rules_sha256"] == report["verified_rules_sha256_after_scan"]
