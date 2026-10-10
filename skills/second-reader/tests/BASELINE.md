# Measured baseline (2026-10-09)

| Measure | Fields | Accuracy | Baseline |
|---|---|---|---|
| heldout.local | 128 | 94.5% | - |
| heldout.haiku | 133 | 89.5% | - |
| heldout.haiku3 | 128 | 95.3% | - |
| sealed.local | 109 | 67.9% | - |
| sealed.haiku | 110 | 80.0% | - |
| sealed.haiku3 | 105 | 91.4% | - |

Unit tests: 111 run, 0 failing, 1 skipped.

Sets: `heldout` (set A, rules were tuned against it), `sealed` (set B, written blind; the toolkit and the v3 prompt were changed after seeing its first scores, so later numbers are not independent). `haiku` = batched Haiku, original prompt; `haiku3` = prompt with the buyer's request.
