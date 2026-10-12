"""Mocked orchestration tests; NOT substitutes for Frappe/MariaDB integration tests."""
import importlib
import sys
import types
from contextlib import nullcontext
from datetime import datetime, timedelta
from unittest.mock import MagicMock, call

import pytest

from ultimatesales_connector.client import APIError
from ultimatesales_connector.domain import RuleError, connection_fingerprint


class Doc(dict):
    __getattr__ = dict.get

    def __setattr__(self, name, value):
        self[name] = value

    def db_set(self, data, **kwargs):
        self.update(data)

    def check_permission(self, *_):
        return None

    def as_dict(self):
        return dict(self)


@pytest.fixture
def framework(monkeypatch):
    names = ["ultimatesales_connector.jobs", "ultimatesales_connector.access", "ultimatesales_connector.service", "ultimatesales_connector.api"]
    for name in names:
        monkeypatch.delitem(sys.modules, name, raising=False)
    f = types.ModuleType("frappe")
    f.db = MagicMock()
    f.db.sql.return_value = [("connection",)]
    f.db.get_value.return_value = "connection"
    f.db.exists.return_value = False
    f.conf = {"ultimatesales_connector_allow_writes": 1}
    f.session = Doc(user="manager")
    f.get_doc = MagicMock()
    f.get_all = MagicMock(return_value=[])
    f.get_list = MagicMock(return_value=[])
    f.has_permission = MagicMock(return_value=True)
    f.enqueue = MagicMock()
    f.PermissionError = type("PermissionError", (Exception,), {})
    f.ValidationError = type("ValidationError", (Exception,), {})
    utils = types.ModuleType("frappe.utils")
    utils.nowdate = lambda: "2026-10-12"
    utils.now_datetime = lambda: datetime(2026, 10, 12, 8)
    utils.get_datetime = lambda value: value
    utils.add_to_date = lambda date, seconds: date + timedelta(seconds=seconds)
    utils.cint = lambda value: int(value or 0)
    monkeypatch.setitem(sys.modules, "frappe", f)
    monkeypatch.setitem(sys.modules, "frappe.utils", utils)
    yield f
    for name in names:
        sys.modules.pop(name, None)


def connection(**changes):
    return Doc(name="connection", company="Company", location_id="loc", pipeline_id="pipeline",
               qualified_stage_id="qualified", crm_currency="SGD", integration_user="worker",
               enabled=1, preview_only=0, allow_quotation_export=1,
               **{"field_" + k: "field_" + k for k in ("opportunity", "quotation", "state", "currency", "total")},
               **changes)


def service_fixture(framework, monkeypatch):
    service = importlib.import_module("ultimatesales_connector.service")
    c = connection()
    client = MagicMock()
    client.get_opportunity.return_value = {"id": "external", "locationId": "loc", "pipelineId": "pipeline",
                                           "pipelineStageId": "qualified", "status": "open", "contactId": "contact", "monetaryValue": 100}
    client.get_contact.return_value = {"id": "contact", "locationId": "loc", "firstName": "Test", "email": "test@example.test"}
    client.get_opportunity_fields.return_value = [
        {"id": c.get("field_" + k), "model": "opportunity", "dataType": "TEXT"}
        for k in ("opportunity", "quotation", "state", "currency", "total")]
    context = MagicMock()
    context.__enter__.return_value = client
    monkeypatch.setattr(service, "get_client", lambda _: context)
    monkeypatch.setattr(service, "integration_identity", lambda _: nullcontext())
    monkeypatch.setattr(service, "require_business_writes", MagicMock())
    monkeypatch.setattr(service, "get_link", MagicMock(return_value=None))
    monkeypatch.setattr(service, "create_link", MagicMock())
    return service, c, client


def test_preview_creates_no_business_records(framework, monkeypatch):
    service, c, client = service_fixture(framework, monkeypatch)
    result = service.import_opportunity(c, "external", preview=True)
    assert "Would create" in result
    framework.get_doc.assert_not_called()
    service.create_link.assert_not_called()
    client.update_opportunity_fields.assert_not_called()


def test_first_handoff_creates_one_lead_and_one_opportunity(framework, monkeypatch):
    service, c, _ = service_fixture(framework, monkeypatch)
    created = []
    def get_doc(data):
        created.append(data)
        record = MagicMock()
        record.insert.return_value.name = "LEAD-1" if data["doctype"] == "Lead" else "OPP-1"
        return record
    framework.get_doc.side_effect = get_doc
    service.import_opportunity(c, "external", preview=False)
    assert [r["doctype"] for r in created] == ["Lead", "Opportunity"]
    assert created[1]["party_name"] == "LEAD-1"
    assert created[1]["company"] == "Company"
    assert service.create_link.call_count == 2


def test_existing_email_is_not_auto_merged(framework, monkeypatch):
    service, c, _ = service_fixture(framework, monkeypatch)
    framework.db.exists.return_value = True
    with pytest.raises(RuleError, match="explicit_binding"):
        service.import_opportunity(c, "external", preview=False)
    framework.get_doc.assert_not_called()


def test_replay_reuses_existing_mapping_without_business_writes(framework, monkeypatch):
    service, c, client = service_fixture(framework, monkeypatch)
    existing = Doc(lead="LEAD", opportunity="OPP", external_contact_id="contact", company="Company")
    service.get_link.side_effect = [existing, Doc(lead="LEAD")]
    framework.db.exists.side_effect = lambda dt, name: not isinstance(name, dict)
    framework.get_doc.side_effect = lambda dt, name: Doc(name=name, company="Company", opportunity_from="Lead", party_name="LEAD")
    client.get_opportunity.return_value.update(status="won", pipelineStageId="closed")
    result = service.import_opportunity(c, "external", preview=False)
    assert "retained" in result
    service.create_link.assert_not_called()
    assert all(isinstance(call.args[0], str) for call in framework.get_doc.call_args_list)


def test_changed_contact_is_not_silently_rebound(framework, monkeypatch):
    service, c, _ = service_fixture(framework, monkeypatch)
    service.get_link.side_effect = [Doc(external_contact_id="different"), None]
    with pytest.raises(RuleError, match="contact_changed"):
        service.import_opportunity(c, "external", preview=False)


def test_wrong_company_on_existing_opportunity_blocks(framework, monkeypatch):
    service, c, _ = service_fixture(framework, monkeypatch)
    service.get_link.side_effect = [Doc(external_contact_id="contact", lead="LEAD", opportunity="OPP", company="Company"), None]
    framework.db.exists.side_effect = lambda dt, name: not isinstance(name, dict)
    framework.get_doc.side_effect = lambda dt, name: Doc(name=name, company="Other Company")
    with pytest.raises(RuleError, match="erp_company_mismatch"):
        service.import_opportunity(c, "external", preview=False)


def test_missing_create_permission_blocks_preview_as_well(framework, monkeypatch):
    service, c, _ = service_fixture(framework, monkeypatch)
    framework.has_permission.return_value = False
    with pytest.raises(RuleError, match="erp_permission_denied"):
        service.import_opportunity(c, "external", preview=True)


def quotation_service(framework, monkeypatch):
    service, c, client = service_fixture(framework, monkeypatch)
    link = Doc(connection="connection", company="Company", lead="LEAD", opportunity="ERP-OPP", external_id="external", external_contact_id="contact")
    monkeypatch.setattr(service, "opportunity_link", lambda _: link)
    framework.get_all.return_value = ["Q-NEW"]
    framework.db.exists.side_effect = lambda dt, name: not isinstance(name, dict)
    quotes = {
        "Q-OLD": Doc(name="Q-OLD", company="Company", opportunity="ERP-OPP", docstatus=2, currency="SGD", grand_total=10),
        "Q-NEW": Doc(name="Q-NEW", company="Company", opportunity="ERP-OPP", docstatus=1, currency="SGD", grand_total=100),
    }
    framework.get_doc.side_effect = lambda dt, name: quotes[name] if dt == "Quotation" else Doc(company="Company", name=name, opportunity_from="Lead", party_name="LEAD")
    return service, c, client, quotes


def test_old_cancellation_exports_newest_quotation_not_old_event(framework, monkeypatch):
    service, c, client, _ = quotation_service(framework, monkeypatch)
    service.publish_quotation(c, "Q-OLD", preview=False)
    payload = client.update_opportunity_fields.call_args.args[1]
    values = {f["id"]: f["fieldValue"] for f in payload["customFields"]}
    assert values["field_quotation"] == "Q-NEW"
    assert values["field_state"] == "Submitted"
    assert framework.get_all.call_args.kwargs["order_by"] == "creation desc, name desc"


def test_export_preview_does_not_call_write_api(framework, monkeypatch):
    service, c, client, _ = quotation_service(framework, monkeypatch)
    service.publish_quotation(c, "Q-OLD", preview=True)
    client.update_opportunity_fields.assert_not_called()


def test_export_disabled_stops_before_remote_access(framework, monkeypatch):
    service, c, client, _ = quotation_service(framework, monkeypatch)
    c.allow_quotation_export = 0
    with pytest.raises(RuleError, match="export_disabled"):
        service.publish_quotation(c, "Q-OLD", preview=False)
    client.get_opportunity.assert_not_called()


def test_wrong_company_quote_does_not_leave_erp(framework, monkeypatch):
    service, c, client, quotes = quotation_service(framework, monkeypatch)
    quotes["Q-OLD"].company = "Wrong Company"
    with pytest.raises(RuleError, match="company_mismatch"):
        service.publish_quotation(c, "Q-OLD", preview=False)
    client.get_opportunity.assert_not_called()


@pytest.mark.parametrize("metadata", [[], [{"id": "field_opportunity", "model": "contact", "dataType": "TEXT"}],
    [{"id": "field_opportunity", "model": "opportunity", "dataType": "NUMERICAL"}]])
def test_runtime_export_metadata_blocks_before_remote_deal_or_write(framework, monkeypatch, metadata):
    service, c, client, _ = quotation_service(framework, monkeypatch)
    client.get_opportunity_fields.return_value = metadata
    with pytest.raises(RuleError, match="export_field_missing|export_requires_text_fields"):
        service.publish_quotation(c, "Q-OLD", preview=False)
    client.get_opportunity.assert_not_called()
    client.update_opportunity_fields.assert_not_called()


def test_revoked_lead_create_blocks_before_remote_reads(framework, monkeypatch):
    service, c, client = service_fixture(framework, monkeypatch)
    framework.has_permission.side_effect = lambda dt, permission: not (dt == "Lead" and permission == "create")
    with pytest.raises(RuleError, match="integration_user_cannot_create_lead"):
        service.import_opportunity(c, "external", preview=False)
    client.get_opportunity.assert_not_called()
    client.get_contact.assert_not_called()


def job_fixture(framework, monkeypatch):
    service = importlib.import_module("ultimatesales_connector.service")
    monkeypatch.setattr(service, "import_opportunity", MagicMock(return_value="done"))
    monkeypatch.setattr(service, "publish_quotation", MagicMock(return_value="done"))
    jobs = importlib.import_module("ultimatesales_connector.jobs")
    monkeypatch.setattr(jobs, "authorize_connection", MagicMock())
    c = connection()
    job = Doc(name="job", connection="connection", configuration_key=connection_fingerprint(c),
              status="Queued", preview_only=0, attempts=0, next_attempt=None,
              operation="Import Opportunity", reference="external", requested_by="manager")
    framework.get_doc.side_effect = lambda dt, name: c if dt == "US Connection" else job
    return jobs, service, c, job


def test_worker_success_commits_and_keeps_business_write_gates(framework, monkeypatch):
    jobs, service, _, job = job_fixture(framework, monkeypatch)
    jobs.run("job")
    assert job.status == "Succeeded" and job.attempts == 1
    assert service.import_opportunity.call_args.kwargs["preview"] is False
    framework.db.commit.assert_not_called()  # Native worker owns final commit.
    framework.db.rollback.assert_called_once_with()  # Read-only discovery reset.


def test_worker_site_gate_downgrades_to_preview(framework, monkeypatch):
    jobs, service, _, job = job_fixture(framework, monkeypatch)
    framework.conf = {}
    jobs.run("job")
    assert job.status == "Preview"
    assert service.import_opportunity.call_args.kwargs["preview"] is True


def test_transient_failure_rolls_back_business_savepoint_and_schedules_retry(framework, monkeypatch):
    jobs, service, _, job = job_fixture(framework, monkeypatch)
    service.import_opportunity.side_effect = APIError("rate_limited", retryable=True, retry_after=120)
    jobs.run("job")
    assert job.status == "Retry" and job.next_attempt == datetime(2026, 10, 12, 8, 2)
    assert framework.db.rollback.call_args_list == [call(), call(save_point="us_operation")]


def test_final_retry_is_visible_failure(framework, monkeypatch):
    jobs, service, _, job = job_fixture(framework, monkeypatch)
    job.attempts = 4
    service.import_opportunity.side_effect = APIError("remote_service_error", retryable=True)
    jobs.run("job")
    assert job.status == "Failed" and job.attempts == 5


def test_permanent_rule_error_is_not_auto_retried(framework, monkeypatch):
    jobs, service, _, job = job_fixture(framework, monkeypatch)
    service.import_opportunity.side_effect = RuleError("location_mismatch")
    jobs.run("job")
    assert job.status == "Failed" and job.error_code == "location_mismatch"


def test_disabled_connection_blocks_already_queued_work(framework, monkeypatch):
    jobs, service, c, job = job_fixture(framework, monkeypatch)
    c.enabled = 0
    jobs.run("job")
    assert job.status == "Blocked"
    service.import_opportunity.assert_not_called()


def test_changed_routing_blocks_old_intents(framework, monkeypatch):
    jobs, service, c, job = job_fixture(framework, monkeypatch)
    c.location_id = "another-location"
    jobs.run("job")
    assert job.status == "Blocked" and job.error_code == "configuration_changed"
    service.import_opportunity.assert_not_called()


def test_duplicate_worker_does_not_reexecute_completed_intent(framework, monkeypatch):
    jobs, service, _, job = job_fixture(framework, monkeypatch)
    job.status = "Succeeded"
    jobs.run("job")
    service.import_opportunity.assert_not_called()


def test_unexpected_error_does_not_store_exception_payload(framework, monkeypatch):
    jobs, service, _, job = job_fixture(framework, monkeypatch)
    service.import_opportunity.side_effect = ValueError("SECRET contact@example.test")
    jobs.run("job")
    assert job.status == "Failed"
    assert "SECRET" not in str(job) and "contact@example.test" not in str(job)
