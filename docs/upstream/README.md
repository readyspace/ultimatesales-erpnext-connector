# Official upstream evidence and unchanged security rules

The original verification was performed on 12 October 2026 against official
public sources. No operational account or installed CRM/Frappe site was used.
`source-verification.json` records immutable source URLs, revisions and original
SHA-256 download hashes. Downloaded third-party source is kept only in the ignored
local `.reference-source/` cache and is not distributed in the app archive or the
clean public Git history. Earlier local history is preserved privately.

`security-rules-manifest.json` pins all twelve original rule URLs/paths/hashes at
Marketplace commit `cb1a58adfacbe9d8e0e4a4d5c7d1ef7786a05e6a`. Fetching verifies
TLS, the fixed host/revision, every hash, the complete rule set, and safe cache
paths. No source is executed by the fetcher. The downloaded rules are unchanged;
there are no new ignores, rule edits or `nosemgrep` suppressions.

Reproduce the scan after installing Semgrep 1.156.0 in an isolated tool environment:

```sh
python tools/fetch_security_rules.py
python tooling/environments/scan-security.py --semgrep /absolute/tool-venv/bin/semgrep
```

The wrapper verifies the rule manifest before scanning and explicitly includes
every installed test helper/module. It fails on missing targets, zero-file scans,
changed source during the scan, parser/runtime errors or blocking findings.
`security-scan.json` records the actual final result, file/rule hashes and remaining
advisories. Historical candidate 0.1.0a2 failure evidence is preserved separately in
`../evidence/security-scan-0.1.0a2.json`; it is not the current verdict.

Shared fixture helpers now leave writes pending for the native command/worker or
owning TestCase to commit. They no longer spawn processes. The native-worker tests
and external CLI runner own those distinct operations explicitly. The rules'
existing test-case policy remains unchanged; this is not independent security
approval, a Marketplace reviewer exemption or installed/live proof.

`container-pins.json` records verified official registry digests for proposed
isolated CI services. Containers and installed acceptance remain unexecuted here.
