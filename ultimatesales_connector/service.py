"""Business writes use the restricted integration user's normal ERPNext permissions."""
from __future__ import annotations

from decimal import Decimal

import frappe
from frappe.utils import nowdate

from .access import integration_identity, internal_records, require_business_writes
from .client import HighLevelClient
from .domain import (
    EXPORT_KEYS, RuleError, custom_field_payload, custom_fields_match, decimal_text,
    export_values, lead_values, opportunity_contact_id, stable_key, verify_opportunity,
)


def get_client(connection):
    return HighLevelClient(connection.get_password("api_token"), connection.location_id)


def get_link(connection, kind, external):
    name = stable_key("link", connection.name, kind, external)
    if not frappe.db.exists("US Record Link", name):
        return None
    link = frappe.get_doc("US Record Link", name)
    if link.connection != connection.name or link.company != connection.company:
        raise RuleError("link_scope_mismatch")
    return link


def create_link(connection, kind, external, *, lead, opportunity=None, contact_id=None):
    with integration_identity(connection):
        if frappe.db.exists("US Record Link", {"lead": lead, "company": ["!=", connection.company]}):
            raise RuleError("lead_linked_to_other_company")
    with internal_records():
        return frappe.get_doc({
        "doctype": "US Record Link",
        "link_key": stable_key("link", connection.name, kind, external),
        "connection": connection.name,
        "company": connection.company,
        "record_kind": kind,
        "external_id": external,
        "external_contact_id": contact_id or external,
        "lead": lead,
        "opportunity": opportunity,
        }).insert(ignore_permissions=True)


def opportunity_link(erp_opportunity):
    names = frappe.get_all("US Record Link", filters={
        "record_kind": "Opportunity", "opportunity": erp_opportunity,
    }, pluck="name", limit_page_length=2)
    if len(names) > 1:
        raise RuleError("ambiguous_opportunity_mapping")
    return frappe.get_doc("US Record Link", names[0]) if names else None


def checked_lead(link):
    if not link.lead or not frappe.db.exists("Lead", link.lead):
        raise RuleError("linked_lead_missing")
    doc = frappe.get_doc("Lead", link.lead)
    doc.check_permission("read")
    if frappe.db.exists("US Record Link", {"lead": link.lead, "company": ["!=", link.company]}):
        raise RuleError("lead_linked_to_other_company")
    return doc


def import_opportunity(connection, remote_id, *, preview):
    with integration_identity(connection):
        pass  # Deny before reading CRM or protected identity mappings.
    existing = get_link(connection, "Opportunity", remote_id)
    for doctype in ("Lead", "Opportunity"):
        if not frappe.has_permission(doctype, "read"):
            raise RuleError("erp_permission_denied")
    if not existing and not frappe.has_permission("Opportunity", "create"):
        raise RuleError("integration_user_cannot_create_opportunity")
    if not existing and not frappe.has_permission("Lead", "create"):
        raise RuleError("integration_user_cannot_create_lead")
    with get_client(connection) as client:
        remote = verify_opportunity(
            client.get_opportunity(remote_id), remote_id, connection.location_id,
            connection.pipeline_id, connection.qualified_stage_id,
            require_qualified=not bool(existing),
        )
        contact_id = opportunity_contact_id(remote)
        contact = client.get_contact(contact_id)
    contact_link = get_link(connection, "Contact", contact_id)
    with integration_identity(connection):
        if existing:
            # This version is a handoff, not destructive ongoing two-way record editing.
            # A deal may move beyond the qualified stage after initial import.
            if existing.external_contact_id != contact_id:
                raise RuleError("opportunity_contact_changed_requires_review")
            checked_lead(existing)
            if not existing.opportunity or not frappe.db.exists("Opportunity", existing.opportunity):
                raise RuleError("linked_opportunity_missing")
            doc = frappe.get_doc("Opportunity", existing.opportunity)
            doc.check_permission("read")
            if doc.company != connection.company:
                raise RuleError("erp_company_mismatch")
            if doc.opportunity_from != "Lead" or doc.party_name != existing.lead:
                raise RuleError("erp_opportunity_identity_changed")
            return "Existing Lead and Opportunity retained; no ERP fields overwritten."

        values = lead_values(contact)
        amount = decimal_text(remote.get("monetaryValue", 0), nonnegative=True)
        if contact_link:
            lead = checked_lead(contact_link)
            lead_name = lead.name
        else:
            lead_name = None
            # Do not merge companies or contacts merely because an email happens to match.
            # Existing email requires an explicit, audited administrator binding.
            if values["email_id"] and frappe.db.exists("Lead", {"email_id": values["email_id"]}):
                raise RuleError("existing_lead_requires_explicit_binding")
            if not frappe.has_permission("Lead", "create"):
                raise RuleError("integration_user_cannot_create_lead")
        if not frappe.has_permission("Opportunity", "create"):
            raise RuleError("integration_user_cannot_create_opportunity")
        if preview:
            return ("Would reuse the explicitly linked Lead and create an Opportunity."
                    if lead_name else "Would create one Lead and one Opportunity; no business writes made.")
        require_business_writes(connection)
        if not lead_name:
            lead = frappe.get_doc({"doctype": "Lead", **values}).insert()
            lead_name = lead.name
            create_link(connection, "Contact", contact_id, lead=lead_name)
        opportunity = frappe.get_doc({
            "doctype": "Opportunity",
            "opportunity_from": "Lead",
            "party_name": lead_name,
            "company": connection.company,
            "currency": connection.crm_currency,
            "opportunity_amount": Decimal(amount),
            "transaction_date": nowdate(),
        }).insert()
        create_link(connection, "Opportunity", remote_id, lead=lead_name,
                    opportunity=opportunity.name, contact_id=contact_id)
        return "Lead linked and Opportunity created. Existing ERP fields were not overwritten."


def publish_quotation(connection, triggering_quotation, *, preview):
    if not preview and not connection.allow_quotation_export:
        raise RuleError("quotation_export_disabled")
    with integration_identity(connection):
        trigger = frappe.get_doc("Quotation", triggering_quotation)
        trigger.check_permission("read")
        link = opportunity_link(trigger.opportunity)
        if not link or link.connection != connection.name or link.company != connection.company:
            raise RuleError("quotation_link_missing_or_wrong_connection")
        if trigger.company != connection.company:
            raise RuleError("erp_company_mismatch")
        erp_opportunity = frappe.get_doc("Opportunity", link.opportunity)
        erp_opportunity.check_permission("read")
        if erp_opportunity.company != connection.company:
            raise RuleError("erp_company_mismatch")
        checked_lead(link)
        if erp_opportunity.opportunity_from != "Lead" or erp_opportunity.party_name != link.lead:
            raise RuleError("erp_opportunity_identity_changed")
        # Recompute latest state at execution time, not from an old queued payload.
        # Creation order prevents a late cancellation of an OLD quote replacing a NEW quote.
        names = frappe.get_all("Quotation", filters={
            "opportunity": link.opportunity,
            "company": connection.company,
            "docstatus": ["in", [1, 2]],
        }, pluck="name", order_by="creation desc, name desc", limit_page_length=1)
        if not names:
            raise RuleError("no_submitted_or_cancelled_quotation")
        quote = frappe.get_doc("Quotation", names[0])
        quote.check_permission("read")
        if quote.currency != connection.crm_currency:
            raise RuleError("quotation_currency_mismatch")
        values = export_values(quote.as_dict(), link.opportunity)
        mapping = {key: connection.get("field_" + key) for key in EXPORT_KEYS}
        payload = custom_field_payload(values, mapping)
    with get_client(connection) as client:
        fields = {field.get("id"): field for field in client.get_opportunity_fields()}
        for field_id in (field["id"] for field in payload["customFields"]):
            metadata = fields.get(field_id)
            if not metadata:
                raise RuleError("export_field_missing")
            if metadata.get("model") != "opportunity" or metadata.get("dataType") != "TEXT":
                raise RuleError("export_requires_text_fields")
        remote = verify_opportunity(
            client.get_opportunity(link.external_id), link.external_id, connection.location_id,
            connection.pipeline_id, connection.qualified_stage_id, require_qualified=False,
        )
        if opportunity_contact_id(remote) != link.external_contact_id:
            raise RuleError("opportunity_contact_changed_requires_review")
        if custom_fields_match(remote, payload):
            return "CRM already contains the latest quotation summary; no external write made."
        if preview:
            return "Would update five mapped opportunity text fields; no external write made."
        require_business_writes(connection, export=True)
        client.update_opportunity_fields(link.external_id, payload, before=remote)
    return "Latest quotation summary published and read back successfully."
