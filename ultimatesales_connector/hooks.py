app_name = "ultimatesales_connector"
app_title = "UltimateSales.ai Connector"
app_publisher = "ReadySpace"
app_description = "Sales-to-quotation handoff for UltimateSales.ai and ERPNext"
app_email = ""
app_license = "GPL-3.0-only"
required_apps = ["erpnext"]

before_install = "ultimatesales_connector.install.check_environment"
after_install = "ultimatesales_connector.install.after_install"
after_migrate = "ultimatesales_connector.install.check_environment"

# No core-file edits, server scripts, guest webhooks, or external I/O in these hooks.
doc_events = {
    "Quotation": {
        "on_submit": "ultimatesales_connector.events.quotation_changed",
        "on_cancel": "ultimatesales_connector.events.quotation_changed",
    }
}
permission_query_conditions = {
    "US Connection": "ultimatesales_connector.access.connection_query",
    "US Record Link": "ultimatesales_connector.access.link_query",
    "US Sync Job": "ultimatesales_connector.access.job_query",
}
has_permission = {doctype: "ultimatesales_connector.access.connector_has_permission"
                  for doctype in ("US Connection", "US Record Link", "US Sync Job")}
doctypes_to_log = []
