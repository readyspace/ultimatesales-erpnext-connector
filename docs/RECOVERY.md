# Recovery and replay operations

**Execution status: procedures supplied, not run on a deployed site or live CRM.** Use fabricated records and a disposable snapshot for recovery drills. The connector provides durable SQL intents and at-least-once processing; the remote API and ERP database do not share a transaction.

## Identify the state before acting

Record the site and installed app/database versions, connection, original requesting user, operation, job ID, status, attempt count, next-attempt time and sanitized error code. Keep credentials, raw API responses and customer data out of the record.

The current session must be the connection's designated restricted System User, match the job's `requested_by`, have UltimateSales Operator and current ERP permissions, and retain the connection's sole global Company User Permission. System Managers configure connections and restore authorization; they cannot execute a job by impersonating its stored requester. The app never changes the session user. The framework supplies the native actor captured at enqueue time.

There is no unattended scheduler dispatcher. A due `Queued` or `Retry` intent remains durable until its authorized operator uses **Dispatch Due Jobs**. Refresh the job after dispatch; a functioning long worker is required. Framework worker retries vary by version; if a retry re-enters under another native identity, the connector blocks it before remote access or business work. Restore a valid operator session and deliberately dispatch/retry as appropriate; do not forge queue user metadata.

| Observed state | Recovery action |
|---|---|
| Queued with no worker execution | Check committed intent, due time, Redis/long worker; dispatch as original operator |
| Retry before its due time | Wait until `next_attempt`, then operator dispatch; preserve the bounded attempt count |
| Retry due | Review transient code, restore connectivity, then operator dispatch; no scheduler promise |
| Failed | Review code and cause, repair authorization/configuration/data, then original operator explicitly retries |
| Blocked due to role/account/company revocation | Manager restores the intended restricted account and permissions; original operator explicitly retries |
| Blocked because requester differs from native actor | Re-establish the original authorized operator session; do not reassign the audit job or queue actor |
| Blocked because configuration fingerprint changed | Old request cannot be retargeted by retry; create a fresh reviewed request under current configuration |
| Succeeded or Preview | Completed intent does not re-execute; create a new deliberate request for reconciliation |

A preview request remains preview on replay. After allowing staging writes, request a separate deliberate writing job. Rotating a token does not change the routing fingerprint; changing the designated operator, company, location, pipeline/stage, currency or export-field mappings does.

## Local rollback and interrupted workers

The app resets its initial read-only discovery snapshot with a rollback, locks the connection and job rows, then keeps Processing and business/mapping writes in a single uncommitted transaction. A handled failure rolls back the business savepoint and prepares a sanitized failure/retry result. Only the native Frappe worker commits after the app returns normally; the app has no manual commit. A worker terminated before that framework commit should roll back its uncommitted transaction, leaving its earlier queued/retry intent recoverable. Never invoke `jobs.run` from an existing business-document transaction.

On the disposable site, deliberately fail after a Lead and Contact mapping insert. Verify that neither survives, the job is visible as Failed, and an explicit repaired replay creates exactly one Lead and Opportunity. The installed suite supplies this real-SQL fault-injection check.

For an actual kill drill, use a debugger breakpoint or temporary reviewed fault-injection build to pause the isolated worker after the savepoint/inserts and before final commit. Record the exact worker/horse PID and job. Terminate only that disposable process, restore worker availability, verify SQL rollback and locks released, and dispatch as the same native operator. Check counts and mappings from a fresh database connection. Repeat while two processes target the same deal. Remove the fault build afterward and record its exact diff. This procedure is not marked passed by an exception-based test.

## Remote acceptance followed by local failure

Before sending the five fields, the service recomputes the latest submitted/cancelled quotation, fetches current custom-field metadata to require opportunity TEXT fields, and reads the mapped CRM opportunity. If the owned fields already match, it skips PUT. After PUT, the client reads back the values and checks preservation of unrelated fields and protected native identity/routing data.

If a PUT succeeds remotely but its response, readback or later local completion fails, the local job can remain Queued/Retry/Failed while the remote fields are already correct. Do not automatically undo the remote values. Inspect only the expected five synthetic fields and preserved scope. Repair the cause and replay through the original operator. A current remote summary should produce Succeeded with an already-current/no-write message and no second PUT. If a newer quotation appeared meanwhile, a fresh summary can legitimately require another PUT.

The root recovery tests model accepted PUT with lost response, readback timeout, mismatched readback and local completion failure using stateful fake HTTP. The installed suite additionally performs normal quotation submission and actual SQL rollback with fake HTTP. Neither proves live API eventual consistency or absence of external workflow notifications. A replay may cause another remote side effect when remote state differs or provider behavior is non-idempotent. Keep campaign and messaging automations disabled in the synthetic location.

On the synthetic live account, record remote field values and a safe request counter before the drill. Pause the worker immediately after remote acceptance and before local completion; terminate it as above. Confirm remote values survive, local completion did not commit, then replay. Record PUT count, final job status, latest quotation selection and preservation of the unrelated sixth field/native deal fields. Use the provider's approved local logging; redact authorization headers and contact data. Mark this live drill pending until performed.

## Queue outage and retry exhaustion

An intent is inserted in the SQL transaction without a Redis call. A successful source quotation submission commits that intent along with the document. Dispatch submits only the current operator's committed due intents through native Frappe enqueue after commit. Redis failure can occur after the SQL commit; it does not erase the intent.

On the disposable bench, interrupt only its queue Redis service, request an import or normally submit a linked quotation, and prove the intended SQL job survives from a new connection. Attempt operator dispatch, restore Redis and the long worker, and dispatch again. Prove correct completion without duplicate local records. The automated suite injects submission failure and then uses a genuine RQ worker; it does not stop the Redis service itself.

Transient transport/5xx/429 failures get bounded Retry state and Retry-After spacing; attempts stop at five. Dispatch does not bypass the due time. Do not edit attempts or status in the database to hide exhaustion. A reviewed explicit retry after fixing the cause resets the attempt cycle and remains subject to current authorization and the original fingerprint. Permanent field/identity/readback errors require review rather than automatic retry.

## Configuration, disabling and credential rotation

Disable the connection and set `ultimatesales_connector_allow_writes` to `0` to pause new work. An already in-flight external request can complete. Disabling is not a remote rollback and does not delete ERP business records. Revoke the remote token if immediate further API access must stop; confirm the provider's revocation behavior.

Enter a replacement scoped location token only in the manager-only Password field. Preserve the site encryption key with backups. Test rotation with preview on a synthetic deal; confirm routing is unchanged and no credential appears in jobs/logs. An enabled operator account needs current normal Lead/Opportunity create/read, Company read and quotation read permissions. Restore only the documented restricted roles, not System Manager.

When routing/export mappings or the designated operator change, inspect every pending request. Old fingerprint-pinned jobs block and require new reviewed requests. Existing mapping routing is immutable; do not repair identity by directly updating mapping rows. Disconnect by disabling, keeping audit/mappings for recovery review. Do not uninstall simply to stop traffic.

## Backups, restore and upgrade

Before each deployment/upgrade, take the deployment's normal full database/files backup and securely preserve `site_config.json` including the encryption key. Record previous/current connector, Frappe and ERPNext commits and the MariaDB version. Test restore into an isolated site with write gates off and provider credentials revoked or replaced by synthetic credentials. Verify decryption locally, retained mappings and job configuration keys, then preview with the intended operator before any writes.

Run migrate on the disposable restored copy. Verify existing connections, immutable links, requested_by/fingerprints and pending/terminal jobs are preserved; no install/migration hook should create a business record or call the remote API. Run the installed acceptance suites on a separate clean synthetic site to avoid conflicts with restored enabled connections. Exercise a data-preserving upgrade from the previous alpha and a complete backup rollback, and record both results. A source checkout rollback by itself is not a database rollback.

Restore never undoes earlier remote writes. Compare the five CRM fields with the latest local quotation after a restore and make a fresh reviewed reconciliation request. Never restore an old job with a different requester or weaken its authorization to force completion. Keep live, kill, Redis outage, key restore and upgrade evidence pending until those drills actually pass.

Shared fixture helpers do not commit or launch processes. Concrete installed
TestCases and native command/worker boundaries own transaction completion, and
native-worker tests own process orchestration. The external acceptance runner
records strict full app commits before/after and requires identical revisions
across tested sites. Fetch unchanged security rules via tools/fetch_security_rules.py
before running the scan wrapper. Installed/live verification is still unrun.
