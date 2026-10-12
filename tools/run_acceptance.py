#!/usr/bin/env python3
"""Run installed acceptance on explicitly opted-in disposable sites.

This tool never provisions sites, sets write flags, installs apps, or takes CRM
credentials. A successful result certifies only its recorded synthetic checks.
"""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


APP_REPOSITORIES = ("frappe", "erpnext", "ultimatesales_connector")


MODULES = (
    "ultimatesales_connector.tests.test_install_contract",
    "ultimatesales_connector.tests.test_permissions_recovery",
    "ultimatesales_connector.tests.test_native_queue",
)


def run_command(command, bench_dir, timeout):
    try:
        result = subprocess.run(command, cwd=bench_dir, text=True, capture_output=True,
                                timeout=timeout, check=False)
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 124, "Acceptance command timed out."


def read_app_revisions(bench_dir):
    """Capture full app SHAs at the external CLI process boundary, never in site code."""
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git is unavailable; installed app revisions cannot be verified.")
    revisions = {}
    for app in APP_REPOSITORIES:
        repository = bench_dir / "apps" / app
        if not repository.is_dir():
            raise RuntimeError("An expected installed app repository is missing.")
        code, output = run_command([git, "-C", str(repository), "rev-parse", "--verify", "HEAD"],
                                   bench_dir, 10)
        revision = output.strip()
        if code != 0 or not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise RuntimeError("An installed app revision could not be verified as a full commit SHA.")
        revisions[app] = revision
    return revisions


def decode_result(output):
    # bench execute prints JSON, but may also print notices. Decode only JSON
    # objects and require the keys emitted by our secret-free preflight helper.
    decoder = json.JSONDecoder()
    for position, character in enumerate(output):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(output[position:])
        except ValueError:
            continue
        if isinstance(value, dict) and {"site", "frappe", "erpnext", "database", "transport"} <= value.keys():
            return value
    return None


def expected_test_count(module):
    path = Path(__file__).resolve().parents[1] / Path(*module.split(".")).with_suffix(".py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
               for node in ast.walk(tree))


def run_site(bench, bench_dir, site):
    record = {"site": site, "status": "failed", "checks": []}
    code, output = run_command(
        [bench, "--site", site, "execute", "ultimatesales_connector.tests.acceptance_support.acceptance_preflight"],
        bench_dir, 120,
    )
    environment = decode_result(output) if code == 0 else None
    if not environment or environment.get("site") != site:
        record["reason"] = "Preflight failed. Check disposable opt-in, synthetic Company, write gate, installed stack and queue locally."
        return record
    try:
        revisions = read_app_revisions(bench_dir)
    except RuntimeError as error:
        record["reason"] = str(error)
        return record
    environment["commits"] = revisions
    record["environment"] = environment
    for module in MODULES:
        print(f"{site}: running {module.rsplit('.', 1)[-1]}", flush=True)
        code, output = run_command([bench, "--site", site, "run-tests", "--module", module], bench_dir, 900)
        counts = re.findall(r"Ran (\d+) tests?\b", output)
        skipped = re.findall(r"skipped[= ](\d+)", output, flags=re.IGNORECASE)
        check = {"module": module, "exit_code": code,
                 "test_count": sum(map(int, counts)), "expected_test_count": expected_test_count(module),
                 "skipped": max(map(int, skipped), default=0)}
        failure_summary = bool(re.search(r"\bFAILED\b|(?:failures|errors)=[1-9]\d*", output))
        check["status"] = "passed" if (code == 0 and not failure_summary and check["test_count"] > 0
                                        and check["test_count"] >= check["expected_test_count"]
                                        and check["skipped"] == 0) else "failed"
        record["checks"].append(check)
        if check["status"] != "passed":
            record["reason"] = "An installed test failed, skipped, timed out or produced no execution count. Inspect local test output; no raw responses are saved here."
            return record
    try:
        record["app_revisions_stable"] = read_app_revisions(bench_dir) == revisions
    except RuntimeError as error:
        record["reason"] = str(error)
        return record
    if not record["app_revisions_stable"]:
        record["reason"] = "Installed app revisions changed during acceptance; rerun on fixed source commits."
        return record
    record["status"] = "passed"
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench-dir", type=Path, required=True)
    parser.add_argument("--site", action="append", required=True, help="Repeat for two distinct disposable sites.")
    parser.add_argument("--confirm-disposable", action="store_true", help="Acknowledge tests commit and clean synthetic records.")
    parser.add_argument("--single-site", action="store_true", help="Run one site only; site isolation remains unverified.")
    parser.add_argument("--parallel-sites", action="store_true", help="Run two site suites concurrently on this bench.")
    parser.add_argument("--report", type=Path, default=Path("acceptance-results.json"))
    args = parser.parse_args(argv)
    if not args.confirm_disposable:
        parser.error("--confirm-disposable is required; the installed suites commit real SQL records.")
    sites = args.site
    if len(set(sites)) != len(sites) or any(not site or site.startswith("-") or "/" in site or "\\" in site for site in sites):
        parser.error("Use distinct explicit site names, not paths or wildcard selectors.")
    if not args.single_site and len(sites) < 2:
        parser.error("Use two disposable sites or explicitly choose --single-site.")
    if args.single_site and len(sites) != 1:
        parser.error("--single-site requires exactly one site.")
    bench_dir = args.bench_dir.resolve()
    if not (bench_dir / "sites").is_dir() or not (bench_dir / "apps").is_dir():
        parser.error("--bench-dir must identify an existing Bench directory.")
    for site in sites:
        if not (bench_dir / "sites" / site / "site_config.json").is_file():
            parser.error(f"Site {site} has no local site_config.json in this bench.")
    bench = shutil.which("bench")
    if not bench:
        parser.error("The Bench executable is unavailable on PATH.")
    if args.parallel_sites:
        with ThreadPoolExecutor(max_workers=min(len(sites), 2)) as executor:
            futures = [executor.submit(run_site, bench, bench_dir, site) for site in sites]
            results = [future.result() for future in futures]
    else:
        results = [run_site(bench, bench_dir, site) for site in sites]
    observed_revisions = [result.get("environment", {}).get("commits") for result in results]
    same_revisions = bool(observed_revisions and observed_revisions[0]) and all(
        revisions == observed_revisions[0] for revisions in observed_revisions)
    passed = all(result["status"] == "passed" for result in results) and same_revisions
    report = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if passed else "failed", "sites": results,
        "same_app_revisions_across_sites": same_revisions,
        "two_site_execution": len(sites) >= 2 and passed,
        "simultaneous_site_execution": args.parallel_sites and len(sites) >= 2 and passed,
        "live_crm_contract": "not run", "worker_kill_restore_upgrade": "not run",
        "scope": "Installed Frappe/ERPNext SQL and permissions; actual Redis/RQ workers; synthetic transport.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Acceptance {'passed' if passed else 'failed'}; report: {args.report.resolve()}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
