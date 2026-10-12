"""Offline tests of evidence classification; never actual installed acceptance."""
import importlib.util
import json
from pathlib import Path

import pytest


COMMITS = {"frappe": "a" * 40, "erpnext": "b" * 40, "ultimatesales_connector": "c" * 40}


@pytest.fixture
def runner():
    path = Path(__file__).parents[1] / "tools" / "run_acceptance.py"
    spec = importlib.util.spec_from_file_location("acceptance_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("code, output", [
    (0, "Ran 0 tests in 0.0s\nOK"),
    (0, "Ran 4 tests in 0.0s\nOK (skipped=1)"),
    (1, "Ran 4 tests in 0.0s\nFAILED (failures=1)"),
    (0, "Ran 4 tests in 0.0s\nFAILED (failures=1)"),
    (0, "Ran 1 test in 0.0s\nOK"),
    (0, "No execution summary"),
])
def test_runner_never_marks_skipped_failed_or_unexecuted_module_passed(runner, monkeypatch, code, output):
    environment = json.dumps({"site": "disposable-a", "frappe": "16", "erpnext": "16",
                              "database": "MariaDB", "transport": "synthetic"})
    commands = iter([(0, environment), (code, output)])
    monkeypatch.setattr(runner, "run_command", lambda *_: next(commands))
    monkeypatch.setattr(runner, "read_app_revisions", lambda _: dict(COMMITS))
    result = runner.run_site("bench", Path("/synthetic"), "disposable-a")
    assert result["status"] == "failed"
    assert result["checks"][0]["status"] == "failed"


def test_runner_requires_real_preflight_for_exact_requested_site(runner, monkeypatch):
    environment = json.dumps({"site": "another-site", "frappe": "16", "erpnext": "16",
                              "database": "MariaDB", "transport": "synthetic"})
    monkeypatch.setattr(runner, "run_command", lambda *_: (0, environment))
    monkeypatch.setattr(runner, "read_app_revisions", lambda _: dict(COMMITS))
    result = runner.run_site("bench", Path("/synthetic"), "disposable-a")
    assert result["status"] == "failed" and not result["checks"]


def test_runner_counts_each_installed_module_only_after_execution(runner, monkeypatch):
    environment = json.dumps({"site": "disposable-a", "frappe": "16", "erpnext": "16",
                              "database": "MariaDB", "transport": "synthetic"})
    commands = iter([(0, "Notice before JSON\n" + environment)] +
                    [(0, f"Ran {runner.expected_test_count(module)} tests in 0.0s\nOK") for module in runner.MODULES])
    monkeypatch.setattr(runner, "run_command", lambda *_: next(commands))
    monkeypatch.setattr(runner, "read_app_revisions", lambda _: dict(COMMITS))
    result = runner.run_site("bench", Path("/synthetic"), "disposable-a")
    assert result["status"] == "passed"
    assert result["environment"]["commits"] == COMMITS
    assert result["app_revisions_stable"] is True
    assert len(result["checks"]) == len(runner.MODULES)
    assert all(check["test_count"] == check["expected_test_count"] and check["skipped"] == 0
               for check in result["checks"])


def app_roots(path):
    for app in COMMITS:
        (path / "apps" / app).mkdir(parents=True)
    return path


def test_external_runner_captures_full_shas_from_fixed_app_paths(runner, monkeypatch, tmp_path):
    bench_dir = app_roots(tmp_path)
    commands = []
    monkeypatch.setattr(runner.shutil, "which", lambda _: "/controlled/bin/git")

    def read_revision(command, cwd, timeout):
        commands.append((command, cwd, timeout))
        app = Path(command[2]).name
        return 0, COMMITS[app] + "\n"

    monkeypatch.setattr(runner, "run_command", read_revision)
    assert runner.read_app_revisions(bench_dir) == COMMITS
    assert commands == [(["/controlled/bin/git", "-C", str(bench_dir / "apps" / app),
                         "rev-parse", "--verify", "HEAD"], bench_dir, 10) for app in COMMITS]


@pytest.mark.parametrize("code,output", [(1, "a" * 40), (0, "unavailable"), (0, "a" * 39),
                                        (0, "a" * 64), (0, "a" * 40 + "\nextra-output")])
def test_revision_capture_rejects_failed_or_ambiguous_evidence(runner, monkeypatch, tmp_path, code, output):
    bench_dir = app_roots(tmp_path)
    monkeypatch.setattr(runner.shutil, "which", lambda _: "/controlled/bin/git")
    monkeypatch.setattr(runner, "run_command", lambda *_: (code, output))
    with pytest.raises(RuntimeError, match="full commit SHA"):
        runner.read_app_revisions(bench_dir)


def test_revision_capture_requires_git(runner, monkeypatch, tmp_path):
    monkeypatch.setattr(runner.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="Git is unavailable"):
        runner.read_app_revisions(tmp_path)


def test_revision_capture_requires_expected_app_repositories(runner, monkeypatch, tmp_path):
    monkeypatch.setattr(runner.shutil, "which", lambda _: "/controlled/bin/git")
    monkeypatch.setattr(runner, "run_command", lambda *_: pytest.fail("Unexpected process launch"))
    with pytest.raises(RuntimeError, match="repository is missing"):
        runner.read_app_revisions(tmp_path)


def test_runner_fails_when_app_revisions_change_during_acceptance(runner, monkeypatch):
    environment = json.dumps({"site": "disposable-a", "frappe": "16", "erpnext": "16",
                              "database": "MariaDB", "transport": "synthetic"})
    commands = iter([(0, environment)] +
                    [(0, f"Ran {runner.expected_test_count(module)} tests in 0.0s\nOK") for module in runner.MODULES])
    revisions = iter([dict(COMMITS), {**COMMITS, "ultimatesales_connector": "d" * 40}])
    monkeypatch.setattr(runner, "run_command", lambda *_: next(commands))
    monkeypatch.setattr(runner, "read_app_revisions", lambda _: next(revisions))
    result = runner.run_site("bench", Path("/synthetic"), "disposable-a")
    assert result["status"] == "failed" and result["app_revisions_stable"] is False
    assert result["environment"]["commits"] == COMMITS
    assert "revisions changed" in result["reason"]
    assert all(check["status"] == "passed" for check in result["checks"])


def test_runner_stops_before_tests_when_revision_evidence_is_unavailable(runner, monkeypatch):
    environment = json.dumps({"site": "disposable-a", "frappe": "16", "erpnext": "16",
                              "database": "MariaDB", "transport": "synthetic"})
    commands = []

    def preflight_only(command, *_):
        commands.append(command)
        assert command[3] == "execute"
        return 0, environment

    def unavailable(_):
        raise RuntimeError("An installed app revision could not be verified as a full commit SHA.")

    monkeypatch.setattr(runner, "run_command", preflight_only)
    monkeypatch.setattr(runner, "read_app_revisions", unavailable)
    result = runner.run_site("bench", Path("/synthetic"), "disposable-a")
    assert result["status"] == "failed" and not result["checks"]
    assert len(commands) == 1
    assert "full commit SHA" in result["reason"]


@pytest.mark.parametrize("same_revisions", [True, False])
def test_two_site_report_requires_identical_app_revisions(runner, monkeypatch, tmp_path, same_revisions):
    bench_dir = app_roots(tmp_path)
    sites = ["disposable-a", "disposable-b"]
    for site in sites:
        site_path = bench_dir / "sites" / site
        site_path.mkdir(parents=True)
        (site_path / "site_config.json").write_text("{}")
    report_path = tmp_path / "report.json"
    monkeypatch.setattr(runner.shutil, "which", lambda _: "/controlled/bin/bench")

    def completed_site(_, __, site):
        revisions = dict(COMMITS)
        if site == sites[1] and not same_revisions:
            revisions["ultimatesales_connector"] = "d" * 40
        return {"site": site, "status": "passed", "checks": [],
                "environment": {"commits": revisions}, "app_revisions_stable": True}

    monkeypatch.setattr(runner, "run_site", completed_site)
    code = runner.main(["--bench-dir", str(bench_dir), "--site", sites[0], "--site", sites[1],
                        "--confirm-disposable", "--report", str(report_path)])
    report = json.loads(report_path.read_text())
    assert code == (0 if same_revisions else 1)
    assert report["status"] == ("passed" if same_revisions else "failed")
    assert report["same_app_revisions_across_sites"] is same_revisions
    assert report["two_site_execution"] is same_revisions
