---
name: web-typescript-frontend-patterns
description: Decide how to structure React and Next.js App Router code: server/client boundaries, data and mutation flow, state ownership, forms, loading and error handling, and interaction accessibility. Use when adding or restructuring interactive UI behavior; skip for pure styling edits and backend-only work.
---

Read the repository's existing components, data layer and conventions before choosing a pattern. Match what is already there; this skill only fills gaps. Check the installed framework versions, because App Router, React and form-handling APIs change between releases.

## Shape components for reuse

- Prefer composition to configuration. A card, panel or list item that takes children (and optional named slots) outlasts one that grows a prop for every variation.
- For a widget made of cooperating parts (tabs, accordion, menu), expose a small family of parts that share state through a scoped context, and fail loudly with a clear message when a part is used outside its parent.
- When logic is reusable but markup is not, extract a hook; when markup is reusable but logic varies, pass a render function or children-as-function. Do not extract until a second real use exists.
- Small reusable hooks worth having: debounced value (for search-as-you-type), previous value, media query, and a data hook that exposes `data`, `error`, `pending` and `refetch`. Check what the repository already provides before adding any.

Concrete examples of each are in [pattern examples](patterns.md).

## Place the boundary first

1. Render on the server by default. A component becomes a client component only because it needs browser state, effects, event handlers or browser-only APIs.
2. Push the client boundary down to the smallest interactive leaf. A page that is mostly static should stay a server component with one small client island.
3. Props that cross the boundary must be serializable and must contain only what the browser is allowed to see. Select the needed fields on the server; never pass a whole database row or session object.
4. Server-only modules (secrets, privileged clients) must be impossible to import from client code. Use the framework's server-only marker where available.
5. A hidden button is not authorization. The server operation re-checks who the caller is and what they may do.

## Move data deliberately

- Read on the server where possible, close to the data, and stream slow parts behind Suspense so the rest of the page is usable.
- Writes go through one mutation path per intent (server action, route handler or operation runner, whichever the repository already uses). Do not add a second path that skips validation.
- Validate input at the boundary with a schema, return typed results, and map failures to user-facing messages from the translation files, not raw error text.
- After a write, revalidate or refetch the affected data instead of patching several caches by hand.
- Optimistic updates are for fast, rarely failing actions. Show the expected result immediately, and roll back with a visible explanation if the server refuses.
- Treat realtime messages as hints to refetch, not as trusted payloads. Refetch after reconnect, tab refocus and regained connectivity.
- Guard against stale responses, double submission and unmount during a request. Cancel or ignore results that no longer match the current input.

## Own state at the lowest sensible level

- Reach for a reducer plus a scoped provider when several fields change together by named events (steps of a wizard, a board with selection and filters). Split the provider into state and dispatch if consumers that only dispatch should not re-render.
- Prefer, in order: derived from props or server data; URL (search params, path) for anything a person might share, bookmark or go back to; local component state; a shared provider only when distant components truly need the same live value.
- Never store a value that can be computed from other state. Computing during render is simpler and cannot drift.
- Use effects only to synchronize with something outside React (subscriptions, timers, browser APIs, third-party widgets) and always clean up. An effect that sets state from other state is usually a bug in disguise.
- Server state (fetched data) and interaction state (is this menu open) are different things with different lifecycles; keep them apart.
- Keep timers that render time on a single shared tick source or a server-aligned clock, and show the same value everywhere on the page.

## Forms

- Use native form elements and a real submit path so Enter, autofill and assistive technology work without extra code.
- Every control has a visible label tied to it, hint and error text connected through `aria-describedby`, and `aria-invalid` when wrong.
- Validate on submit first, then on change after the first error. Never wipe what the person typed after a failure.
- Disable or guard the submit control while pending and say what is happening. Confirm success where the person is looking, not only in a console or a toast they may miss.
- Autosave long forms and show the save state in text. Warn before discarding unsaved work.
- Move focus to the first invalid field or to the error summary after a failed submit.

## Loading, empty and error states

Every data-driven view defines four states: loading (skeleton that matches the final layout to avoid shifting), empty (what belongs here and the one action to fill it), error (what failed, what to try, a retry that works) and success. Use route-level loading and error boundaries for whole pages and local boundaries around independent widgets so one failure does not blank the screen. Distinguish "not found" and "not allowed" from "something broke".

## Performance, only with evidence

Lists of about fifty or more rows that are actually rendered together deserve virtualization; below that, plain rendering is usually faster to build and to debug. Measure before optimizing: look at the actual bundle, render counts or the profiler. Typical wins are real: fewer client components, dynamic import of heavy rarely used widgets, correctly sized and lazy images, stable list keys, virtualization for lists that are truly long (hundreds of rows), and moving expensive work to the server. Memoization is a targeted tool for a measured re-render problem, not a default coat.

## Failure containment

Wrap independent regions in error boundaries (the framework's route-level error files for pages, a small boundary component for widgets) so a crash in one panel leaves the rest usable. A fallback names what failed, never prints a raw exception message to the user, offers a working retry, and logs details where the team can see them. Reset the boundary when the input that caused the failure changes.

## Interaction accessibility

- Use the right element: `button` for actions, `a` for navigation, `dialog` or a tested primitive for modals. Do not attach click handlers to generic containers.
- Dialogs trap focus, close on Escape, restore focus to the opener and name themselves. Route changes and async content updates move focus or announce through a polite live region.
- Everything reachable by pointer is reachable by keyboard in a sensible order with a visible focus indicator.
- Composite widgets (menus, comboboxes, listboxes) follow the standard keyboard model: arrow keys move the active option, Enter or Space selects, Escape closes, Home and End jump to the ends, and the active option is exposed to assistive technology. Prefer a tested primitive from the project's component library over hand-rolling one; see [pattern examples](patterns.md) for the minimum a custom one needs.
- Motion is optional: prefer CSS transitions, keep them short, and disable or reduce them under `prefers-reduced-motion`. Never rely on motion alone to convey state.

## Finish

Run the repository's own lint, typecheck and tests, then exercise the changed flow in a real browser when one is available: success path, error path, keyboard only, a narrow phone viewport. Static checks do not prove layout or interaction. State what was run and what was not.

## Provenance

Adapted from the React/Next.js patterns skill of the `everything-claude-code` project (README declares the MIT license; the fork this was read from carries no license file). Reworded, reorganized and fitted to this harness, with new examples. See [NOTICE](NOTICE.md).
