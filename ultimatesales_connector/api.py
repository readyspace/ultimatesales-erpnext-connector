"""Authenticated POST actions with separate configuration and operator policies."""
import frappe
from frappe.utils import cint, now_datetime

from .access import integration_identity, lock_connection, manager_connection, require_operator, require_operator_connection
from .domain import RuleError, connection_fingerprint, external_id
from .jobs import dispatch, queue_job
from .service import create_link, get_client, get_link, opportunity_link


@frappe.whitelist(methods=["POST"])
def request_import(connection: str, opportunity_id: str, preview: int = 1):
    doc = require_operator_connection(connection)
    return queue_job(doc, "Import Opportunity", external_id(opportunity_id),
                     preview=bool(cint(preview) or doc.preview_only))


@frappe.whitelist(methods=["POST"])
def request_export(quotation: str, preview: int = 1):
    require_operator()
    quote = frappe.get_doc("Quotation", quotation)
    quote.check_permission("read")
    link = opportunity_link(quote.opportunity)
    if not link:
        frappe.throw("The quotation needs an Opportunity imported by this connector.")
    doc = require_operator_connection(link.connection)
    if quote.company != doc.company:
        frappe.throw("The quotation and connection must belong to the same company.")
    return queue_job(doc, "Publish Quotation", quote.name,
                     preview=bool(cint(preview) or doc.preview_only))


@frappe.whitelist(methods=["POST"])
def bind_existing_lead(connection: str, contact_id: str, lead: str):
    doc = require_operator_connection(connection)
    contact_id = external_id(contact_id)
    lock_connection(doc.name)
    doc = frappe.get_doc("US Connection", doc.name, for_update=True)
    with integration_identity(doc):
        existing = frappe.get_doc("Lead", lead)
        existing.check_permission("read")
    with get_client(doc) as client:
        client.get_contact(contact_id)  # Verifies exact contact ID and location.
    link = get_link(doc, "Contact", contact_id)
    if link:
        if link.lead != lead:
            frappe.throw("This CRM contact already has a different mapping. Review it; do not overwrite.")
        return link.name
    # Explicit administrative identity mapping, not an email-heuristic merge.
    return create_link(doc, "Contact", contact_id, lead=lead).name


@frappe.whitelist(methods=["POST"])
def retry_job(job_name: str):
    require_operator()
    job = frappe.get_doc("US Sync Job", job_name)
    connection = require_operator_connection(job.connection)
    job.check_permission("read")
    if job.requested_by != frappe.session.user:
        frappe.throw("Only the original operator can retry this request.", frappe.PermissionError)
    lock_connection(job.connection)
    connection = frappe.get_doc("US Connection", connection.name, for_update=True)
    with integration_identity(connection):
        pass
    job = frappe.get_doc("US Sync Job", job_name, for_update=True)
    job.check_permission("read")
    if job.requested_by != frappe.session.user:
        frappe.throw("Only the original operator can retry this request.", frappe.PermissionError)
    if job.configuration_key != connection_fingerprint(connection):
        frappe.throw("Configuration changed. Create a new reviewed request.")
    if job.status not in ("Failed", "Blocked"):
        frappe.throw("Only failed or blocked jobs may be explicitly retried.")
    job.db_set({"status": "Queued", "attempts": 0, "error_code": "",
                "result_summary": "", "completed_on": None,
                "next_attempt": now_datetime()}, update_modified=False)
    return job.name


@frappe.whitelist(methods=["POST"])
def dispatch_pending():
    if frappe.session.user == "Guest":
        frappe.throw("Authentication is required.", frappe.PermissionError)
    count = dispatch()
    return {"submitted": count, "status": "Your due intents will be queued after commit. Redis failures retain the intent; dispatch again."}


@frappe.whitelist(methods=["POST"])
def setup_diagnostics(connection: str):
    if frappe.session.user == "Guest":
        frappe.throw("Authentication is required.", frappe.PermissionError)
    from .setup import diagnostics
    doc = frappe.get_doc("US Connection", connection)
    doc.check_permission("read")
    return diagnostics(doc)


@frappe.whitelist(methods=["POST"])
def test_connection(connection: str, opportunity_id: str | None = None):
    if frappe.session.user == "Guest":
        frappe.throw("Authentication is required.", frappe.PermissionError)
    from .setup import test_connection as test
    if "System Manager" in frappe.get_roles():
        doc = manager_connection(connection)
    else:
        doc = require_operator_connection(connection)
    return test(doc, opportunity_id=external_id(opportunity_id) if opportunity_id else None)


@frappe.whitelist(methods=["POST"])
def job_diagnostics(job_name: str):
    if frappe.session.user == "Guest":
        frappe.throw("Authentication is required.", frappe.PermissionError)
    from .setup import job_guidance
    job = frappe.get_doc("US Sync Job", job_name)
    job.check_permission("read")
    return job_guidance(job.error_code)
