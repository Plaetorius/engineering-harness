# Architecture

Follow established boundaries. Use a service or domain module when behavior has multiple callers or business invariants need one owner. Use ports/adapters when testing, multiple providers or changeable infrastructure justify them; a single route does not require a hexagonal scaffold.

Separate transport validation from business authorization and persistence invariants. Name dependencies and failure ownership. Preserve compatibility for existing clients; design rollout and rollback for contract or schema changes. Account for timeouts, duplicate delivery and partial failures at external boundaries.
