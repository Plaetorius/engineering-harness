# Frontend behavior

Use semantic controls, keyboard navigation, visible focus and accessible names. Cover loading, empty, success and error states. Preserve established design tokens and component patterns; don't redesign unrelated screens.

Keep state at the smallest shared owner and distinguish server state from local interaction state. Avoid effects for derived data. Handle stale responses, cancellation and duplicate submission where behavior depends on them. Validate important flows in a browser when available; static checks don't prove interaction or layout.

Enforce authorization on the server even if the interface hides controls. Prevent sensitive data from being serialized into client props or caches.
