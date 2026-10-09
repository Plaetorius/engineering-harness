---
name: scientific-rust-performance-benchmarking
description: Design or run an explicitly budgeted scientific Rust benchmark comparing equivalent numerical workloads with reproducible timing, memory and scaling evidence.
---

Read [Rust performance](../../standards/rust-performance.md) and [reproducibility](../../standards/reproducible-research.md). Establish the performance question, baseline revision, workload, accuracy contract and resource budget. Confirm correctness equivalence before interpreting speed differences. Inspect existing benchmark targets/tools and actual project commands; do not install a framework or assume a nightly harness.

Define inputs, optimized profile, target/features, precision, thread counts, warmup, repetitions, noise controls and reported statistic. Specify which costs are included (setup, transfer, I/O, kernel, full run) and relevant memory/scaling metrics. Account for dead-code elimination, caches and nested thread pools. Record hardware and software context without environment/credential dumps.

Prefer a small representative experiment before an expensive run. Execute only authorized workloads within declared wall-time/memory/disk/worker limits using existing project/OS controls. Pack activation and a runner timeout are not authorization or resource isolation. Missing hardware, references or budget block claims that depend on them; do not submit cluster jobs or download large data automatically.

Use the profile's `scientific-benchmark` command for repeatable runs. Return baseline/candidate commands and revisions, accuracy evidence, sample/variability statistics, memory/resource observations, artifact locations, limitations and the scope of any supported claim. For design-only requests return a protocol, not invented timings. Unmeasured optimizations remain hypotheses; do not cherry-pick samples or silently change tolerances/workloads.
