# Security posture — implementation candidate

Candidate 0.1.0a3 has offline security checks, not an independent security audit.
Installed permissions, live scope/isolation, real recovery and two-site tests
remain blocked. Read TEST_EVIDENCE.md and the authorization decision.

All public methods are authenticated POSTs. System Manager configures; a designated
restricted System User with UltimateSales Operator and exactly one global Company
User Permission requests/dispatches only their own jobs. Guest, Administrator and
System Manager cannot execute the sales workflow. Frappe's native requester identity
is retained and verified at worker entry; the app never switches users. Normal ERP
record read/create permissions apply. Company checks do not make Leads tenant-private.

Connections, jobs and links have role plus query/document scope checks. Credentials
are stored only in a manager-level Password field; no job contains a token. Only
validated immutable mapping/audit insertion bypasses permissions, through a
context-local code capability; direct changes to internal records are denied.
There are no guest callbacks, core overrides, hidden telemetry or arbitrary API hosts.
TLS verification, disabled redirects, validated IDs, bounded timeouts and sanitized
error codes protect the external adapter. Installation/migration has no CRM requests.

The client sends five dedicated opportunity TEXT fields, verifies owned-field
readback and checks unrelated/native-field preservation. Account semantics remain
unproven until the designated synthetic live test. A remote write can succeed before
a local failure and can trigger external automations; local rollback never reverses
it. Disable test account campaigns and customer-facing/chargeable workflows. No
exactly-once effects are promised.

The app stores selected Lead identity fields, stable external IDs, ERP references,
requester/timestamps and safe diagnostic codes. Preview makes CRM GETs and creates
an audit intent; explicit identity binding creates a mapping. CRM responses are
transient, not payload archives. No automatic retention purge is implemented.
Provider token/DB/encryption-key backups belong to the deployment owner. A Password
field does not protect a fully compromised host/database plus encryption key.

Pause by disabling the connection/site gate; revoke the provider token when stopping
external access. In-flight requests may complete. Never share tokens, raw customer
payloads, environment dumps, site_config.json, backups, key material or debugger
locals in issue reports or test artifacts. Use synthetic data and safe error codes.
Focused source/history credential scanning is recorded separately from the real
pinned Marketplace Semgrep scan; neither constitutes a full independent review.

Publisher-approved monitored support/security contacts and public privacy/support
policies are pending. No fictitious address or service is supplied. Use the owner's
established private reporting channel until those are approved. These publication
prerequisites do not authorize external messages, production changes or releases.
