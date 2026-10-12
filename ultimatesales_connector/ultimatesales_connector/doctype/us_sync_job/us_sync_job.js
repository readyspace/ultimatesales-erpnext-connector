frappe.ui.form.on("US Sync Job", {
    refresh(frm) {
        if (frm.is_new()) return;
        frm.add_custom_button(__("Refresh Result"), () => frm.reload_doc());
        frm.set_intro(__("This is an internal audit job. The designated operator must dispatch their own due requests. A preview request remains a preview after settings change."), "blue");
        if (frm.doc.error_code) {
            frm.add_custom_button(__("How to Resolve"), () => {
                frappe.call({method: "ultimatesales_connector.api.job_diagnostics", args: {job_name: frm.doc.name},
                    callback: (r) => {if (r.message) frappe.msgprint({title: __("Review Job Failure"), message: frappe.utils.escape_html(r.message.action)});}});
            });
        }
        const own = frappe.user.has_role("UltimateSales Operator") && frappe.session.user === frm.doc.requested_by;
        if (!own) return;
        if (["Queued", "Retry"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Dispatch My Due Jobs"), () => {
                frappe.call({method: "ultimatesales_connector.api.dispatch_pending", callback: (r) => {
                    if (r.message) frappe.msgprint(__("Your due jobs were submitted: {0}. Future retries remain due until you explicitly dispatch them.", [r.message.submitted]));
                }});
            });
        }
        if (["Failed", "Blocked"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Retry After Review"), () => {
                frappe.confirm(__("Have you corrected the reported problem and reviewed the intended operation? A changed connection configuration requires a new request."), () => {
                    frappe.call({method: "ultimatesales_connector.api.retry_job", args: {job_name: frm.doc.name}, callback: () => frm.reload_doc()});
                });
            });
        }
    }
});
