# Installation changes and ownership

Keep the canonical checkout at a stable location. Always preview installation and review collisions before applying.

| Destination | Managed resource |
| --- | --- |
| CODEX_HOME/AGENTS.md | Canonical core instructions |
| CLAUDE_CONFIG_DIR/rules/engineering-harness.md | Same canonical core instructions |
| ~/.agents/skills/<skill> | Six canonical skill entry points |
| CLAUDE_CONFIG_DIR/skills/<skill> | Same six canonical skill entry points |
| ~/.engineering-harness/ | Private ownership, lock, journal and optional backup |

Default homes are ~/.codex and ~/.claude. Alternate homes/state directories require their own resolved preview. Existing instructions, skills, hooks, permissions, model settings and shell startup files remain user-owned. The installer refuses unowned destinations and records exact link identities; it does not silently adopt matching links.

The optional Claude both-file instruction-mode patch is separately requested and backed up before writing. Restore requires the current settings to match recorded installed bytes. Later edits remain untouched: explicit `--preserve-settings` allows a link-only update while retaining original guarded rollback ownership. It does not authorize automatic restoration over edited settings.

Project activation owns selected native skill links and narrow ignore blocks within the project. Portable profiles may be committed; local approvals, journals and reports must remain ignored. Discovery never authorizes pack execution.

See [installation](install.md), [rollback](rollback.md) and the [threat model](security.md) for transaction behavior and limitations. Never publish private ownership manifests, backups or full host configuration diffs.
