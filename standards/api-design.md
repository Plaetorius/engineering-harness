# API boundaries

Define request validation, success response and stable error contracts using existing conventions. Reject malformed/unsupported input before side effects. Preserve callers' expectations for status codes, pagination and serialization; don't leak database errors or sensitive fields.

Authorize the route and the object. Decide explicitly whether retries require idempotency, writes require transactions, and expensive/abusable operations require rate limits. Place limits at the actual shared boundary with a concrete actor/key and storage strategy; per-process counters are inadequate across replicas.

Set timeouts and cancellation for integrations; retry only operations whose semantics support it. Use the existing integration client unless a concrete capability requires a change. Test failures as well as successes and document changed contracts.
