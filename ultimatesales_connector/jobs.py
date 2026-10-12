"""Durable SQL intents, bounded retries and per-connection transactional serialization."""
from __future__ import annotations

from uuid import uuid4

import frappe
from frappe.utils import add_to_date, cint, get_datetime, now_datetime

from .access import authorize_connection, internal_records, lock_connection
from .client import APIError
from .domain import MAX_ATTEMPTS, RuleError, connection_fingerprint, effective_preview, retry_delay, stable_key


TERMINAL = {"Succeeded", "Preview", "Failed", "Blocked"}


def queue_job(connection, kind, reference, *, preview, revision=None):
    authorize_connection(connection)
    name = stable_key("job", connection.name, kind, reference,
                      str(revision or uuid4()), bool(preview))
    if frappe.db.exists("US Sync Job", name):
        return name
    job = frappe.get_doc({
        "doctype": "US Sync Job", "job_key": name,
        "connection": connection.name, "configuration_key": connection_fingerprint(connection), "operation": kind,
        "reference": reference, "preview_only": int(bool(preview)),
        "status": "Queued", "attempts": 0, "next_attempt": now_datetime(),
        "requested_by": frappe.session.user,
    })
    with internal_records():
        job.insert(ignore_permissions=True)
    # No Redis/network call inside a business document's transaction.
    # The scheduler discovers committed intents; an outage does not lose the intent.
    return job.name


def dispatch():
    # Only the currently authenticated operator can use native enqueue identity.
    actor = frappe.session.user
    if actor in ("Guest", "Administrator") or "UltimateSales Operator" not in frappe.get_roles(actor):
        raise RuleError("operator_role_required")
    submitted = 0
    for row in frappe.get_all("US Sync Job", filters={
        "status": ["in", ["Queued", "Retry"]], "next_attempt": ["<=", now_datetime()],
        "requested_by": actor,
    }, fields=["name", "connection"], order_by="creation asc", limit_page_length=20):
        connection = frappe.get_doc("US Connection", row.connection)
        authorize_connection(connection)
        frappe.enqueue(
            "ultimatesales_connector.jobs.run", queue="long", timeout=300,
            enqueue_after_commit=True, sync_job_name=row.name,
            job_id="ultimatesales-" + row.name, deduplicate=True,
        )
        submitted += 1
    return submitted


def run(sync_job_name):
    from .service import import_opportunity, publish_quotation

    connection_name = frappe.db.get_value("US Sync Job", sync_job_name, "connection")
    if not connection_name:
        return
    # Discard a read-only discovery snapshot before waiting for the row lock.
    # Native Frappe worker owns final commit. No caller transaction may surround run().
    frappe.db.rollback()
    lock_connection(connection_name)
    frappe.db.sql("SELECT name FROM `tabUS Sync Job` WHERE name = %s FOR UPDATE", (sync_job_name,))
    job = frappe.get_doc("US Sync Job", sync_job_name)
    if job.status in TERMINAL:
        return
    if job.next_attempt and get_datetime(job.next_attempt) > now_datetime():
        return
    connection = frappe.get_doc("US Connection", connection_name)
    if job.configuration_key != connection_fingerprint(connection):
        _finish(job, "Blocked", "configuration_changed", "Create a new job for the current connection configuration.")
        return
    if not connection.enabled:
        _finish(job, "Blocked", "connection_disabled", "Enable the connection, then retry explicitly.")
        return
    try:
        if job.requested_by != frappe.session.user:
            raise RuleError("requesting_identity_changed")
        authorize_connection(connection)
        connection.check_permission("read")
        job.check_permission("read")
    except (RuleError, frappe.PermissionError) as error:
        _finish(job, "Blocked", getattr(error, "code", "erp_permission_denied"),
                "The original restricted operator must retain authorization before dispatch or retry.")
        return
    preview = effective_preview(
        bool(job.preview_only), bool(connection.preview_only),
        bool(cint(frappe.conf.get("ultimatesales_connector_allow_writes", 0))),
    )
    attempts = int(job.attempts or 0) + 1
    job.db_set({"status": "Processing", "attempts": attempts, "error_code": ""}, update_modified=False)
    # Processing and all business writes stay uncommitted. A worker crash rolls the
    # whole transaction back, leaving a recoverable queued/retry intent, not a stale lease.
    frappe.db.savepoint("us_operation")
    try:
        if job.operation == "Import Opportunity":
            message = import_opportunity(connection, job.reference, preview=preview)
        elif job.operation == "Publish Quotation":
            message = publish_quotation(connection, job.reference, preview=preview)
        else:
            raise RuleError("invalid_job_operation")
    except APIError as error:
        frappe.db.rollback(save_point="us_operation")
        if error.retryable and attempts < MAX_ATTEMPTS:
            job.db_set({
                "status": "Retry", "error_code": error.code,
                "next_attempt": add_to_date(now_datetime(), seconds=retry_delay(attempts, error.retry_after)),
                "result_summary": "Transient API failure. Retry scheduled; no raw response stored.",
            }, update_modified=False)
        else:
            _finish(job, "Failed", error.code, "Review the error-code guide, then retry explicitly.")
    except RuleError as error:
        frappe.db.rollback(save_point="us_operation")
        _finish(job, "Failed", error.code, "Configuration or mapping needs administrator review.")
    except frappe.PermissionError:
        frappe.db.rollback(save_point="us_operation")
        _finish(job, "Failed", "erp_permission_denied", "Check the integration user's ERP permissions.")
    except frappe.ValidationError:
        frappe.db.rollback(save_point="us_operation")
        _finish(job, "Failed", "erp_validation_failed", "Check mandatory ERP fields and staging customizations.")
    except Exception:
        frappe.db.rollback(save_point="us_operation")
        # Deliberately no traceback/locals/HTTP body: these can contain tokens or PII.
        _finish(job, "Failed", "unexpected_connector_error", "Reproduce in staging and inspect code safely.")
    else:
        _finish(job, "Preview" if preview else "Succeeded", "", message)
    # Returning normally lets the native framework worker commit status and writes.


def _finish(job, status, error_code, summary):
    job.db_set({"status": status, "error_code": error_code, "result_summary": summary,
                "completed_on": now_datetime()}, update_modified=False)
