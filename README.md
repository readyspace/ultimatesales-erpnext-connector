# UltimateSales.ai Connector for ERPNext

ReadySpace's separate Frappe app for one deliberate sales-to-quotation handoff.
Implementation candidate **0.1.0a3**, clean-install-only; no public beta or release
has been published. The owner has authorized public source publication at
[readyspace/ultimatesales-erpnext-connector](https://github.com/readyspace/ultimatesales-erpnext-connector);
source availability does not establish installed compatibility or beta approval. See [Step 1–4 report](docs/STEP_1_TO_4_REPORT.md) and
[test evidence](docs/TEST_EVIDENCE.md) for actual results and blocked gates.

Select one qualified OPEN CRM opportunity → preview → explicitly import → create
or explicitly link a Lead and Opportunity → prepare the quotation normally in
ERPNext → optionally return five summary values to that same CRM opportunity.
Email equality never merges identities. Existing ERP fields remain ERP-owned.
There is no bulk synchronization, automatic discovery, webhook, Customer creation,
financial posting, marketing messaging, CRM replacement or HRMS dependency.

The candidate adds a Desk workspace, ordered setup checklist, GET-only connection
checks, scoped linked-record/job views and actionable sanitized diagnostics.
System Manager configures; one designated restricted UltimateSales Operator
requests, dispatches and retries their own work; UltimateSales Auditor has scoped
read-only diagnostics. Credentials use a manager-only Password field.

Jobs execute under Frappe's native captured requester identity. The app never
switches users. Access is checked again at execution and before writing. The
operator explicitly dispatches their due committed intents: unattended scheduler
impersonation is unsupported. Redis failure retains the SQL intent. Remote writes
and local commits are separate; readback/replay provides convergence without an
exactly-once or remote rollback guarantee.

New connections are disabled, preview is enabled and quotation export is disabled.
Installation/migration requires no CRM credentials or CRM requests. The deployment
owner explicitly sets `ultimatesales_connector_allow_writes`; all import gates
must allow writes. Quotation return also requires five opportunity TEXT fields
and a real synthetic-account preservation test before enabling its verification
gate. Submitted means Submitted; it does not mean sent, accepted, won or paid.

The pinned acceptance target is Frappe 16.51.1 + ERPNext 16.50.0, Python 3.14,
Node 24 and MariaDB, with exact source/runtime pins in
[the environment matrix](docs/ENVIRONMENT_MATRIX.md). This is a proposed test
matrix, **not observed installed compatibility**. Two disposable environments
have not been designated. Bench, Pilot, installed permissions/UI, live CRM,
worker kill/restart, two-site isolation and lifecycle tests remain blocked.

Start with [installation](docs/INSTALLATION.md), then
[configuration](docs/CONFIGURATION.md), [authorization decision](docs/decisions/authorization-and-job-execution.md),
[recovery](docs/RECOVERY.md) and [acceptance runbook](docs/ACCEPTANCE_RUNBOOK.md).
A ReadySpace-hosting account, shared publisher token and HRMS are unnecessary.

Offline tests and packaging:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]' build wheel
.venv/bin/python -m pytest -q
.venv/bin/python -m build --no-isolation --outdir /tmp/ultimatesales-package-check
.venv/bin/python tools/verify_package.py /tmp/ultimatesales-package-check
```

Use an empty output directory. Root tests use fake framework/HTTP state; they are
not installed-site or live API acceptance. CI definitions are configured; remote
runs have not occurred. The app requires its site's pinned Frappe Python runtime;
standalone testing on another Python does not establish Frappe compatibility.

GPL-3.0-only; original licence preserved. Support/security contacts, public
privacy/support policies and independent beta approval remain pending. No
Marketplace submission or production synchronization is authorized by this work.
