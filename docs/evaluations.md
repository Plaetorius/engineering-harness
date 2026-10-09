# Evaluation evidence

Automated installer and structural tests exercise deterministic safety and reference resolution. They do not establish that a model obeys instructions or that the harness improves cost, latency or defect detection.

The [runtime protocol](../tests/discovery/manual-cli-protocol.md), [six task fixtures](../tests/fixtures/README.md) and [private rubric](../tests/fixtures/evaluation-rubric.md) define repeatable manual evaluation. Baseline comparisons are unrun until recorded otherwise. Store transcripts privately; only sanitized findings belong here.

## Local implementation record — 2026-10-08

Installed on macOS arm64 with Codex 0.161.0 and Claude Code 2.1.293. Self-verification passed: 43 installer tests, 5 structural/fixture tests, shell syntax checks and the Skill Creator metadata validator for all four skills. The intentionally broken fixture still reproduces its known failure as an expected structural test. CI is configured for macOS/Linux but has not run remotely.

The host installation has two core links and eight skill links pointing to one canonical checkout. Doctor passes; repeated install preview has no changes. Claude settings were compared to the private pre-install backup after removing only the approved new subtree: all unrelated values matched. Backup permissions are 0600. A source-routing correction was recorded by a private provenance refresh without changing the links or settings.

## Native discovery evidence

| Check | Codex | Claude Code |
| --- | --- | --- |
| Core/global paths resolve | Pass | Pass |
| Fresh session reports exact global heading without being supplied it | Pass, normal user config and controlled config | Blocked by weekly usage limit |
| Shared skills available | All four named; all four source manifests read during explicit invocation | All four present in fresh-session runtime initialization metadata |
| Project AGENTS coexists with global core | Pass, synthetic project marker | Configured both-mode; model observation blocked by limit |
| Coexisting project CLAUDE | Codex sees AGENTS marker and does not report CLAUDE marker | Not executed after quota failure |
| Canonical web profile accessible | Pass, observed source read after routing correction | Not model-verified |

Claude initialized successfully enough to emit skill metadata, then returned a weekly-limit error before responding to the task. No attempt was made to switch account, credentials or paid provider. Claude smoke tools, non-managed hooks and external MCP were disabled for that invocation; model session persistence was disabled. Effective managed policy, import deduplication and alternate-home live sessions remain untested. Codex's first smoke used ignored user config; its repeat used normal user config and passed. This current Codex app session also received the installed protocol when it changed, providing additional host-side discovery evidence.

## Codex behavioral fixtures

Fresh sessions used the existing CLI default model selection, disposable fixture directories, read-only sandbox for plan/review cases, and workspace-write sandbox for two edits. Each prompt supplied only the fixture task and applicable skill name, not the evaluation rubric. No delegation or external services were requested. Raw logs and fixture paths remain in ignored private `.local/` evidence.

| Fixture | Observed outcome | Changed files | Seconds |
| --- | --- | --- | --- |
| Routine UI | Correct label; source inspection; no architecture rewrite | `component.tsx` only | 24.57 |
| Endpoint authorization | Identified cross-owner disclosure at route lines 4–5; concrete negative test | None | 22.58 |
| API design | Validation, workspace ownership, transaction/idempotency and provider duplicate-delivery limitation; no forced client/scaffold | None | 41.02 |
| Database migration | Identified unsafe drop at SQL line 2; compatible rollout, old-writer race and required production approval | None | 47.46 |
| Seeded diff | Identified zero-to-one regression at target `counter.ts:2`; fix and test | None | 18.35 |
| Repeated failing test | Reproduced `-1900 != 80`, corrected percentage units; regression and extra boundaries passed | `example.py` only | 31.19 |

All four skill source reads were observed. The final failing-test result was independently rerun by the outer evaluator and passed. Read-only tasks made no fixture changes; edit tasks changed only the intended source. No unrelated defects were reported in the two seeded review tasks; this is a small smoke sample, not a false-positive rate estimate.

The first routine run (19.12 seconds) changed only the label but could not locate the profile, revealing ambiguous global resource routing. The protocol was corrected with explicit CLI discovery paths and source resolution. The rerun actually read the canonical web profile and retained the same minimal edit. Only this affected case was repeated after the correction.

## Remaining evidence

- Claude skill invocation, core/project behavior and all six behavioral tasks after quota availability returns.
- Bare-agent baselines and repeated, model/version-controlled performance comparisons. No cost/latency improvement is claimed.
- Live alternate homes, nested instruction behavior, disabled built-in support and import/symlink deduplication.
- Linux execution and remote CI results, and separate cloud/remote bootstrap if requested.
- Public-release license choice and full scanner/history/artifact audit. A local targeted credential-signature/personal-path scan passed for the 64 release-visible files; dedicated secret scanners were unavailable, and the new repository has no commits/history. Private logs are ignored. This does not clear the project for public release.

## Modular refactor verification (2026-10-08)

The approved modular refactor passes 70 local automated tests: 43 existing installer tests, five discovery/structure tests and 22 new modular tests. The new cases cover pack discovery without execution, schema/path rejection, explicit external trust, two-pack isolation, shared native skill targets, collisions, modified-link preservation, profile approval drift, removed-source deactivation, rollback/retry, journal confinement, named command cwd, success/failure/skip/launch-error/timeout and required-check gating. `scripts/verify` executes all three suites.

Global install preview required only source-hash refresh, which was applied. Global modular doctor passed all two instruction/eight skill links and validated the built-in web pack. No runtime settings were changed by this refactor. The adapter contracts target the previously audited Codex 0.161.0 and Claude Code 2.1.293. Earlier behavioral evaluations are historical evidence for the original content, not fresh model evaluation of this refactor. Claude model evaluation remains limited by its previously observed quota; this update proves canonical native discovery paths and filesystem isolation through automated fixtures, not renewed model adherence. Linux CI and live new-pack invocation in both models remain unexecuted.

## Vertical Slice Delivery (2026-10-08)

` scripts/verify ` passes 78 tests: 44 installer, eight discovery/resource and 26 modular tests. The additions verify both adapters' canonical policy/skill references, evaluation-fixture integrity and portable template routing, plus mandatory failure, unavailable named command, subset-selection and CLI nonzero gates using the existing runner. All four skills pass Skill Creator metadata validation. These checks do not establish model compliance or lifecycle transitions: there is no runtime state machine.

A read-only Codex 0.161.0 combined smoke session covered the 13 VSD fixture prompts without supplying their rubric. Hooks/apps and delegation execution were disabled for controlled planning; sandbox was read-only, native global instructions/skills remained available, and no model was pinned. Tool/source evidence confirmed reads of `plan-feature`, the VSD standard and architecture guidance. The answers demonstrated direct routine handling, bounded decomposition, dependency readiness, isolated parallelism, refusal of conflicting shared-contract writes, a delegation contract, failure/blocked handling, separation of local verification from integration, risk by consequences, non-web usage and the exploration exception. This is a smoke observation, not a fresh-session matrix or improvement estimate.

The combined capability-planning answer omitted per-slice risk/ownership detail, so it was scored partial. A fresh individual capability case after a planning-skill refinement supplied bounded grant/revoke/history outcomes, scope/non-goals, dependencies, criteria, risk and statuses, but left owners TBD. The final policy/skill now defaults ownership to the primary agent unless a specific delegate is assigned; that final clarification has not been model-reevaluated. Do not claim complete behavioral conformance. No reference/control baseline or actual parallel-writing/worktree integration was evaluated.

Claude Code 2.1.293 attempted the same controlled planning prompts with hooks disabled, empty strict MCP configuration and read-only tools in plan mode. It returned its weekly quota limit, so its VSD behavioral evaluation is unavailable. Both real adapters were separately inspected and resolve the same updated canonical core, four skills and VSD standard; fixture installation tests also prove routing without mutating the host. CLI version/help and official native subagent/worktree documentation were checked; feature availability is distinct from successful live delegation.

Raw prompts, answers and runtime outputs remain in ignored private `.local/` evidence. No credentials were copied, project files changed by model sessions, commits created, packs modified or settings persisted. Linux CI remains unexecuted. Global provenance refresh follows the authorized installer path and preserves existing links/settings.

## Architecture mapping and role-aware review (2026-10-09)

The local suite passes 93 tests: 48 installer, 13 discovery/helper and 32 modular tests. New coverage includes upgrading the four-skill installation while preserving legacy links, conflict refusal and failed-upgrade rollback; preserving edited Claude settings and the original backup/rollback record; optional reviewer manifest/path/metadata validation, core/cross-pack conflicts, activation/deactivation and fingerprint drift; and conservative renderer input, unavailable-tool fallback, strict configuration and failure reporting. Renderer protocol tests use a stub subprocess and are not evidence of real Mermaid syntax validation. Mapping/review/compatibility skill metadata validators pass. No new verification runner or orchestration service was added.

Codex 0.161.0 used the installed `$architecture-map` in a controlled read-only fixture session to produce overview, scoped component/depth, sequence and data-flow Mermaid views. It correctly identified the in-process store, followed verifier/store success/error paths, excluded unrelated inventory from auth scope, treated verifier internals as unknown, and did not promote the unused queue dependency or illustrative deployment configuration into runtime topology. Source/skill reads were observed. Mermaid source remained parser-unvalidated because neither Mermaid nor mmdc is installed.

A second Codex session used `$review` for six requested core roles, plan review, an explicit supplied-file diff baseline, a clean implementation and an unknown role. It read all selected profile documents, found the seeded authorization, destructive migration, inaccessible-name and forbidden-dependency defects with locations/corrections/checks, avoided measured performance claims, returned zero findings for the bounded clean fixture and reported the unknown role unavailable. This was a shared-context multi-role smoke evaluation, not independent reviews or a controlled performance comparison.

Claude Code 2.1.295 successfully completed mapping and security-review evaluation this time; earlier quota limitations are historical. Native initialization advertised architecture-map, review and review-diff in skills/slash commands, and the response resolved the requested scope/view/depth and role/target/scope. It produced the actual sequence and found missing object authorization. Its first review also severity-rated weakly supported missing mechanisms. The canonical skill was tightened to keep unknown host behavior/absent mechanisms as coverage questions unless an evidenced failure path supports a full actionable finding. A fresh `/review security-engineer --target=code` session then produced the full authorization finding and left contract/typing questions unranked, without the initial generic logging/rate-limit criticism. It still overstated invalid-token behavior in its strengths despite the injected verifier being unknown; the final workflow now explicitly applies evidence standards to summary/strength claims as well. That final clarification has not been model-reevaluated. Do not claim complete behavioral conformance.

All model sessions used disposable synthetic fixtures, read-only tools/sandbox, disabled hooks and external integrations, no delegation, and existing model selection. Before/after file hashes matched, and synthetic credential canaries were absent from captured outputs/events. Raw artifacts remain ignored in `.local/`. No application execution, dependency installation or public transcript export occurred. Real renderer/parser validation, broader fresh-case matrices, live custom-pack-role review and Linux CI remain unexecuted.

The approved global upgrade added architecture-map and review links in both native homes (two core plus twelve skill links). Existing review-diff remains a compatibility entry point to one canonical review workflow. Installation detected later Claude settings edits; the explicit link-only preserve-settings option retained current settings bytes and the original guarded rollback backup. Uninstall still refuses automatic restore of edited settings; no permissions/model/hook configuration was changed by the installer. Doctor with preserve-settings reports this retained drift while checking canonical links. Native alias resolution was successful for the audited Claude version; other versions must verify the loaded source or use review-diff with the same logical parameters.
