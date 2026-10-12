# Delivery roadmap

## 0 — Source alpha (this bundle)

Independent Frappe app; one-ID handoff; explicit existing-lead binding; quote-summary return; settings/maps/jobs; offline tests; staging and security specifications. Status: source authored; offline checks run; no live deployment.

## 1 — Prove the internal workflow

Confirm real versions and account API access. Install on an isolated ERPNext site and test CRM location. Execute the full staging acceptance matrix, including concurrency, permissions, token rotation, partial custom-field semantics and rollback. Fix defects against recorded versions. Do not replace HostBill, Xero, QuickBooks or existing payment handling.

## 2 — Controlled beta automation

Add qualified-stage discovery with pagination, durable cursors and reconciliation, or authenticated/signature-verified webhooks with replay protection plus a reconciliation pull. Build false-duplicate/link-repair tooling, a useful operator dashboard, bounded backfill and explicit field ownership. Keep one source of truth per field. Preserve drafts and human financial approvals.

Add full Frappe database integration tests and reproducible test images; implement metrics/alerts and a deliberate audit retention policy. Expand currency/multi-company routing only after defining unambiguous ownership and test cases.

## 3 — Reusable public app

Implement appropriate OAuth onboarding/token lifecycle for broad account onboarding, without assuming that Frappe Marketplace itself requires HighLevel OAuth. Retain a reviewed private-token mode for supported self-hosted use cases. Test fresh installs across explicitly supported versions and unrelated test businesses. No ReadySpace-only company names, account IDs or workflows may be required.

Document the external UltimateSales subscription, data flow, support boundaries, security reporting, maintenance policy, licence and branding. Replace placeholder support metadata with verified publisher contacts and public docs. Perform an independent security review. Publish an actual GitHub repository/releases only after owner approval.

## 4 — Marketplace submission

Recheck the current Frappe registry/publishing process. Add real app metadata and an immutable tagged/committed release with tested compatibility and ERPNext dependency. Submit for review; do not claim that approval or one-click installation is automatic.

Future financial-status integrations are separate: invoice/payment visibility can be designed after establishing the authoritative finance system and how customer/project records are linked. This alpha neither decides nor changes that accounting architecture.
