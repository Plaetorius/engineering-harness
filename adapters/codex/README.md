# Codex local adapter

Global instructions link into `CODEX_HOME/AGENTS.md`, default `~/.codex/AGENTS.md`. Skills use `HOME/.agents/skills` independently of CODEX_HOME. Do not install duplicate copies into legacy `.codex/skills`. Existing global override files block installation until explicitly resolved, because they can shadow the core.

No config TOML edits, model settings, permission changes or hooks are needed. Doctor checks resolved links and manifests; fresh-session validation separately proves discovery. [Official discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [skills](https://learn.chatgpt.com/docs/build-skills).

The installer reads `discovery.json`; project activation uses its `.agents/skills` layout. It creates individual symlinks to selected canonical pack skills. Global core resources remain available without a project profile. Restart sessions after activation; instruction precedence remains native Codex behavior.

## Slice delegation and isolation

Use native subagents when available and allowed for focused slice work; the primary agent supplies the [shared delegation contract](../../standards/vertical-slice-delivery.md). Current official documentation describes native spawning, messaging, waiting and interrupting; no harness agent definitions or scheduler are needed. Consult [official subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents) for the active client's capabilities, not an assumed cross-client tool API.

[Managed worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees) isolate app chats; installed Codex 0.161.0 `exec --help` also advertises `--worktree`, but this is not proof that a CLI subagent automatically receives one. Verify the actual workspace/baseline before concurrent edits, and use explicit Git worktrees or equivalent isolation when needed. If unavailable, serialize writers. Respect existing permissions and do not commit/merge/push or clean up user work without authorization. Git worktrees require an existing commit.

New worktrees need their own reviewed `project sync --project <worktree>` for tracked profiles. Do not copy `.harness/local` approvals/journals or assume ignored native skill symlinks transfer; managed Codex worktrees skip source symlinks when copying ignored files. Verify profile inspection and checks in each workspace. Shared databases/services still need separate ownership. Native delegation is capability/version-dependent and model execution needs separate evaluation; local help/version evidence is not proof of model behavior.

## Portable skill arguments

See [mapping/review invocation and native alias caveats](../../docs/architecture-map-review.md). Use `$architecture-map auth --view=sequence` and `$review security-engineer --target=diff --scope=auth` as prompt text, not the native `/review` command. No vendor substitution is embedded in canonical skills.
