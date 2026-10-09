# Scientific Rust pack

`scientific-rust` provides research engineering guidance through the existing pack system: four portable skills, three reviewer profiles, numerical/reproducibility/performance standards and seven named project checks. It supports local Rust scientific workflows, including independently justified Python references. It does not supply a solver, validated physical model, dataset downloader, benchmark engine or cluster scheduler.

## Activate and configure

From the harness checkout:

```sh
scripts/harness pack validate packs/scientific-rust
scripts/harness pack activate scientific-rust --project /path/to/research-repository
scripts/harness pack activate scientific-rust --project /path/to/research-repository --apply
scripts/harness project inspect --project /path/to/research-repository
```

Activation exposes the selected pack's canonical skills through both project-native skill paths. The centrally installed global core remains shared; the pack is available from any project but requires explicit activation in that project. Neither activation nor discovery runs Cargo or changes native permissions/settings.

Inspect [the example profile](../packs/scientific-rust/templates/project-profile.example.json). After activation, merge the relevant `commands`, `required_checks` and `acceptance_criteria` into the existing project profile. **Do not replace its `packs` array or unrelated fields with the example.** Activation supplies actual version/digest pins; the example deliberately contains no invented pin. Adapt commands to the repository's workspace, features, toolchain and existing CI.

The four Cargo commands are starting points, not universal requirements. They assume Cargo/rustfmt/Clippy and locked dependencies are already available. Frozen mode avoids Cargo dependency downloads/lockfile changes; toolchain managers or build scripts can still have their own effects. Do not install missing tools or fetch dependencies/data without authorization. Workspace tests include normal applicable doctests; all-target static analysis is separate. Debug and optimized tests cover different profile behavior.

Define `scientific-differential` and `scientific-invariants` using real repository tests or scripts and record the independent reference, tolerance rationale and applicable scientific invariants. These commands are deliberately absent from the example: missing required checks remain skipped and block acceptance. Never replace them with unconditional success. The optional `scientific-benchmark` command is relevant only when measured performance is part of the task; declare it required for performance acceptance when appropriate.

```sh
scripts/harness project sync --project /path/to/research-repository
scripts/harness project sync --project /path/to/research-repository --apply
scripts/harness check list --project /path/to/research-repository
scripts/harness check run --project /path/to/research-repository --check scientific-rust:differential --execute
```

Selecting one check still includes profile-required checks. Preview the resolved commands and approve an execution budget before running expensive work. The runner captures output/status and bounds wall time; it does not constrain memory/disk/network/cluster resources or assess scientific validity. Required failures/skips block acceptance. Use [run records](../packs/scientific-rust/templates/research-run.md) for provenance, resource limits and scientific evidence. Private/large datasets stay in the research project or its approved storage.

## Skills and reviews

| Capability | Portable skill ID |
| --- | --- |
| Establish reference semantics and uncertainty | `scientific-rust-reference-characterization` |
| Design reference/invariant/edge-case tests | `scientific-rust-differential-test-design` |
| Review numerical code and evidence | `scientific-rust-numerical-correctness-review` |
| Design or run budgeted performance experiments | `scientific-rust-performance-benchmarking` |

In Codex invoke `$scientific-rust-reference-characterization`; in Claude use `/scientific-rust-reference-characterization`. Supply ordinary task text and the intended scope. The numerical review skill reuses the globally installed core review workflow. Alternatively select a pack profile through core review:

```text
Codex: $review scientific-rust-numerical-methods-engineer --target=diff --scope=solver
Claude: /review scientific-rust-numerical-methods-engineer --target=diff --scope=solver
```

Establish the actual diff baseline. If a Claude version resolves `/review` to a native alias, use `/review-diff` with the same logical arguments and verify the loaded skill source. Other role IDs are `scientific-rust-hpc-performance-engineer` and `scientific-rust-data-provenance-reviewer`. All reviews retain core evidence standards and are read-only by default.

For example, implement one integration step with documented units and error budget, compare it to a characterized reference, test invalid inputs and a justified refinement/conservation property, then verify the optimized implementation. Only after correctness is established compare a proposed parallel kernel to the baseline under equal accuracy and workload. Physics/fusion equations, validation datasets and domain approval belong in project documents; activation does not certify them.

Remove with `pack deactivate scientific-rust --project /path/to/research-repository --apply` after preview. Other packs/core skills are retained. Required check entries remain deliberately unsatisfied until explicitly revised, so removal cannot silently weaken acceptance. Start fresh agent sessions after lifecycle changes.

## Evidence and limitations

Deterministic tests cover manifest discovery, no implicit activation/execution, native link/role exposure, named command execution, missing scientific gates and coexistence/removal. The [controlled evaluation cases](../tests/fixtures/scientific-research/evaluation.md) exercise policy decisions separately. These checks establish routing and conventions, not scientific validity or live runtime conformance; see [recorded evidence](evaluations.md).

The standards link to official Rust/Cargo references for floating-point behavior, profiles and command semantics. They prescribe no universal tolerance, feature matrix, benchmark tool or physical law. Supported harness platforms remain macOS/Linux. No host research repositories are automatically activated.
