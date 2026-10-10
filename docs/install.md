# Installation

Prerequisites: macOS or Linux, Bash, Python 3.9+ and a stable local checkout. No pip dependencies or network installation by the harness itself. Optional but recommended: the Mermaid CLI, `npm i -g @mermaid-js/mermaid-cli` (provides `mmdc`; downloads a headless Chromium, 150 to 300 MB), which `architecture-map` uses to render and open diagrams as PNG. Without it the skill returns Mermaid source only. Windows is not supported. Python 3.9+ is needed for path APIs; CI and tests determine actual portability evidence.

```sh
bash scripts/verify
bash scripts/install
```

The second command is read-only by default. Review all proposed destinations and existing instruction overlap. A private state directory is reserved for ownership and rollback. The baseline refuses existing destinations even if their content/target looks identical; it will not adopt someone else's files.

After authorization:

```sh
bash scripts/install --apply
bash scripts/doctor --versions
```

Claude's optional project instruction mode can be previewed and applied separately, or included in the initial reviewed install:

```sh
bash scripts/install --claude-project-instructions both
bash scripts/install --claude-project-instructions both --apply
```

This requires installed Claude 2.1.285+ and sets both-file project discovery. It does not change hooks, models or permissions. All unrelated JSON values are preserved, but JSON formatting is normalized. An existing incompatible setting or disabled AGENTS built-in causes refusal. Stop active settings writers first. The source version probe runs `claude --version`; CLI startup is not guaranteed to be side-effect free.

`HOME`, `CODEX_HOME` and `CLAUDE_CONFIG_DIR` select destinations. `--home`, `--codex-home`, `--claude-home` and `--state-dir` override them. If selecting a fake HOME, also unset or replace both config-home environment overrides, so they cannot point to the real host. HOME must already exist. Supply canonical paths when system/user symlink parents would redirect writes. Codex user skills use HOME/.agents/skills independently of CODEX_HOME.

## Default discovery

The same canonical core is linked into Codex global AGENTS and Claude user rules. Seven canonical skill entry-point directories are linked into both user skill paths. Portable standards are accessed from the resolved source repository; vertical standards/roles require explicit project activation. Project AGENTS remains owned by each project; an optional [template](../templates/AGENTS.md) is available.

Start fresh sessions after installation. Existing resumed sessions may retain old context. See [CLI verification protocol](../tests/discovery/manual-cli-protocol.md). Doctor validates files and configuration, not model obedience or effective managed policy. Canonical content edits take effect through existing links; reinstall preview shows a private provenance-hash refresh, and authorized apply records it without replacing links.

## Troubleshooting

- Conflict: preserve the existing file; explicitly resolve/migrate it or select an isolated home. Never delete a whole configuration directory.
- Broken links after moving the checkout: invoke the new checkout's uninstall with the original HOME/config/state arguments; preview first. Restore the old source location if needed, then reinstall from the new stable location.
- Interrupted apply: use uninstall `--recover` preview, then authorized `--recover --apply`. If an entry changed, recovery refuses; inspect privately before manual merge.
- Claude AGENTS missing: check ancestor CLAUDE/local files, built-in support, actual mode and managed policy. Both-mode is optional, but necessary for consistent native AGENTS use when ancestor CLAUDE files exist.
- Skills missing: check resolved link manifests, skill-name collisions, active config homes and CLI customization-disable flags. Restart. Cloud/remote sessions require their own explicit bootstrap; a host install does not apply there.

For a link-only update when Claude settings were edited after the optional patch, preview `scripts/install --preserve-settings` and apply with `--apply`. This leaves current settings bytes and the original backup/rollback record untouched. `scripts/doctor --preserve-settings` checks links while reporting the retained drift. The flag cannot be combined with a new both-mode patch or used for uninstall; automatic restore still refuses edited settings. Resolve rollback with a reviewed manual merge, never by resetting unrelated values.
