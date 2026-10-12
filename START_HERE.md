# UltimateSales.ai Connector for ERPNext
## First internal-pilot alpha — 12 October 2026

**Deliverable:** source code, configuration screens, offline tests, staging instructions and release checklist.
**Not delivered:** a deployment, a live API connection, a created GitHub repository, or an approved Marketplace listing.

### The first workflow

A selected OPEN opportunity in the configured UltimateSales qualified stage is previewed, then deliberately imported into ERPNext. The app creates or explicitly reuses a Lead and creates a linked Opportunity. Your team prepares the quotation in ERPNext. When enabled, submission/cancellation of a linked quotation queues its latest summary for return to that CRM opportunity.

This alpha intentionally starts with **one opportunity ID at a time**. Automatic stage discovery, webhooks and bulk import are later milestones. The background scheduler processes requested work; it does not discover sales opportunities.

### What to do with this package

1. Give the full source directory to the developer responsible for the pilot. Start with `README.md`, `docs/INSTALLATION.md`, and `docs/STAGING_ACCEPTANCE.md`.
2. Verify the actual ERPNext/Frappe versions and prepare an isolated ERPNext staging site. This alpha targets matching version 16 apps on MariaDB. Version 15 and PostgreSQL are not covered.
3. Use a synthetic-data UltimateSales location or isolated test opportunity with outbound campaigns and automations disabled. Never enter production tokens into chat or Git.
4. Run the preview, one actual staging handoff, one quotation return, and the failure/replay tests. Only then make a production rollout decision.

### Decisions already reflected in the code

- Separate Frappe app; no ERPNext/Frappe core edits; no Frappe HR dependency.
- Technical app name: `ultimatesales_connector`.
- Suggested future repository name: `readyspace/ultimatesales-erpnext-connector`. This repository has NOT been created.
- Current source version: `0.1.0a1` (human-facing label `v0.1.0-alpha.1`).
- GPL-3.0-only source licence, subject to publisher review before public release.
- One location maps to one ERPNext company. Start the pilot with one connection.
- No HostBill, Xero, QuickBooks or n8n changes or dependencies.
- No invoice, payment, sales-order or customer-master creation. No marketing messages or consent changes.

### Inputs the deployment owner must supply locally

Actual staging site and versions; ERPNext Company; a restricted integration user; UltimateSales location, pipeline and qualified-stage IDs; the CRM location currency; and a sub-account private-integration token. The quotation return path additionally needs five opportunity TEXT custom-field IDs.

These are deployment configuration values, not assumptions embedded in the source. Token entry belongs in the Frappe Password field.

### Evidence

`docs/VALIDATION_REPORT.md` distinguishes checks run in this workspace from live/staging tests still outstanding. `AGENTS.md` is a development handoff for an engineer or coding agent. Do not describe this alpha as production-ready or Marketplace-approved.
