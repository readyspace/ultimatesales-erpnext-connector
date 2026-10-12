# Candidate architecture and invariants

This file describes candidate 0.1.0a3. Historical alpha test evidence remains in
VALIDATION_REPORT.md. See decisions/authorization-and-job-execution.md for the
requester/worker policy and upstream source evidence.

A single enabled US Connection maps one CRM location to one ERP company. One
restricted operator deliberately previews/imports a selected qualified OPEN deal.
Stable Contact and Opportunity mapping keys prevent silent reassignment; email
matches require explicit Lead binding. The first import uses ordinary ERP
permissions to create Lead/Opportunity; replay keeps existing fields. Lead is
not assumed company-private, and cross-company existing link reuse is denied.

The operator creates a durable US Sync Job under their authenticated identity.
Frappe captures that identity when the operator dispatches due committed work.
A worker locks connection then job, verifies requester/current actor/configuration
and current Company/ERP access, then uses a savepoint for local business writes.
Only connector links/audit intents use a guarded internal permission exception.
Direct edits cannot forge job ownership/configuration. No app session switching,
queue identity override or core patch exists. Scheduler impersonation is removed;
dispatch/retries require the operator's session. A queue outage retains the intent.

Preview is permanently pinned per request. Default settings disable writes;
actual business writes recheck the saved connection and site gate. Old routing,
company, operator and export-field changes block queued jobs. Token rotation
keeps the mapping route; the API validates current scoped records on every use.
Configuration changes and disable are serialized with worker connection locks;
already transmitted remote writes can complete before a pause takes effect.

Quotation hooks create intents only for the designated operator. Quotations
submitted by other normal ERP users remain valid ERP operations; the operator
explicitly requests their return. The service internally selects the latest
created submitted/cancelled quotation for the mapped deal and checks permission
on that exact document, so a hidden newer quotation is denied rather than replaced
with an older accessible one. Draft amendments do not replace committed summaries.
The currency must match the connection. Submitted and Cancelled are document
states, without a sent/paid/won interpretation.

The fixed HTTPS HighLevel v3 client uses bounded timeouts, TLS, no redirects,
validated IDs and no environmental proxy/credential inheritance. Connection tests
use GET-only pipeline/stage/field/sample reads. Export sends only five mapped
opportunity TEXT fields; unrelated fields are never included in a read/modify/write
payload. Readback verifies owned fields, unrelated field preservation and native
deal fields. This detects corruption or concurrent edits after a remote change;
it cannot atomically prevent or roll back an external write. Real account partial
semantics must pass before export is enabled.

Local failure after remote success leaves a recoverable intent. A replay recomputes
the current quotation and reads the provider; an already-current summary avoids
another PUT. This is at-least-once convergence. API side effects and simultaneous
third-party changes are outside the local transaction. There is no cross-system
exactly-once guarantee, remote rollback or broad reconciliation engine.

All records/locks/jobs use the current Frappe site; native queue IDs are site
namespaced by pinned Framework code. Two-site isolation, real concurrency,
worker/Redis outages and lifecycle remain installed acceptance gates. Company
checks inside one site do not replace independent sites for unrelated clients.
No CRM discovery, full UI, webhook, bulk backfill, Customer, invoice, payment,
sales-order, marketing or HR behavior is implemented.
