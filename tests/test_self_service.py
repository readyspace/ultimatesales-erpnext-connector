"""Offline self-service checks. Installed UI/permission tests remain separate."""
import importlib
import json
from pathlib import Path
import sys
import types
from unittest.mock import MagicMock, call

import pytest

from ultimatesales_connector.client import APIError
from ultimatesales_connector.domain import RuleError

ROOT = Path(__file__).parents[1]


class Doc(dict):
    __getattr__ = dict.get

    def is_new(self):
        return self.get("_new", True)

    def get_doc_before_save(self):
        return self.get("_previous")

    def get_password(self, *_args, **_kwargs):
        return self.get("_secret")


def connection(**changes):
    values = dict(name="connection", enabled=0, preview_only=1, company="Company",
                  crm_currency="SGD", integration_user="operator", location_id="location",
                  pipeline_id="pipeline", qualified_stage_id="stage", api_token="*****",
                  allow_quotation_export=0, export_contract_verified=0, _secret="synthetic-secret")
    values.update(changes)
    return Doc(values)


@pytest.fixture
def setup_framework(monkeypatch):
    f = types.ModuleType("frappe")
    f.db = MagicMock()
    f.db.get_value.return_value = "SGD"
    f.db.exists.return_value = False
    f.conf = {}
    f.get_doc = MagicMock(side_effect=lambda doctype, name: Doc(enabled=1, user_type="System User") if doctype == "User" else Doc(default_currency="SGD"))
    f.get_roles = MagicMock(return_value=["UltimateSales Operator"])
    f.get_all = MagicMock(return_value=["Company"])
    f.has_permission = MagicMock(return_value=True)
    f.PermissionError = type("PermissionError", (Exception,), {})
    def throw(message, exc=ValueError):
        raise exc(message)
    f.throw = throw
    utils = types.ModuleType("frappe.utils")
    utils.cint = lambda value: int(value or 0)
    monkeypatch.setitem(sys.modules, "frappe", f)
    monkeypatch.setitem(sys.modules, "frappe.utils", utils)
    model = types.ModuleType("frappe.model")
    document = types.ModuleType("frappe.model.document")
    document.Document = Doc
    monkeypatch.setitem(sys.modules, "frappe.model", model)
    monkeypatch.setitem(sys.modules, "frappe.model.document", document)
    scheduler = types.ModuleType("frappe.utils.scheduler")
    scheduler.is_scheduler_inactive = lambda verbose=False: False
    scheduler.is_schduler_process_running = lambda: True
    background = types.ModuleType("frappe.utils.background_jobs")
    background.get_queue = lambda name: name
    background.get_workers = lambda queue: [object()]
    monkeypatch.setitem(sys.modules, "frappe.utils.scheduler", scheduler)
    monkeypatch.setitem(sys.modules, "frappe.utils.background_jobs", background)
    monkeypatch.delitem(sys.modules, "ultimatesales_connector.setup", raising=False)
    setup = importlib.import_module("ultimatesales_connector.setup")
    yield f, setup, scheduler, background
    sys.modules.pop("ultimatesales_connector.setup", None)


def remote_fixture(monkeypatch, client):
    service = types.ModuleType("ultimatesales_connector.service")
    context = MagicMock()
    context.__enter__.return_value = client
    service.get_client = MagicMock(return_value=context)
    monkeypatch.setitem(sys.modules, "ultimatesales_connector.service", service)
    return service


def remote_client():
    client = MagicMock()
    client.get_pipelines.return_value = [{"id": "pipeline", "stages": [{"id": "stage"}]}]
    client.get_opportunity.return_value = {"id": "sample", "locationId": "location", "pipelineId": "pipeline", "pipelineStageId": "stage", "status": "open", "contactId": "contact"}
    client.get_contact.return_value = {"id": "contact", "locationId": "location", "email": "private@example.test"}
    return client


def test_local_diagnostics_never_decrypts_token_or_calls_crm(setup_framework, monkeypatch):
    f, setup, _, _ = setup_framework
    c = connection()
    c.get_password = MagicMock(side_effect=AssertionError("secret access"))
    service = remote_fixture(monkeypatch, remote_client())
    result = setup.diagnostics(c)
    assert result["ready_for_preview"] is True
    assert result["site_writes_enabled"] is False
    assert "synthetic-secret" not in str(result)
    c.get_password.assert_not_called()
    service.get_client.assert_not_called()
    f.db.set_value.assert_not_called()


def test_disabled_incomplete_configuration_has_actionable_failures(setup_framework):
    _, setup, _, _ = setup_framework
    result = setup.diagnostics(connection(company=None, integration_user=None, location_id=None, pipeline_id=None, qualified_stage_id=None, crm_currency=None, api_token=None))
    assert result["ready_for_preview"] is False
    checks = {row["code"]: row for row in result["checks"]}
    assert checks["routing"]["status"] == "FAIL"
    assert checks["credential_saved"]["status"] == "FAIL"
    assert checks["operator"]["action"]


def test_currency_permission_and_company_user_scope_are_rechecked(setup_framework):
    f, setup, _, _ = setup_framework
    f.db.get_value.return_value = "USD"
    f.has_permission.return_value = False
    f.get_all.return_value = ["Other Company", "Company"]
    checks = {row["code"]: row for row in setup.diagnostics(connection())["checks"]}
    assert checks["currency"]["status"] == "FAIL"
    assert checks["company_user_permission"]["status"] == "FAIL"
    assert checks["permission_lead_create"]["status"] == "FAIL"
    assert all(call.kwargs["user"] == "operator" for call in f.has_permission.call_args_list)


@pytest.mark.parametrize("roles,enabled", [(["System Manager"], 1), ([], 1), (["UltimateSales Operator"], 0)])
def test_local_diagnostics_rejects_excessive_missing_or_disabled_operator(setup_framework, roles, enabled):
    f, setup, _, _ = setup_framework
    f.get_roles.return_value = roles
    f.get_doc.side_effect = lambda doctype, name: Doc(enabled=enabled, user_type="System User")
    checks = {row["code"]: row for row in setup.diagnostics(connection())["checks"]}
    assert checks["operator"]["status"] == "FAIL"


def test_worker_outage_is_redacted_and_blocks_readiness(setup_framework):
    _, setup, _, background = setup_framework
    background.get_workers = MagicMock(side_effect=RuntimeError("SECRET redis://private-host"))
    result = setup.diagnostics(connection())
    assert result["ready_for_preview"] is False
    assert "SECRET" not in str(result) and "private-host" not in str(result)
    assert any(row["code"] == "long_worker" and row["status"] == "FAIL" for row in result["checks"])


def test_pinned_worker_api_receives_queue_object_not_queue_name(setup_framework):
    _, setup, _, background = setup_framework
    queue = object()
    background.get_queue = MagicMock(return_value=queue)
    background.get_workers = MagicMock(return_value=[object()])
    setup.diagnostics(connection())
    background.get_queue.assert_called_once_with("long")
    background.get_workers.assert_called_once_with(queue)


def test_connection_test_is_get_only_and_returns_no_crm_values(setup_framework, monkeypatch):
    _, setup, _, _ = setup_framework
    client = remote_client()
    remote_fixture(monkeypatch, client)
    result = setup.test_connection(connection(), "sample")
    assert result["remote_read_checks_passed"] is True
    assert result["ready_for_preview"] is True
    assert result["external_contract_verified"] is False
    client.get_contact.assert_called_once_with("contact")
    client.update_opportunity_fields.assert_not_called()
    assert "private@example.test" not in str(result)


def test_no_sample_discloses_read_scopes_not_proven(setup_framework, monkeypatch):
    _, setup, _, _ = setup_framework
    client = remote_client()
    remote_fixture(monkeypatch, client)
    result = setup.test_connection(connection())
    assert any(row["code"] == "crm_sample_read" and row["status"] == "WARN" for row in result["checks"])
    client.get_opportunity.assert_not_called()
    client.get_opportunity_fields.assert_not_called()


@pytest.mark.parametrize("pipeline,error", [([], "pipeline_missing"), ([{"id": "pipeline", "stages": [{"id": "other-stage"}]}], "qualified_stage_missing")])
def test_missing_pipeline_and_stage_fail_safely(setup_framework, monkeypatch, pipeline, error):
    _, setup, _, _ = setup_framework
    client = remote_client()
    client.get_pipelines.return_value = pipeline
    remote_fixture(monkeypatch, client)
    result = setup.test_connection(connection())
    assert result["remote_read_checks_passed"] is False
    assert error in str(result)
    assert result["checks"][-1]["action"]
    client.update_opportunity_fields.assert_not_called()


@pytest.mark.parametrize("model,data_type,error", [("contact", "TEXT", "export_requires_text_fields"), ("opportunity", "NUMERICAL", "export_requires_text_fields"), (None, None, "export_field_missing")])
def test_invalid_return_field_metadata_blocks_readiness(setup_framework, monkeypatch, model, data_type, error):
    _, setup, _, _ = setup_framework
    client = remote_client()
    client.get_opportunity_fields.return_value = [{"id": "field", "model": model, "dataType": data_type}] if model else []
    remote_fixture(monkeypatch, client)
    result = setup.test_connection(connection(field_opportunity="field"))
    assert result["ready_for_preview"] is False
    assert error in str(result)
    client.update_opportunity_fields.assert_not_called()


def test_five_text_fields_are_checked_without_write_contract_claim(setup_framework, monkeypatch):
    _, setup, _, _ = setup_framework
    client = remote_client()
    mapping = {"field_" + key: key for key in ("opportunity", "quotation", "state", "currency", "total")}
    client.get_opportunity_fields.return_value = [{"id": key, "model": "opportunity", "dataType": "TEXT"} for key in ("opportunity", "quotation", "state", "currency", "total")]
    remote_fixture(monkeypatch, client)
    result = setup.test_connection(connection(**mapping), "sample")
    assert result["ready_for_preview"] is True
    assert result["external_contract_verified"] is False
    client.update_opportunity_fields.assert_not_called()


@pytest.mark.parametrize("error", [APIError("authentication_failed"), APIError("scope_or_location_forbidden"), RuntimeError("SECRET token and private CRM body")])
def test_connection_errors_are_actionable_and_redacted(setup_framework, monkeypatch, error):
    _, setup, _, _ = setup_framework
    client = remote_client()
    client.get_pipelines.side_effect = error
    remote_fixture(monkeypatch, client)
    result = setup.test_connection(connection())
    assert result["ready_for_preview"] is False
    assert "SECRET" not in str(result) and "private CRM body" not in str(result)
    assert result["checks"][-1]["action"]


def test_error_guide_never_reflects_unknown_input(setup_framework):
    _, setup, _, _ = setup_framework
    assert "SECRET" not in str(setup.job_guidance("SECRET"))
    assert "Rotate" in setup.job_guidance("authentication_failed")["action"]


def controller(name, monkeypatch, internal=False):
    access = types.ModuleType("ultimatesales_connector.access")
    access.internal_write_allowed = lambda: internal
    monkeypatch.setitem(sys.modules, "ultimatesales_connector.access", access)
    path = "ultimatesales_connector.ultimatesales_connector.doctype." + name + "." + name
    monkeypatch.delitem(sys.modules, path, raising=False)
    module = importlib.import_module(path)
    return getattr(module, {"us_connection": "USConnection", "us_record_link": "USRecordLink", "us_sync_job": "USSyncJob"}[name])


def test_disabled_incomplete_connection_can_save_without_token(setup_framework, monkeypatch):
    f, _, _, _ = setup_framework
    klass = controller("us_connection", monkeypatch)
    klass(connection(enabled=0, company=None, integration_user=None, crm_currency=None, location_id=None, pipeline_id=None, qualified_stage_id=None, _secret=None)).validate()
    f.get_doc.assert_not_called()
    f.db.sql.assert_not_called()


@pytest.mark.parametrize("changes,message", [({"integration_user": None}, "Complete"), ({"_secret": None}, "token"), ({"integration_user": "Administrator"}, "restricted")])
def test_enabling_incomplete_or_privileged_connection_is_rejected(setup_framework, monkeypatch, changes, message):
    klass = controller("us_connection", monkeypatch)
    with pytest.raises(ValueError, match=message):
        klass(connection(enabled=1, **changes)).validate()


def test_enabling_requires_operator_role(setup_framework, monkeypatch):
    f, _, _, _ = setup_framework
    f.get_roles.return_value = []
    klass = controller("us_connection", monkeypatch)
    with pytest.raises(ValueError, match="UltimateSales Operator"):
        klass(connection(enabled=1)).validate()


def test_activation_locks_site_metadata_before_current_enabled_state(setup_framework, monkeypatch):
    f, _, _, _ = setup_framework
    f.db.sql.side_effect = [[("US Connection",)], []]
    klass = controller("us_connection", monkeypatch)
    klass(connection(enabled=1)).validate()
    assert f.db.sql.call_args_list == [
        call("SELECT name FROM `tabDocType` WHERE name = %s FOR UPDATE", ("US Connection",)),
        call("SELECT name FROM `tabUS Connection` WHERE enabled = 1 AND name != %s FOR UPDATE", ("connection",)),
    ]
    f.db.commit.assert_not_called()
    assert not any(args.args[0] == "US Connection" for args in f.db.exists.call_args_list)


def test_activation_rejects_current_enabled_connection_after_lock(setup_framework, monkeypatch):
    f, _, _, _ = setup_framework
    # db.exists sees no active record, but a current locking read sees another
    # activation committed while this transaction waited on the common lock.
    f.db.exists.return_value = False
    f.db.sql.side_effect = [[("US Connection",)], [("other-connection",)]]
    klass = controller("us_connection", monkeypatch)
    with pytest.raises(ValueError, match="one enabled connection"):
        klass(connection(enabled=1)).validate()
    f.db.commit.assert_not_called()


def test_activation_fails_closed_when_site_metadata_is_missing(setup_framework, monkeypatch):
    f, _, _, _ = setup_framework
    f.db.sql.return_value = []
    klass = controller("us_connection", monkeypatch)
    with pytest.raises(ValueError, match="metadata is missing"):
        klass(connection(enabled=1)).validate()
    assert f.db.sql.call_count == 1
    f.db.commit.assert_not_called()


@pytest.mark.parametrize("name", ["us_record_link", "us_sync_job"])
def test_internal_records_reject_direct_save_and_deletion_even_administrator(setup_framework, monkeypatch, name):
    f, _, _, _ = setup_framework
    klass = controller(name, monkeypatch)
    doc = klass()
    with pytest.raises(f.PermissionError):
        doc.validate()
    with pytest.raises(f.PermissionError):
        doc.on_trash()


def test_schema_secret_permissions_and_role_separation():
    base = ROOT / "ultimatesales_connector/ultimatesales_connector/doctype"
    config = json.loads((base / "us_connection/us_connection.json").read_text())
    fields = {f["fieldname"]: f for f in config["fields"]}
    assert fields["api_token"]["permlevel"] == 1
    assert fields["enabled"]["search_index"] == 1
    assert fields["api_token"]["reqd"] == 0
    assert fields["api_token"]["mandatory_depends_on"] == "eval:doc.enabled"
    assert {p["role"] for p in config["permissions"] if p.get("permlevel") == 1} == {"System Manager"}
    assert all(not any(p.get(action) for action in ("write", "create", "delete")) for p in config["permissions"] if p["role"] != "System Manager")
    for name in ("us_record_link", "us_sync_job"):
        data = json.loads((base / name / (name + ".json")).read_text())
        assert all(not any(p.get(action) for action in ("write", "create", "delete")) for p in data["permissions"])


def test_workspace_is_discoverable_and_checklist_links_resolve():
    data = json.loads((ROOT / "ultimatesales_connector/ultimatesales_connector/workspace/ultimatesales_connector/ultimatesales_connector.json").read_text())
    assert data["module"] == "UltimateSales Connector" and data["public"] == 1
    assert {p["role"] for p in data["roles"]} == {"System Manager", "UltimateSales Operator", "UltimateSales Auditor"}
    content = json.loads(data["content"])
    assert any(row["type"] == "paragraph" and "Setup order" in row["data"]["text"] for row in content)
    assert {row["link_to"] for row in data["links"] if row["type"] == "Link"} == {"US Connection", "US Record Link", "US Sync Job"}
