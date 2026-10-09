# Slice: <stable ID> — <capability>

## Outcome

Observable user/system result; explain why this is a bounded capability.

## Scope and non-goals

Included work across necessary components; explicit exclusions.

## Dependencies and contracts

Upstream slice IDs/readiness evidence, affected components, shared interfaces and mutable resources. Record approved test doubles and any file ownership conflicts. State safe execution/integration order and whether parallel work is justified.

## Acceptance criteria

Observable conditions, including relevant invariants and denial/edge/failure behavior.

## Verification

Required local checks and criterion evidence; integration/regression checks; risk-appropriate independent review/reference validation. Use existing repository commands or qualified pack check IDs. Name environment prerequisites and external-action approval needs. Distinguish mandatory checks from optional checks.

## Risk and ownership

Risk classification and consequences; one implementation owner; allowed modifications; integration coordinator; intended baseline; workspace/isolation; escalation conditions. A single agent may hold both roles.

## Status and evidence

Current status: Specified. Update only with evidence under the [shared policy](../standards/vertical-slice-delivery.md).

Record local results separately from target-baseline integration results: commands/check IDs, actual outcomes, report paths, revision/workspace, reviews and unexecuted checks. Record acceptance decision, known limitations/deferred work and approved waivers if any. For blocked/rework/cancelled work, record reason and resume condition or replacement ID.
