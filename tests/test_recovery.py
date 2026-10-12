"""Offline fault injection only: fake SQL and HTTP, never installed/live evidence.

Unlike isolated method mocks, these cases run the real job -> service -> client
path against a stateful remote simulator, including PUT and readback behavior.
"""
import copy
import importlib
import sys
import types
from contextlib import nullcontext
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
import requests

from ultimatesales_connector.client import HighLevelClient
from ultimatesales_connector.domain import connection_fingerprint


class Record(dict):
    __getattr__ = dict.get

    def __setattr__(self, key, value):
        self[key] = value

    def db_set(self, values, **_):
        self.update(values)

    def check_permission(self, *_):
        pass

    def as_dict(self):
        return dict(self)


class RemoteHTTP:
    """Models an accepted write surviving a lost response/local rollback."""

    def __init__(self, mode="normal"):
        self.headers = {}
        self.trust_env = True
        self.mode = mode
        self.calls = []
        self.after_put = False
        self.remote = {
            "id": "external", "locationId": "location", "pipelineId": "pipeline",
            "pipelineStageId": "qualified", "status": "open", "contactId": "contact",
            "customFields": [{"id": "unrelated", "fieldValue": "retain me"}],
        }

    def close(self):
        pass

    def request(self, method, url, **kwargs):
        self.calls.append((method, copy.deepcopy(kwargs.get("json"))))
        if "/locations/" in url:
            fields = [{"id": "field_" + key, "model": "opportunity", "dataType": "TEXT",
                       "locationId": "location"}
                      for key in ("opportunity", "quotation", "state", "currency", "total")]
            return types.SimpleNamespace(status_code=200, headers={}, content=b"{}",
                                         json=lambda: {"customFields": fields})
        if method == "PUT":
            owned = {field["id"] for field in kwargs["json"]["customFields"]}
            self.remote["customFields"] = [
                field for field in self.remote["customFields"] if field["id"] not in owned
            ] + copy.deepcopy(kwargs["json"]["customFields"])
            self.after_put = True
            if self.mode == "lost_put_response":
                self.mode = "normal"
                raise requests.ConnectionError("fabricated dropped response")
        elif self.after_put and self.mode == "lost_readback":
            self.mode = "normal"
            raise requests.Timeout("fabricated readback timeout")
        payload = copy.deepcopy(self.remote)
        if method == "GET" and self.after_put and self.mode == "stale_readback":
            payload["customFields"] = [{"id": "unrelated", "fieldValue": "retain me"}]
            self.mode = "normal"
        return types.SimpleNamespace(
            status_code=200, headers={}, content=b"{}",
            json=lambda: {"opportunity": payload},
        )

    @property
    def puts(self):
        return [payload for method, payload in self.calls if method == "PUT"]


@pytest.fixture
def recovery(monkeypatch):
    module_names = ["ultimatesales_connector.access", "ultimatesales_connector.service",
                    "ultimatesales_connector.jobs"]
    for name in module_names:
        monkeypatch.delitem(sys.modules, name, raising=False)
    framework = types.ModuleType("frappe")
    framework.session = Record(user="operator")
    framework.conf = {"ultimatesales_connector_allow_writes": 1}
    framework.db = MagicMock()
    framework.db.sql.return_value = [("connection",)]
    framework.db.get_value.return_value = "connection"
    framework.db.exists.side_effect = lambda doctype, *_: doctype == "Lead"
    framework.PermissionError = type("PermissionError", (Exception,), {})
    framework.ValidationError = type("ValidationError", (Exception,), {})
    utils = types.ModuleType("frappe.utils")
    utils.nowdate = lambda: "2026-10-12"
    utils.now_datetime = lambda: datetime(2026, 10, 12, 8)
    utils.get_datetime = lambda value: value
    utils.add_to_date = lambda value, seconds: value + timedelta(seconds=seconds)
    utils.cint = lambda value: int(value or 0)
    monkeypatch.setitem(sys.modules, "frappe", framework)
    monkeypatch.setitem(sys.modules, "frappe.utils", utils)
    service = importlib.import_module("ultimatesales_connector.service")
    jobs = importlib.import_module("ultimatesales_connector.jobs")
    monkeypatch.setattr(service, "integration_identity", lambda _: nullcontext())
    monkeypatch.setattr(service, "require_business_writes", lambda *_, **__: None)
    # Authorization has dedicated tests. This fixture isolates recovery behavior.
    if hasattr(jobs, "authorize_connection"):
        monkeypatch.setattr(jobs, "authorize_connection", lambda _: None)
    connection = Record(
        name="connection", company="Company", location_id="location", pipeline_id="pipeline",
        qualified_stage_id="qualified", crm_currency="SGD", integration_user="operator",
        enabled=1, preview_only=0, allow_quotation_export=1,
        **{"field_" + key: "field_" + key for key in
           ("opportunity", "quotation", "state", "currency", "total")},
    )
    job = Record(
        name="job", connection=connection.name, configuration_key=connection_fingerprint(connection),
        operation="Publish Quotation", reference="Q-OLD", status="Queued", attempts=0,
        next_attempt=None, requested_by="operator", preview_only=0,
    )
    quotes = {"Q-OLD": Record(name="Q-OLD", company="Company", opportunity="ERP-OPP",
                                docstatus=1, currency="SGD", grand_total=100)}
    latest = ["Q-OLD"]
    link = Record(connection="connection", company="Company", lead="LEAD", opportunity="ERP-OPP",
                  external_id="external", external_contact_id="contact")
    framework.get_all = MagicMock(side_effect=lambda *_, **__: list(latest))
    framework.get_doc = MagicMock(side_effect=lambda doctype, name:
        connection if doctype == "US Connection" else job if doctype == "US Sync Job"
        else quotes[name] if doctype == "Quotation" else Record(name=name, company="Company",
                                                               opportunity_from="Lead", party_name="LEAD"))
    monkeypatch.setattr(service, "opportunity_link", lambda _: link)
    persisted = copy.deepcopy(job)

    def commit():
        persisted.clear()
        persisted.update(copy.deepcopy(job))

    def rollback(**kwargs):
        if not kwargs:
            job.clear()
            job.update(copy.deepcopy(persisted))

    framework.db.commit.side_effect = commit
    framework.db.rollback.side_effect = rollback
    state = types.SimpleNamespace(framework=framework, jobs=jobs, service=service, job=job,
                                  quotes=quotes, latest=latest, connection=connection)

    def use_remote(mode="normal"):
        http = RemoteHTTP(mode)
        monkeypatch.setattr(service, "get_client", lambda _:
                            HighLevelClient("fabricated-test-token", "location", session=http))
        return http

    state.use_remote = use_remote

    def run_as_native_worker():
        jobs.run("job")
        # Framework-owned commit after a normal return; app code never commits.
        framework.db.commit()

    state.run = run_as_native_worker
    yield state
    for name in module_names:
        sys.modules.pop(name, None)


def fail_completion_once(state, monkeypatch):
    original = state.jobs._finish
    failures = [True]

    def finish(job, status, code, summary):
        if status == "Succeeded" and failures and failures.pop():
            raise RuntimeError("fabricated local completion failure")
        return original(job, status, code, summary)

    monkeypatch.setattr(state.jobs, "_finish", finish)


def test_remote_success_local_failure_replay_converges_without_second_put(recovery, monkeypatch):
    remote = recovery.use_remote()
    fail_completion_once(recovery, monkeypatch)
    with pytest.raises(RuntimeError, match="local completion"):
        recovery.run()
    recovery.framework.db.rollback()
    assert recovery.job.status == "Queued"
    assert len(remote.puts) == 1
    recovery.run()
    assert recovery.job.status == "Succeeded"
    assert "no external write" in recovery.job.result_summary
    assert len(remote.puts) == 1
    assert {"id": "unrelated", "fieldValue": "retain me"} in remote.remote["customFields"]


@pytest.mark.parametrize("fault", ["lost_put_response", "lost_readback"])
def test_accepted_write_transport_failure_replay_reads_current_remote(recovery, fault):
    remote = recovery.use_remote(fault)
    recovery.run()
    assert recovery.job.status == "Retry"
    assert recovery.job.error_code == "transport_error"
    assert len(remote.puts) == 1
    recovery.job.next_attempt = None  # Simulate the recorded retry time becoming due.
    recovery.framework.db.commit()
    recovery.run()
    assert recovery.job.status == "Succeeded" and recovery.job.attempts == 2
    assert len(remote.puts) == 1


def test_readback_mismatch_is_visible_and_explicit_replay_can_converge(recovery):
    remote = recovery.use_remote("stale_readback")
    recovery.run()
    assert recovery.job.status == "Failed"
    assert recovery.job.error_code == "export_readback_mismatch"
    assert len(remote.puts) == 1
    # Model a reviewed retry, not an automatic retry of this permanent error.
    recovery.job.status = "Queued"
    recovery.job.next_attempt = None
    recovery.framework.db.commit()
    recovery.run()
    assert recovery.job.status == "Succeeded"
    assert len(remote.puts) == 1


def test_recovery_recomputes_newer_quote_instead_of_replaying_old_payload(recovery, monkeypatch):
    remote = recovery.use_remote()
    fail_completion_once(recovery, monkeypatch)
    with pytest.raises(RuntimeError):
        recovery.run()
    recovery.framework.db.rollback()
    recovery.quotes["Q-NEW"] = Record(name="Q-NEW", company="Company", opportunity="ERP-OPP",
                                     docstatus=1, currency="SGD", grand_total=250)
    recovery.latest[:] = ["Q-NEW"]
    recovery.run()
    assert recovery.job.status == "Succeeded"
    assert len(remote.puts) == 2
    values = {field["id"]: field["fieldValue"] for field in remote.puts[-1]["customFields"]}
    assert values["field_quotation"] == "Q-NEW"
    assert values["field_total"] == "250"
