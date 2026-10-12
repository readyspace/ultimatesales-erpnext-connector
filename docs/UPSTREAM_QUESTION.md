# Prepared authorization question — not posted

Pinned Framework: Frappe 16.51.1 commit
2871914b69b6e14a4b023d9b7cc52dc3e269cc1b.

A request creates a durable SQL intent under a restricted operator. Native
frappe.enqueue captures the authenticated requester; a scheduler later sees the
intent under its framework identity. Passing user= to public enqueue forwards a
method kwarg and does not override the captured actor. Our app does not use
set_user, forge sessions, mutate queue internals or bypass business permissions.
We therefore require authenticated operator dispatch after queue outage/retry.

Is there a supported public mechanism for durable re-dispatch under the original
restricted requester without app-side user switching? Please also confirm whether
execute_job's database deadlock/timeout recursion intentionally omits the captured
user argument; our worker denies a retry if the current identity differs.

Minimal synthetic reproduction:
1. Enqueue a no-op probe as an enabled restricted test operator; inspect the native
   worker user and site (no credentials or business payloads).
2. Persist an intent and re-dispatch the probe from the scheduler; observe that the
   native worker actor is the scheduler's captured actor, not the stored requester.
3. On a disposable site, trigger the framework DB retry path and inspect actor
   continuity. Do not claim this step executed in the current session.

Marketplace README and its immutable actual rules disagree about set_user's
severity; API_CONTRACT.md/ENVIRONMENT_MATRIX.md record the exact validator source.
We removed app switching regardless. No public maintainer message was sent.

The former fixture commit findings have been resolved locally by explicit native
and TestCase transaction ownership, with unchanged rules. Shared helpers now
leave writes pending, rather than committing a caller's transaction. No upstream
reviewer waiver or public message was requested.
