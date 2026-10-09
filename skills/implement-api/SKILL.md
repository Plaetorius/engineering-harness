---
name: implement-api
description: Implement or change a backend endpoint, external service integration or domain boundary with explicit contracts, authorization and failure behavior.
---

When this boundary change belongs to a substantial slice, read [Vertical Slice Delivery](../../standards/vertical-slice-delivery.md), confirm its readiness, owner, scope and shared contracts, and implement the assigned outcome across all necessary components and tests. Escalate cross-slice contract or ownership changes. Return criterion-level evidence and actual lifecycle status; local completion does not establish integration or acceptance.

Prerequisites: requested behavior and repository context. Inspect existing routes, clients, validation, authorization and persistence patterns. Read [API guidance](../../standards/api-design.md) and [security guidance](../../standards/security.md). Load the project profile and explicitly active pack guidance.

Define the request/success/error contract and locate all callers. Validate boundary input, establish trusted identity, and authorize the action and target object/tenant. Keep secrets server-side. Preserve existing architecture; introduce an HTTP client or ports/adapters only for a concrete need.

Decide whether writes need transactions, retries need idempotency, integrations need timeout/cancellation, and abuse needs rate limiting with a concrete key and shared enforcement point. Explain an unnecessary mechanism briefly rather than adding scaffolding. Read [database guidance](../../standards/data-integrity.md) for data changes.

Implement the smallest coherent change, including success and relevant denial/failure tests and updated contract documentation. Discover verification commands from the repository and run proportionate checks.

Deliver behavior/contracts changed, authorization placement, failure semantics, tests executed and remaining risks. Stop if the identity/ownership contract is unknown or before an unapproved destructive migration/production action; don't invent a permissive authorization fallback.
