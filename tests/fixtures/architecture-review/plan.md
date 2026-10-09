# Document access change

Serve documents to authenticated callers. Preserve owner-only access: other authenticated users must receive a denial. Preserve all existing data and ownership during schema changes. Keep the domain independent of transport.

Verification proposed: only a successful owner request. Negative authorization and migration compatibility tests are not yet planned.
