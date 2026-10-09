# Controlled VSD evaluations

[scenarios.json](scenarios.json) contains neutral task prompts and separate maintainer scoring criteria for the twelve required scenarios plus an exception case. Supply only the prompt to the model, never the rubric. Use fresh read-only planning sessions, the actual installed global protocol/skill discovery, stable model/runtime settings and no external services, user hooks or MCP integrations. Do not add expected slice/status rules to the task prompt.

Use the [existing runtime protocol](../../discovery/manual-cli-protocol.md), and record runtime/model/settings, source/tool-read evidence, actual answers, rubric decisions, elapsed time and unavailable cases. Runtime instruction self-report alone is insufficient. A combined batch can be a labeled smoke evaluation but does not replace fresh-case evaluation. Evaluate bare/control sessions separately if claiming a measured policy benefit. Keep raw transcripts under ignored `.local/`; publish only sanitized summaries. Do not copy credentials or initialize a task tracker.

Deterministic tests check fixture integrity, shared routing and existing software gate failures. They do not prove that an agent follows scheduling/lifecycle rules. Lifecycle is Markdown convention; no persistent transition engine is introduced just to test it.
