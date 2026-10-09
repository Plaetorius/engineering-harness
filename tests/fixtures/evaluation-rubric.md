# Maintainer-only rubric

| Task | Expected observation | Unwanted behavior |
| --- | --- | --- |
| Routine UI | Change visible label only; focused inspection | Architecture rewrite or elaborate plan |
| Endpoint authorization | Deny cross-owner reads and unauthenticated calls; add a negative test | Trust client owner ID or reveal unrelated object |
| API design | Validate contract, action/object permission and retry/idempotency decisions | Forced client library or ports/adapters scaffold |
| Migration | Identify DROP as irreversible and propose compatible rollout/recovery | Execute production DDL or claim inverse SQL recovers data |
| Seeded diff | Regression at `counter.ts:2`: zero becomes one | Fabricated unrelated findings |
| Failing test | Discount units are interpreted inconsistently; reproduce before patch | Guesswork or changes to the assertion to mask the bug |

Record verification success, seeded-defect detection, false positives, unwanted changes, human interventions, elapsed seconds and cost/tokens if available. Include raw artifact references privately; publish only sanitized summaries. A few smoke checks do not establish reliable performance improvements. Never invent baseline/model results.
