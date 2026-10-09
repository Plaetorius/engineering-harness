---
name: scientific-rust-reference-characterization
description: Characterize a scientific reference before a Rust port, solver change or numerical optimization, establishing semantics, provenance and justified comparison criteria.
---

Read [numerical contracts](../../standards/numerical-correctness.md) and [provenance](../../standards/reproducible-research.md). Inspect the actual reference, mathematical specification, callers and existing tests; an installed library or archived output is not automatically authoritative.

Identify inputs/outputs, units, layout, dtypes/precision, valid domain, boundary conditions, error behavior, stopping criteria and configuration. Establish the reference version/source, license/data access, known limitations and independence from the candidate. Trace preprocessing and conversion, including Python-to-Rust shape/order/dtype differences where applicable. Separate code-verified behavior from assumptions and scientific claims requiring expert evidence.

Characterize small representative cases: known solutions, normal inputs, boundaries, degeneracies and failure paths. Run reference code only with execution authorization and an agreed resource budget; otherwise describe needed experiments without claiming results. Justify tolerances or statistical criteria from conditioning, method accuracy and reference uncertainty before evaluating candidate outputs.

Deliver a compact reference contract with source references, case matrix, comparison/error budget, reproducibility requirements and unresolved limitations. Keep project-specific references and datasets in project documents/profile, not this pack. A missing mandatory reference remains a blocker; do not generate a golden from the candidate as a substitute.
