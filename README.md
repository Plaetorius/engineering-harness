# Engineering Harness

[![Verify harness](https://github.com/Plaetorius/engineering-harness/actions/workflows/verify.yml/badge.svg)](https://github.com/Plaetorius/engineering-harness/actions/workflows/verify.yml)

A shared, local engineering workflow for **OpenAI Codex and Claude Code**. Keep one canonical source for engineering instructions, portable Agent Skills and explicitly activated domain packs.

Build small, verifiable capabilities; inspect architecture from code; review work with evidence rather than invented criticism. No hosted backend, telemetry, automatic hooks or custom agent orchestrator.

## What it provides

- **Shared engineering protocol:** proportional planning, risk classification, verification and honest completion reports.
- **Vertical Slice Delivery:** bounded outcomes, accountable ownership, dependency-aware execution and separate local, integration and acceptance gates.
- **Architecture maps:** Mermaid system, component, sequence and data-flow views with source evidence and uncertainty.
- **Role-aware review:** general, architecture, security, data, design and performance perspectives; plan, diff, code and architecture targets.
- **Extensible packs:** standards, skills, checks and reviewer profiles activated through a portable project profile. The initial `web-typescript` pack covers Next.js, React, TypeScript, Supabase/PostgreSQL and Vercel.
- **Safe local lifecycle:** preview-first installation, collision refusal, private ownership records, guarded rollback and preservation of unrelated configuration.

The optional [scientific Rust pack](docs/scientific-rust.md) adds reference characterization, differential test design, numerical review and reproducible performance workflows for research. Activate it explicitly per project; scientific models, datasets and acceptance thresholds stay project-specific.

## Quick start

Requires **macOS or Linux, Bash and Python 3.9+**. No third-party Python runtime dependencies. Review the checkout before installing: changes to canonical files affect future agent context through symlinks.

```sh
git clone https://github.com/Plaetorius/engineering-harness.git
cd engineering-harness
bash scripts/verify
bash scripts/install              # preview; no changes
bash scripts/install --apply     # apply the reviewed installation
bash scripts/doctor
```

Installation links the core instructions and six skill entry points into the native user discovery paths. It does not replace Codex/Claude configuration, change permissions or activate packs automatically. Start a fresh agent session after installation.

Claude's optional project AGENTS/CLAUDE coexistence setting is a separate backed-up operation. See [installation and troubleshooting](docs/install.md) before using it. If Claude settings were edited after that patch, use the documented `--preserve-settings` option for a link-only update; automatic uninstall still refuses to overwrite later edits.

## Use the skills

| Task | Claude Code | Codex |
| --- | --- | --- |
| Plan substantial work | `/plan-feature` | `$plan-feature` |
| Map a subsystem | `/architecture-map auth --depth=2` | `$architecture-map auth --depth=2` |
| Trace an operation | `/architecture-map auth --view=sequence` | `$architecture-map auth --view=sequence` |
| Review a plan | `/review software-architect --target=plan` | `$review software-architect --target=plan` |
| Review security boundaries | `/review security-engineer --target=code --scope=auth` | `$review security-engineer --target=code --scope=auth` |
| Debug a reproducible failure | `/debug-root-cause` | `$debug-root-cause` |

`implement-api` covers boundary implementation; `review-diff` preserves earlier review invocations and delegates to the canonical review workflow. Native command aliases can differ: see [mapping/review arguments and compatibility](docs/architecture-map-review.md). These are agent instructions, not deterministic guarantees of model behavior.

Architecture maps always produce Mermaid source. Optional SVG rendering uses an already installed local Mermaid CLI; the harness never downloads a renderer or sends repository content to an online rendering service.

## Activate a domain pack

```sh
scripts/harness pack list
scripts/harness pack activate web-typescript --project /path/to/project
scripts/harness pack activate web-typescript --project /path/to/project --apply
scripts/harness project inspect --project /path/to/project
scripts/harness check list --project /path/to/project
```

Declare actual repository commands and required checks in `.harness/project.json`, then preview/apply `project sync`. Checks run only with explicit `check run --execute`; discovery and validation never execute pack scripts. External packs additionally require fingerprint approval. Profiles are portable; local approvals, links, journals and reports remain private and ignored.

[Create a pack](docs/packs.md) without editing core source. [Deactivate packs and recover changes](docs/rollback.md) through the ownership-aware lifecycle tools.

## Architecture

| Layer | Responsibility |
| --- | --- |
| Core | Portable principles, skills, delivery policy and generic verification |
| Vertical packs | Domain standards, workflows, skills, checks and reviewer profiles |
| Project profiles | Explicit pack pins, repository rules, commands and acceptance criteria |
| Runtime adapters | Native discovery paths and platform-specific configuration |

Read the [architecture](docs/architecture.md), [Vertical Slice Delivery policy](docs/vertical-slice-delivery.md), [pack contracts](docs/packs.md) and [compatibility notes](docs/compatibility.md).

## Validation and limitations

Run `bash scripts/verify`. Tests cover installation, rollback, configuration preservation, pack isolation, trust boundaries, discovery and verification results. GitHub Actions runs the suite on macOS and Linux.

[Evaluation records](docs/evaluations.md) distinguish automated tests, actual CLI behavior and unexecuted checks. Windows, cloud/remote clients and Cowork are outside the current support claim. Mermaid parser/render validation requires local tooling. Native sandboxes and permissions remain essential: instructions are not a security boundary, and explicitly executed checks inherit user permissions.

## Contributing and security

See [contributing](docs/contributing.md) and the [security policy](SECURITY.md). Never include credentials, host settings, private transcripts, local approvals or installation backups in contributions or issues.

## License

[MIT](LICENSE) © 2026 Plaetorius.
