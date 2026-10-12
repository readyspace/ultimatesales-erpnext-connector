# Verified public API contract and live acceptance gate

Checked on 12 October 2026. This is public-document/source evidence. **No live
account request or quotation return was executed.** UltimateSales is used as a
HighLevel white-label; provider documentation does not prove the target
white-label account's entitlement, token scopes or actual response behavior.

## Host, authentication and version

Only `https://services.leadconnectorhq.com` is allowed. TLS verification,
non-followed redirects, bounded timeouts and redacted errors remain required.
Use a location/sub-account Private Integration token entered locally in the
Frappe Password field. Do not use a legacy API v1 key or general agency token.

The current [versioning documentation](https://marketplace.gohighlevel.com/docs/Versioning/index.html)
lists named `v3`, released 11 June 2026, with no announced retirement date. Each
used endpoint requires the explicit `Version: v3` header. Date headers still
exist for older APIs; their existence does not require this connector to replace
the verified v3 header. Endpoint headers and scopes must still pass the
designated account test before activation.

| Operation | Route | Minimum scope | Shape / isolation |
|---|---|---|---|
| [Get Contact](https://marketplace.gohighlevel.com/docs/ghl/contacts/get-contact/index.html) | `GET /contacts/{id}` | `contacts.readonly` | Wrapped `contact`; require contact ID and `locationId` to match the opportunity and configured location. |
| [Get Opportunity](https://marketplace.gohighlevel.com/docs/ghl/opportunities/get-opportunity/index.html) | `GET /opportunities/{id}` | `opportunities.readonly` | Wrapped `opportunity`; require stable contact, opportunity, location and pipeline identity before business writes. Initial import also requires qualified stage and OPEN status. |
| [List Pipelines](https://marketplace.gohighlevel.com/docs/ghl/opportunities/get-pipelines/index.html) | `GET /opportunities/pipelines?locationId={id}` | `opportunities.readonly` | Wrapped `pipelines` array for explicit location. No automatic opportunity discovery. |
| [Get Pipeline](https://marketplace.gohighlevel.com/docs/ghl/opportunities/get-pipeline/) | `GET /opportunities/pipelines/{id}` | `pipelines.readonly` | Unwrapped pipeline with `locationId` and `stages`; validate configured pipeline and stage. This additional scope is needed only if using this single-pipeline endpoint. |
| [Get Custom Fields](https://marketplace.gohighlevel.com/docs/ghl/locations/get-custom-fields/index.html) | `GET /locations/{id}/customFields?model=opportunity` | `locations/customFields.readonly` | Wrapped `customFields` array. Require five distinct configured IDs with matching location, `model=opportunity`, and `dataType=TEXT`. |
| [Update Opportunity](https://marketplace.gohighlevel.com/docs/ghl/opportunities/update-opportunity/index.html) | `PUT /opportunities/{id}` | `opportunities.write` | Body contains only `customFields: [{id, fieldValue}]` for five owned text fields. Readback must confirm the same opportunity and values. |

The [official scopes table](https://marketplace.gohighlevel.com/docs/Authorization/Scopes/index.html)
maps these reads/writes to sub-account access. It lists pipeline collection reads
under `opportunities.readonly`; single-pipeline docs independently specify
`pipelines.readonly`. Request only the scopes for endpoints actually enabled.
No `contacts.write`, custom-field schema writes, agency account administration,
messaging, campaigns, webhook or finance scope is needed. A provider-issued
write scope can authorize more provider operations than this app uses; the app
must enforce its narrower request allowlist.

## Ownership and partial-update limitation

The five connector-owned values are ERP opportunity reference, quotation
reference, Submitted/Cancelled document state, currency and grand total. They
belong to the **same CRM opportunity**, never its shared contact. Do not send
pipeline, name, stage, status, contact, value, tags or other business fields.

Public Update Opportunity documentation describes `customFields` updates but
does **not** explicitly guarantee preservation of omitted custom-field entries,
atomic conditional writes or idempotency keys. This is an unverified account
contract. A successful mocked PUT and a readback of owned fields cannot prove
unrelated-field preservation. Do not replace a narrow write with an entire
read-modify-write field array: that may overwrite concurrent human changes.

Keep quotation export disabled until the owner records a successful test on a
designated synthetic location, with all customer-facing/chargeable automations
disabled. Use two opportunities sharing a synthetic contact, five owned text
fields and one unrelated sentinel field. Capture sanitized PASS/FAIL evidence
for these account checks:

1. Minimal read token succeeds only for the designated location. A valid
   foreign-location opportunity/contact is rejected locally before a write.
2. Pipeline/stage and opportunity-level field metadata validate under ordinary
   sub-account access. Wrong model/type, duplicate IDs and wrong scope fail.
3. A five-field-only PUT changes the selected opportunity; the unrelated
   sentinel, core opportunity fields, sibling opportunity and shared contact
   remain unchanged. Read back both owned values and unrelated sentinels.
4. Missing/expired token and denied write scope fail with a sanitized result.
   Verify 429, timeout and server-error recovery without unbounded retries.
5. After a remote success followed by local failure, retry first reads current
   CRM values and converges without falsely claiming cross-system rollback or
   exactly-once provider/workflow effects.

Record only test IDs/field hashes or synthetic aliases, result codes, version
headers, enabled scope names, timestamp and revision. Never retain tokens, raw
customer/API responses, encryption keys or request headers with authorization.
No live account exists in this task's approved inventory, so these checks are
**BLOCKED**, and the complete round trip remains unproven.
