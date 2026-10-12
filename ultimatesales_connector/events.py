import frappe

from .jobs import queue_job
from .service import opportunity_link


def quotation_changed(doc, method=None):
    if not doc.opportunity:
        return
    link = opportunity_link(doc.opportunity)
    if not link:
        return
    connection = frappe.get_doc("US Connection", link.connection)
    if not connection.enabled or not connection.allow_quotation_export:
        return
    if frappe.session.user != connection.integration_user:
        # Ordinary quotation approval must remain usable by other ERP users.
        # The designated operator can explicitly request the current summary.
        return
    if doc.company != connection.company or link.company != connection.company:
        frappe.throw("UltimateSales quotation mapping belongs to a different company.")
    # An intent only; no contact-data transfer or network request in this transaction.
    # If creating the intent fails, the originating submission/cancellation rolls back too.
    queue_job(connection, "Publish Quotation", doc.name,
              preview=bool(connection.preview_only), revision=f"{doc.modified}:{doc.docstatus}")
