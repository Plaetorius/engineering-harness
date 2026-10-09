# Verification

Test observable changed behavior and the failure it prevents. Discover commands from the repository rather than enforcing a common script name. Routine copy/style edits can use a focused inspection or smoke check; significant behavior needs meaningful regression coverage.

Prefer focused tests first, then typecheck/lint, integration, build or browser checks when their scope adds confidence. Include authorization denial, duplicate requests, transaction failure and concurrency cases where relevant. Test security using the role that production callers actually use.

Separate flaky infrastructure or unrelated baseline failures from change failures without declaring either a pass. State omitted checks and why. Avoid snapshot-only assurance for contracts and tests that simply repeat implementation logic.

For substantial sliced work apply [Vertical Slice Delivery gates](vertical-slice-delivery.md). Record local criterion evidence separately from combined target-baseline checks and acceptance review. Existing pack check reports provide software evidence, not automatic lifecycle promotion. Failed, unavailable or unapproved skipped mandatory checks block acceptance; owner-authored tests alone do not provide independent assurance when risk requires it.
