---
name: scientific-rust-numerical-correctness-review
description: Review a scientific Rust plan or implementation for numerical correctness, reference validity, floating-point failure paths and reproducible scientific evidence; read-only by default.
---

Use the canonical shared review procedure and report fields; resolve its `review` skill through native discovery rather than duplicating it. Select this activated pack's `scientific-rust-numerical-methods-engineer` profile. Read [numerical correctness](../../standards/numerical-correctness.md) and relevant [research provenance](../../standards/reproducible-research.md). If the shared workflow is unavailable, report that limitation before presenting a partial numerical assessment.

Establish target, intended baseline, scientific requirements and acceptance tolerances. Follow units, dimensions, discretization, stopping criteria, precision conversions and caller error handling through actual code. Inspect comparator nonfinite/shape behavior, cancellation, near-zero cases, overflow, reduction order and debug/optimized differences as relevant. Examine reference independence and whether tests distinguish the intended method from realistic wrong alternatives.

Separate confirmed implementation defects from hypotheses and from scientific model-validation questions. Cite evidence, a concrete failing scenario, correction and regression test with severity/confidence. Do not claim mathematical/physical validity from compilation, a passing test suite or conserved quantity alone. Zero findings is valid. Do not edit files, regenerate reference data, execute expensive experiments without authorization, weaken tolerances or waive required checks. Report missing expert/reference evidence and local versus integrated verification accurately.
