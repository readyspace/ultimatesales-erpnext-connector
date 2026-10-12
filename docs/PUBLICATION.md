# Owner-authorized public source publication

12 October 2026, Asia/Singapore. The owner explicitly requested resolving the
fixture findings, refreshing the candidate archive/handoff, creating a local
repository in GitHub Desktop and pushing a public ReadySpace repository.

Target: https://github.com/readyspace/ultimatesales-erpnext-connector.
Candidate 0.1.0a3: 264 offline tests PASS; unchanged pinned rules PASS with zero
blocking findings, 43 advisory findings, no scanner errors and complete targets.
Source/build/credential checks precede publication. No live customer data or token
is present in the source; credentials are entered only locally on future test sites.

Original local implementation history is preserved privately. A new clean source
repository excludes downloaded third-party code/rule copies; immutable source
URLs/hashes and the fetcher reproduce unchanged rules without redistributing them.
The GPL-3.0-only app licence remains unchanged. GitHub Desktop created and registered the clean local repository on main.
The GitHub API verified visibility=public, private=false and default_branch=main.
The first pushed source commit is `a0b280917a6199b053183b9d18531ebe53bfbce5`, matching local HEAD at publication.
Final archive/commit hashes are recorded in the delivery manifest.

Publication execution: **PASS — created and pushed publicly**.
Remote CI **PASS** for the first published source commit:

- [Offline tests](https://github.com/readyspace/ultimatesales-erpnext-connector/actions/runs/38234142819): completed/success.
- [Unchanged pinned security rules](https://github.com/readyspace/ultimatesales-erpnext-connector/actions/runs/38234142907): completed/success.

`evidence/public-source-ci.json` records exact run IDs and source SHA. Subsequent
documentation-only commits trigger fresh CI; the above results apply specifically
to the recorded source commit. Final delivery reports record the current remote SHA.
The installed-site workflow was not dispatched. No public-beta
release/tag, Marketplace submission, production rollout or installed/live approval
is implied. Disposable Bench/Pilot/CRM resources remain undesignated; 26 installed
checks are supplied but unrun. Publisher support/security contacts remain pending.
