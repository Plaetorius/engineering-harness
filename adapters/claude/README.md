# Claude local adapter

The baseline links the canonical core into the user `rules/engineering-harness.md`, and seven individual skill entry points into user `skills/`. Existing CLAUDE files, rules, hooks and plugins remain. Symlinked user rules avoid project external-import approval; project rules have different constraints. See [official user rules](https://code.claude.com/docs/en/memory#user-level-rules).

`project-instructions.patch.json` is an opt-in subtree, never a replacement settings file. The installer supports Claude 2.1.285+ for this new built-in ID and rejects explicit conflicting mode/disabled support. Use `--claude-project-instructions both` to preview/apply. No hooks or model settings are provided.

The installer reads `discovery.json`; project activation uses its `.claude/skills` layout. It projects the same canonical portable pack skill targets as Codex, with no settings edits. Restart sessions after activation. Native user/project/plugin precedence and target deduplication remain Claude behavior; profile inspection resolves standards without injecting them globally.

## Slice delegation and isolation

Claude's native subagents can receive the [shared delegation contract](../../standards/vertical-slice-delivery.md); supporting reviewers/researchers do not need new harness-specific agent definitions. [Official subagent guidance](https://code.claude.com/docs/en/sub-agents) supports `isolation: worktree`; without it a subagent starts in the main workspace. [Native session worktrees](https://code.claude.com/docs/en/common-workflows#run-parallel-sessions-with-worktrees) use `claude --worktree <name>`, also present in audited CLI 2.1.293 help. Verify the selected starting baseline: isolated subagent worktrees may start from the default branch rather than the parent's HEAD. Do not assume isolation or incorporation from a completion report.

Git worktrees require an existing commit. Use equivalent isolated workspaces or serialize edits when prerequisites are missing; no worktree is needed for trivial read-only support. Each worktree with a tracked project profile needs its own reviewed `project sync --project <worktree>`; do not copy local approvals/journals or assume ignored pack links transfer. Validate instructions, profile and checks before implementation. Worktrees do not isolate shared databases/services. Preserve native permissions; no automatic commits, merges, pushes, deployments, migrations or destructive cleanup. Capability/help evidence does not establish successful live delegation.

## Portable skill arguments

See [mapping/review invocation and native alias caveats](../../docs/architecture-map-review.md). Use `/architecture-map auth --view=sequence` and `/review security-engineer --target=diff --scope=auth`. Native skill handling appends invocation arguments when no substitution placeholder is present, so canonical files need no vendor variables. Verify `/review` resolves to the harness; if the bundled alias shadows it, `/review-diff` accepts the same role/target/scope through the canonical workflow. No command shadowing is forced by configuration edits.
