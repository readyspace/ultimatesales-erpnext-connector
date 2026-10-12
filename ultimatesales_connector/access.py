"""Current-actor authorization. Never switches users or forges queue identity."""
from contextlib import contextmanager
from contextvars import ContextVar

import frappe

from .domain import RuleError

_internal_depth = ContextVar("ultimatesales_internal_records", default=0)


@contextmanager
def internal_records():
    """Code-only capability for validated immutable mapping/audit inserts."""
    token = _internal_depth.set(_internal_depth.get() + 1)
    try:
        yield
    finally:
        _internal_depth.reset(token)


def internal_write_allowed():
    return _internal_depth.get() > 0


def require_manager():
    if frappe.session.user == "Guest" or "System Manager" not in frappe.get_roles():
        frappe.throw("System Manager access is required.", frappe.PermissionError)


def manager_connection(name):
    require_manager()
    connection = frappe.get_doc("US Connection", name)
    connection.check_permission("write")
    return connection


def authorize_connection(connection):
    actor = frappe.session.user
    if actor != connection.integration_user:
        raise RuleError("execution_identity_mismatch")
    user = frappe.get_doc("User", actor)
    if not user.enabled or user.user_type != "System User" or actor in ("Guest", "Administrator"):
        raise RuleError("invalid_integration_user")
    roles = frappe.get_roles(actor)
    if "System Manager" in roles:
        raise RuleError("integration_user_has_excessive_permissions")
    if "UltimateSales Operator" not in roles:
        raise RuleError("operator_role_required")
    companies = frappe.get_all("User Permission", filters={
        "user": actor, "allow": "Company", "apply_to_all_doctypes": 1,
    }, pluck="for_value")
    if set(companies) != {connection.company}:
        raise RuleError("company_permission_required")
    company = frappe.get_doc("Company", connection.company)
    company.check_permission("read")
    if company.default_currency != connection.crm_currency:
        raise RuleError("crm_company_currency_mismatch")
    if not connection.enabled:
        raise RuleError("connection_disabled")
    return actor


def require_operator():
    actor = frappe.session.user
    if actor in ("Guest", "Administrator"):
        raise RuleError("invalid_integration_user")
    roles = frappe.get_roles(actor)
    if "UltimateSales Operator" not in roles or "System Manager" in roles:
        raise RuleError("operator_role_required")
    user = frappe.get_doc("User", actor)
    if not user.enabled or user.user_type != "System User":
        raise RuleError("invalid_integration_user")
    return actor


def require_operator_connection(name):
    require_operator()
    connection = frappe.get_doc("US Connection", name)
    authorize_connection(connection)
    connection.check_permission("read")
    return connection


@contextmanager
def integration_identity(connection):
    authorize_connection(connection)
    yield


def require_business_writes(connection, *, export=False):
    from frappe.utils import cint
    from .domain import connection_fingerprint
    authorize_connection(connection)
    fresh = frappe.get_doc("US Connection", connection.name)
    if connection_fingerprint(fresh) != connection_fingerprint(connection):
        raise RuleError("configuration_changed")
    if not fresh.enabled or fresh.preview_only or not cint(frappe.conf.get("ultimatesales_connector_allow_writes", 0)):
        raise RuleError("business_writes_paused")
    if export and (not fresh.allow_quotation_export or not fresh.export_contract_verified):
        raise RuleError("quotation_export_disabled_or_unverified")


def lock_connection(name):
    rows = frappe.db.sql("SELECT name FROM `tabUS Connection` WHERE name = %s FOR UPDATE", (name,))
    if not rows:
        raise RuleError("connection_missing")


def _scope(user=None):
    user = user or frappe.session.user
    roles = frappe.get_roles(user)
    if user != "Guest" and "System Manager" in roles:
        return user, roles, None
    if user in ("Guest", "Administrator") or not frappe.db.get_value("User", user, "enabled"):
        return user, roles, []
    companies = frappe.get_all("User Permission", filters={
        "user": user, "allow": "Company", "apply_to_all_doctypes": 1,
    }, pluck="for_value")
    if not ({"UltimateSales Operator", "UltimateSales Auditor"} & set(roles)):
        companies = []
    return user, roles, companies


def _condition(doctype, user=None):
    user, roles, companies = _scope(user)
    if companies is None:
        return ""
    if not companies:
        return "1=0"
    values = ",".join(frappe.db.escape(value) for value in companies)
    if doctype == "US Connection":
        condition = f"`tabUS Connection`.`company` IN ({values})"
        if "UltimateSales Auditor" not in roles:
            condition += " AND `tabUS Connection`.`integration_user` = " + frappe.db.escape(user)
        return condition
    condition = f"`tab{doctype}`.`company` IN ({values})" if doctype == "US Record Link" else (
        f"`tabUS Sync Job`.`connection` IN (SELECT name FROM `tabUS Connection` WHERE company IN ({values}))")
    if doctype == "US Sync Job" and "UltimateSales Auditor" not in roles:
        condition += " AND `tabUS Sync Job`.`requested_by` = " + frappe.db.escape(user)
    if doctype == "US Record Link" and "UltimateSales Auditor" not in roles:
        condition += " AND `tabUS Record Link`.`connection` IN (SELECT name FROM `tabUS Connection` WHERE integration_user = " + frappe.db.escape(user) + ")"
    return condition


def connection_query(user=None):
    return _condition("US Connection", user)


def link_query(user=None):
    user, roles, companies = _scope(user)
    condition = _condition("US Record Link", user)
    if companies is None or not companies:
        return condition
    if not all(frappe.has_permission(dt, "read", user=user) for dt in ("Lead", "Opportunity")):
        return "1=0"
    filters = {"company": ["in", companies]}
    if "UltimateSales Auditor" not in roles:
        filters["connection"] = ["in", frappe.get_all("US Connection", filters={
            "company": ["in", companies], "integration_user": user,
        }, pluck="name")]
    references = frappe.get_all("US Record Link", filters=filters, fields=["lead", "opportunity"], limit_page_length=0)
    allowed = {}
    for dt, key in (("Lead", "lead"), ("Opportunity", "opportunity")):
        candidates = {row.get(key) for row in references if row.get(key)}
        visible = frappe.get_list(dt, filters={"name": ["in", list(candidates)]},
                                 pluck="name", limit_page_length=0, user=user) if candidates else []
        allowed[key] = [name for name in visible if frappe.has_permission(dt, "read", doc=name, user=user)]
    if not allowed["lead"]:
        return "1=0"
    lead_values = ",".join(frappe.db.escape(name) for name in allowed["lead"])
    opportunity_values = ",".join(frappe.db.escape(name) for name in allowed["opportunity"])
    opportunity_clause = "`tabUS Record Link`.`opportunity` IS NULL OR `tabUS Record Link`.`opportunity` = ''"
    if opportunity_values:
        opportunity_clause += f" OR `tabUS Record Link`.`opportunity` IN ({opportunity_values})"
    return condition + f" AND `tabUS Record Link`.`lead` IN ({lead_values}) AND ({opportunity_clause})"


def job_query(user=None):
    return _condition("US Sync Job", user)


def connector_has_permission(doc, user=None, ptype=None, permission_type=None):
    user, roles, companies = _scope(user)
    if companies is None:
        return True  # Pass controller layer; normal role/User Permission checks still apply.
    if (ptype or permission_type) not in (None, "read", "select", "print", "report"):
        return False
    connection = doc if doc.doctype == "US Connection" else frappe.get_doc("US Connection", doc.connection)
    if connection.company not in companies:
        return False
    if "UltimateSales Auditor" not in roles:
        if connection.integration_user != user:
            return False
        if doc.doctype == "US Sync Job" and doc.requested_by != user:
            return False
    if doc.doctype == "US Record Link":
        for doctype, name in (("Lead", doc.lead), ("Opportunity", doc.opportunity)):
            if name and not frappe.has_permission(doctype, "read", doc=name, user=user):
                return False
    return True
