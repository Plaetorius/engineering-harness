# Web application suite v1

Apply the relevant parts when this stack is present or selected. Inspect package versions, router layout, server/client boundaries, database schema and repository commands before choosing framework-specific APIs. Verify version-sensitive details in official documentation when uncertain; this profile does not pin versions or require a migration.

- Next.js/React/TypeScript: keep server-only code out of client imports and serialized props. Validate and authorize Route Handlers, Server Actions and alternate write paths individually. Consider rendering/cache scope for user-specific data; do not share tenant/private responses through public caches. Use existing typed validation and error conventions.
- Supabase/PostgreSQL: distinguish request-scoped user clients from privileged server clients. Protect service-role keys. RLS is an additional trust boundary, not a substitute for understanding bypass behavior. Test object and tenant isolation under actual caller roles. Read [database guidance](../standards/database.md) for transactions and migration rollout.
- APIs/integrations: apply the core API and security standards. Choose idempotency, retry and rate-limit placement from real failure/threat scenarios; don't introduce Axios or a new layer by default.
- UI/Tailwind: preserve tokens, semantic controls and responsive states. Read [frontend guidance](../standards/frontend.md) for interaction changes.
- Vercel/GitHub: use repository CI and existing deployment commands. Account for function timeouts, shared rate-limit storage and environment-specific secrets. Preview deployment is an external action requiring authorization; no automatic push/deploy/migration.

Acceptance evidence: focused behavioral tests plus applicable lint/typecheck/build; browser checks for critical interaction; negative authorization/RLS tests for data boundaries; migration validation for schema changes. Discover actual commands from the project profile, repository instructions and CI. Report unrun checks honestly.


Use the existing HTTP client or native fetch; add Axios only for a concrete capability.
