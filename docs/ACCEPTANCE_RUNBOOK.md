# Disposable installed-site acceptance runbook

**Status on 12 October 2026: supplied, not executed against Frappe/MariaDB/Redis or a live CRM in this workspace.** The root pytest suite is offline. The installed modules below must be run separately on the recorded target stack before claiming installed permissions, concurrency or recovery are verified.

## Scope and prerequisites

Use two disposable Frappe 16 / ERPNext 16 MariaDB sites in an isolated bench. Do not use the HR-only site or a production clone containing customer data or working provider tokens. Install this reviewed source and migrate both sites. Complete ERPNext setup with a synthetic Company on each site, standard Sales User permissions, All Item Groups and Nos UOM. The quotation recovery case creates its own company-currency Price List, normally inserts and submits a nonstock Item and Quotation, and does not need currency conversion; site customizations may legitimately make this case fail and must be investigated.

No live token is needed for these installed tests. Synthetic connection credentials are fabricated, and the tests replace only the CRM transport. Normal Frappe permission checks, actual MariaDB inserts/savepoints/rollbacks and actual Redis/RQ workers remain in use. Fixtures create uniquely named users, Company User Permissions, connectors, jobs and business records and normally clean up their own records. Tests commit; a killed test process can leave synthetic fixtures. Take a disposable snapshot first and restore it after faults or incomplete cleanup.

Each site must start with no enabled US Connection. Reserve the custom `us_acceptance` queue for this disposable bench; do not run a permanent worker on that queue. The suite starts its own burst workers. Keep Redis available. The connector's production job queue remains `long`.

Frappe supports custom queues through `workers` in common configuration and burst workers through `bench worker --queue NAME --burst`. Verify these options against your installed versions. [Frappe background-job documentation](https://docs.frappe.io/framework/user/en/api/background_jobs), [configuration command reference](https://docs.frappe.io/framework/user/en/bench/reference/set-config).

## Explicit opt-in

Run these commands in the isolated bench, substituting the actual synthetic company names. `workers` replaces that setting, so preserve any existing custom queues if the disposable bench has them.

```sh
bench set-config -g --parse workers '{"us_acceptance":{"timeout":120}}'
bench --site acceptance-a.localhost set-config allow_tests true
bench --site acceptance-a.localhost set-config ultimatesales_connector_acceptance_tests 1
bench --site acceptance-a.localhost set-config ultimatesales_connector_acceptance_company 'Synthetic Company A'
bench --site acceptance-a.localhost set-config ultimatesales_connector_allow_writes 1
bench --site acceptance-b.localhost set-config allow_tests true
bench --site acceptance-b.localhost set-config ultimatesales_connector_acceptance_tests 1
bench --site acceptance-b.localhost set-config ultimatesales_connector_acceptance_company 'Synthetic Company B'
bench --site acceptance-b.localhost set-config ultimatesales_connector_allow_writes 1
```

For a fresh disposable CI site that has ERPNext installed but no Company, the optional `bench --site SITE execute ultimatesales_connector.tests.acceptance_support.bootstrap_synthetic_company` helper creates a normally validated Singapore/USD Company under the native Administrator after disposable opt-in. It returns a per-site synthetic company name; save that exact result in `ultimatesales_connector_acceptance_company`. The helper does not mark setup, installation or live API acceptance passed.

The write flag must be saved in the site's configuration: a Python process's in-memory change is invisible to child workers. The fixture gate prevents accidental use on an unapproved site, but is not a replacement for a disposable environment.

## Run and record

From a machine with Bench on PATH, run the supplied runner using the installed app checkout's script:

```sh
python tools/run_acceptance.py \
  --bench-dir /absolute/path/to/disposable-bench \
  --site acceptance-a.localhost --site acceptance-b.localhost \
  --confirm-disposable --parallel-sites \
  --report /absolute/path/to/local-evidence/acceptance-results.json
```

The runner records the actual site, Python/Frappe/ERPNext/connector/database versions and app commits, module execution counts and statuses. It fails on an infrastructure preflight failure, a skipped installed suite, a failed command or missing execution counts. It records live CRM, worker kill, restore and upgrade checks as **not run**. It saves no raw HTTP response or token. For a failure, run the affected module directly below and review local sanitized test/worker logs. Do not share site configuration or database dumps.

```sh
bench --site acceptance-a.localhost run-tests --module ultimatesales_connector.tests.test_install_contract
bench --site acceptance-a.localhost run-tests --module ultimatesales_connector.tests.test_permissions_recovery
bench --site acceptance-a.localhost run-tests --module ultimatesales_connector.tests.test_native_queue
```

`--single-site` is available for diagnosis. A one-site result must leave two-site isolation unverified. Parallel two-site execution runs the same synthetic external identity on both sites and each genuine native worker asserts its own site and requesting operator. Same-deal concurrency uses two native worker processes with a Redis barrier before the connection lock; a failure to start both workers is a failed check, not a fallback to sequential mocked execution.

## Evidence boundaries

| Supplied check | Actual boundary exercised when run | Remaining limitation |
|---|---|---|
| Install contract | Installed version/schema/defaults and manager guard | Does not itself perform clean install, upgrade or UI rendering |
| Permission revocation | Real User/role/Company permissions and business create permissions, rechecked at execution | Site-specific sharing and every custom role need review |
| Operator isolation | Native requester, designated operator, settings protection, job visibility and request/retry/dispatch guards | Direct Python calls do not replace HTTP authentication/method/security testing |
| Inbound rollback | Real Lead and mapping insertion followed by savepoint rollback | Fault injected deliberately; no process kill |
| Completion interruption | Real SQL job/business rollback followed by replay | Python completion failure, not operating-system kill |
| Outbound recovery | Real submitted Quotation + SQL rollback, real HighLevelClient against stateful fake HTTP; one PUT then no-op replay | Does not establish remote provider behavior or external workflow effects |
| Redis submission failure | Deliberate enqueue failure preserves committed SQL intent; genuine worker later recovers | Redis failure is injected; actual Redis restart/outage remains required |
| Native queue/concurrency | Actual Redis serialization, Frappe enqueue actor/site, RQ processes, MariaDB row locks and duplicate prevention | Not a stress test, distributed-host test or disaster recovery exercise |
| Two sites | Identical synthetic external ID processed under independently asserted native site/user contexts | Installed two-site result is only established after the runner succeeds on both |

Synchronous fault-injection fixtures simulate the framework's transaction boundary by committing after `jobs.run` returns normally. The native queue cases use the actual Frappe/RQ worker's commit. The app itself resets only its read-only snapshot with a rollback and never commits manually.

## Live and lifecycle gates still required

Complete every applicable row of `STAGING_ACCEPTANCE.md` on a synthetic UltimateSales location. Verify all five opportunity TEXT field IDs, unrelated custom fields, native name/pipeline/stage/status/value/contact preservation, wrong scopes, revoked provider credentials, ambiguous mapping, two deals sharing a contact, cancellation/amendment and actual workflow effects. Record safe provider/account and field-model evidence locally; never paste credentials or contact payloads into a report.

Use `RECOVERY.md` for actual worker-kill, API-response-loss, Redis outage, token rotation, backup/encryption-key restore and app upgrade/rollback drills. Record timestamps, app/database versions, job IDs and sanitized error codes with before/after counts. Mark those gates pending until they are performed; the automated installed suite does not perform them.

After testing, reset the site write flag and acceptance opt-in to `0` and restore or destroy the disposable snapshots. Keep the acceptance report separate from the source's offline validation report. A green installed report supports only its stated synthetic boundaries; production rollout and public/Marketplace review require their own approvals and evidence.

Shared fixture helpers do not commit or launch processes. Concrete installed
TestCases and native command/worker boundaries own transaction completion, and
native-worker tests own process orchestration. The external acceptance runner
records strict full app commits before/after and requires identical revisions
across tested sites. Fetch unchanged security rules via tools/fetch_security_rules.py
before running the scan wrapper. Installed/live verification is still unrun.
