# PostgreSQL and data changes

Protect invariants with suitable constraints, transactions and isolation. Explain races between reads and writes; a preflight uniqueness check alone does not enforce uniqueness. Design idempotency keys and transaction boundaries around duplicate delivery and partial failures.

For migrations distinguish additive changes, backfills and destructive cleanup. Estimate table size, lock behavior and rollback/data recovery; never assume reversing DDL recovers deleted data. Use expand/backfill/contract when compatibility requires it. Obtain approval before an irreversible production step.

When RLS applies, test real application roles and tenant isolation; privileged credentials can bypass policies. Cover SELECT and writes, including ownership/tenant changes. Review indexes against actual query patterns, not hypothetical scale. Use schema-local conventions and the repository's migration tooling.

On Supabase use the new API keys (publishable `sb_publishable_...`, secret `sb_secret_...`), never the deprecated legacy `anon`/`service_role` JWT keys; the secret key is a privileged credential that bypasses RLS and stays on the server. See the web workflow for the full rule.
