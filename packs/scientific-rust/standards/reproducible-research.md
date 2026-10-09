# Reproducible research and provenance

Track the chain from source data through transformations to reported conclusions. Record dataset identifier/version, origin, license/access conditions, content hash, preprocessing parameters, exclusions, units, missing-data policy and output schema. A filename or timestamp alone is not provenance. Generated synthetic cases also need their generator revision, parameters and seed.

Pin the relevant Rust toolchain and dependency resolution according to repository conventions; record enabled features, target, compiler flags, native libraries, Python environment when used, and accelerator/runtime versions. `--locked` protects dependency resolution but does not prevent network access; offline/frozen modes need already available dependencies and toolchains. Never fetch missing data/dependencies or change a lockfile silently during verification. Cargo build scripts and procedural macros execute code even during some compilation checks; source review and execution authorization still apply.

Capture commands, input hashes, configuration, seeds/streams, thread counts, hardware and output hashes/report locations. Avoid storing environment dumps, credentials, private filesystem inventories or sensitive raw records. Retain enough sanitized metadata to reproduce the result under the project's access restrictions. Changes to reference results need provenance and scientific justification; do not regenerate goldens from the candidate and call that independent verification.

For restartable long runs, establish checkpoint format/version, atomic publication, resume validation and partial-result semantics. Separate independent experiments' output locations and shared caches; do not let concurrent workers overwrite datasets, reference files or checkpoints. Streaming/chunking must preserve the specified ordering, aggregation and error semantics.

Document uncertainty, unsuccessful runs and missing evidence along with successful results. A repeatable computation can still implement the wrong model. Scientific acceptance may require a domain expert or external measurements; unavailable evidence remains a stated blocker when mandatory.

Dependency execution modes: [Cargo test options](https://doc.rust-lang.org/cargo/commands/cargo-test.html).
