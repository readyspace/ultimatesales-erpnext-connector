# Primary technical references

Reviewed for the source design on 12 October 2026. Documentation can change; deployment still requires live contract verification. References describe platform behavior, not proof this app has passed integration tests.

| Topic | Official source | Use in this app |
|---|---|---|
| HighLevel private integrations | https://marketplace.gohighlevel.com/docs/Authorization/PrivateIntegrationsToken/index.html | Scoped sub-account bearer token for internal pilot, not a legacy API v1 key. |
| Get Contact | https://marketplace.gohighlevel.com/docs/ghl/contacts/get-contact/index.html | Contact identity and location; contacts.readonly; v3. |
| Get Opportunity | https://marketplace.gohighlevel.com/docs/ghl/opportunities/get-opportunity/index.html | Deal identity, location, pipeline, stage and contact. |
| Update Opportunity | https://marketplace.gohighlevel.com/docs/ghl/opportunities/update-opportunity/index.html | PUT customFields with id/fieldValue; opportunities.write; v3. |
| HighLevel scopes | https://marketplace.gohighlevel.com/docs/Authorization/Scopes/index.html | Least-privilege endpoint scopes. |
| HighLevel changelog | https://marketplace.gohighlevel.com/docs/Changelog/ | v3 contract differences; no silent fallback to old snake_case search parameters. |
| Frappe hooks | https://docs.frappe.io/framework/user/en/python-api/hooks | Standard Quotation document hooks, no core overrides. |
| Frappe background jobs | https://docs.frappe.io/framework/user/en/api/background_jobs | Scheduler dispatch and worker queue. |
| Frappe database API | https://docs.frappe.io/framework/user/en/api/database | Transaction/savepoint implementation model. |
| Framework v16 runtime | https://github.com/frappe/frappe/blob/version-16/pyproject.toml | v16 currently specifies Python >=3.14,<3.15. |
| ERPNext Opportunity schema | https://github.com/frappe/erpnext/blob/version-16/erpnext/crm/doctype/opportunity/opportunity.json | Standard party, company, currency, opportunity amount fields. |
| ERPNext Quotation schema | https://github.com/frappe/erpnext/blob/version-16/erpnext/selling/doctype/quotation/quotation.json | Standard Opportunity link, company and quotation totals. |
| Frappe Marketplace registry | https://github.com/frappe/marketplace | Future release metadata and automated submission validation. |

The first alpha deliberately uses only get-by-ID reads and a narrow opportunity update, not the broader API surface. The current v3 docs may still coexist with older pages. Keep headers, request fields, endpoint scope and sample account behavior aligned; do not blindly combine versions.
