import frappe
from frappe.model.document import Document

from ultimatesales_connector.access import internal_write_allowed


class USSyncJob(Document):
    """Only connector code writes queue records; UI access is read-only."""

    def validate(self):
        if not internal_write_allowed():
            frappe.throw("Use the authorized connector actions to request or retry a job.", frappe.PermissionError)

    def on_trash(self):
        frappe.throw("Connector audit jobs cannot be deleted directly. Retention requires a reviewed maintenance policy.", frappe.PermissionError)
