# Staging acceptance — mandatory before production

**Execution status: not run in the source-authoring workspace.** Record actual app commits, Python/Frappe/ERPNext/MariaDB versions, location/company, date, tester and sanitized evidence. Use synthetic records and disabled customer-facing workflows.

| Test | Required evidence |
|---|---|
| Clean install and migrate | Matching v16 stack; all three DocTypes and form scripts load; no core diff; no business records on install. |
| Upgrade from this alpha | Data-preserving migrate with existing connections/maps/jobs; encryption key preserved; rollback procedure tested. |
| Default-off behavior | Fresh connection/site cannot create business records or call PUT. |
| Read-only preview | API reads succeed; Lead/Opportunity counts and all CRM fields remain unchanged; audit job reports Preview. |
| First import | Exactly one Lead and one Opportunity, correct identity/company/currency/value, two correct mapping records. |
| Repeated/concurrent import | Repeat the same ID; run two workers for it; no duplicate business records or corrupted job states. Test actual MariaDB isolation. |
| Existing email | An unmapped matching ERP Lead stops import; explicit reviewed binding reuses it; no heuristic merge. |
| Contact reassignment | Changing the CRM deal contact after import stops work without automatic reassignment. |
| Wrong scope/identity | Wrong returned location, pipeline, contact ID or ERP company produces a visible failure and no business/API writes. |
| Restricted user | No System Manager privilege; normal allowed operations succeed; revoked create/read/company permissions fail safely. |
| Guest/general user access | All five administrative endpoints deny unauthorized users; settings, token, mappings and jobs are not public. |
| Five-field API contract | Opportunity TEXT fields accept the v3 partial update; unrelated custom field and native pipeline/stage/status/name/value/contact are preserved. |
| Quotation return | Manually prepare/submit quote from imported opportunity; five accurate fields appear on the correct CRM deal; never on every contact deal. |
| Two deals, one contact | Each CRM opportunity receives only its own ERP quotation summary. |
| Submission meaning | Field says Submitted, not Sent/Accepted/Paid/Won; no invoice or payment is created. |
| Cancellation/amendment | Correct latest submitted/cancelled quote; no draft exposure; old cancellation never overwrites a newer quote summary. |
| Outbound no-op replay | Unchanged remote owned fields skip PUT; no duplicate notifications are emitted by test workflows. |
| API failures | 401/403/404/422 visible permanent failures; 429 honors Retry-After; transport/5xx retries stop after five attempts. |
| ERP validation failure | Force missing mandatory custom field after Lead insertion; both new Lead and new mappings roll back. |
| Kill/crash recovery | Kill a worker before commit and around remote success; retry recovers without duplicate local records; inspect external effects. |
| Redis outage | A committed intent remains in SQL even if dispatch fails; restore Redis/workers and verify recovery. |
| Configuration change | Queue a job then alter mapping/user before execution; old intent blocks; create a fresh reviewed job. |
| Token rotation/revocation | Safe token rotation does not invalidate routing; revoked token fails visibly without revealing secrets. |
| Disable controls | Disable connection and site write flag while queued; verify no new writes; document any in-flight completion. |
| PII/log review | No bearer tokens, raw response bodies, full contact records, or exception text appear in job logs or CI artifacts. |
| Recovery and retention | Backups/keys restore successfully; disconnect leaves existing business data intact; retention policy signed off. |

Preview, rule tests and mocked HTTP tests do not prove database atomicity, installed Frappe permissions, JavaScript rendering, live API conformance, or third-party workflow behavior. Do not mark these rows passed merely because offline tests pass.

Acceptance owner must approve both the inbound handoff and outward quotation contract before any real customer data is used. Marketplace acceptance is a separate external review.
