# Authorization and queued execution

Decision recorded 12 October 2026 before refactoring the alpha. Installed-site
verification remains required; this decision is an implementation policy, not
independent security approval.

The alpha switched the app session to a configured integration user. Remove that
behavior. The requester is now the designated restricted operator configured in
US Connection. Frappe's supported enqueue path captures the authenticated current
session user. The worker must match that user to both `requested_by` and
`integration_user`, then revalidate an enabled System User, the UltimateSales
Operator role, an explicit global Company User Permission, Company read access,
and normal Lead/Opportunity/Quotation permissions. Guest, Administrator and
System Manager cannot act as the business operator. ERP inserts use ordinary
document permissions. Configuration administrators do not impersonate operators.

Installation/configuration belongs to System Manager. The designated operator
can preview, request import/export, explicitly bind an accessible Lead, retry
their own job, and dispatch their own due jobs. UltimateSales Auditor has scoped
read-only local diagnostics. Role permissions plus query/document checks protect
connections, links and jobs. Credentials have a separate manager permission level;
operators invoke narrowly scoped server-side reads without receiving the token.

One location maps to one company, with one active connection initially. An
operator needs exactly one global Company User Permission for that company.
Lead is not assumed company-scoped: ordinary Lead read permission is required,
and an explicit mapping cannot reuse a Lead mapped to another company. Matching
email is only a review signal. The operator must see all relevant quotations;
select the latest committed quotation internally, then check permission on that
exact document, rather than exporting an older permission-filtered result.

Database intents are inserted in the requesting transaction. Only immutable
connector links and audit intents use a narrow internal permission exception,
guarded by a context-local code capability and validated routing. Direct REST
inserts/edits are rejected. The worker resets its read-only discovery snapshot using rollback, locks
connection then job and makes business changes within a savepoint. The native
Frappe worker commits on normal return; the app never manually commits. All data remains in the current Frappe site.

The scheduler runs under a privileged framework identity and cannot safely
enqueue historical requests as their actors through the public enqueue API.
Therefore unattended scheduler dispatch is removed. The operator dispatches due
committed intents from the connection form, including Retry intents after their
bounded backoff. Redis failure leaves the SQL intent intact. A restart or retry
under another identity is denied. No `user=` enqueue override, session mutation,
queue-internal impersonation or broad business permission bypass is used.
This deliberate manual dispatch limitation is visible in the UI and runbook;
autonomous dispatch is blocked pending a supported upstream design.

Every execution rechecks the configuration fingerprint and current privileges.
Changing company/location/pipeline/stage/operator/export fields blocks old jobs.
Retry cannot change ownership or retarget a fingerprint; create a new reviewed
request after a configuration correction. Pause/write gates are checked again
immediately before business writes or remote PUT. An already transmitted remote
request may still complete. Token rotation never stores a credential in an intent.

Remote writes and local commits are separate transactions. Replays read back
the owned fields, avoid an already-current PUT and verify unrelated fields after
an update. This is at-least-once convergence; remote rollback and exactly-once
effects are not promised. Live partial-update verification is required before
export is enabled.

Upstream immutable source references and actual validator execution are recorded
in ENVIRONMENT_MATRIX.md, API_CONTRACT.md and TEST_EVIDENCE.md. A real framework
permission test, worker/Redis recovery and independent review remain release gates.

## Follow-up: acceptance transaction ownership

Shared synthetic fixture helpers leave database writes pending. Native Bench
execute commits a successful Company bootstrap; native RQ execute_job commits
normal worker completion. Genuine installed TestCases explicitly own setup,
request visibility, synchronous worker-completion simulation, and cleanup
transactions. Failed helpers do not commit partial fixture writes. Worker process
launches live in native-worker tests and Git revision collection belongs to the
external CLI runner. This changes ownership rather than disguising calls or
renaming helpers. The unchanged pinned rules retain their existing test-case
policy; no new exemption or suppression is added. Offline transaction models
verify control flow. Actual installed database/native-worker evidence remains
blocked until a disposable environment is designated.
