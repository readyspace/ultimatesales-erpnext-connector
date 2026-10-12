"""Install-time checks only; never changes core settings or creates business records."""
import frappe


def check_environment():
    import sys
    try:
        import erpnext
    except ImportError:
        frappe.throw("Install ERPNext 16 on this isolated Frappe site before installing the connector.")
    if "erpnext" not in frappe.get_installed_apps():
        frappe.throw("ERPNext must be installed on this site before installing the connector. HRMS is not required.")
    if frappe.conf.get("db_type", "mariadb") != "mariadb":
        frappe.throw("The connector candidate requires MariaDB; PostgreSQL has not been qualified.")
    if sys.version_info[:2] != (3, 14):
        frappe.throw("The pinned Frappe 16 target requires Python 3.14. Use the isolated target environment.")
    if frappe.__version__.split(".")[0] != "16" or erpnext.__version__.split(".")[0] != "16":
        frappe.throw("This candidate targets matching Frappe 16 and ERPNext 16 only. Use an isolated site.")
    required = {
        "Lead": ("first_name", "last_name", "email_id", "mobile_no", "company_name"),
        "Opportunity": ("opportunity_from", "party_name", "company", "currency", "opportunity_amount"),
        "Quotation": ("opportunity", "company", "currency", "grand_total"),
    }
    for doctype, fields in required.items():
        meta = frappe.get_meta(doctype)
        for field in fields:
            if not meta.has_field(field):
                frappe.throw(f"Required standard field is missing: {doctype}.{field}")


def after_install():
    check_environment()
    for name in ("UltimateSales Operator", "UltimateSales Auditor"):
        if not frappe.db.exists("Role", name):
            frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": 1}).insert()
