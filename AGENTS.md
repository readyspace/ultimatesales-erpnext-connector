# Engineering handoff

Read README, SECURITY, docs/ARCHITECTURE, docs/INSTALLATION and docs/VALIDATION_REPORT first.

This is an internal-pilot alpha for a future public community app, NOT a completed deployment. User-approved direction: reliable UltimateSales.ai–ERPNext sales-to-finance connector, prove internally, then generalize; do not recreate a whole CRM inside ERPNext.

Maintain these invariants:

- Keep technical app name `ultimatesales_connector`; no core ERPNext/Frappe edits.
- No Customer/invoice/payment/order posting or accounting-system replacement in this milestone.
- HighLevel transport is separate from framework-independent rules and Frappe persistence.
- Scope every operation to the explicit location, pipeline, company and stable external identity.
- Normal ERP record permissions execute as a restricted user. Only internal mapping/audit records bypass permissions.
- Do not auto-merge by email or overwrite ERP-owned business fields on replay.
- Return quotation information per CRM opportunity, never per contact; Submitted is not Sent or Paid.
- Preserve site write gates, preview semantics, fixed API host, no guest endpoints, redacted logs and bounded retries.
- Never invoke jobs.run from another database transaction. It resets its initial read-only snapshot with rollback and relies on the native Frappe worker for final commit.
- Do not claim database/live API correctness based on mocks. Complete staging acceptance on recorded versions.
- Do not paste tokens into source, issues, this document, tests or prompts. Enter them only in the approved secret store/UI.

First engineering task: verify the actual target stack, execute clean installation and the installed-site smoke tests, then prove one synthetic opportunity and quotation round trip. Version 16 is a target, not an observed ReadySpace environment. Do not assume the existing HR site also has ERPNext installed.

Root pytest tests are offline. The separate installed-site module uses Frappe and must not be counted as executed until run on an isolated site. Add real transaction/permission/upgrade tests before widening scope or removing alpha status.

Repository identity: `readyspace/ultimatesales-erpnext-connector`. The owner has
explicitly authorized public source publication in this follow-up. Preserve the
private alpha-derived implementation history locally; publish only the clean
app source and pinned reference metadata, without downloaded third-party code.
Source publication is separate from beta, release, production and Marketplace
approval. Read current test evidence/handoff before claiming any validation.
