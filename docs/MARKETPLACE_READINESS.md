# Marketplace readiness gate

**Current state: NOT READY FOR SUBMISSION.** No listing or publisher account has been created through this bundle.

Before submitting:

- Public repository, reviewed licence/ownership, reproducible source release and immutable commit.
- Confirmed app name/title, publisher support contact, security reporting, README, screenshots, public documentation/privacy and external service disclosure.
- Verified clean install, migration, uninstall/disconnect behavior, compatibility versions and required ERPNext dependency.
- Native-stack integration tests, actual API conformance tests, abuse/security review, documented data retention and customer-account separation.
- Pilot acceptance and external beta feedback; clear non-goals and support responsibilities.
- Recheck the latest `frappe/marketplace` schema and validation process. Do not fabricate repository/logo URLs, release commit hashes, reviews or approval status.

The primary registry currently describes `apps.json` metadata and `apps/<name>.json` release files, with branch, immutable commit, version compatibility and dependencies. This package intentionally does not ship a misleading publishable record with invented values. It also does not publish an app into HighLevel's separate app marketplace.

See `SOURCES.md` for official registry/policy references checked during development.
