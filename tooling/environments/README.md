# Isolated acceptance definitions

Status on 12 October 2026: configured, **NOT RUN**. This host has no designated
Frappe/MariaDB/Redis/Pilot test environment and no container runtime. These assets
do not claim a successful source installation, lifecycle rehearsal or live CRM
round trip.

`versions.env` fixes the selected source revisions and runtimes. Upstream requires
Python `>=3.14,<3.15`, Node `>=24`, MariaDB 11.8, Redis/Valkey 6+, Yarn 1.22+ and
pip 25.3+. Selected patch pins are reproducibility choices, not claims that these
are the newest Python/Node/database releases. Frappe and ERPNext are the latest
observed stable version-16 releases on the evidence date. Ubuntu 24.04 CI runner
and system packages remain moving infrastructure; capture resolved package
versions and freeze output before accepting a run as a repeatable host image.

## Conventional Bench

On an explicitly designated, disposable Linux host, provision the fixed runtimes
and isolated MariaDB/Redis services first. Configure MariaDB for utf8mb4 and
utf8mb4_unicode_ci, and install development headers, Git, pkg-config and Yarn.
Install the pinned Bench source in a separate tool virtualenv:

```sh
python3.14 -m venv /absolute/disposable/tools/bench-cli
/absolute/disposable/tools/bench-cli/bin/python -m pip install pip==25.3
/absolute/disposable/tools/bench-cli/bin/python -m pip install 'git+https://github.com/frappe/bench.git@f21f11793872705560e710b2bda69934c9c34011'
```

Put that virtualenv's `bin` on PATH. Check out and commit the candidate. Use the
same full candidate SHA for this test and Pilot. `bench-acceptance.sh` refuses an
existing destination and an uncommitted source checkout. It installs ERPNext and
the connector on two new sites and runs credential-free/default-off smoke tests.
It fetches Frappe/ERPNext by full commit SHA into a new disposable sibling source
directory before Bench imports/builds them; moving upstream tags are not used
for installation. Leave that source directory with the bench for provenance.
It then explicitly opts both disposable sites into acceptance, bootstraps one
synthetic Company per site, configures the dedicated `us_acceptance` queue and
runs real SQL/permission/native worker suites with synthetic HTTP transport.
The runner rejects skipped/zero-test runs. The write gate and acceptance opt-in
are turned off on exit. No live CRM request or live credential is used.

```sh
export US_DISPOSABLE_ENV=1
export US_ACCEPTANCE_ROOT=/absolute/disposable/ultimatesales-bench
export US_APP_SHA=FULL_REVIEWED_COMMIT
read -r -s -p 'Isolated database root password: ' US_DB_ROOT_PASSWORD
export US_DB_ROOT_PASSWORD
bash tooling/environments/bench-acceptance.sh
unset US_DB_ROOT_PASSWORD
```

Optional non-secret service settings: `US_DB_HOST`, `US_DB_PORT`,
`US_REDIS_CACHE`, `US_REDIS_QUEUE`, `US_PYTHON_BIN`. The write gate remains off.
No service is started or exposed publicly by this script. Installed-site tests
may create and clean synthetic records; use only disposable sites. Review test
output before sharing. Never attach site configuration, databases, secrets or
encryption keys. The recorded pip freeze is ordinary public package provenance;
inspect it for credential-bearing direct URLs before distributing it.

## Separate Pilot-managed source installation

Pilot has no observed GitHub release at `/releases/latest`. Use the verified
source revision `e5f590d1eb3b69541249ccc6db5fc6c1c625e60f`; do not claim a stable
release label. Do not install Pilot or run its system setup against an operational
host. An infrastructure owner must designate/provision a separate disposable
Pilot host and bench with the same Frappe/ERPNext/runtime pins.

At that revision, `pilot -b BENCH get-app REPO --branch REF` is the supported Git
route. The source accepts a **full commit SHA** in `--branch` and performs a
staged clone, real app validation, promotion, environment installation and asset
build. Site installation is a separate command. Marketplace listing is not a
prerequisite. A source repository URL must be credential-free; private repository
access uses the host's approved secure Git credential setup.

```sh
pilot -b DESIGNATED_TEST_BENCH get-app https://github.com/frappe/erpnext.git --branch 7474d9e786277383de1242ab882f16856d17a9c9
pilot -b DESIGNATED_TEST_BENCH get-app APPROVED_READABLE_CANDIDATE_GIT_URL --branch FULL_REVIEWED_COMMIT
pilot -b DESIGNATED_TEST_BENCH install-app DESIGNATED_TEST_SITE erpnext ultimatesales_connector
pilot -b DESIGNATED_TEST_BENCH frappe --site DESIGNATED_TEST_SITE set-config ultimatesales_connector_allow_writes 0
pilot -b DESIGNATED_TEST_BENCH frappe --site DESIGNATED_TEST_SITE set-config allow_tests true
pilot -b DESIGNATED_TEST_BENCH frappe --site DESIGNATED_TEST_SITE migrate
pilot -b DESIGNATED_TEST_BENCH frappe --site DESIGNATED_TEST_SITE run-tests --module ultimatesales_connector.tests.test_install_contract
```

Confirm the pinned CLI's `--help` before executing; archive sanitized app commit,
site app list, Pilot revision and run output. Do not count a Bench run as Pilot
evidence. The above Pilot commands run the default-off smoke module only. For
the destructive synthetic acceptance suite, persist the disposable opt-in,
synthetic Company setting, write gate and custom queue as described in the
installed acceptance runbook, then use `tools/run_acceptance.py --single-site`
with that bench/site. Restore the gates to off afterward. Conventional Bench
plus two sites also does not substitute for the
separate Pilot site, real worker/concurrency/fault tests, lifecycle tests, live
CRM account tests or independent tester approval. If Git access is unavailable,
mark the Pilot install BLOCKED. Public source publication is authorized separately
by the owner; it does not authorize a Pilot deployment.

The GitHub installed-site workflow is a separate, secret-free Bench test
definition. It is not a Pilot workflow and has not run remotely in this task.
