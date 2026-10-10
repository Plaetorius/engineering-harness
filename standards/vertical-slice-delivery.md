# Vertical Slice Delivery

Optimize for verified, integrated capabilities, not code volume or agent activity. A slice delivers a meaningful user or system outcome through all necessary components, with observable acceptance criteria. Do not split implementation exclusively into technical layers or defer all tests until the end. Split a large capability into smaller demonstrable outcomes when feasible; one large feature is not automatically one bounded slice.

## Choose proportionately

Routine, low-risk work proceeds directly with focused verification; no slice document or delegation ceremony is required. For substantial tasks, inspect the system and define bounded capabilities, dependencies, contracts and integration order before implementation. Classify risk by blast radius and failure consequences, not file count. A tiny security or correctness change may be high-risk.

For high-risk work, identify invariants and failure modes, require relevant negative, edge and regression tests, and consider independent design/security/correctness review. Reference checks or additional validation may be needed: tests authored by the implementation owner alone are not independent assurance. Avoid concurrent mutation of sensitive shared state. This includes authorization, payments, migrations, concurrency, numerical correctness and widely shared contracts; it does not mandate any particular technology.

Exceptions include small tasks, research, architectural exploration, shared foundations and inseparable system-wide refactors. Document why slicing would be artificial and use a suitable bounded plan with verification. Foundations can be prerequisite work without pretending they are a complete user capability. Do not continue an unsafe or blocked slice merely to finish it.

## Specify and schedule

Use the [slice template](../templates/slice.md) within the existing task plan; no task database is needed. For work that spans many steps or sessions, keep the plan, decisions and evidence in a file in the workspace, not only in the conversation, so they survive context compaction and handoff. Record a stable ID, outcome, scope/non-goals, dependencies, affected components/contracts, acceptance criteria, verification requirements, risk, one accountable implementation owner and current status. Identify the integration coordinator and intended baseline. Unless delegation is explicitly assigned, the primary agent owns implementation and integration; do not leave ownership unassigned merely because a plan is hypothetical. Add evidence and limitations as work proceeds; do not record progress from a completion claim alone.

Before assignment, identify dependency edges, shared mutable resources, unstable interfaces, conflicting files and integration order. Use a small dependency graph only when it clarifies readiness. A dependency can be an available contract or an explicitly approved test double; a test double does not establish integration correctness. Agree shared contracts before delegation. No two owners independently redefine the same contract.

Prefer finishing and integrating active work before expanding work in progress. Start conservatively and adjust concurrency to dependency structure, resources and observed progress; there is no universal worker count. Sequence dependent work, unstable shared interfaces, competing schema/authorization changes or work whose coordination costs exceed its benefit. Independent capabilities may proceed concurrently when contracts, files and resources can be isolated and integration order is understood. Parallel research, test design or review is distinct from simultaneous code modification.

## Lifecycle and evidence

`Specified → Ready → In Progress → Locally Verified → Integrated → Accepted` describes evidence-based milestones, not an automatic state machine. Record regressions in status when new evidence invalidates an earlier gate.

| Status | Required evidence |
| --- | --- |
| Specified | Outcome, scope, acceptance criteria and dependencies are defined. |
| Ready | Upstream dependencies are available and interfaces sufficiently stable, or approved test doubles permit independent development. |
| In Progress | One implementation owner is accountable for all necessary components and tests. |
| Locally Verified | Intended behavior and local acceptance criteria are demonstrated; applicable static/behavioral checks pass, relevant negative/edge cases are covered, and no unexplained failure remains. Record unexecuted checks and limitations; incomplete mandatory local checks prevent this status. |
| Integrated | Changes are incorporated into the intended baseline; combined integration/regression checks confirm compatibility and parallel changes do not conflict. Evaluate relevant data/deployment implications. Local passing results alone do not establish this status. |
| Accepted | Required verification and relevant security/correctness reviews are complete; the integrated outcome is demonstrably usable or independently verifiable, limitations/deferred work are documented, and the final diff has no unexplained unrelated changes. |

Additional outcomes: **Blocked** (name the dependency/uncertainty and resume condition), **Failed verification** (record the failing gate and evidence), **Needs rework** (state the unmet criterion), and **Cancelled or superseded** (record reason/replacement ID). They are not completion states. Retain the last achieved milestone when helpful. Acceptance never follows automatically from an agent report or locally passing tests.

Never mark Accepted when mandatory checks failed, could not run, or were skipped without explicit approval. An approved waiver must name the check, reason, approving authority, residual risk and substitute evidence; it is not a passing check. The software runner continues to report failed/skipped required checks honestly. A failing mandatory requirement remains a blocker unless its requirement is explicitly revised by an authorized decision.

## Delegate through native capabilities

Use the runtime's existing delegation facilities when useful and permitted; if they are unavailable, proceed sequentially or report the limitation. Do not change permissions, models or runtime configuration merely to enable delegation. The primary agent remains accountable for coordination and truthful status reporting.

Every delegated implementation assignment includes:

1. Slice ID/objective, scope and non-goals.
2. Relevant files, architectural constraints and allowed modification scope.
3. Interfaces, dependencies, readiness evidence and shared mutable resources.
4. Acceptance criteria, risk/invariants and required checks.
5. Implementation owner, integration coordinator, intended baseline and integration responsibilities.
6. Expected return: changed behavior/files, actual checks and evidence, lifecycle status, unresolved issues and limitations.
7. Escalation conditions and work isolation.

For simultaneous writers, prefer separate Git worktrees or equivalent isolated workspaces. Do not permit uncontrolled concurrent edits to one working tree. Verify each workspace's actual baseline, relevant instructions, active profile, checks, shared resources and file ownership before editing. Worktrees isolate files, not databases, services, ports or other external mutable state. Avoid incompatible concurrent migrations. Do not create worktrees for trivial read-only support tasks. If isolation is unavailable, serialize writes.

Use one accountable coordinator to integrate authorized changes and run combined checks; native worktree creation does not authorize commits, merges, pushes, deployments or destructive cleanup. In an existing target working tree, incorporation and verification can establish integration without a Git commit. Record the actual baseline; do not call a separate workspace integrated merely because its patch is ready.

Escalate when dependencies are unavailable, a shared contract must change, ownership conflicts arise, criteria are ambiguous, invariant correctness cannot be established, significant out-of-scope work is needed, or repeated failures yield no new diagnostic evidence. Reassess with the debugging workflow rather than making endless speculative fixes. A blocked slice stays blocked until its resume condition is satisfied; other ready work may proceed safely.

Model tiers are optional guidance, not a mandate, and never authorise changing models or runtime configuration. When several tiers are available and delegation is permitted, route by task rather than habit: bounded, verifiable work (extraction into a schema, search, mechanical checks) to the cheapest sufficient tier, batched where possible, with deterministic code doing arithmetic and comparison; orchestration to a middle tier; the deepest tier only to adjudicate a short explicit list of open conflicts, not to read raw material. A tier escalates only with a stated reason (a gap, a disagreement, low confidence), and delegated output is verified against its source before it is relied on.

## Verification and packs

Use existing repository checks and the harness verification runner, not a second test system. Resolve an active profile with `project inspect`, discover checks with `check list`, and execute authorized checks with `check run --execute` (optionally `--check pack:check`). Profile-required checks still apply when selecting a subset. Associate report paths, commands, tested revision/workspace and criterion-level evidence with each gate. No profile is required for VSD: direct repository commands and their results are valid evidence.

The runner reports software results, not slice lifecycle or human acceptance. A successful report does not prove untested criteria, independent review, integration or usability. Optional skipped checks still need honest reporting. Packs may add domain-specific checks and acceptance requirements; project/slice requirements cannot silently weaken core gates or bypass trust/approval boundaries. Applicable integration verification must run on the combined target baseline, not only the implementation workspace.
