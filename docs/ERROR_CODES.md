# Operator error-code guide

The connector intentionally stores codes, not API bodies or raw exception text. Troubleshoot with synthetic data locally.

| Code / group | Action |
|---|---|
| authentication_failed | Rotate/check the sub-account private-integration token in the Password field. Do not paste it into a ticket. |
| scope_or_location_forbidden | Check sub-account scope, allowed location and current token permissions. |
| external_record_not_found | Verify the exact opportunity/contact ID and that the record still exists. |
| location_mismatch / pipeline_mismatch | Stop and verify routing; never weaken the check to force a record through. |
| opportunity_not_in_qualified_open_stage | New imports must be OPEN in the configured qualified stage. |
| existing_lead_requires_explicit_binding | Compare actual identities and, only when correct, use Link Existing Lead. No automatic email merge. |
| linked_lead_missing / linked_opportunity_missing | Review deletion/migration history. Automatic recreation or remapping is deliberately absent. |
| opportunity_contact_changed_requires_review | Resolve the identity change deliberately; do not silently move a financial relationship. |
| crm_company_currency_mismatch | Confirm CRM location and ERP company currencies; no FX is performed. |
| erp_company_mismatch / link_scope_mismatch | Correct configuration/source records through a reviewed process, not by bypassing permissions. |
| integration_user_* / erp_permission_denied | Inspect enabled user, System User type, restricted roles, Company User Permissions and document sharing. |
| erp_validation_failed | Check site-specific required fields, naming and ERP validations in staging. Preview cannot validate all insertion hooks. |
| quotation_link_missing_or_wrong_connection | Create the quote from the linked ERP Opportunity, for the configured company. |
| no_submitted_or_cancelled_quotation | Drafts do not export. Use normal human approval/submission in the pilot. |
| incomplete_export_mapping / duplicate_export_field_id | Supply five distinct opportunity TEXT field IDs, not contact field IDs. |
| export_readback_mismatch | Stop export; verify current v3 field schema, field types and actual account behavior. A remote write may already have happened. |
| quotation_export_disabled | Enable only after the isolated export-contract test and approval. |
| configuration_changed | Do not replay into changed routing. Request a new job for the current reviewed configuration. |
| connection_disabled | Enable only after review, then explicitly retry. |
| rate_limited / transport_error / remote_service_error | Transient retries are bounded to five attempts. Respect the provider's Retry-After; investigate sustained failures. |
| invalid_* / remote_request_rejected | Check schema/IDs against current official docs and a synthetic response. Do not store raw customer data in issues. |
| unexpected_connector_error | Reproduce in a local staging debugger; report a fabricated reproduction without token/PII or debugger locals. |

Failed/Blocked jobs can normally be retried from US Sync Job after correcting the cause. A changed configuration requires a NEW job. Previously requested preview jobs never become writing jobs when retried.
