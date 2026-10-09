# Interface audit checklist

Use what applies; answer each item from the rendered result. Items are grouped in priority order.

## 1. Accessibility
- Normal text reaches 4.5:1 against its background; large text and meaningful non-text elements (input borders, informative icons, focus rings) reach 3:1.
- Every interactive element shows a clear focus indicator, and sticky bars, banners or overlays never cover the focused control.
- Tab order matches visual order; no keyboard traps; a skip link reaches main content; after a route change focus moves to the new content.
- Headings step down one level at a time; landmarks and real buttons and links are used instead of clickable containers.
- Decorative icons next to visible text are hidden from assistive technology; meaningful icons and images have a text alternative; icon-only controls have an accessible name and expose selected, pressed or expanded state.
- Meaning never rests on color alone; add text or an icon.
- Text can scale and spacing can increase without truncation or overlap.
- Animation honors `prefers-reduced-motion`; auto-rotating content can be paused and stops on focus.
- Drag, swipe or other path-based gestures have a single-pointer or keyboard alternative.
- Pointer targets are at least 24 by 24 CSS px, and 44 by 44 wherever feasible.
- Repeated help mechanisms stay in the same place; information already entered in a process is reused, not requested again.
- Authentication allows password managers and paste and offers a path that is not a memory or puzzle test.
- A changed count or status is announced as a complete phrase through one polite live region, without moving focus.

## 2. Touch and interaction
- Targets of 44 by 44 (platform guidance up to 48), expanded beyond the visible icon when it is smaller, with at least 8 px between neighbors.
- Primary actions work by tap or click; hover only adds extra information.
- A pressed state appears within about 100 ms; buttons disable and show progress while an async action runs.
- Clickable elements look and feel clickable (cursor, affordance); small icons do not demand pixel-precise taps.
- Gestures do not collide with system gestures or main scrolling; swipe actions show an affordance; drags start only after a small movement threshold.
- Critical actions always have a visible control, never gesture-only access.

## 3. Perceived performance
- Images are modern formats, responsive, below-the-fold ones lazy, and every image reserves its space to prevent layout shift.
- Fonts avoid invisible text and layout jumps; only critical fonts are preloaded.
- Above-the-fold content ships first; non-hero components load on demand; third-party scripts are deferred or removed.
- Skeletons replace long blocking spinners; input feedback arrives in about 100 ms; per-frame work stays near 16 ms.
- Long lists (50 or more rows rendered together) are virtualized; high-frequency events are debounced or throttled.
- Offline and slow-network states are messaged, with a lighter fallback when sensible.

## 4. Style consistency
- One visual language across all pages; shadows, blur and radius belong to that style; blur marks background dismissal, never decoration.
- One icon family with one stroke width and a fixed size scale; no emoji as structural icons; brand logos come from official assets.
- A single elevation scale; hover, pressed, disabled and focused states are distinct yet on-style.
- Light and dark variants designed together; prefer native or system controls unless branding needs otherwise.
- One primary action per screen, secondary actions visibly subordinate.

## 5. Layout and responsiveness
- The viewport allows zoom; design starts at phone width and scales up with consistent breakpoints.
- No horizontal scroll at 320 CSS px; content reflows.
- Body text at least 16 px on phones; line length about 35 to 60 characters on phones and 60 to 75 on desktop.
- A 4/8 px spacing scale with defined tiers; consistent maximum content width; a defined z-index scale.
- Fixed headers and bars reserve space so content is not hidden, respect device safe areas, and the page uses dynamic viewport units instead of raw 100vh on mobile.
- Landscape stays usable; core content comes first on small screens; avoid nested scroll regions.
- Hierarchy comes from size, spacing and contrast, not color alone.
- Compact labels (badges, chips) wrap before they shrink, keep essential text available, and expose any overflow as an operable control.

## 6. Typography and color
- Body line height about 1.5 to 1.75; one type scale; weight reinforces hierarchy; headings and body have complementary personalities.
- Semantic color tokens (primary, error, surface, on-surface), never raw values scattered in components.
- Dark mode uses tuned tonal variants, not inverted colors, and its contrast is tested separately; borders, dividers and states stay visible in both themes.
- Scrims and overlays are measured against the real composed background.
- Prefer wrapping to truncation; when truncating, expose the full text. Long URLs and IDs wrap without breaking ordinary prose; short headings use balanced wrapping.
- Timers, prices and data columns use tabular numerals.

## 7. Motion
- Every animation shows cause and effect; at most one or two key elements move per view.
- Use transform and opacity, not width, height, top or left; motion must not cause layout shift.
- Durations come from shared tokens chosen by distance and context; entering eases out, leaving eases in, exits are shorter than entrances (around two thirds).
- Staggers are short (about 30 to 50 ms per item); transitions keep spatial continuity and consistent direction.
- Animations are interruptible, never block input, and rapid state changes cancel prior micro-interactions cleanly without depending on an animation-end event.
- Springs suit direct manipulation; avoid long fades that linger at low opacity.

## 8. Forms and feedback
- A visible label per field; helper text for complex inputs; required fields marked; related fields grouped.
- Validate when leaving a field, not on every keystroke; show a specific error below the field tied with `aria-describedby`; say the cause and how to fix it.
- After a failed submit, retain entries; with several errors, focus a linked summary at the top and keep inline errors; with one, focus the field.
- Correct input types, autocomplete and keyboard hints; phone-height inputs of at least 44 px; password show/hide where relevant.
- Submit shows loading, then clear success or error; toasts do not steal focus, are announced politely and dismiss after roughly three to five seconds; errors offer retry or another recovery path, and timeouts say so.
- Destructive actions are confirmed or undoable and separated visually; read-only differs from disabled; disabled looks disabled and is exposed as such.
- Long forms autosave; dismissing a sheet with unsaved changes asks first; multi-step flows show progress and allow going back.
- Empty states say what belongs there and offer the next action.

## 9. Navigation
- Back is predictable and restores scroll, filters and input; the stack is never silently reset.
- Every key screen has a URL for sharing; current location is highlighted; items carry both icon and label.
- Bottom navigation holds at most five top-level destinations; secondary items live in a drawer or overflow menu; large screens favor a sidebar; do not mix patterns at one level.
- Placement stays the same on every page; dangerous items sit apart from ordinary ones; unavailable destinations explain why.
- Modals are not primary navigation and always offer a clear dismiss; deep hierarchies get breadcrumbs.
- Search is easy to reach; badges are sparing and cleared after the visit.

## 10. Charts and data
- Chart type matches the data (trend, comparison, proportion); avoid pies beyond five categories.
- Palettes are color-blind safe, supplemented by pattern, shape or direct labels; data marks reach 3:1 and data text 4.5:1.
- Provide a table or text summary for screen readers; interactive elements are keyboard reachable; tooltips do not rely on hover alone.
- Legends near the chart (and toggling where useful), labeled axes with units and readable tick spacing, subtle grid lines.
- Charts simplify or reflow on small screens; loading uses a skeleton; empty and error states explain and offer retry; entrance animation respects reduced motion; large datasets are aggregated with drill-down; numbers and dates use the locale.

## Pre-delivery pass
- [ ] Screens viewed at 320 or 375 px, a tablet width and desktop; landscape checked where relevant.
- [ ] Light and dark themes each checked on their own, including borders, states and overlays.
- [ ] Reduced motion and largest text setting tried; nothing breaks.
- [ ] Keyboard-only run through the main flow; focus always visible and never covered.
- [ ] Targets sized and spaced; nothing hidden behind fixed bars or safe areas.
- [ ] Icons from one family, no emoji structure, tokens used instead of raw values.
- [ ] Forms: labels, hints, specific errors, summary focus after failure.
- [ ] Every user-visible string translated in all supported languages; longer text still fits.
- [ ] Automated accessibility and layout checks run, or their absence stated.
