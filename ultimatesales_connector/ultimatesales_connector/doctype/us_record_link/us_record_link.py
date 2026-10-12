import frappe
from frappe.model.document import Document

from ultimatesales_connector.access import internal_write_allowed
from ultimatesales_connector.domain import external_id, stable_key


class USRecordLink(Document):
    def validate(self):
        if not internal_write_allowed():
            frappe.throw("Connector identity links can only be created by the authorized connector operation.", frappe.PermissionError)
        external_id(self.external_id)
        external_id(self.external_contact_id)
        expected = stable_key("link", self.connection, self.record_kind, self.external_id)
        if self.link_key != expected:
            frappe.throw("Invalid connector mapping key.")
        if frappe.db.get_value("US Connection", self.connection, "company") != self.company:
            frappe.throw("Mapping company does not match its connection.")
        if self.record_kind == "Opportunity" and not self.opportunity:
            frappe.throw("Opportunity mappings require an ERPNext Opportunity.")
        if not self.is_new():
            frappe.throw("Connector mappings are immutable in this alpha. Review remapping separately.")

    def on_trash(self):
        frappe.throw("Connector identity links are immutable. Disable the connection and review recovery separately.", frappe.PermissionError)
