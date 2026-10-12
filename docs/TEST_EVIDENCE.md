# Actual test evidence — Step 1–4 candidate

Recorded **12 October 2026, Asia/Singapore**. No historical result is counted as a new run.
Status vocabulary: PASS / FAIL / BLOCKED / NOT RUN. An offline PASS is not an installed/live PASS.

## Revision and environment record

| Item | Actual evidence |
|---|---|
| Repository / branch | Preserved local implementation history; owner-authorized clean public source at `readyspace/ultimatesales-erpnext-connector`, main; exact publication status/commit in PUBLICATION.md and delivery manifest |
| Verified source ZIP | SHA-256 `11a57c4f0f53e2145ad4e345c7f19d92b36e4e60cfc3a50a6a1d60be90b93158` |
| Baseline | `b9d7d17`, unmodified supplied 0.1.0a1, 50 files preserved |
| Candidate | 0.1.0a3 fixture/process-boundary repair; original 0.1.0a2 implementation provenance `1b524b45c81100fed14b69c655e224ee24b607c9`; final exact hashes in delivery manifest |
| Actual local runtime | macOS 26.6.2; Python 3.12.14; Node 22.23.1; pytest 9.1.1; requests 2.34.2 |
| Development / acceptance sites | BLOCKED — none designated (user confirmed) |
| Proposed exact installed matrix | ENVIRONMENT_MATRIX.md; no observed installed support claim |
| CRM account / Company fixture | No designated live location or account; test code contains synthetic fixtures only |
| Security validator | Marketplace `cb1a58adfacbe9d8e0e4a4d5c7d1ef7786a05e6a`, Semgrep 1.156.0 |
| Evidence time | 2026-10-12T09:54:39.540394+00:00 UTC; client zone Asia/Singapore |
| Independent reviewer / tester | Not assigned; source review by task agents is not independent beta sign-off |

## Validation layers actually observed

| Layer | Status | Exact action / evidence |
|---|---|---|
| Baseline offline | PASS | `.venv/bin/python -m pytest -q` on preserved baseline; **99 passed in 0.16s**; `evidence/baseline-offline.txt` |
| Candidate offline | PASS | `.venv/bin/python -m pytest -q`; **264 passed**; `evidence/candidate-offline.txt`. Adds stateful transaction ownership, CLI/native process boundaries and unchanged-rule fetch regressions. |
| Original baseline build | PASS | `python -m build --no-isolation` on `git archive b9d7d17`; original wheel/sdist and required metadata/schema/form assets verified |
| Candidate source/wheel build | PASS | `python -m build --no-isolation`; contents verified with `tools/verify_package.py`; `evidence/candidate-build.txt`, `evidence/package-contents.txt` |
| Python / JSON / JavaScript syntax | PASS | compileall on app/tests/tools, wheel JSON parsing, both form scripts `node --check`; local-checks.json records commands and exits |
| Environment shell / workflow syntax | PASS | `bash -n` and actual YAML 1.2 parsing; recipes are still unexecuted infrastructure definitions |
| Patch whitespace | PASS | `git diff --check`, exit 0 |
| Focused credential scan | PASS for explicit patterns only | `tools/scan_secrets.py` on preserved baseline and final local history; delivery manifest carries final scan output; not an exhaustive scan |
| Real current Marketplace Semgrep rules | **PASS** | Semgrep 1.156.0; all 12 immutable rule hashes verified; 29 files, **0 blocking**, 43 advisory findings, 0 errors, all explicit installed targets present; `upstream/security-scan.json` |
| Full registry get-app/install validator | BLOCKED | Scanner is not full source-install/Marketplace reviewer approval; no designated install resource/remote |
| Installed database/permissions/native worker | BLOCKED | 26 installed checks supplied, not executed; opted-in disposable site required |
| Browser/UI configuration | BLOCKED | No installed Desk site; syntax/schema is not rendering/role acceptance |
| Live CRM API/round trip | BLOCKED | No designated location/token/automation-disable evidence; no live API call |
| Bench / separate Pilot install | BLOCKED | Source-install recipes and CI configured, no environment designated |
| Real worker kill/Redis restart/two-site/lifecycle | BLOCKED | Fault runbook/harness supplied; mocks do not establish these outcomes |
| Remote CI runs | **PASS** for published source `a0b2809` | Offline run 38234142819 and security run 38234142907 completed/success; exact SHA/URLs in PUBLICATION.md and evidence/public-source-ci.json. Installed workflow remains undispatched. |
| Documentation-only self-rehearsal / human acceptance | NOT RUN | No second installed rehearsal or independent tester |

The original eight blocking findings came from commits in shared fixture helpers.
Those helpers now leave writes pending. Native Bench/RQ boundaries and genuine
installed TestCases explicitly own transactions. Shared helpers also no longer
spawn Git/worker processes: native-worker tests own worker orchestration, and the
external CLI runner verifies full app revisions before/after and across sites.
These are substantive ownership changes; no helper was renamed, call disguised,
rule altered or finding suppressed. Existing rule policies for genuine tests
remain unchanged. Historical 0.1.0a2 FAIL evidence is preserved separately in
`evidence/security-scan-0.1.0a2.json`; the current scan is PASS, with advisory
findings still visible. This is not an independent audit or installed/live proof.

## Acceptance matrix

Overall technical statuses remain BLOCKED until installed/live evidence exists. Supporting
unit checks below do not replace the original expected outcomes.

| ID | Scenario | Expected result | Status | Evidence / actual result |
|---|---|---|---|---|
| A01 | Fresh supported Bench site | Installs and opens with ERPNext; HRMS absent. | BLOCKED | Configured Bench install recipe and 4 installed smoke checks; no site run. |
| A02 | Fresh Pilot-managed ERPNext site | Same app commit installs through supported Git route. | BLOCKED | Pinned Pilot Git route documented; no designated Pilot host/source access. |
| A03 | Missing dependency or unsupported stack | Clear preflight error; no partial activation or silent fallback. | BLOCKED | Dependency/Python/database preflight implemented; actual installed rejection not run. |
| A04 | No credentials / disabled settings | No CRM requests or business writes during installation/migration. | BLOCKED | Default-off/package tests PASS offline; installed install/migrate side effects unproven. |
| A05 | Connection test and preview | No business/CRM writes; internal audit/job changes disclosed. | BLOCKED | GET-only connection/preview regression tests PASS offline; live and UI checks blocked. |
| A06 | First selected qualified opportunity | Exactly one linked ERP Lead/Opportunity as specified. | BLOCKED | First/repeated import orchestration PASS with mocked framework; real SQL harness supplied. |
| A07 | Repeat import and two concurrent workers | No duplicate business records or cross-linking. | BLOCKED | Replay checks PASS offline; two genuine native worker/SQL concurrency tests supplied, not run. |
| A08 | Same email, unrelated Lead; changed remote contact | Explicit review required; no automatic merge or reassignment. | BLOCKED | Email ambiguity/contact/ERP identity checks PASS offline; installed fixtures supplied. |
| A09 | Wrong company/location or unauthorised user | No protected reads, writes or exports; safe error. | BLOCKED | Role/company/location/record and scoped mapping-list checks PASS offline; installed negatives blocked. |
| A10 | User disabled/permission removed while queued | Execution is denied on retry/restart as well as first run. | BLOCKED | Revocation/actor-loss regression tests PASS offline; installed disable/role/company cases supplied. |
| A11 | Submit/cancel/amend quotation; two deals for one contact | Latest relevant summary goes only to its mapped deal. | BLOCKED | Latest committed quote/currency/identity checks PASS offline; actual submit/cancel/amend/live sibling-deal blocked. |
| A12 | Unrelated CRM custom fields | Values are preserved through update and retry. | BLOCKED | Owned-only payload and unrelated/native-field readback checks PASS offline; live partial semantics blocked. |
| A13 | Rate limit, API outage and expired/revoked token | Bounded transient retries; permanent denials require correction. | BLOCKED | HTTP denial/429/outage/redaction/backoff tests PASS with fake responses; live faults blocked. |
| A14 | Queue outage, worker kill and rescheduling | No lost committed request, duplicates or uncontrolled retry storm. | BLOCKED | Durable intent/dispatch tests and native-worker harness supplied; injected Redis failure is not a real outage/kill. |
| A15 | Remote update succeeds, then local commit fails | Readback/retry converges safely; do not claim remote rollback or exactly-once delivery. | BLOCKED | 5 stateful HTTP/local-failure recovery tests PASS offline; actual SQL synthetic test supplied; live drill blocked. |
| A16 | Config changes, pause and credentials revoked | Queued work is safely blocked; active-request limitations documented. | BLOCKED | Paused/configuration/current actor gates PASS offline; real in-flight/token revocation behavior blocked. |
| A17 | Two independent sites with colliding external IDs | No credential, cache, link, job or log leakage between sites. | BLOCKED | Site-specific DB/native queue design and two-site runner supplied; no actual two-site execution. |
| A18 | Logs, exports, issue templates and screenshots | No tokens, password fields or unnecessary customer data exposed. | BLOCKED | Focused source/history credential scan and redaction tests run locally; real site logs/screenshots/export review blocked. |
| A19 | Upgrade / disable / uninstall / restore | Behavior matches documentation; no unexpected core-record deletion. | BLOCKED | Clean-install-only; disposable lifecycle/restore procedure supplied; upgrade/disable/uninstall/restore not executed. |
| A20 | Independent documentation-only installation | Successful round trip without developer rescue or private access. | NOT RUN | No documentation-only installed rehearsal or independent tester; later independent gate NOT RUN. |

## Run records and limitations

`evidence/local-checks.json` records each actual command, exit and sanitized output file.
All local commands in that record exited 0. `upstream/security-scan.json` records exact rules,
file hashes, status and findings; its source hashes were checked against the final app tree.
`upstream/source-verification.json` and ENVIRONMENT_MATRIX.md retain immutable source pins.
Complete source/archive/patch/build hashes and focused credential scan output are delivered
separately so they do not create a circular self-hash in a committed report.

No actual Frappe/MariaDB/Redis/CRM installation is present. No real customer payload, token,
site key, backup, personal API response or production configuration was collected. Historical
VALIDATION_REPORT.md and offline-test-results.txt remain unchanged. Coverage was not rerun;
no inherited 99% coverage claim applies to this candidate.

## Handoff verdict

Step 1 baseline and Step 2–4 implementation assets are complete locally; required installed,
live, UI, lifecycle and independent security-review gates are unfinished. The local pinned static scan gate now passes. Full Step 1–4 completion: **NO**.
Ready for Step 5 independent beta verification/sign-off: **NO**. Ready for source review and
designated isolated acceptance: **YES**. Public beta published / Marketplace submitted: **NO**.
See STEP_1_TO_4_REPORT.md, BLOCKERS.md and HANDOFF_STATE.md for secure continuation.
