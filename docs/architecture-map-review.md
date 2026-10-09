# Architecture maps and role-aware reviews

Both capabilities use canonical globally installed portable skills and the same logical arguments. Claude invokes slash skills; Codex explicitly invokes dollar-named skills in a prompt. Arguments are ordinary task text, never a shell command.

| Intent | Claude Code | Codex |
| --- | --- | --- |
| System overview | `/architecture-map` | `$architecture-map` |
| Scoped component | `/architecture-map auth --depth=2` | `$architecture-map auth --depth=2` |
| Sequence | `/architecture-map auth --view=sequence` | `$architecture-map auth --view=sequence` |
| Data flow | `/architecture-map --view=data` | `$architecture-map --view=data` |
| Default review | `/review` | `$review` |
| Plan perspective | `/review software-architect --target=plan` | `$review software-architect --target=plan` |
| Scoped security review | `/review security-engineer --target=code --scope=auth` | `$review security-engineer --target=code --scope=auth` |

Also accept explicit `--scope=` for mapping and `--role=` for review. Mapping views are system/component/sequence/data; absent view means system without scope, component with scope. Depth is a positive expansion-level integer, default 1. Reviews default to general-reviewer and infer a relevant target from the artifact/task; target choices are plan/diff/code/architecture. Selected parameters are reported. Invalid or unknown parameters need correction; materially ambiguous artifacts/baselines need clarification. Unknown role IDs are unavailable unless an explicitly requested custom perspective is described with assumptions. `senior-backend-engineer` is not a built-in profile.

Claude's existing `/review` alias may resolve to its bundled code-review capability depending on client behavior. If native resolution shadows the harness skill, use `/review-diff --target=plan --role=software-architect` (or the desired target/role) as the compatibility route and verify the loaded source. Codex's native `/review` is distinct from `$review`; use the dollar skill invocation for this harness. Both entry points share the canonical review workflow and arguments; there is no second review methodology.

Architecture maps inspect actual implementations/callers, schemas, tests and relevant configuration. A declared dependency is not an active integration; checked-in infrastructure is not production topology. Relationships are Verified, Inferred or Unknown, with file/line evidence. Maps include canonical Mermaid source, explanation and limitations. Use progressive detail and trace actual error paths for sequences. Never read credential stores or environment-value files; sanitize potentially sensitive source/config extracts before exposing them to a model. If safe evidence is unavailable, omit it and state Unknown. Diagrams must not contain secrets, active links, external images or HTML.

Mermaid source is always available. Interfaces may render fenced Mermaid directly. For offline SVG using an already installed trusted Mermaid CLI:

```sh
python3 <harness>/skills/architecture-map/scripts/render.py /approved/output/map.mmd --output-directory /approved/output
```

The helper writes a fresh directory, uses strict configuration, accepts a conservative flowchart/sequence subset and never downloads tooling. No renderer yields an explicit unavailable result, not validated syntax. A renderer failure does not prove the source invalid; report compatibility/diagnostic limits. This helper is not a sandbox, secret scanner or dependency engine. Use sanitized generated source and an approved output directory; existing source/artifacts remain untouched. No online rendering service, application startup or dependency installation is part of mapping.

Reviews challenge assumptions using realistic failure scenarios and alternatives while recognizing sound decisions and permitting zero findings. Core perspectives are [general-reviewer](../standards/reviewers/general-reviewer.md), [software-architect](../standards/reviewers/software-architect.md), [security-engineer](../standards/reviewers/security-engineer.md), [data-engineer](../standards/reviewers/data-engineer.md), [designer](../standards/reviewers/designer.md) and [performance-engineer](../standards/reviewers/performance-engineer.md). They change priorities, never the standard of evidence. Visual defects require rendered evidence; semantic accessibility can be established by markup. Performance effects require comparable measurements; an unmeasured complexity concern remains a risk.

Reports cover context, summary/strengths, severity-grouped confirmed defects versus plausible risks, missing verification, prioritized corrections and coverage limits. Each finding supplies artifact location, evidence, failure consequence, correction, suggested check and confidence. Reviews are read-only by default; no automatic fixes, criteria changes, waivers, merges or mutating checks. A separate authorized implementation can apply findings. Independent native read-only review is useful when risk warrants it; avoid anchoring on the implementer's conclusions. It is not mandatory for routine work.

For substantial slices, mapping can clarify dependencies before implementation, and a selected role can review a plan or later diff. Neither is a ritual for trivial changes. Local test results, integration and acceptance remain distinct; generated diagrams and clean reviews do not override code evidence or mandatory verification.

## Pack reviewer extensions

Add an optional field to an existing pack manifest:

```json
{"reviewers": [{"id": "example-auditor", "path": "reviewers/example-auditor.md"}]}
```

The Markdown file has scalar `name` and `description` frontmatter; name, filename stem and manifest ID agree. Its body states expertise, checklist and domain concerns. IDs carry the pack prefix and cannot override core profiles. Duplicate declarations and active cross-pack collisions are rejected. There is no inheritance system.

Activate the pack normally; `project inspect` exposes approved profile IDs and canonical paths. Unactivated packs are never searched for requested roles. Deactivation removes availability without deleting core/shared profiles. Changed role content changes the pack fingerprint and requires explicit reactivation. Old manifests remain valid; older harness validators do not understand the optional field, so update the harness before using reviewer extensions. No core source edits are needed to add a new pack role.

See the [fixture rubric](../tests/fixtures/architecture-review/evaluation.md) and [evaluation record](evaluations.md) for actual evidence and unavailable checks. Deterministic installer/manifest/helper tests are distinct from model behavior and real Mermaid validation.
