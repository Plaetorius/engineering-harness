---
name: web-typescript-review
description: Review an explicitly activated web application pack for server/client boundaries, authorization, database isolation and interaction correctness.
---

Read [web workflow](../../workflows/web.md), [database guidance](../../standards/database.md) and [frontend guidance](../../standards/frontend.md) as relevant. Inspect actual versions, call sites and repository commands. Review concrete failure scenarios, including alternate mutation paths, private cache scope, privileged client access and critical interaction states. Run applicable profile checks only with execution authorization. Report findings with evidence and unexecuted checks; preserve core security and project constraints.
