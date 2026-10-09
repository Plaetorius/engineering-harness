---
name: scientific-rust-differential-test-design
description: Design differential and invariant tests for scientific Rust against a characterized independent reference, including floating-point edge cases and reproducible failing inputs.
---

Read [numerical contracts](../../standards/numerical-correctness.md). Establish the reference contract first; use the reference-characterization skill when it is genuinely missing. Identify the slice's scientific claim, reference uncertainty and intended precision/feature/optimized-build matrix.

Design paired cases over the justified input domain, including near-zero outputs, boundaries, scale extremes, ill-conditioned regions and invalid inputs. Specify conversions, units, shape/length checks and nonfinite handling before any tolerance expression. State absolute/relative/norm or statistical criteria with a scientific rationale. Include at least one case that exposes a plausible implementation defect; passing identical copies of an algorithm does not provide independence.

Combine reference comparisons with applicable analytical solutions, convergence tests, conservation/metamorphic properties and negative cases. Explain why each property follows from this method. For randomized cases record seeds and streams, retain/minimize failing examples, and distinguish deterministic regression from statistical assurance. Never widen tolerances or discard failures without investigating their cause and obtaining any required criteria revision.

Fit the cases into existing project tests and named `scientific-differential` / `scientific-invariants` commands. For a design request, produce the test matrix and proposed commands without editing code. When implementation is requested, add tests within the allowed slice and run only authorized checks. Report actual results, missing reference coverage and resource limits; absent mandatory commands must remain visible as skipped/blocked checks.
