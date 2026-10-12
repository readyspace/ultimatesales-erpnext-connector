# Validation report — v0.1.0-alpha.1

**Prepared: 12 October 2026. Status: source alpha; NOT production-ready or Marketplace-approved.**

## Checks actually executed

| Check | Result | Scope |
|---|---|---|
| Offline pytest suite | **99 passed** | Framework-independent rules, mocked HTTP client, mocked service/job orchestration, and static packaging/schema checks. |
| Python syntax compilation | Passed | Application Python files; root tests also parsed/executed. |
| JavaScript syntax | Passed | Both DocType form scripts checked with Node.js; no browser rendering test. |
| JSON schema-file parsing | Passed | Three DocType JSON files and their field-order checks. |
| Wheel build | Passed | Built offline using installed setuptools; no dependency download. |
| Wheel data-file inspection | Passed | Required DocType JSON, form JavaScript and modules.txt included. |
| Focused statement coverage | 99% | **Only domain.py and client.py**: 203 of 204 measured statements exercised. NOT full-app or Frappe integration coverage. |

Workspace: Python **3.13.5**; Node.js **v22.16.0**. No Frappe package, MariaDB-backed site, Redis worker or live CRM token was available in this source-authoring workspace. Python 3.13 was used only for standalone tests; the target Frappe v16 runtime must satisfy Frappe's own current Python requirements (the reviewed branch specifies Python 3.14).

The 99 checks include parameterized cases and mocked assertions. They are not 99 installed-system or live API test scenarios. The separately included installed-site smoke module contains four checks that were NOT executed here.

## Specifically tested offline

ID validation; wrong-location/pipeline rejection; initial qualified/open-stage gate; identity reassignment rejection; manual email-match review; narrow field mapping; invalid amounts and text; no marketing-consent transfer; opportunity-scoped quotation payloads; no Submitted-to-Paid/Sent/Won inference; retry classification and Retry-After parsing; HTTP error redaction; TLS/redirect/host settings; readback validation; preview gates; routing fingerprints; default-off settings; POST-only/manager-guard structure; first/replayed handoff orchestration; latest-quotation selection; mocked worker savepoint/retry/disable behavior.

## NOT executed or established

- Actual Frappe/ERPNext installation, migrations, upgrade, uninstall, permissions or DocType UI rendering.
- Live UltimateSales/HighLevel v3 API calls, token scopes or account-specific partial custom-field semantics.
- MariaDB concurrency, transaction rollback under real ERP hooks, Redis outages, worker kill/restart or crash-after-remote-write recovery.
- Full unit/integration coverage of every Frappe adapter, installed controller, public endpoint and hook.
- GitHub Actions execution, repository creation or remote push.
- Public security review, approved privacy/support policies, production rollout, external beta or Marketplace submission/approval.

## Release decision

**GO:** engineer review, local repository creation and isolated synthetic-data staging pilot.

**NO-GO:** production customer-data synchronization, public compatibility claims, paid support promises based on this alpha, or Marketplace submission.

Complete docs/STAGING_ACCEPTANCE.md on recorded stack and API versions; resolve every failure; obtain pilot/security approval before changing this decision. Passing a wheel build proves package construction, not a successful Frappe app installation.
