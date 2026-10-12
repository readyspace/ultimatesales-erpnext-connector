# Remaining prerequisites

All entries reflect observed missing resources as of 12 October 2026.

| ID | Affected gate | Missing prerequisite | Secure continuation | Owner |
|---|---|---|---|---|
| B01 | A01, installed permissions/concurrency/recovery/UI | No disposable Bench environment designated; local Bench, MariaDB, Redis/container runtime absent | Deployment owner provisions the pinned isolated host and runs the committed recipe/harness; enter secrets locally | Owner to designate deployment engineer |
| B02 | A02 | No separate Pilot-managed test environment designated | Provide an isolated Pilot source-install resource, pin manager and install same exact candidate revision | Deployment owner |
| B03 | Live A05–A16 | No designated synthetic UltimateSales location/account/token, automations status or intended customer onboarding evidence | Disable customer-facing/chargeable automations in test location; enter scoped token in Password field through normal secure access; run live contract matrix | CRM owner |
| B05 | Autonomous dispatch | Supported public queue API cannot re-dispatch arbitrary saved requesters from scheduler identity; framework DB retry drops user argument in pinned source | Candidate uses explicit operator dispatch and fails closed after identity loss. Review prepared upstream question privately before adding automation | Development/security reviewer |
| B06 | A17/A19/A20, beta readiness | Two-site/lifecycle/document-only rehearsal and independent human sign-off have not occurred | Use disposable backed-up sites; record actual results and failures. Upgrade support remains unclaimed | Deployment engineer / independent tester |
| B07 | Later publication | Monitored publisher support/security contacts and privacy/support policy URLs are not approved | Publisher supplies actual contacts/policies after technical acceptance; no invented address | ReadySpace release owner |

User confirmed **no test environments designated yet** during this implementation.
Safe local work was completed; no production or operational account was used.
Public source publication completed in this follow-up. PUBLICATION.md records actual
remote/CI status; installed/live gates remain blocked. Missing resources
block the affected acceptance gates, not review of the delivered source.

Resolved: former B08 fixture static-scan findings. Current unchanged rules report
zero blocking findings; advisory findings remain documented. Repository existence
and source publication are handled in PUBLICATION.md, separately from deployment.
