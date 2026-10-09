---
name: plan-feature
description: Plan a new subsystem, cross-cutting feature, migration or explicitly requested design before implementation. Routine local edits can proceed directly.
---

For substantial work read [Vertical Slice Delivery](../../standards/vertical-slice-delivery.md). Plan meaningful bounded capabilities across necessary components; split large outcomes further when feasible. Use the compact slice specification: outcome, scope/non-goals, dependencies/contracts, criteria/checks, risk, one owner, status and target baseline. Preserve these fields even in a short plan. Default implementation/integration ownership to the primary agent unless a specific delegate is assigned. Identify safe parallel opportunities and file/resource conflicts before delegation; justify foundations or inseparable work. Keep routine tasks direct.

Inspect relevant instructions, architecture, call sites and tests. Read [architecture](../../standards/architecture.md) for boundary changes and [database](../../standards/data-integrity.md) for migrations. Load the project profile and explicitly active pack guidance.

Define the goal, current behavior with source references, scope/non-goals, observable acceptance criteria, affected interfaces/schema, key alternatives and trade-offs, risks, test plan and incremental implementation sequence. Label source-verified facts separately from assumptions. Size the plan to the change.

For high-risk work challenge a consequential assumption with a concrete failure scenario; use an independent reviewer/session when available and appropriate. Do not impose repetitive review passes or model choices.

Output a reviewable plan and material unresolved blockers; do not create implementation code during a planning-only request. Stop for a missing decision that changes correctness, or before an unapproved irreversible action. If implementation is already authorized, transition after the plan's blocking decisions are resolved.
