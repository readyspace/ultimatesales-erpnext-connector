"""Negative current-actor unit tests; real database tests are a separate layer."""
import importlib
from unittest.mock import MagicMock

import pytest

from test_orchestration import Doc, connection, framework, job_fixture
from ultimatesales_connector.domain import RuleError


def authorized(framework):
    access = importlib.import_module("ultimatesales_connector.access")
    c = connection()
    framework.session.user = "worker"
    user = Doc(name="worker", enabled=1, user_type="System User")
    company = Doc(name="Company", default_currency="SGD")
    framework.get_doc.side_effect = lambda dt, name: {"User": user, "Company": company, "US Connection": c}[dt]
    framework.get_roles = MagicMock(return_value=["UltimateSales Operator"])
    framework.get_all.return_value = ["Company"]
    framework.db.escape.side_effect = lambda value: "'" + value.replace("'", "''") + "'"
    return access, c, user, company


def test_guard_keeps_native_identity_without_switch(framework):
    access, c, _, _ = authorized(framework)
    framework.set_user = MagicMock()
    with access.integration_identity(c):
        assert framework.session.user == "worker"
    framework.set_user.assert_not_called()


@pytest.mark.parametrize("case,code", [
    ("wrong_actor", "execution_identity_mismatch"),
    ("disabled", "invalid_integration_user"),
    ("website", "invalid_integration_user"),
    ("manager", "integration_user_has_excessive_permissions"),
    ("role_revoked", "operator_role_required"),
    ("company_revoked", "company_permission_required"),
    ("other_company", "company_permission_required"),
    ("multiple_companies", "company_permission_required"),
    ("currency", "crm_company_currency_mismatch"),
    ("paused", "connection_disabled"),
])
def test_current_authority_is_revalidated(framework, case, code):
    access, c, user, company = authorized(framework)
    if case == "wrong_actor": framework.session.user = "other"
    elif case == "disabled": user.enabled = 0
    elif case == "website": user.user_type = "Website User"
    elif case == "manager": framework.get_roles.return_value += ["System Manager"]
    elif case == "role_revoked": framework.get_roles.return_value = []
    elif case == "company_revoked": framework.get_all.return_value = []
    elif case == "other_company": framework.get_all.return_value = ["Other"]
    elif case == "multiple_companies": framework.get_all.return_value = ["Company", "Other"]
    elif case == "currency": company.default_currency = "USD"
    elif case == "paused": c.enabled = 0
    with pytest.raises(RuleError, match=code):
        access.authorize_connection(c)


def test_unauthorized_import_never_opens_crm_or_reads_links(framework, monkeypatch):
    _, c, _, _ = authorized(framework)
    framework.session.user = "other"
    service = importlib.import_module("ultimatesales_connector.service")
    monkeypatch.setattr(service, "get_client", MagicMock())
    monkeypatch.setattr(service, "get_link", MagicMock())
    with pytest.raises(RuleError, match="execution_identity_mismatch"):
        service.import_opportunity(c, "external", preview=True)
    service.get_client.assert_not_called()
    service.get_link.assert_not_called()


def test_worker_rejects_native_identity_loss_before_service(framework, monkeypatch):
    jobs, service, _, job = job_fixture(framework, monkeypatch)
    framework.session.user = "Administrator"
    jobs.run(job.name)
    assert job.status == "Blocked" and job.error_code == "requesting_identity_changed"
    service.import_opportunity.assert_not_called()


@pytest.mark.parametrize("code", ["invalid_integration_user", "operator_role_required", "company_permission_required"])
def test_worker_rechecks_revocation_after_enqueue(framework, monkeypatch, code):
    jobs, service, _, job = job_fixture(framework, monkeypatch)
    jobs.authorize_connection.side_effect = RuleError(code)
    jobs.run(job.name)
    assert job.status == "Blocked" and job.error_code == code
    service.import_opportunity.assert_not_called()


@pytest.mark.parametrize("gate", ["site", "preview", "connection", "export"])
def test_last_write_gate_recheck_denies_changes(framework, gate):
    access, c, _, _ = authorized(framework)
    if gate == "site": framework.conf = {}
    elif gate == "preview": c.preview_only = 1
    elif gate == "connection": c.enabled = 0
    elif gate == "export": c.export_contract_verified = 0
    with pytest.raises(RuleError):
        access.require_business_writes(c, export=gate == "export")


def test_internal_bookkeeping_capability_is_context_local_and_resets(framework):
    access = importlib.import_module("ultimatesales_connector.access")
    assert not access.internal_write_allowed()
    with pytest.raises(RuntimeError):
        with access.internal_records():
            assert access.internal_write_allowed()
            raise RuntimeError("synthetic")
    assert not access.internal_write_allowed()


def test_dispatch_only_selects_requester_and_uses_supported_enqueue(framework, monkeypatch):
    jobs = importlib.import_module("ultimatesales_connector.jobs")
    framework.get_roles = MagicMock(return_value=["UltimateSales Operator"])
    framework.session.user = "worker"
    framework.get_all.return_value = [Doc(name="job", connection="connection")]
    monkeypatch.setattr(jobs, "authorize_connection", MagicMock())
    assert jobs.dispatch() == 1
    assert framework.get_all.call_args.kwargs["filters"]["requested_by"] == "worker"
    options = framework.enqueue.call_args.kwargs
    assert "user" not in options and options["enqueue_after_commit"] is True
    assert options["deduplicate"] is True


def test_scheduler_administrator_cannot_dispatch_operator_intents(framework):
    jobs = importlib.import_module("ultimatesales_connector.jobs")
    framework.session.user = "Administrator"
    framework.get_roles = MagicMock(return_value=["System Manager"])
    with pytest.raises(RuleError, match="operator_role_required"):
        jobs.dispatch()
    framework.get_all.assert_not_called()
    framework.enqueue.assert_not_called()


@pytest.mark.parametrize("ptype,allowed", [("read", True), ("select", True), ("write", False), ("create", False), ("delete", False)])
def test_pinned_framework_permission_hook_uses_ptype(framework, ptype, allowed):
    access, c, _, _ = authorized(framework)
    c.doctype = "US Connection"
    framework.db.get_value.return_value = 1
    assert access.connector_has_permission(c, user="worker", ptype=ptype) is allowed


def test_connection_permission_hook_denies_wrong_company(framework):
    access, c, _, _ = authorized(framework)
    c.doctype = "US Connection"
    framework.db.get_value.return_value = 1
    framework.get_all.return_value = ["Other"]
    assert access.connector_has_permission(c, user="worker", ptype="read") is False


def test_jobs_permission_hook_denies_other_requester(framework):
    access, c, _, _ = authorized(framework)
    framework.db.get_value.return_value = 1
    job = Doc(doctype="US Sync Job", connection=c.name, requested_by="other")
    assert access.connector_has_permission(job, user="worker", ptype="read") is False


def test_mapping_lists_require_underlying_erp_access(framework):
    access, _, _, _ = authorized(framework)
    framework.db.get_value.return_value = 1
    framework.get_roles.return_value = ["UltimateSales Auditor"]
    framework.has_permission.return_value = False
    assert access.link_query("worker") == "1=0"
    framework.get_list.assert_not_called()


def test_binding_rechecks_fresh_locked_connection_before_crm_read(framework, monkeypatch):
    _, c, user, company = authorized(framework)
    framework.whitelist = lambda **kwargs: lambda function: function
    fresh = connection()
    fresh.integration_user = "different-operator"
    seen = []
    def get_doc(dt, name, **kwargs):
        seen.append((dt, kwargs))
        if dt == "US Connection": return fresh if kwargs.get("for_update") else c
        if dt == "User": return user
        if dt == "Company": return company
        return Doc(name=name)
    framework.get_doc.side_effect = get_doc
    api = importlib.import_module("ultimatesales_connector.api")
    monkeypatch.setattr(api, "get_client", MagicMock())
    with pytest.raises(RuleError, match="execution_identity_mismatch"):
        api.bind_existing_lead(c.name, "contact", "LEAD")
    api.get_client.assert_not_called()
    assert ("US Connection", {"for_update": True}) in seen
    assert not any(dt == "Lead" for dt, _ in seen)


def test_nonoperator_export_denies_before_quotation_or_mapping_discovery(framework):
    authorized(framework)
    framework.get_roles.return_value = []
    framework.whitelist = lambda **kwargs: lambda function: function
    api = importlib.import_module("ultimatesales_connector.api")
    framework.get_doc.reset_mock()
    with pytest.raises(RuleError, match="operator_role_required"):
        api.request_export("QUOTE")
    framework.get_doc.assert_not_called()
