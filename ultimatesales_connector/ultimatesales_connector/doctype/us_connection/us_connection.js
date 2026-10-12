const usSetupChecklist = () => `<ol>
    <li>${__("Verify the supported ERPNext stack, Redis and long worker on an isolated staging site.")}</li>
    <li>${__("Choose the company and matching CRM currency; designate one restricted UltimateSales Operator with normal sales permissions.")}</li>
    <li>${__("Enter this location's pipeline and qualified stage IDs. A System Manager saves the private integration token locally.")}</li>
    <li>${__("Save disabled, run Setup Diagnostics and Test Connection, then enable with Preview Only checked.")}</li>
    <li>${__("Sign in as the designated operator. Preview one qualified OPEN opportunity and dispatch your due jobs.")}</li>
    <li>${__("After staging review, the deployment owner explicitly enables the site write gate and the manager turns Preview Only off.")}</li>
    <li>${__("Optional quotation return: configure five opportunity TEXT fields and verify a synthetic partial update before enabling export.")}</li>
    </ol><p>${__("Installation needs no CRM token. Tests use CRM GETs only. Previews create internal audit jobs; identity linking separately creates an immutable mapping.")}</p>`;

const usRenderChecks = (result) => {
    const escape = frappe.utils.escape_html;
    const rows = (result.checks || []).map((check) => `<tr><td>${escape(check.status)}</td><td>${escape(check.message)}</td><td>${escape(check.action || "")}</td></tr>`).join("");
    frappe.msgprint({title: __("Connector Setup Checks"), wide: true,
        message: `<p>${escape(result.notice || "")}</p><table class="table table-bordered"><thead><tr><th>${__("Status")}</th><th>${__("Check")}</th><th>${__("Next action")}</th></tr></thead><tbody>${rows}</tbody></table>`});
};

frappe.ui.form.on("US Connection", {
    refresh(frm) {
        frm.get_field("setup_checklist").$wrapper.html(usSetupChecklist());
        frm.set_intro(__("Implementation candidate. Use synthetic staging data. Writes require Enabled, Preview Only off and the deployment owner's site write gate."), "orange");
        if (frm.is_new()) return;
        const manager = frappe.user.has_role("System Manager");
        const operator = frappe.user.has_role("UltimateSales Operator") && frappe.session.user === frm.doc.integration_user;
        frm.add_custom_button(__("Setup Diagnostics"), () => {
            frappe.call({method: "ultimatesales_connector.api.setup_diagnostics", args: {connection: frm.doc.name}, callback: (r) => {if (r.message) usRenderChecks(r.message);}});
        }, __("Setup"));
        if (manager || (operator && frm.doc.enabled)) {
            frm.add_custom_button(__("Test Connection"), () => {
                frappe.prompt([{fieldname: "opportunity_id", label: __("Synthetic qualified OPEN opportunity ID (optional)"), fieldtype: "Data",
                    description: __("Optional sample verifies opportunity/contact read access. No business records, CRM updates or jobs are created.")}], (values) => {
                    frappe.call({method: "ultimatesales_connector.api.test_connection", args: {connection: frm.doc.name, opportunity_id: values.opportunity_id || ""}, freeze: true,
                        freeze_message: __("Checking saved configuration and CRM read access…"), callback: (r) => {if (r.message) usRenderChecks(r.message);}});
                }, __("Read-only Connection Test"), __("Run test"));
            }, __("Setup"));
        }
        frm.add_custom_button(__("Linked Records"), () => frappe.set_route("List", "US Record Link", {connection: frm.doc.name}), __("View"));
        frm.add_custom_button(__("Sync Jobs"), () => frappe.set_route("List", "US Sync Job", {connection: frm.doc.name}), __("View"));
        if (!operator || !frm.doc.enabled) return;
        const requestImport = (preview) => {
            frappe.prompt([{fieldname: "opportunity_id", label: __("UltimateSales Opportunity ID"), fieldtype: "Data", reqd: 1}], (values) => {
                const queue = () => frappe.call({method: "ultimatesales_connector.api.request_import",
                    args: {connection: frm.doc.name, opportunity_id: values.opportunity_id, preview},
                    callback: (r) => {if (r.message) frappe.set_route("Form", "US Sync Job", r.message);}});
                if (preview) queue();
                else frappe.confirm(__("Queue this reviewed opportunity for import? If all write gates permit it, the worker creates or reuses the mapped Lead and Opportunity under your ERP permissions."), queue);
            }, preview ? __("Preview One Opportunity") : __("Queue One Opportunity"));
        };
        frm.add_custom_button(__("Preview Opportunity"), () => requestImport(1), __("Operations"));
        frm.add_custom_button(__("Queue Opportunity Import"), () => requestImport(0), __("Operations"));
        frm.add_custom_button(__("Dispatch My Due Jobs"), () => {
            frappe.call({method: "ultimatesales_connector.api.dispatch_pending", callback: (r) => {if (r.message) frappe.msgprint(__("Your due jobs were submitted: {0}. Refresh job results after the long worker processes them.", [r.message.submitted]));}});
        }, __("Operations"));
        frm.add_custom_button(__("Link Existing Lead"), () => {
            frappe.prompt([
                {fieldname: "contact_id", label: __("UltimateSales Contact ID"), fieldtype: "Data", reqd: 1},
                {fieldname: "lead", label: __("ERPNext Lead"), fieldtype: "Link", options: "Lead", reqd: 1}
            ], (values) => {
                frappe.confirm(__("Confirm these are the same person or organisation and that the Lead is appropriate for this company. This creates an immutable identity mapping even in preview mode; it does not edit the Lead."), () => {
                    frappe.call({method: "ultimatesales_connector.api.bind_existing_lead", args: {connection: frm.doc.name, ...values},
                        callback: (r) => {if (r.message) frappe.set_route("Form", "US Record Link", r.message);}});
                });
            }, __("Explicit Identity Mapping"));
        }, __("Operations"));
        const requestExport = (preview) => {
            frappe.prompt([{fieldname: "quotation", label: __("Quotation"), fieldtype: "Link", options: "Quotation", reqd: 1}], (values) => {
                const queue = () => frappe.call({method: "ultimatesales_connector.api.request_export", args: {...values, preview},
                    callback: (r) => {if (r.message) frappe.set_route("Form", "US Sync Job", r.message);}});
                if (preview) queue();
                else frappe.confirm(__("Queue the latest submitted or cancelled quotation summary for its mapped CRM opportunity? Export still requires all saved and site write gates."), queue);
            });
        };
        frm.add_custom_button(__("Preview Quotation Return"), () => requestExport(1), __("Operations"));
        if (frm.doc.allow_quotation_export) frm.add_custom_button(__("Queue Quotation Return"), () => requestExport(0), __("Operations"));
    }
});
