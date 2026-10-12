# Historical fixture findings and unresolved upstream documentation question

The eight blocking manual-commit findings recorded for candidate 0.1.0a2 were
resolved by moving transaction ownership from shared fixture helpers to native
Bench/RQ boundaries and genuine TestCase lifecycle/test methods. Shared helper
writes now remain pending and failed invocations can roll back. Process launches
were also separated into native-worker tests and the external runner. No rule was
edited, suppressed or renamed around; no reviewer waiver was requested.

The original 0.1.0a2 scan is preserved in ../evidence/security-scan-0.1.0a2.json.
The current unsuppressed result is security-scan.json. Pinned metadata/hashes
prove that all twelve rules are unchanged. Installed checks are still blocked.

An unsent upstream documentation question remains: Marketplace README calls
`frappe.set_user` blocking, while the pinned actual authorization rule is WARNING
and internal-only. Should the README or rule metadata be corrected? Production
connector code does not switch users. No issue/comment/email was sent.
