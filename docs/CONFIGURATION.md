# Configure and operate the connector

This implementation candidate is for a synthetic staging pilot, clean installation only. Installed UI, Bench/Pilot and live CRM acceptance remain required; offline tests do not certify them. Installation and migration make no CRM calls and need no CRM credentials. No HRMS, ReadySpace hosting or external middleware is required.

## Privileges and setup order

| Actor | Responsibilities and access |
|---|---|
| Installer / deployment owner | Installs the app on an approved isolated supported site, maintains backups including the encryption key, workers and Redis, and explicitly sets the site write gate. A Desk role does not grant host installation access. |
| Configuration administrator | System Manager configures and enables connections, enters/rotates the Password field and reviews diagnostics. This user does not execute the restricted sales workflow. |
| Designated operator | Enabled System User with UltimateSales Operator and normal ERP sales permissions; the connection's Designated Restricted Operator field names this sole operator. Requests, links identities, dispatches and retries their own jobs. No System Manager or Administrator permission. |
| Diagnostics auditor | UltimateSales Auditor plus Company User Permissions. Reads connections, linked-record references and jobs within permitted companies and views local diagnostics. Cannot read the secret field, call the CRM test, mutate settings, dispatch, retry, import or export. |

The app creates its two connector roles during installation without assigning them to anyone. An administrator grants roles through the normal User form. The connector roles alone do not grant Lead, Opportunity, Company or Quotation permissions. Give the designated operator exactly one **Company User Permission**, selecting this connection's company with **Apply To All Document Types** enabled. Verify the normal sales permissions for Lead read/create, Opportunity read/create, Company read and relevant Quotation read with the actual site's Role Permission Manager and synthetic documents. Quotation submission still follows normal ERP approvals.

Leads are not inherently isolated by Company. Explicitly review a Lead's identity, normal permissions and existing sharing before linking it; a Company User Permission alone does not turn a Lead into a private company record. Use separate sites for unrelated customers. System Managers may inspect all connector records; auditors' scope comes from their permitted companies, while operators see their designated connections and their own jobs.

1. Open **UltimateSales Connector** from the Desk workspace/sidebar or search. **Connections / Settings** opens US Connection. Create a named connection with Enabled off, Preview Only on and quotation export off. An incomplete disabled connection can be saved while setup is in progress; no token is necessary to open the workspace.
2. Select the ERPNext Company and confirmed CRM location currency. They must match; the connector does no currency conversion. Select the designated restricted operator described above.
3. Copy the UltimateSales location ID, pipeline ID and qualified stage ID from that location. Manual IDs are supported. The first handoff requires a selected OPEN opportunity in that exact stage. IDs use letters, digits, underscores and hyphens. Routing becomes immutable after an identity mapping exists.
4. Create an ordinary sub-account private integration for the isolated UltimateSales location. Disable any synthetic-account automations that could send messages or incur charges. A System Manager enters its token locally in **Sub-account Private Integration Token**, a Frappe Password field at permission level 1. Save without pasting credentials into chat, source, logs, screenshots or issues.
5. Click **Setup Diagnostics**. It performs local routing, configured operator, Company User Permission, ERP permission, currency and worker checks. It does not decrypt the token, call the CRM or save results. A registered long worker and an enabled scheduler are observations, not proof that a job executes. Follow each displayed next action.
6. Click **Test Connection** as the administrator, or as the designated operator once enabled. The saved disabled connection may be tested by its configuration administrator. The test performs CRM GETs, verifies the configured pipeline and stage, and checks any configured return fields. Supply one synthetic qualified OPEN opportunity ID to also test its opportunity/contact reads and routing. It returns safe transient checks and creates no ERP business records, CRM updates, jobs or saved test result. It does not prove the remote currency, PUT scope or partial-update behavior.
7. Enable the saved connection while Preview Only remains on. Only one connection may be enabled on this candidate site. Activation acquires a site-local metadata-row lock and checks the current enabled state within the same transaction; the administrator cannot retarget already mapped routing. Real concurrent-activation behavior still requires MariaDB acceptance testing. Sign in as the designated operator to perform the workflow below.

## Token scopes and IDs

| Purpose | Scope |
|---|---|
| Read selected contact | `contacts.readonly` |
| Read selected opportunity and list this location's pipelines/stages | `opportunities.readonly` |
| Check configured return-field metadata | `locations/customFields.readonly` (only needed when fields are configured) |
| Write the optional quotation return | `opportunities.write` |

Do not grant contacts.write, agency-wide access or unrelated scopes. Pipeline selectors are unnecessary: the form uses manual IDs and the location-filtered pipeline GET with the existing opportunity read scope. Field metadata checks require the documented additional read scope when the five mappings are used. The provider response cannot prove a token's every scope; the connection test says exactly which GETs passed. The account's availability of these scopes and the live v3 contract must be verified on the designated synthetic location.

## Preview, import and linked records

As the designated operator, open the enabled connection and select **Preview Opportunity**. Enter one synthetic qualified OPEN opportunity ID. The request creates an internal US Sync Job. Click **Dispatch My Due Jobs** from the connection or job, then **Refresh Result** after the long worker runs. Jobs retain the requesting operator's native Frappe identity. This candidate intentionally uses explicit dispatch from that operator's session; the scheduler does not impersonate the user or automatically dispatch saved requests. Retries become due at a bounded future time and require another explicit dispatch.

A Preview result means CRM reads and validation completed with no Lead/Opportunity creation or CRM write. It is not a promise that all site customizations will pass during actual insertion. If identity ambiguity is reported, review the normal ERP Lead and CRM contact, then use **Link Existing Lead** only after confirming they represent the same identity. This separately confirmed action creates an immutable mapping even in preview mode; it does not edit the Lead. Email equality alone never merges records.

After the synthetic preview and review, the deployment owner explicitly sets the site-level write gate using the supported deployment CLI:

```sh
bench --site YOUR-STAGING-SITE set-config ultimatesales_connector_allow_writes 1
```

The System Manager then turns Preview Only off. As the operator select **Queue Opportunity Import**, confirm the deliberate operation and dispatch due jobs. Enabled, Preview Only off and the site gate must all allow writing. A job originally requested as preview never becomes a writing job; create a new import request. **Linked Records** and **Sync Jobs** on the connection show its mappings and audit jobs within the viewer's permissions. Repeat-import checks preserve ERP-owned fields and mappings.

## Optional quotation return

Create five distinct **opportunity-level TEXT** custom fields dedicated to this connector in the configured CRM location. Enter their actual IDs, not labels:

| US Connection field | Suggested CRM label | Value |
|---|---|---|
| ERPNext Opportunity Reference — CRM Field ID | ERPNext Opportunity Reference | ERP Opportunity name |
| Latest Quotation Reference — CRM Field ID | ERPNext Latest Quotation Reference | Latest relevant submitted/cancelled Quotation name |
| Quotation Document State — CRM Field ID | ERPNext Quotation Document State | Submitted or Cancelled |
| Quotation Currency — CRM Field ID | ERPNext Quotation Currency | Currency code |
| Quotation Grand Total — CRM Field ID | ERPNext Quotation Grand Total | Decimal text |

Keep an unrelated sixth CRM custom field as a preservation test. Run Test Connection to check the configured fields' existence, model and TEXT type; quotation jobs also validate the five fields against current metadata before a preview or write. Then follow `STAGING_ACCEPTANCE.md` to prove a real synthetic PUT/readback preserves unrelated custom fields and native deal identity/name/value/pipeline/stage/status. This test cannot be replaced by ticking a checkbox or a successful GET. Only after it passes may the administrator tick **Staging Export Contract Verified** and **Enable Quotation Export Intents**.

Prepare a quotation normally **from the imported ERPNext Opportunity**, preserving its standard Opportunity link. Use **Preview Quotation Return** to queue a read-only preview, then dispatch it. Optional submission/cancellation hooks create durable intents only under the approved operator policy; explicit **Queue Quotation Return** is available after enabling export. The operator dispatches their own due jobs. A different user's submission must not silently acquire the operator's authority. Each summary targets its mapped opportunity; two deals for one contact keep separate summaries. Submitted does not mean sent, accepted, won, invoiced or paid.

## Diagnostics, pause and retention

US Sync Job shows the operation, preview flag, requester, attempts, next attempt, status, sanitized error code and short result. **How to Resolve** supplies an allowlisted action. A configuration administrator corrects settings; the original authorized operator uses **Retry After Review** after fixing a Failed/Blocked job. Changed routing/operator/field mappings invalidate old job fingerprints: create a new reviewed request. Direct REST/form mutation of jobs and identity mappings is rejected, including attempts by Administrator; supported actions provide the internal bookkeeping capability.

Authentication failures require local token review/rotation; wrong scope/location requires correcting account access; missing Company/User Permissions needs administrator review; wrong field type requires opportunity TEXT fields; currency mismatch requires matching confirmed currencies; queue/worker failure needs the deployment owner. Diagnostics return neither credentials, raw HTTP bodies nor personal CRM values. Unknown errors have generic guidance rather than reflecting exception text.

Pause by disabling the connection and setting `ultimatesales_connector_allow_writes` to 0. To disconnect external access, revoke the provider token and review its stored replacement/removal through the Password field while disabled. An in-flight remote request may still complete; pause and database rollback do not reverse external writes. Do not uninstall merely to stop work. Use `RECOVERY.md` and the disposable-site lifecycle plan before uninstall/restore. Returning older source does not undo schema changes.

The app stores only selected ERP identity fields, stable external IDs, record references, requester/times and sanitized job diagnostics. It has no full-payload archive, hidden telemetry, marketing sends or financial posting. Audit jobs and links remain until an explicit reviewed retention policy is implemented; automatic purging/deletion is absent. Backups and encryption-key protection belong to the site owner. Publisher support/security contacts and public privacy/support policies remain pending; no unverified public URL is presented.

## Required installed UI walkthrough

On the approved clean acceptance site, record exact app/Framework/ERPNext revisions, date and result for: workspace discovery by each role; disabled incomplete save without a token; secret field inaccessible to operator/auditor; manager-only configuration; scoped lists/forms; GET-only connection test; preview and dispatch as designated operator; auditors unable to invoke operations; diagnostics and recovery action labels; stop and token rotation. Run the documentation-only round trip with synthetic records. Mark these BLOCKED until performed on the real site; local JavaScript syntax/schema tests alone are not UI evidence.
