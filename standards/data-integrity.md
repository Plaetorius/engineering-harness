# Data integrity

Identify ownership and authorization at every mutation boundary. Preserve invariants under concurrent writes; use atomic operations, constraints or transactions appropriate to the storage system. Establish retry and idempotency semantics. Test denial, partial failure and competing writes when relevant.

Plan schema and format changes for old and new readers, rollback and recovery. Obtain authorization for destructive or production actions. Load storage-specific standards only from an explicitly active pack.
