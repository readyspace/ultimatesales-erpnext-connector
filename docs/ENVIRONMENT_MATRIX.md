# Environment and compatibility evidence

Evidence date: **12 October 2026, Asia/Singapore**. Latest means observed from
official upstream on this date, not ReadySpace deployment state. No operational
ERPNext/HR/CRM site was accessed or changed. The user has not designated a test
environment. All Frappe-site, Pilot and live CRM gates remain **BLOCKED**.

| Environment | Observed / proposed exact stack | Status | Evidence / missing prerequisite |
|---|---|---|---|
| Local offline source checks | macOS 26.6.2; Python 3.12.14; Node 22.23.1; pytest 9.1.1; requests 2.34.2 | PASS for recorded offline suite only | Baseline at `b9d7d17`; see `TEST_EVIDENCE.md` for candidate runs. No Frappe, database, worker or CRM proof. |
| Conventional isolated Bench | Frappe 16.51.1; ERPNext 16.50.0; Bench 5.31.0; Python 3.14.0; Node 24.12.0; Yarn 1.22.22; pip 25.3; MariaDB 11.8.3; Redis 7.2.6 | BLOCKED | No designated disposable host/database/Redis; host has no container runtime. Two-site executable source recipe and CI definition prepared. |
| Clean second site | Same full candidate app SHA and stack as the conventional Bench | BLOCKED | Documentation-only rehearsal requires the designated host and second new site. No independent tester sign-off claimed. |
| Separate Pilot-managed site | Pilot source `e5f590d1eb3b69541249ccc6db5fc6c1c625e60f`; same app/Frappe/ERPNext/runtime pins | BLOCKED | No designated separate Pilot host/site; source repository publication is authorized separately; the Pilot host is absent. Pilot has no observed latest release endpoint. |
| Live synthetic CRM location | HighLevel current named API `Version: v3`; location-scoped Private Integration | BLOCKED | No designated synthetic UltimateSales location or approved secure credential entry; customer/chargeable automations must be disabled first. No account API request made. |
| Remote CI | Offline suite and unchanged-rule security scan on published source `a0b2809` | **PASS** | Both actual workflows completed/success; exact run URLs and SHA in PUBLICATION.md. Installed definition remains undispatched. |

## Immutable upstream source baseline

| Component | Verified release / revision | Requirement verified from exact source |
|---|---|---|
| Frappe | [`v16.51.1`](https://github.com/frappe/frappe/releases/tag/v16.51.1), `2871914b69b6e14a4b023d9b7cc52dc3e269cc1b` | `pyproject.toml`: Python `>=3.14,<3.15`; `package.json`: Node `>=24` |
| ERPNext | [`v16.50.0`](https://github.com/frappe/erpnext/releases/tag/v16.50.0), `7474d9e786277383de1242ab882f16856d17a9c9` | Python `>=3.14`; Frappe dependency `>=16.50.0,<17.0.0`; no HRMS dependency |
| Bench | [`v5.31.0`](https://github.com/frappe/bench/releases/tag/v5.31.0), `f21f11793872705560e710b2bda69934c9c34011` | Source supports local Git `get-app`; selected version, not installed-site evidence |
| Pilot | [`e5f590d1eb3b69541249ccc6db5fc6c1c625e60f`](https://github.com/frappe/pilot/commit/e5f590d1eb3b69541249ccc6db5fc6c1c625e60f) | CLI Python `>=3.11`; source `get-app REPO --branch REF` supports a full commit SHA; Frappe runtime still governs the bench |
| Current Marketplace registry validator | [`cb1a58adfacbe9d8e0e4a4d5c7d1ef7786a05e6a`](https://github.com/frappe/marketplace/commit/cb1a58adfacbe9d8e0e4a4d5c7d1ef7786a05e6a) | Semgrep findings block on explicit `is_blocking` or Critical/Major severity; exact rule manifest retained; unchanged rules fetched into ignored local cache |
| Press historical/current Cloud comparator | [`a67a08425797e8910a2a60b10ca053c62192ac4d`](https://github.com/frappe/press/commit/a67a08425797e8910a2a60b10ca053c62192ac4d) | Separate Cloud audit source; not substituted for current Marketplace registry validation |

ERPNext's GitHub `/releases/latest` returned version **15.122.0** during this
verification. Version **16.50.0** was selected from the release list filtered for
stable major 16, then resolved to the exact tag commit. A moving `version-16`
branch and a global latest endpoint are not an immutable acceptance baseline.

The [official version-16 installation table](https://docs.frappe.io/framework/user/en/installation)
requires MariaDB 11.8, Python 3.14, Node 24, Redis/Valkey 6+, Yarn 1.22+ and pip
25.3+. Selected Python/Node/database patch pins are verified artifact choices for
reproduction; they do not assert the latest patch or production recommendation.
The version requirements and exact source agreement justify a candidate test
stack, **not a tested support certification**.

`tooling/environments/versions.env` and `upstream/container-pins.json` retain exact
runtime/image pins. MariaDB and Redis image indexes are pinned by SHA-256 from
the anonymous official registry. Neither container was executed here. OS system
packages, resolved Python/JS dependency graphs and host manager behavior must be
captured from the actual acceptance run before claiming a reproducible host
image. No v15, PostgreSQL, custom application Docker image or alpha upgrade
support is certified. The candidate is **clean-install-only pending site tests**.

## Worker identity and security-source findings

The exact Frappe worker source captures `frappe.session.user` when enqueuing and
restores it on initial asynchronous execution. Its database-error recursive
retry omits `user`. The connector must revalidate the current authenticated
execution identity instead of trusting a persisted requester or inventing a
queue identity override. See the authorization decision for the candidate's
restricted operator design and the installed-site gate.

At the pinned Marketplace revision, the `frappe-setuser` rule is WARNING,
internal-only and excludes test modules. The registry README describes it as
blocking, but actual rule metadata and actual validator logic make it advisory
unless another rule produces a blocking finding. This documented inconsistency
is not permission to disguise user switching or skip a security review. No
Marketplace submission, reviewer approval or get-app validator success is
claimed. `upstream/security-scan.json` records the actual local scanner result:
**PASS**, 29 scanned files, 43 advisory findings, **0 blocking findings**,
0 scanner errors and all explicit installed targets present. All twelve rule
hashes match the immutable manifest. No rule/finding was suppressed. Shared
helpers no longer commit or launch processes; native commands/workers, genuine
TestCases and the external CLI own those boundaries. Historical FAIL evidence is
preserved separately. Static scan success is not installed security or beta approval.
