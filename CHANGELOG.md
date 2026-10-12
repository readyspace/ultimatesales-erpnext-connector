# Changelog

## 0.1.0a3 — fixture security repair and public source, 12 October 2026

- Shared acceptance helpers no longer commit; native Bench/RQ boundaries and
  genuine installed TestCases own fixture and completion transactions explicitly.
- Shared fixture helpers no longer launch processes. Native-worker tests own
  their worker processes, and the external runner records exact source revisions.
- Fetch and verify all twelve unchanged pinned Marketplace rules using immutable
  URLs/hashes in an ignored local cache; no rule changes or suppressions.
- Exclude downloaded third-party reference copies from distributed source and
  public Git history. Preserve the earlier local implementation history privately.
- Public source publication is authorized by the owner. This remains an alpha
  implementation candidate, with installed/live/beta/Marketplace gates pending.

## 0.1.0a2 — Step 1–4 implementation candidate, 12 October 2026

- Preserve verified 0.1.0a1 provenance; introduce native-requester authorization,
  explicit operator dispatch and current role/company/record revalidation.
- Add scoped operator/auditor roles, manager-only secret fields, immutable internal
  records, workspace/setup diagnostics, GET-only connection tests and clear actions.
- Verify latest quotation identity/currency/access and unowned remote fields;
  add stateful remote-success/local-failure recovery and negative authorization tests.
- Add source/package checks, pinned Bench/Pilot acceptance definitions, installed
  SQL/permission/native-worker harness, CI definitions and truthful blocked evidence.
- Clean-install-only. No installed compatibility, live CRM, public beta,
  production readiness, independent approval or Marketplace claim.

## 0.1.0a1 — supplied internal-pilot alpha

Original separate-app sales-to-quotation handoff with offline/mocked validation.
Original historical report is preserved unchanged in docs/VALIDATION_REPORT.md.
