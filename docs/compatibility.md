# Runtime compatibility

The harness targets local Codex and Claude Code on macOS/Linux. Native discovery, precedence and permissions differ; the adapters share canonical resources without normalizing runtime internals. Consult [evaluation evidence](evaluations.md) for actual tested versions and limitations.

| Capability | Contract | Official reference |
| --- | --- | --- |
| Codex instructions | Global CODEX_HOME/AGENTS.md; global override can shadow it. Project instructions follow native root-to-working-directory precedence. | [Instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md) |
| Codex skills | User ~/.agents/skills; project .agents/skills; directory symlinks supported. CODEX_HOME does not relocate the shared user skills path. | [Skills](https://learn.chatgpt.com/docs/build-skills) |
| Claude instructions | User rules load globally; existing CLAUDE files and rules coexist. Project AGENTS selection can require the optional both-file mode. | [Memory](https://code.claude.com/docs/en/memory) |
| Claude skills | User and project .claude/skills with native precedence, aliases and symlink handling. CLAUDE_CONFIG_DIR relocates user configuration. | [Skills](https://code.claude.com/docs/en/skills), [settings](https://code.claude.com/docs/en/settings) |
| Delegation/isolation | Use native capabilities when available and authorized; verify actual workspaces and baselines. No harness scheduler is installed. | [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), [Claude subagents](https://code.claude.com/docs/en/sub-agents) |

Audited CLI versions include Codex 0.161.0 and Claude Code 2.1.293/2.1.295. Version/help or filesystem checks do not prove effective managed policy or model adherence. Existing global/project instructions, plugins and hooks can influence sessions; the harness preserves them. Semantic conflicts and third-party plugin name collisions may need manual review.

Cloud/remote clients, Cowork and Windows require separate validation. GitHub Actions checks the local scripts on macOS/Linux; live CLI behavior is separately evaluated. Do not copy host credentials into test environments. CLI startup itself may write native state.
