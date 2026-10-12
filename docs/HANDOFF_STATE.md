# Resumable candidate 0.1.0a3 handoff

The fixture security repair is complete locally: **264 offline tests PASS**;
unchanged pinned Marketplace Semgrep scan **PASS**, **0 blocking**, 43 advisory
findings, 29 scanned files, no errors or missing installed targets. Remote offline
and security CI also passed for published source a0b2809; exact IDs/SHA are in
PUBLICATION.md and evidence/public-source-ci.json. Historical
0.1.0a2 failure is retained separately; it is no longer the current verdict.

Shared helpers neither commit nor spawn processes. Native Bench execute owns
successful Company bootstrap commits; native RQ owns worker completion. Concrete
installed TestCases explicitly own fixture setup, intent visibility, synchronous
completion and cleanup. Native-worker tests use fixed argument lists, shell=False
and bounded process timeouts. The external CLI runner validates full source SHAs
before/after and requires matching revisions across sites. Offline models prove
this control flow; **26 installed checks remain unrun**.

Public source destination: https://github.com/readyspace/ultimatesales-erpnext-connector.
Public source was created in GitHub Desktop and pushed to the verified public
ReadySpace remote on main. First source commit: `a0b280917a6199b053183b9d18531ebe53bfbce5`.
PUBLICATION.md and the delivery manifest record actual status and final commits. The older alpha-derived Git history stays local and is not pushed.
The clean public history excludes downloaded third-party reference copies;
immutable URLs/hashes and tools/fetch_security_rules.py reproduce the exact
unchanged rules in ignored .reference-source. No release tag, Marketplace approval,
production deployment or independent beta sign-off is authorized by source publication.

Original alpha source ZIP SHA-256:
11a57c4f0f53e2145ad4e345c7f19d92b36e4e60cfc3a50a6a1d60be90b93158.
Original local baseline b9d7d17, implementation 1b524b45c81100fed14b69c655e224ee24b607c9,
and 0.1.0a2 report 0046ab22a9b24d8c4d05ee99ce8ee90067997643 are provenance,
not commits to install from the clean public history. Use the exact final public
commit recorded in the delivery manifest for BOTH Bench and Pilot.

Read STEP_1_TO_4_REPORT.md, TEST_EVIDENCE.md, ENVIRONMENT_MATRIX.md, the authorization
decision, INSTALLATION.md, CONFIGURATION.md and ACCEPTANCE_RUNBOOK.md. No disposable
site or synthetic CRM location has been designated. Provision the pinned isolated
Bench and separate Pilot sites via the deployment owner's normal secure process,
never the operational ERP/HR site. Disable customer-facing/chargeable automations
in the synthetic CRM location; enter the scoped token locally, never in chat.

Run credential-free/default-off install smoke first, then explicitly opted-in
SQL/permission/native-worker tests with skip detection. Execute A01–A19 real-site
and live cases, two-site isolation, worker kill/Redis restart, remote-success/local
failure, unrelated-field preservation and lifecycle. Independent A20 remains NOT RUN.
Restore write/acceptance gates to off after tests. Alpha upgrade is unclaimed.

Operator policy remains one restricted enabled System User with UltimateSales
Operator, exactly one global Company User Permission and normal ERP permissions.
That operator explicitly dispatches their own due intents. No production app
user switching or queue user override exists. Pinned Framework DB retry can lose
actor identity; the app denies mismatches. Never call jobs.run from a business
transaction. Production commits remain owned by the native Framework worker.

Follow RECOVERY.md. Old jobs cannot be retargeted after routing/operator/field
changes. Keep quotation export off until a real synthetic account proves narrow
updates preserve unrelated/native fields. Source availability and a green static
scan do not establish installed/live compatibility. Independent security/beta,
support/security contacts and public policy approval remain later prerequisites.
