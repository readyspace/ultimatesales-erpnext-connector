# Step 1–4 implementation and verification report

Implementation commit `1b524b45c81100fed14b69c655e224ee24b607c9`.
Evidence date: 12 October 2026, Asia/Singapore. Candidate **0.1.0a3**;
clean-install-only. No production access, repository publication, release tag,
default-branch merge, paid infrastructure or customer communication. This follow-up
authorizes a clean public source repository; publication is recorded separately.

| Step | Actual status | Completed work | Remaining gate |
|---|---|---|---|
| 1. Baseline/environment | PARTIAL — environment BLOCKED | Verified input SHA-256, preserved Git baseline, reran 99 tests and baseline build, inventoried tools/repository access; immutable upstream stack and runnable two-site definition | User confirmed no isolated environments designated |
| 2. Authorization/API | PARTIAL — installed/live BLOCKED | Full unchanged security scan PASS, zero blocking findings; fixture transaction/process ownership repaired; native requester execution, revocation checks, role/company/document scope, fresh locking reads, internal record protection, runtime field validation; documented official v3 contract and actual security scan | Installed negative permissions/worker behavior, account scope/isolation/partial semantics and independent security review |
| 3. Self-service | IMPLEMENTED — UI acceptance BLOCKED | Workspace, manager/operator/auditor separation, Password permission level, tokenless disabled setup, read-only connection checks, diagnostics/views/runbook | Real role/UI walkthrough and documentation-only setup |
| 4. Workflow/install/recovery | PARTIAL — acceptance BLOCKED | Offline recovery/permission regressions, package checks, installed SQL/native-worker harness, Bench/Pilot recipes, CI and lifecycle/recovery docs | Same-revision Bench and Pilot installs, live round trip, real outage/kill/two-site/lifecycle drills and documentation rehearsal |
| 5. Independent beta/release | BLOCKED / OUT OF SCOPE | Public source is authorized separately in this follow-up; no beta or release approval | Installed/live acceptance and independent sign-off remain required |
| 6. Marketplace | OUT OF SCOPE | Actual rules reviewed and locally scanned; no submission | Later publication and immutable tested release |

## What changed

The alpha switched identities inside application code. The candidate requires the
actual authenticated designated operator and uses supported Frappe enqueue identity,
then rechecks current requester, enabled user, roles, explicit Company permission,
current document access and routing. It uses explicit operator dispatch for durable
requests and bounded due retries. Scheduler impersonation is removed. Pinned
Framework DB-retry identity loss fails closed. Normal ERP inserts remain normal
permission checks. Native Framework owns the final commit; internal links/audit
inserts alone use a narrowly guarded exception. Concurrent activation uses a
site-local common lock and a current active-connection read.

Settings and records now have scoped query/document permissions; mapping lists also
require underlying ERP visibility. Identity binding reauthorizes the current locked
connection before a CRM read. Jobs preserve requester, preview and configuration
on retry. Unrelated same-email Leads require explicit review; changed contact/ERP
identity and wrong-company links are denied.

Quotations stay human-created/submitted. Return uses the latest committed
submitted/cancelled quotation, checks that exact document's access/currency and
its linked deal, validates five opportunity TEXT-field metadata entries and sends
only those fields. Readback checks owned values, unrelated custom fields and native
deal fields. Stateful failure tests show remote-success/local-failure replay
convergence; they do not prove live preservation, remote rollback or exactly-once
side effects. Nonoperator quotation submission remains a normal ERP action; the
operator explicitly requests its return.

The workspace/settings flow now includes a setup checklist, GET-only connection
checks, operator/company/worker diagnostics, linked records and allowlisted recovery
messages. Default gates are off; install requires no token or CRM request. Source
recipes pin exact Framework/ERPNext/Bench/Pilot/runtime revisions and configure
separate clean sites without HRMS. CI definitions include skip-failing installed
acceptance; no remote run has occurred.

## Actual tests and deliverables

TEST_EVIDENCE.md contains the final exact counts, exit codes, sanitized artifacts,
security findings and all A01–A20 statuses. ENVIRONMENT_MATRIX.md separates the
observed standalone runtime from proposed unexecuted Frappe/Pilot stacks.
Original VALIDATION_REPORT.md and its prior output remain unchanged historical
records. Local implementation/report commits, full updated archive, baseline diff
and artifact hashes are identified in HANDOFF_STATE.md and the delivery manifest.

## Verdict and required continuation

The candidate is ready for source review and designated isolated acceptance.
**It is not ready for Step 5 independent beta verification/sign-off.** No complete
Step 1–4 installed workflow was established. User confirmed no test environments
designated yet; local Bench/MariaDB/Redis/container runtime and synthetic CRM
location/account are absent. The intended remote returned 404 and was absent from the accessible organization
inventory. The active account has ReadySpace admin membership; the owner now
authorizes a clean public source repository, preserving old local history privately.

Designate a conventional Bench host and a separate Pilot test site, use the exact public source commit after publication, and designate a synthetic
CRM location with outbound/chargeable automations disabled. Enter scoped credentials
locally in the Password field. Execute the committed runbooks on the same full
candidate commit, fix/retest failures and record sanitized evidence. Real worker
kill/Redis restart, live partial-update/recovery, two-site privacy and lifecycle
checks are required. Alpha upgrade is unclaimed. Publisher contacts/policies and
independent tester assignment remain later publication prerequisites. See
BLOCKERS.md and HANDOFF_STATE.md for the exact resumable state.

## Security repair follow-up

Candidate 0.1.0a3 reran **264 offline tests**, all PASS. The unchanged twelve-rule
Semgrep scan PASS covers 29 files: zero blocking findings, 43 advisory findings
and zero errors. Shared helpers leave SQL pending; native Bench/RQ and concrete
TestCases own commits. Worker processes belong to genuine native-worker tests;
the external runner verifies fixed full source revisions before/after/across sites.
No suppression, helper renaming or disguised calls were used. Third-party source
references remain local, with immutable URLs/hashes and an unchanged-rule fetcher
in the distributable source. See PUBLICATION.md for GitHub Desktop/remote status.
Installed and live gates remain BLOCKED.
