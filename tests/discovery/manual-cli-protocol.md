# Runtime acceptance protocol

Use fresh sessions and a trusted temporary fixture. Keep private command output in an ignored local directory; export only sanitized evidence. Do not copy credentials into test homes. Authentication and model cost require an authorized existing runtime. Disable external integrations and custom hooks for controlled checks without disabling instruction/skill discovery.

1. Run doctor and record CLI versions. Confirm core links and skill manifests resolve to one source.
2. In a directory with no project instructions, ask each CLI to state the loaded global protocol heading and the six skill entry-point names. Do not supply the heading or names in the prompt. Verify against actual content, not a guessed answer.
3. Add a synthetic project AGENTS marker, then a CLAUDE marker. Verify both-mode sees both in Claude, and Codex sees AGENTS. Test Claude import/symlink deduplication separately; do not infer it from similar output.
4. Invoke each shared skill explicitly (`$skill-name` for Codex, `/skill-name` for Claude) using a relevant task. Confirm the source manifest and referenced standards/profile are readable. Run review/planning tasks read-only; run edits only in disposable fixtures.
5. Repeat with alternate homes, nested instructions and CLI configuration that disables native AGENTS support. Record unsupported/unrun cases honestly.
6. Run all six behavioral tasks on both CLIs and a bare baseline, using the same tasks and permissions. Compare against the private rubric. Record elapsed time, verification, false positives, unwanted edits, interventions and cost when available.

Claude `--settings '{"disableAllHooks":true}'` temporarily disables non-managed hooks. `--strict-mcp-config` with an empty MCP configuration avoids external servers. `--bare` and `--safe-mode` disable relevant discovery and cannot prove normal integration. Managed policy may still apply.

Model self-report alone is weak evidence. Prefer observed runtime skill metadata, explicit invocation, source/tool-read evidence and concrete fixture behavior. Do not claim a full acceptance matrix passed from a single smoke run.

## Vertical Slice Delivery

Use [VSD scenarios](../fixtures/vsd/README.md) for routine execution, decomposition, dependency ordering, justified parallelism, ownership conflict, delegation contracts, failed gates, local-only status, blocking, high risk, non-web usage and exceptions. Give the model only scenario prompts; keep rubric judgments separate. Planning-only evaluations can prohibit execution/delegation without prohibiting the model from proposing it. Observe policy/skill reads and actual decisions, not only self-reported loading.

Run fresh individual sessions when evaluating a case, or label a combined batch as a smoke test. Keep native settings/model stable; disable hooks and external integrations for controlled sessions without suppressing global instructions/skills. Record partial answers as partial, runtime quota/access failures as unavailable, and software fixture checks separately from model behavior. Do not claim native parallel-writing/worktree integration from read-only planning answers. No baseline improvement claim is valid without a controlled baseline comparison.

## Architecture and review capabilities

Use the [mapping/role fixture rubric](../fixtures/architecture-review/evaluation.md) with the [clean fixture](../fixtures/clean-review/README.md). Omit rubrics from model input. Evaluate explicit skill invocations and ordinary arguments; distinguish native `/review` aliases from the harness skill by source/tool-read evidence. Preserve before/after fixture snapshots, scan private outputs for a synthetic secret canary, and record actual Mermaid parser/renderer availability. Do not treat stub renderer tests or correct-looking source as actual syntax validation. Missing runtime quota is unavailable evidence. Pack profile activation, collision/refusal and upgrade preservation use existing deterministic suites.
