"""Offline transaction-ownership regressions for the installed acceptance harness.

The stateful database below models pending/committed rows and worker snapshot
rollback. It proves harness control flow, never Frappe/ERPNext SQL correctness.
"""
import copy
import importlib
import sys
import types

import pytest


class Record(dict):
    __getattr__ = dict.get

    def __setattr__(self, key, value):
        self[key] = value


class TransactionDB:
    def __init__(self):
        company = {"doctype": "Company", "name": "Synthetic Company", "default_currency": "USD"}
        self.committed = {("Company", company["name"]): company}
        self.pending = copy.deepcopy(self.committed)
        self.events = []
        self.sequence = 0

    def commit(self):
        self.events.append("commit")
        self.committed = copy.deepcopy(self.pending)

    def rollback(self):
        self.events.append("rollback")
        self.pending = copy.deepcopy(self.committed)

    def write(self, data):
        self.pending[(data["doctype"], data["name"])] = copy.deepcopy(dict(data))

    def matching(self, doctype, filters=None):
        rows = [row for (kind, _), row in self.pending.items() if kind == doctype]
        if isinstance(filters, str):
            return [row for row in rows if row["name"] == filters]
        return [row for row in rows if all(row.get(key) == value for key, value in (filters or {}).items())]

    def exists(self, doctype, filters=None):
        rows = self.matching(doctype, filters)
        return rows[0]["name"] if rows else None

    def get_value(self, doctype, name, field):
        rows = self.matching(doctype, name)
        return rows[0].get(field) if rows else None

    def delete(self, doctype, filters):
        for row in self.matching(doctype, filters):
            self.pending.pop((doctype, row["name"]))

    def set_value(self, doctype, name, field, value):
        self.pending[(doctype, name)][field] = value


class Document(Record):
    def __init__(self, data, db):
        super().__init__(copy.deepcopy(data))
        object.__setattr__(self, "database", db)

    def insert(self, **_):
        self.database.sequence += 1
        self.name = (self.get("name") or self.get("company_name") or self.get("email")
                     or self.get("connection_name") or self.get("item_code")
                     or self.get("price_list_name") or f"synthetic-{self.database.sequence}")
        self.database.write(self)
        return self

    def submit(self):
        self.docstatus = 1
        self.database.write(self)


@pytest.fixture
def harness(monkeypatch):
    names = ["ultimatesales_connector.tests.acceptance_support",
             "ultimatesales_connector.tests.test_permissions_recovery",
             "ultimatesales_connector.tests.test_native_queue",
             "ultimatesales_connector.api", "ultimatesales_connector.jobs",
             "ultimatesales_connector.service"]
    for name in names:
        monkeypatch.delitem(sys.modules, name, raising=False)
    framework = types.ModuleType("frappe")
    db = framework.db = TransactionDB()
    framework.conf = Record(ultimatesales_connector_acceptance_tests=1,
                            ultimatesales_connector_allow_writes=0)
    framework.session = Record(user="previous-user")
    framework.local = Record(site="disposable-synthetic")
    framework.PermissionError = type("PermissionError", (Exception,), {})
    framework.set_user = lambda user: setattr(framework.session, "user", user)
    framework.clear_cache = lambda **_: None
    framework.get_site_path = lambda: "/tmp/synthetic-bench/sites/disposable-synthetic"
    framework.get_doc = lambda data, name=None: Document(
        data if isinstance(data, dict) else db.pending[(data, name)], db)
    framework.delete_doc = lambda doctype, name, **_: db.delete(doctype, name)
    framework.get_all = lambda doctype, filters=None, pluck=None, **_: [
        row[pluck] if pluck else Record(copy.deepcopy(row)) for row in db.matching(doctype, filters)]
    utils = types.ModuleType("frappe.utils")
    utils.cint = lambda value: int(value or 0)
    monkeypatch.setitem(sys.modules, "frappe", framework)
    monkeypatch.setitem(sys.modules, "frappe.utils", utils)

    api = types.ModuleType("ultimatesales_connector.api")

    def request_import(connection, reference, preview=0):
        db.sequence += 1
        name = f"job-{db.sequence}"
        db.write({"doctype": "US Sync Job", "name": name, "connection": connection,
                  "reference": reference, "preview_only": preview, "status": "Queued"})
        return name

    api.request_import = request_import
    jobs = types.ModuleType("ultimatesales_connector.jobs")

    def run(name):
        db.events.append("worker entry")
        # A real jobs.run discards its initial read-only snapshot. Committing
        # inside request/run helpers would hide an incorrectly ordered caller.
        db.rollback()
        row = db.pending[("US Sync Job", name)]
        assert ("US Connection", row["connection"]) in db.pending
        row["status"] = "Preview" if row["preview_only"] else "Succeeded"

    jobs.run = run
    service = types.ModuleType("ultimatesales_connector.service")
    service.get_client = lambda _: None
    monkeypatch.setitem(sys.modules, api.__name__, api)
    monkeypatch.setitem(sys.modules, jobs.__name__, jobs)
    monkeypatch.setitem(sys.modules, service.__name__, service)
    # patch() resolves package attributes too; ensure no older test mock survives.
    import ultimatesales_connector
    monkeypatch.setattr(ultimatesales_connector, "api", api, raising=False)
    monkeypatch.setattr(ultimatesales_connector, "jobs", jobs, raising=False)
    monkeypatch.setattr(ultimatesales_connector, "service", service, raising=False)
    support = importlib.import_module(names[0])
    permissions = importlib.import_module(names[1])
    native = importlib.import_module(names[2])
    for cls in (support.DisposableSiteTestCase, permissions.TestPermissionsAndRecovery, native.TestNativeQueue):
        monkeypatch.setattr(cls, "environment", {"company": "Synthetic Company"}, raising=False)
    yield Record(db=db, frappe=framework, api=api, jobs=jobs, support=support,
                 permissions=permissions.TestPermissionsAndRecovery, native=native.TestNativeQueue)
    for name in names:
        sys.modules.pop(name, None)


def case_for(harness, kind="permissions"):
    cls = harness[kind]
    method = next(name for name in dir(cls) if name.startswith("test_"))
    return cls(method)


def test_bootstrap_leaves_company_pending_for_native_execute(harness):
    harness.frappe.set_user("Administrator")
    name = harness.support.bootstrap_synthetic_company()
    key = ("Company", name)
    assert key in harness.db.pending and key not in harness.db.committed
    assert "commit" not in harness.db.events
    harness.db.rollback()
    assert key not in harness.db.pending
    # The invoking native CLI commits only after the callable returns normally.
    name = harness.support.bootstrap_synthetic_company()
    harness.db.commit()
    assert ("Company", name) in harness.db.committed


@pytest.mark.parametrize("opt_in,user,error", [(0, "Administrator", RuntimeError),
                                                (1, "restricted-user", PermissionError)])
def test_bootstrap_refusal_never_commits_or_mutates(harness, opt_in, user, error):
    harness.frappe.conf.ultimatesales_connector_acceptance_tests = opt_in
    harness.frappe.set_user(user)
    expected = RuntimeError if error is RuntimeError else harness.frappe.PermissionError
    with pytest.raises(expected):
        harness.support.bootstrap_synthetic_company()
    assert harness.db.pending == harness.db.committed
    assert "commit" not in harness.db.events


def test_shared_fixture_setup_does_not_make_partial_rows_durable(harness):
    case = harness.support.DisposableSiteTestCase()
    case.setUp()
    key = ("US Connection", case.connection.name)
    assert key in harness.db.pending and key not in harness.db.committed
    assert "commit" not in harness.db.events
    harness.db.rollback()
    assert key not in harness.db.pending


@pytest.mark.parametrize("kind", ["permissions", "native"])
def test_concrete_testcase_owns_setup_and_cleanup_commits(harness, kind):
    case = case_for(harness, kind)
    case.setUp()
    key = ("US Connection", case.connection.name)
    assert key in harness.db.committed
    assert harness.db.events == ["commit"]
    case.tearDown()
    assert key not in harness.db.committed
    assert harness.db.events == ["commit", "rollback", "commit"]
    assert harness.frappe.session.user == "previous-user"
    assert harness.frappe.conf.ultimatesales_connector_allow_writes == 0


def test_request_helper_leaves_intent_pending(harness):
    case = case_for(harness)
    case.setUp()
    harness.db.events.clear()
    name = case.request()
    assert ("US Sync Job", name) in harness.db.pending
    assert ("US Sync Job", name) not in harness.db.committed
    assert "commit" not in harness.db.events
    harness.db.rollback()
    assert ("US Sync Job", name) not in harness.db.pending
    case.tearDown()


def test_run_helper_leaves_normal_completion_pending(harness):
    case = case_for(harness)
    case.setUp()
    name = case.request()
    harness.db.commit()
    harness.db.events.clear()
    job, _ = case.run_job(name)
    assert job.status == "Succeeded"
    assert harness.db.committed[("US Sync Job", name)]["status"] == "Queued"
    assert "commit" not in harness.db.events
    harness.db.rollback()
    assert harness.db.pending[("US Sync Job", name)]["status"] == "Queued"
    case.tearDown()


def test_failed_run_helper_never_commits_partial_worker_writes(harness, monkeypatch):
    case = case_for(harness)
    case.setUp()
    name = case.request()
    harness.db.commit()
    harness.db.events.clear()

    def interrupted(_):
        harness.db.rollback()
        harness.db.pending[("US Sync Job", name)]["status"] = "Running"
        harness.db.write({"doctype": "Lead", "name": "partial-lead"})
        raise RuntimeError("synthetic interruption")

    monkeypatch.setattr(harness.jobs, "run", interrupted)
    with pytest.raises(RuntimeError, match="synthetic interruption"):
        case.run_job(name)
    assert "commit" not in harness.db.events
    harness.db.rollback()
    assert harness.db.pending[("US Sync Job", name)]["status"] == "Queued"
    assert ("Lead", "partial-lead") not in harness.db.pending
    case.tearDown()


def test_quotation_helper_leaves_submission_pending(harness):
    case = case_for(harness)
    case.setUp()
    harness.db.events.clear()
    quote = case.prepare_submitted_quote("synthetic-opportunity", "synthetic-lead")
    key = ("Quotation", quote.name)
    assert harness.db.pending[key]["docstatus"] == 1
    assert key not in harness.db.committed
    assert "commit" not in harness.db.events
    harness.db.rollback()
    assert key not in harness.db.pending
    case.tearDown()


def test_cleanup_helper_does_not_commit_deletes(harness):
    case = case_for(harness)
    case.setUp()
    key = ("US Connection", case.connection.name)
    harness.db.events.clear()
    case.cleanup_fixture()
    assert key not in harness.db.pending and key in harness.db.committed
    assert "commit" not in harness.db.events
    harness.db.rollback()
    assert key in harness.db.pending
    case.tearDown()
    assert key not in harness.db.committed


@pytest.mark.parametrize("kind", ["permissions", "native"])
def test_failed_setup_cleans_up_without_committing_partial_fixture(harness, monkeypatch, kind):
    case = case_for(harness, kind)

    def failed_connection(_):
        raise RuntimeError("synthetic setup failure after users")

    monkeypatch.setattr(case, "new_connection", failed_connection)
    with pytest.raises(RuntimeError, match="synthetic setup failure"):
        case.setUp()
    assert list(harness.db.committed) == [("Company", "Synthetic Company")]
    assert harness.db.pending == harness.db.committed
    assert harness.frappe.session.user == "previous-user"
    assert harness.frappe.conf.ultimatesales_connector_allow_writes == 0


@pytest.mark.parametrize("kind", ["permissions", "native"])
def test_failed_cleanup_rolls_back_and_restores_context(harness, monkeypatch, kind):
    case = case_for(harness, kind)
    case.setUp()
    before = copy.deepcopy(harness.db.committed)
    harness.db.events.clear()

    def failed_delete(*_):
        raise RuntimeError("synthetic cleanup failure")

    monkeypatch.setattr(harness.db, "delete", failed_delete)
    with pytest.raises(RuntimeError, match="synthetic cleanup failure"):
        case.tearDown()
    assert harness.db.committed == before == harness.db.pending
    assert "commit" not in harness.db.events
    assert harness.frappe.session.user == "previous-user"
    assert harness.frappe.conf.ultimatesales_connector_allow_writes == 0


def test_actual_installed_preview_test_commits_request_before_worker_rollback(harness):
    case = harness.permissions("test_default_preview_writes_no_business_records")
    case.setUp()
    case.test_default_preview_writes_no_business_records()
    assert harness.db.events == ["commit", "commit", "worker entry", "rollback", "commit"]
    jobs = [row for (doctype, _), row in harness.db.committed.items() if doctype == "US Sync Job"]
    assert len(jobs) == 1 and jobs[0]["status"] == "Preview"
    case.tearDown()


def test_actual_native_recovery_test_enqueues_only_durable_intent(harness, monkeypatch):
    queued = []

    class QueueJob:
        def __init__(self, kwargs):
            self.kwargs = {"site": harness.frappe.local.site, "user": harness.frappe.session.user,
                           "kwargs": kwargs}
            self.status = "queued"

        def get_status(self, **_):
            return self.status

        def delete(self):
            pass

    def enqueue(method=None, **kwargs):
        name = kwargs.pop("sync_job_name")
        assert ("US Sync Job", name) in harness.db.committed
        job = QueueJob({"sync_job_name": name, **kwargs})
        queued.append(job)
        return job

    harness.frappe.enqueue = enqueue
    harness.api.dispatch_pending = lambda: harness.frappe.enqueue()
    case = harness.native("test_redis_submission_failure_keeps_sql_intent_for_operator_dispatch")

    def separate_worker():
        for job in queued:
            name = job.kwargs["kwargs"]["sync_job_name"]
            # A separate native worker's commit does not refresh the parent's read snapshot.
            harness.db.committed[("US Sync Job", name)]["status"] = "Succeeded"
            job.status = "finished"

    monkeypatch.setattr(case, "start_worker", separate_worker)
    case.setUp()
    case.test_redis_submission_failure_keeps_sql_intent_for_operator_dispatch()
    assert len(queued) == 1
    assert queued[0].kwargs["user"] == case.operator
    assert queued[0].kwargs["site"] == harness.frappe.local.site
    case.tearDown()



def test_shared_fixture_module_has_no_process_launcher(harness):
    assert not hasattr(harness.support, "subprocess")
    assert not hasattr(harness.support.DisposableSiteTestCase, "start_worker")


def test_site_preflight_reads_site_facts_without_launching_git(harness, monkeypatch):
    erpnext = types.ModuleType("erpnext")
    erpnext.__version__ = "16.50.0"
    background = types.ModuleType("frappe.utils.background_jobs")
    background.get_queues_timeout = lambda: {"us_acceptance": 120}
    install = types.ModuleType("ultimatesales_connector.install")
    install.check_environment = lambda: None
    monkeypatch.setitem(sys.modules, erpnext.__name__, erpnext)
    monkeypatch.setitem(sys.modules, background.__name__, background)
    monkeypatch.setitem(sys.modules, install.__name__, install)
    harness.frappe.__version__ = "16.51.1"
    harness.frappe.conf.ultimatesales_connector_allow_writes = 1
    harness.frappe.conf.ultimatesales_connector_acceptance_company = "Synthetic Company"
    harness.db.sql = lambda _: [("11.8.3-MariaDB",)]
    harness.db.write({"doctype": "Role", "name": "UltimateSales Operator"})
    before = copy.deepcopy(harness.db.pending)
    result = harness.support.acceptance_preflight()
    assert result["site"] == "disposable-synthetic"
    assert result["frappe"] == "16.51.1" and result["erpnext"] == "16.50.0"
    assert "commits" not in result  # The external runner owns revision evidence.
    assert harness.db.pending == before
    assert harness.db.events == []


@pytest.mark.parametrize("exit_code", [0, 2])
def test_native_testcase_owns_worker_process_with_fixed_argv(harness, monkeypatch, exit_code):
    module = sys.modules[harness.native.__module__]
    calls = []
    monkeypatch.setattr(module.shutil, "which", lambda _: "/controlled/bin/bench")

    def process(command, **kwargs):
        calls.append((command, kwargs))
        return types.SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr(module.subprocess, "run", process)
    case = case_for(harness, "native")
    case.setUp()
    assert calls == []
    if exit_code:
        with pytest.raises(AssertionError, match="Dedicated acceptance worker failed"):
            case.start_worker()
    else:
        case.start_worker()
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command == ["/controlled/bin/bench", "worker", "--queue", "us_acceptance", "--burst", "--quiet"]
    assert kwargs["cwd"] == module.Path("/tmp/synthetic-bench").resolve()
    assert kwargs == {"cwd": case.bench_dir, "stdout": module.subprocess.DEVNULL,
                      "stderr": module.subprocess.DEVNULL, "shell": False,
                      "timeout": 90, "check": False}
    case.tearDown()


def test_native_worker_refuses_missing_bench_without_launch(harness, monkeypatch):
    module = sys.modules[harness.native.__module__]
    monkeypatch.setattr(module.shutil, "which", lambda _: None)
    monkeypatch.setattr(module.subprocess, "run", lambda *_, **__: pytest.fail("Unexpected process launch"))
    case = case_for(harness, "native")
    case.setUp()
    with pytest.raises(AssertionError, match="Bench executable is required"):
        case.start_worker()
    case.tearDown()
