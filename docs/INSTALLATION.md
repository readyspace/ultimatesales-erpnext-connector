# Reproducible isolated source installation

Candidate 0.1.0a3 is clean-install-only. These instructions have not been rehearsed
on an installed site in this session. Do not apply them to an operational ERPNext
or HR site. Historical alpha installation instructions are superseded by this
file; docs/VALIDATION_REPORT.md remains unchanged historical evidence.

## Baseline and target

Use the exact full candidate commit recorded in HANDOFF_STATE.md and the delivery
manifest. Keep the same commit for conventional Bench and the separate Pilot
installation. A 404 when inspecting the intended GitHub repository does not prove
it is absent; this follow-up authorizes a clean public source repository at
`https://github.com/readyspace/ultimatesales-erpnext-connector`. Confirm the exact
commit recorded in the delivery manifest. Earlier local reference-bearing history
is preserved privately and is not pushed.

Review ENVIRONMENT_MATRIX.md, tooling/environments/versions.env and its README.
The selected pins are Frappe 16.51.1, ERPNext 16.50.0, Bench 5.31.0,
Python 3.14.0, Node 24.12.0, Yarn 1.22.22, MariaDB 11.8.3 and Redis 7.2.6.
Immutable app/dependency revisions and container digests are recorded there.
These pins are reproducibility choices, not an installation support certification.
Use no HRMS. Runtime/dependency updates require a newly recorded acceptance run.

Before installation, inventory the actual isolated resource with `bench version`,
`bench --site ACTUAL_SITE list-apps`, and `./env/bin/python --version`. The
connector's preflight rejects missing ERPNext, another app major, non-MariaDB and
an incompatible Python runtime, before activation. Preserve a coherent backup of
site database, files, app revisions and encryption key through the deployment
owner's secure procedure. Keep keys and backups out of shared evidence.

## Conventional Bench

On a newly provisioned, explicitly designated disposable host, install the pinned
Python, Node, Yarn, Bench, MariaDB and Redis through the host owner's normal
procedure. No host provisioning or paid infrastructure is performed by the app.
Review the environment script before running it. It refuses an existing Bench
root, checks exact source/runtime pins and creates separate development and clean
acceptance sites without a CRM credential. Required values are documented in
`tooling/environments/README.md`; enter any isolated database credential locally,
never into chat. Run:

```sh
US_DISPOSABLE_ENV=1 US_ACCEPTANCE_ROOT=/absolute/new/isolated-bench \
US_APP_SHA=FULL_REVIEWED_CANDIDATE_COMMIT bash tooling/environments/bench-acceptance.sh
```

Replace the placeholder with the real full commit. This is a runnable recipe,
not an observed successful installation. The script's evidence must be examined
for nonzero exits and skipped tests. Installed tests use synthetic HTTP, never a
live CRM account. Live API acceptance is a separate gate.

For a separately prepared clean Bench with the exact pinned stack, use the normal
source route reviewed in pinned Bench code:

```sh
bench get-app /absolute/path/to/reviewed/ultimatesales_connector
bench --site YOUR-DISPOSABLE-SITE install-app ultimatesales_connector
bench --site YOUR-DISPOSABLE-SITE set-config ultimatesales_connector_allow_writes 0
bench --site YOUR-DISPOSABLE-SITE migrate
bench build --app ultimatesales_connector
bench --site YOUR-DISPOSABLE-SITE run-tests --module ultimatesales_connector.tests.test_install_contract
```

Confirm `apps/ultimatesales_connector` is at the reviewed commit, ERPNext is
installed and HRMS absent. Neither a wheel build nor this unexecuted command list
is installation evidence. Open UltimateSales Connector in Desk without a token;
validate default-off settings and role visibility. Follow CONFIGURATION.md using
supported forms/CLI, with no Python or SQL edits. Installed negative/recovery
suites need the disposable opt-in, synthetic Company, write gate and dedicated
queue described in ACCEPTANCE_RUNBOOK.md. Do not silently count skipped tests.

## Separate Pilot-managed acceptance

Pilot's pinned experimental source and supported Git source-install route are
recorded in tooling/environments/README.md and ENVIRONMENT_MATRIX.md. Use a
separate designated host/site, pin Pilot to the recorded revision and follow its
current CLI help. Download/install the same exact connector commit using the
Git route; install ERPNext on the site first. Marketplace publication is not
required. A private local/reachable source repository must be supplied through
normal secure access, without making the repository public. Verify the checked-out
commit rather than trusting a moving branch.

Record Pilot revision, Python/Node/Bench/database/Redis versions, app commits,
install/migrate/build exits, default-off tokenless UI and the synthetic round trip.
Run the same installed-site modules and A01–A19 matrix. A Bench result does not
prove Pilot. No Pilot host or source repository access is currently designated.
Docker/custom-image, PostgreSQL and v15 support remain unqualified.

## Credentials, stopping and lifecycle

Installation has no CRM I/O. A manager may save an incomplete disabled connection.
Once configured, operators use scoped server-side reads without seeing the token.
Pause by disabling the connection and setting the site write gate to 0; revoke
the provider token if external access must stop. Already transmitted requests may
complete. Changed routing/operator/fields block old intents; do not retarget them.

Do not upgrade an installed alpha with this candidate. Alpha upgrade, uninstall
and full restore behavior have not been tested. Test them on disposable sites
only before claiming lifecycle support. The candidate does not deliberately
remove ERP Leads/Opportunities/Quotations or undo CRM writes. Framework uninstall
can remove connector metadata and audit/link tables, so inspect a secured backup
and verify the actual process before using it. Follow RECOVERY.md. Restoring old
source alone cannot reverse schema changes or remote writes. No release tag,
production install or Marketplace submission is part of this
assignment. The follow-up explicitly authorizes public source publication only.
