import frappe
from frappe.model.document import Document

from ultimatesales_connector.domain import EXPORT_KEYS, RuleError, external_id


class USConnection(Document):
    def validate(self):
        required = ("company", "integration_user", "location_id", "pipeline_id", "qualified_stage_id", "crm_currency")
        if self.enabled and any(not self.get(key) for key in required):
            frappe.throw("Complete company, operator, location, pipeline, qualified stage and currency before enabling the connection.")
        if self.enabled and not self.get_password("api_token", raise_exception=False):
            frappe.throw("Save a private integration token in the Password field before enabling the connection.")
        try:
            for key in ("location_id", "pipeline_id", "qualified_stage_id"):
                if self.get(key):
                    external_id(self.get(key))
            configured = [self.get("field_" + k) for k in EXPORT_KEYS if self.get("field_" + k)]
            for field in configured:
                external_id(field)
            if len(configured) != len(set(configured)):
                raise RuleError("duplicate_export_field_id")
        except RuleError as error:
            frappe.throw(error.code)
        if self.integration_user:
            if self.integration_user in ("Guest", "Administrator"):
                frappe.throw("Use a dedicated, restricted System User, not Guest or Administrator.")
            user = frappe.get_doc("User", self.integration_user)
            if not user.enabled or user.user_type != "System User":
                frappe.throw("The designated operator must be an enabled System User.")
            roles = frappe.get_roles(self.integration_user)
            if "System Manager" in roles:
                frappe.throw("The designated operator must not have the System Manager role.")
            if self.enabled and "UltimateSales Operator" not in roles:
                frappe.throw("Assign UltimateSales Operator to the designated user before enabling the connection.")
        if self.company and self.crm_currency:
            currency = frappe.db.get_value("Company", self.company, "default_currency")
            if self.crm_currency != currency:
                frappe.throw("CRM and company currencies must match. Currency conversion is outside this connector.")
        if self.allow_quotation_export and (len(configured) != 5 or not self.export_contract_verified):
            frappe.throw("Configure five unique opportunity TEXT field IDs and verify the staging export contract.")
        if self.enabled:
            # Serialize activation against one existing site-local metadata row.
            # The subsequent locking read sees the latest committed enabled state,
            # including after a wait, rather than an earlier consistent-read snapshot.
            metadata = frappe.db.sql("SELECT name FROM `tabDocType` WHERE name = %s FOR UPDATE", ("US Connection",))
            if not metadata:
                frappe.throw("Connection metadata is missing. Ask the deployment owner to migrate the installed connector.")
            enabled = frappe.db.sql("SELECT name FROM `tabUS Connection` WHERE enabled = 1 AND name != %s FOR UPDATE", (self.name or "",))
            if enabled:
                frappe.throw("This candidate supports one enabled connection per site. Disable the current connection before enabling another.")
        previous = self.get_doc_before_save()
        if previous and frappe.db.exists("US Record Link", {"connection": self.name}):
            for key in ("company", "location_id", "pipeline_id", "qualified_stage_id", "crm_currency"):
                if previous.get(key) != self.get(key):
                    frappe.throw("Connection routing is immutable after a record link exists. Use a separate connection/site for a different routing.")

    def on_trash(self):
        if frappe.db.exists("US Record Link", {"connection": self.name}) or frappe.db.exists("US Sync Job", {"connection": self.name}):
            frappe.throw("Disable this connection instead. It has audit jobs or mappings.")
