"""Read-only setup checks and allowlisted troubleshooting messages.

Public callers must authorize the connection before entering this module. Checks
never persist a token, CRM response, business document or test result.
"""
from __future__ import annotations

import frappe
from frappe.utils import cint

from .client import APIError
from .domain import EXPORT_KEYS, RuleError, external_id, opportunity_contact_id, verify_opportunity


ERROR_HELP = {
    "authentication_failed": "Rotate or re-enter the private integration token locally. Check expiry/revocation with the account administrator.",
    "scope_or_location_forbidden": "Confirm this sub-account token belongs to the configured location and has the documented read scopes.",
    "missing_or_invalid_token": "Ask a System Manager to save the token in the connection Password field.",
    "location_mismatch": "Stop and review the location and token. Do not reuse another location's record IDs.",
    "pipeline_missing": "Copy the pipeline ID from the configured CRM location, then save and test again.",
    "qualified_stage_missing": "Copy a stage ID belonging to the configured pipeline, then save and test again.",
    "pipeline_mismatch": "Select an opportunity in the configured pipeline. Existing mappings must be reviewed rather than retargeted.",
    "opportunity_not_in_qualified_open_stage": "Select an OPEN opportunity in the configured qualified stage for its first handoff.",
    "crm_company_currency_mismatch": "Set the confirmed CRM currency to the company's currency. Currency conversion is outside this connector.",
    "invalid_integration_user": "Configure an enabled restricted System User as the designated operator.",
    "integration_user_has_excessive_permissions": "Remove System Manager from the designated operator; grant only the required sales permissions.",
    "operator_role_required": "Assign UltimateSales Operator to the designated user and verify their normal ERP permissions.",
    "company_permission_required": "Create exactly one Company User Permission for the operator, set Apply To All Document Types, and select this connection's company.",
    "business_writes_paused": "Review Enabled, Preview Only and the deployment owner's site write gate. Create a new reviewed request after enabling writes.",
    "quotation_export_disabled_or_unverified": "Keep return writes paused until the five opportunity TEXT fields and synthetic partial-update contract have been verified.",
    "requester_not_operator": "Sign in as the designated operator for this connection before requesting or dispatching work.",
    "execution_identity_mismatch": "Dispatch from the designated operator's own session. The worker must execute as that same requester.",
    "requester_disabled": "An administrator must review the disabled requester. Re-enable only after checking the intended access.",
    "erp_permission_denied": "Review the operator's normal Company, Lead, Opportunity and Quotation permissions and User Permissions.",
    "cannot_create_lead": "Grant the designated operator the required normal Lead create permission; do not grant Administrator.",
    "cannot_create_opportunity": "Grant the designated operator the required normal Opportunity create permission for the configured company.",
    "erp_validation_failed": "Review mandatory ERP fields, naming and custom validations on staging, then retry after correction.",
    "existing_lead_requires_explicit_binding": "Review the CRM identity and ERP Lead. Use Link Existing Lead only after confirming they represent the same identity.",
    "contact_changed_after_linking": "Review the CRM contact reassignment. The connector will not silently replace an immutable identity link.",
    "incomplete_export_mapping": "Configure five distinct opportunity TEXT custom-field IDs, or keep quotation export disabled.",
    "duplicate_export_field_id": "Use a different CRM custom-field ID for each of the five quotation values.",
    "export_field_missing": "Create or select the configured custom fields in this CRM location. Use their IDs, not labels.",
    "export_requires_text_fields": "Use opportunity-level TEXT custom fields for all five values; contact and numeric fields are rejected.",
    "configuration_changed": "Create a new job after reviewing the saved routing/operator configuration. Old jobs cannot be retargeted.",
    "connection_disabled": "A System Manager must review and enable the saved connection. Then explicitly retry or create a new job.",
    "export_disabled": "Keep export disabled until the five fields and partial-update contract pass the synthetic staging test.",
    "export_contract_not_verified": "Verify the partial update preserves unrelated fields in the synthetic account before confirming the staging export contract.",
    "export_readback_mismatch": "Compare the five owned fields locally in the synthetic account. Review remote automations before retrying.",
    "external_record_not_found": "Check the selected external ID in the configured CRM location; no record is created remotely.",
    "rate_limited": "Wait for the bounded scheduled retry, then dispatch due work as the designated operator. Avoid repeated manual requests.",
    "transport_error": "Check provider reachability, TLS and network access from the worker. Transient failures have bounded retries.",
    "remote_service_error": "Check provider availability. Dispatch the due retry as the designated operator after the outage resolves.",
    "unexpected_connector_error": "Reproduce with synthetic data on staging. Share the sanitized error code and job ID, without tokens or customer payloads.",
    "requesting_identity_changed": "Dispatch as the same designated operator who requested the job. A new designated operator must create a new reviewed request.",
    "integration_user_cannot_create_lead": "Grant the designated operator normal Lead create permission and verify it with synthetic records.",
    "integration_user_cannot_create_opportunity": "Grant the designated operator normal Opportunity create permission for the configured company.",
    "opportunity_contact_changed_requires_review": "Review the remote contact reassignment against the immutable mapping. Do not silently relink it.",
    "lead_linked_to_other_company": "Review the Lead's existing company mapping and identity. Use an appropriate permitted Lead; do not repurpose another company's mapping.",
    "erp_opportunity_identity_changed": "Review the linked ERP Opportunity's Lead identity and company. Repair requires a separate approved recovery process.",
    "quotation_currency_mismatch": "Review the quotation and company currencies. This connector does not convert quotation values.",
    "unrelated_custom_fields_changed": "Pause export and review the live partial-update contract and remote automations. An unrelated custom field changed.",
    "unowned_opportunity_fields_changed": "Pause export and review the live contract. A native or unowned opportunity value changed during the return.",
}


def job_guidance(error_code):
    """Unknown codes do not become reflected arbitrary text in the UI."""
    return {"action": ERROR_HELP.get(error_code, "Review the sanitized job result, connection setup and staging acceptance guide before retrying.")}


def _check(code, status, message, action=""):
    return {"code": code, "status": status, "message": message, "action": action}


def _worker_checks():
    checks = []
    try:
        from frappe.utils.scheduler import is_scheduler_inactive, is_schduler_process_running
        inactive = is_scheduler_inactive(verbose=False)
        running = is_schduler_process_running()
        checks.append(_check("scheduler", "WARN" if inactive or not running else "PASS",
                             "Scheduler is inactive or not detected." if inactive or not running else "Scheduler process is detected and enabled.",
                             "Connector jobs require explicit dispatch from the designated operator's session. Scheduler presence does not authorize job execution."))
    except Exception:
        checks.append(_check("scheduler", "WARN", "Scheduler health could not be inspected.", "Ask the deployment owner to inspect scheduler health locally."))
    try:
        from frappe.utils.background_jobs import get_queue, get_workers
        workers = get_workers(get_queue("long"))
        checks.append(_check("long_worker", "PASS" if workers else "FAIL",
                             "A long-queue worker is registered." if workers else "No long-queue worker is registered.",
                             "A registered worker is not a proof of a processed job. Run a synthetic preview and verify its result." if workers else "Ask the deployment owner to start the long worker and inspect Redis locally."))
    except Exception:
        checks.append(_check("long_worker", "FAIL", "Queue/worker health is unavailable.", "Ask the deployment owner to inspect Redis and the long worker locally; connection details are not included here."))
    return checks


def diagnostics(connection):
    """No external calls, secret decryption, business writes or audit insertion."""
    checks = []
    missing = [key for key in ("company", "integration_user", "location_id", "pipeline_id", "qualified_stage_id", "crm_currency") if not connection.get(key)]
    invalid = False
    for key in ("location_id", "pipeline_id", "qualified_stage_id"):
        if connection.get(key):
            try:
                external_id(connection.get(key))
            except RuleError:
                invalid = True
    checks.append(_check("routing", "FAIL" if missing or invalid else "PASS",
                         "Complete the company, operator, location, pipeline, stage and currency fields." if missing or invalid else "Required routing values are configured.",
                         "Save a disabled connection while completing setup. IDs must contain only letters, digits, underscores or hyphens." if missing or invalid else "Use Test Connection to verify the CRM values."))
    # Password columns contain a presence marker, never the decrypted secret.
    checks.append(_check("credential_saved", "PASS" if connection.get("api_token") else "FAIL",
                         "A credential is saved." if connection.get("api_token") else "No credential is saved.",
                         "Only a System Manager can enter or rotate the Password field. Test Connection checks validity without displaying it."))
    if connection.get("company") and connection.get("crm_currency"):
        currency = frappe.db.get_value("Company", connection.company, "default_currency")
        checks.append(_check("currency", "PASS" if currency == connection.crm_currency else "FAIL",
                             "Company and configured CRM currencies match." if currency == connection.crm_currency else "Company and CRM currencies differ.",
                             ERROR_HELP["crm_company_currency_mismatch"] if currency != connection.crm_currency else "Confirm the CRM location currency manually; the API check does not prove its currency."))
    operator = connection.get("integration_user")
    valid_user = False
    if operator:
        user = frappe.get_doc("User", operator)
        roles = frappe.get_roles(operator)
        valid_user = bool(user.enabled and user.user_type == "System User" and operator not in ("Guest", "Administrator") and "System Manager" not in roles and "UltimateSales Operator" in roles)
    checks.append(_check("operator", "PASS" if valid_user else "FAIL",
                         "An enabled restricted operator is configured." if valid_user else "An enabled restricted operator with UltimateSales Operator is required.",
                         "The operator requests and dispatches their own jobs. Configuration administrators and auditors do not execute business operations."))
    if valid_user:
        companies = frappe.get_all("User Permission", filters={"user": operator, "allow": "Company", "apply_to_all_doctypes": 1}, pluck="for_value")
        scoped = set(companies) == {connection.get("company")}
        checks.append(_check("company_user_permission", "PASS" if scoped else "FAIL", "Operator has exactly the configured Company User Permission." if scoped else "Operator needs exactly one Company User Permission applying to all document types.", ERROR_HELP["company_permission_required"] if not scoped else "Lead access remains governed by its normal permissions; Leads are not inherently company-private."))
        for doctype, permission in (("Lead", "read"), ("Lead", "create"), ("Opportunity", "read"), ("Opportunity", "create"), ("Quotation", "read")):
            allowed = frappe.has_permission(doctype, ptype=permission, user=operator)
            checks.append(_check("permission_" + doctype.lower() + "_" + permission, "PASS" if allowed else "FAIL",
                                 f"{doctype} {permission} permission is available." if allowed else f"{doctype} {permission} permission is missing.",
                                 "Document-level Company/User Permissions are rechecked during execution. Verify them with synthetic records."))
        if connection.get("company"):
            company = frappe.get_doc("Company", connection.company)
            allowed = frappe.has_permission("Company", ptype="read", doc=company, user=operator)
            checks.append(_check("company_access", "PASS" if allowed else "FAIL", "Configured company is readable by the operator." if allowed else "Operator cannot read the configured company.", ERROR_HELP["erp_permission_denied"] if not allowed else ""))
    fields = [connection.get("field_" + key) for key in EXPORT_KEYS]
    configured = [field for field in fields if field]
    mapping_valid = len(configured) == 5 and len(set(configured)) == 5
    checks.append(_check("export_mapping", "PASS" if mapping_valid else ("FAIL" if connection.get("allow_quotation_export") else "WARN"),
                         "Five distinct field IDs are configured." if mapping_valid else "Quotation return needs five distinct opportunity TEXT fields.",
                         "Test Connection checks field metadata. Keep export off until a synthetic partial-update/readback test passes."))
    checks.extend(_worker_checks())
    site_writes = bool(cint(frappe.conf.get("ultimatesales_connector_allow_writes", 0)))
    checks.append(_check("write_gates", "PASS", "Business writes are enabled by all import gates." if connection.enabled and not connection.preview_only and site_writes else "Business writes are disabled or forced to preview.", "The deployment owner sets the site write gate; a System Manager controls Enabled and Preview Only on this form."))
    return {"checks": checks, "read_scopes": ["contacts.readonly", "opportunities.readonly"],
            "field_metadata_scope": "locations/customFields.readonly", "export_scope": "opportunities.write",
            "site_writes_enabled": site_writes, "connection_enabled": bool(connection.enabled),
            "preview_only": bool(connection.preview_only), "ready_for_preview": not any(c["status"] == "FAIL" for c in checks),
            "external_contract_verified": False,
            "notice": "Local checks do not prove installed-site permissions or a live API contract. Connection tests return only transient, sanitized checks; previews create internal audit jobs."}


def test_connection(connection, opportunity_id=None):
    """GET-only CRM checks; even a disabled saved connection can be tested."""
    from .service import get_client

    result = diagnostics(connection)
    checks = result["checks"]
    remote_passed = False
    try:
        for key in ("location_id", "pipeline_id", "qualified_stage_id"):
            external_id(connection.get(key))
        with get_client(connection) as client:
            pipelines = client.get_pipelines()
            pipeline = next((row for row in pipelines if row.get("id") == connection.pipeline_id), None)
            if not pipeline:
                raise RuleError("pipeline_missing")
            if not any(stage.get("id") == connection.qualified_stage_id for stage in pipeline.get("stages", []) if isinstance(stage, dict)):
                raise RuleError("qualified_stage_missing")
            checks.append(_check("crm_routing", "PASS", "The configured pipeline and qualified stage are available in this location."))
            configured = [connection.get("field_" + key) for key in EXPORT_KEYS if connection.get("field_" + key)]
            if configured:
                fields = {row.get("id"): row for row in client.get_opportunity_fields()}
                for field_id in configured:
                    field = fields.get(field_id)
                    if not field:
                        raise RuleError("export_field_missing")
                    if field.get("model") != "opportunity" or field.get("dataType") != "TEXT":
                        raise RuleError("export_requires_text_fields")
                checks.append(_check("crm_export_fields", "PASS", "Configured return fields are opportunity TEXT fields.", "This GET check does not verify write scope or partial-update semantics."))
            if opportunity_id:
                record = client.get_opportunity(external_id(opportunity_id))
                verify_opportunity(record, opportunity_id, connection.location_id, connection.pipeline_id, connection.qualified_stage_id, require_qualified=True)
                client.get_contact(opportunity_contact_id(record))
                checks.append(_check("crm_sample_read", "PASS", "The selected qualified OPEN opportunity and its contact are readable in this location."))
            else:
                checks.append(_check("crm_sample_read", "WARN", "Opportunity/contact read access has not been tested.", "Run Test Connection with a synthetic qualified OPEN opportunity ID, or request a preview."))
            remote_passed = True
    except (APIError, RuleError) as error:
        checks.append(_check("crm_connection", "FAIL", "CRM read check failed: " + error.code + ".", job_guidance(error.code)["action"]))
    except Exception:
        checks.append(_check("crm_connection", "FAIL", "CRM read check could not complete.", "Review the saved credential and setup locally. No exception, token or response body is returned."))
    result["remote_read_checks_passed"] = remote_passed
    result["ready_for_preview"] = remote_passed and not any(c["status"] == "FAIL" for c in checks)
    result["external_contract_verified"] = False
    result["notice"] = "Only local permission checks and CRM GETs were performed. No ERP business records, CRM updates, jobs or saved test result were created. PUT scope, unrelated-field preservation and installed workflow still require staging acceptance."
    return result
