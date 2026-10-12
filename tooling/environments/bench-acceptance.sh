#!/usr/bin/env bash
# Creates two disposable sites on a NEW, already provisioned Bench host.
# No CRM credentials, external API calls, HRMS, public listener, or host setup.
set -euo pipefail
set +x

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$script_dir/versions.env"
source_dir=$(cd -- "$script_dir/../.." && pwd)
: "${US_DISPOSABLE_ENV:?Set US_DISPOSABLE_ENV=1 only on a designated isolated host}"
[[ "$US_DISPOSABLE_ENV" == 1 ]] || { echo 'Disposable environment designation required.' >&2; exit 2; }
: "${US_ACCEPTANCE_ROOT:?Set an absolute path for a NEW isolated bench}"
: "${US_APP_SHA:?Set the full reviewed commit to install on BOTH managers}"
[[ "$US_ACCEPTANCE_ROOT" == /* && ! -e "$US_ACCEPTANCE_ROOT" && ! -e "${US_ACCEPTANCE_ROOT}-sources" ]] || {
  echo 'Acceptance root must be absolute and must not already exist.' >&2; exit 2;
}
[[ "$US_APP_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo 'A full app commit is required.' >&2; exit 2; }
[[ "$(git -C "$source_dir" rev-parse HEAD)" == "$US_APP_SHA" ]] || {
  echo 'Source checkout does not match reviewed revision.' >&2; exit 2;
}
[[ -z "$(git -C "$source_dir" status --porcelain)" ]] || {
  echo 'Commit the reviewed source before a reproducible installation.' >&2; exit 2;
}
python_bin=${US_PYTHON_BIN:-python3.14}
[[ "$("$python_bin" -c 'import platform; print(platform.python_version())')" == "$PYTHON_VERSION" ]] || {
  echo 'Python does not match acceptance pin.' >&2; exit 2;
}
[[ "$(node --version)" == "v$NODE_VERSION" ]] || { echo 'Node does not match acceptance pin.' >&2; exit 2; }
[[ "$(yarn --version)" == "$YARN_VERSION" ]] || { echo 'Yarn does not match acceptance pin.' >&2; exit 2; }
[[ "$(bench --version)" == "$BENCH_VERSION" ]] || { echo 'Bench does not match acceptance pin.' >&2; exit 2; }

# Database authentication is entered locally. Empty root is allowed only for the
# ephemeral, loopback-bound CI service; never an operational database.
if [[ "${US_CI_EMPTY_DB_ROOT:-0}" != 1 ]]; then
  : "${US_DB_ROOT_PASSWORD:?Enter the isolated database root password locally}"
fi
db_password=${US_DB_ROOT_PASSWORD:-}
db_host=${US_DB_HOST:-127.0.0.1}
db_port=${US_DB_PORT:-3306}
redis_cache=${US_REDIS_CACHE:-redis://127.0.0.1:6379/0}
redis_queue=${US_REDIS_QUEUE:-redis://127.0.0.1:6379/1}

# Fetch immutable commits before Bench installs/imports any upstream code.
# These local branches are private disposable source handles, never release tags.
sources_dir="${US_ACCEPTANCE_ROOT}-sources"
mkdir -p "$sources_dir"
fetch_pinned_source() {
  local app=$1 repo=$2 revision=$3
  git init --quiet "$sources_dir/$app"
  git -C "$sources_dir/$app" remote add origin "$repo"
  git -C "$sources_dir/$app" fetch --depth=1 origin "$revision"
  git -C "$sources_dir/$app" checkout --quiet -b acceptance-source FETCH_HEAD
  [[ "$(git -C "$sources_dir/$app" rev-parse HEAD)" == "$revision" ]] || exit 3
}
fetch_pinned_source frappe https://github.com/frappe/frappe.git "$FRAPPE_SHA"
fetch_pinned_source erpnext https://github.com/frappe/erpnext.git "$ERPNEXT_SHA"
bench init "$US_ACCEPTANCE_ROOT" --frappe-path "$sources_dir/frappe" \
  --frappe-branch acceptance-source --python "$python_bin" --no-backups --skip-assets \
  --skip-redis-config-generation
cd -- "$US_ACCEPTANCE_ROOT"
[[ "$(git -C apps/frappe rev-parse HEAD)" == "$FRAPPE_SHA" ]] || exit 3
bench set-config -g redis_cache "$redis_cache"
bench set-config -g redis_queue "$redis_queue"
bench set-config -g redis_socketio "$redis_cache"
bench get-app "$sources_dir/erpnext" --branch acceptance-source --skip-assets
[[ "$(git -C apps/erpnext rev-parse HEAD)" == "$ERPNEXT_SHA" ]] || exit 3
bench get-app "$source_dir" --skip-assets
[[ "$(git -C apps/ultimatesales_connector rev-parse HEAD)" == "$US_APP_SHA" ]] || exit 3
bench build

for site in us-development.test us-acceptance.test; do
  # Random throwaway site credential; not displayed or retained in evidence.
  admin_password=$("$python_bin" -c 'import secrets; print(secrets.token_urlsafe(32))')
  bench new-site "$site" --db-type mariadb --db-host "$db_host" --db-port "$db_port" \
    --db-root-username root --db-root-password "$db_password" --admin-password "$admin_password" \
    --mariadb-user-host-login-scope='%'
  unset admin_password
  bench --site "$site" install-app erpnext
  bench --site "$site" install-app ultimatesales_connector
  bench --site "$site" set-config ultimatesales_connector_allow_writes 0
  bench --site "$site" set-config allow_tests true
  bench --site "$site" migrate
  # Establish credential-free installation/default-off smoke evidence first.
  bench --site "$site" run-tests --module ultimatesales_connector.tests.test_install_contract
  bench --site "$site" set-config ultimatesales_connector_acceptance_tests 1
  company_output=$(bench --site "$site" execute \
    ultimatesales_connector.tests.acceptance_support.bootstrap_synthetic_company)
  # Pinned v16 execute strips quotes from a returned JSON string. Also accept
  # a JSON string/object so CLI notices or a future formatting change fail safely.
  synthetic_company=$(printf '%s' "$company_output" | "$python_bin" -c '
import json, re, sys
for line in reversed(sys.stdin.read().splitlines()):
    candidate = line.strip()
    try:
        value = json.loads(candidate)
        candidate = value.get("company") if isinstance(value, dict) else value
    except ValueError:
        pass
    if isinstance(candidate, str) and re.fullmatch(r"UltimateSales Acceptance [0-9a-f]{6}", candidate):
        print(candidate)
        raise SystemExit(0)
raise SystemExit("Synthetic Company bootstrap did not produce the expected fixture.")
')
  unset company_output
  bench --site "$site" set-config ultimatesales_connector_acceptance_company "$synthetic_company"
done
unset db_password

mkdir -p acceptance-evidence
# Preserve any existing custom queues; the framework's short/default/long queues
# remain native defaults. No permanent us_acceptance worker is started here.
workers_config=$(env/bin/python - <<'PY'
import json
from pathlib import Path
config = json.loads(Path('sites/common_site_config.json').read_text())
workers = dict(config.get('workers') or {})
workers['us_acceptance'] = {'timeout': 120}
print(repr(workers))
PY
)
bench set-config -g workers "$workers_config" --parse
pause_after_tests() {
  for site in us-development.test us-acceptance.test; do
    bench --site "$site" set-config ultimatesales_connector_allow_writes 0
    bench --site "$site" set-config ultimatesales_connector_acceptance_tests 0
  done
}
trap pause_after_tests EXIT
for site in us-development.test us-acceptance.test; do
  bench --site "$site" set-config ultimatesales_connector_allow_writes 1
done
"$python_bin" "$source_dir/tools/run_acceptance.py" --bench-dir "$US_ACCEPTANCE_ROOT" \
  --site us-development.test --site us-acceptance.test --confirm-disposable \
  --parallel-sites --report "$US_ACCEPTANCE_ROOT/acceptance-evidence/synthetic-installed-results.json"
bench version > acceptance-evidence/bench-version.txt
env/bin/python -m pip freeze > acceptance-evidence/python-dependencies.txt
node --version > acceptance-evidence/node-version.txt
yarn --version > acceptance-evidence/yarn-version.txt
for app in frappe erpnext ultimatesales_connector; do
  git -C "apps/$app" rev-parse HEAD > "acceptance-evidence/$app-commit.txt"
done
for site in us-development.test us-acceptance.test; do
  bench --site "$site" list-apps > "acceptance-evidence/$site-apps.txt"
done
echo 'Two isolated installed-site suites completed with synthetic transport. No live CRM workflow was tested.'
