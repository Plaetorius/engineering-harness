# Modular architecture

The shared protocol, foundational workflows, global installer and ownership/recovery mechanisms are preserved. The former conditional web profile is now the explicitly activated `web-typescript` pack. Existing global link locations and the global ownership schema remain unchanged; existing installations follow the canonical updated files. No profile means no active vertical.

| Layer | Canonical resources | Responsibility |
| --- | --- | --- |
| Core | `core/`, `skills/`, portable `standards/`, `scripts/lib/` | Proportional planning, boundaries, review, debugging, validation and generic verification |
| Packs | `packs/<id>/pack.json` and local payload | Domain standards, workflows, portable skills, checks and optional templates/tools |
| Project | `.harness/project.json` | Exact pack pins, rules, docs, commands, required checks, human acceptance criteria and pack config |
| Adapters | `adapters/<runtime>/discovery.json` | Native instruction/skill paths; platform configuration stays outside portable policy |

The lightweight CLI uses Python's standard library and the existing safe filesystem helpers. There is no registry, dependency solver, hosted service, workflow language or new agent runtime. Pack discovery reads JSON and files; it never imports pack code or runs declared checks. Built-in packs are maintained with this checkout. External local directories require explicit fingerprint approval before their instructions are exposed.

Global installation still projects two instruction links and twelve skill entry-point links. Project activation records reviewed profile bytes and payload fingerprints in ignored `.harness/local/ownership.json`, then projects only selected pack skills into `.agents/skills` and `.claude/skills`. Profiles have portable paths and content fingerprints; machine-specific source paths, local approvals, journals and reports stay in ignored private state. Another checkout must independently sync/approve its profile. Packs remain independently removable; shared core skills are never owned by a project activation.

Activation/deactivation default to previews. Apply refuses foreign destinations, conflicting skill names, edited owned links and conflicting managed ignore blocks. Transactions journal configuration bytes and link identities, restore on errors and support explicit recovery after interruption. User ignore entries and native runtime settings remain intact. Deactivation retains required checks so it cannot silently lower acceptance requirements; review the profile explicitly if requirements should change.

Standards are resolved by `project inspect`, rather than copied or blindly merged into global instructions. Portable skills expose names/descriptions through native discovery, loading detailed references on demand. Core security remains authoritative; conflicting pack/project instructions require resolution. This is instruction discipline, not an OS security boundary.

Checks are distinct from instructions and acceptance criteria. The runner resolves activated pack declarations and named project commands, requires `--execute`, verifies approved fingerprints/profile bytes, executes argv without a shell, confines declared working directories, captures output and enforces timeouts. Human acceptance criteria are reported but never automatically declared satisfied. The design accommodates new kinds of command-produced reports without specialized numerical or benchmark engines.

Migration: retain foundational skill identities and installation links, refresh installer provenance, activate the relevant pack per selected project, declare actual repository commands, and sync profile edits before execution. The old `profiles/nextjs-supabase.md` and domain standard locations contain compatibility notices; they do not activate anything. The optional [scientific-rust pack](scientific-rust.md) uses the same manifest/profile/check/reviewer interfaces without core changes; it supplies research engineering guidance, not a scientific solver or validated physical model.

Architecture mapping and canonical role-aware review extend the same global library; `review-diff` is a compatibility entry point. Optional pack `reviewers` declarations resolve through existing activation and `project inspect`, with no independent registry. See [capability contracts](architecture-map-review.md).
