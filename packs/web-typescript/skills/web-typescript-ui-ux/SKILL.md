---
name: web-typescript-ui-ux
description: Design, redesign or audit how a web interface looks, flows and meets accessibility needs, grounded in the rendered result. Use for new screens, "make it nicer or clearer" requests, UX reviews and accessibility passes; skip for backend logic, data modeling and non-visual changes.
---

Visual and usability claims need rendered evidence. Look at the real screens (screenshots at phone and desktop widths, or the running app) before judging, and again after changing. If nothing can be rendered, say so and limit findings to source-level observations.

## 1. Establish context

- Find the existing design system first: tokens, theme files, component library, project instructions. Existing rules win over this skill, and the user's words win over both. Respect frozen or owned areas; propose shared-token changes instead of editing them silently.
- Record in a sentence each: the product type, who uses this screen and in what situation (device, lighting, attention, time pressure, connectivity), the style the user asked for, and the one job the screen must do.
- Detect the stack from the repository (manifests, config), never assume it. Stack changes the available primitives, not the principles.
- Identify the two or three screens or flows that carry the product and spend effort there.

## 2. Set a direction before touching pixels

Answer these before choosing colors or components, and write the answers down where the repository keeps design notes (or in the reply when it has none):

- Product pattern: what structure fits this kind of page or flow (landing, dashboard, form flow, feed)?
- Style: one coherent visual language, chosen on purpose and applied everywhere. Mixing flat and skeuomorphic treatments, or several icon families, reads as unfinished.
- Three dials, each low, middle or high: how bold or asymmetric the layout is, how much motion, how dense the information. A dashboard wants high density and low motion; a marketing page the opposite.
- One distinctive move, specific to the subject, with everything around it quiet.
- Defaults to treat as warning signs, not plans: stock gradient heroes, glow blobs, emoji as icons, identical rounded cards, everything centered, an unconsidered system font. Do one only if the user asks.
- Tokens, not raw values: a small named palette (surface, text, muted text, accent, plus success/warning/danger), a type scale, a spacing scale and a radius/elevation scale. Neutrals are tinted deliberately; light and dark themes are designed together.
- If decisions must persist across sessions, keep a master note of tokens and rules with per-page overrides, and read it before generating anything new. Do not overwrite an existing one without the owner's approval.

## 3. Design for the actual moment

Tired, hurried or distracted people on a phone need one obvious primary action per screen, plain labels, large targets, the changing state (time left, status, count) where the eye lands first, and no dead ends. Every screen answers: where am I, what is the state, what do I do next. Show a realistic example state, not an empty shell.

## 4. Apply the rules in priority order

When time is short, higher items win. Details for each are in [the audit checklist](checklist.md).

1. Accessibility: contrast, focus visibility, labels, keyboard order, reduced motion, text scaling, focus never hidden.
2. Touch and interaction: target size and spacing, feedback on every action, no hover-only behavior, gesture alternatives.
3. Performance as perceived: stable layout, sized images, lazy loading, skeletons, fast feedback.
4. Style consistency: one language, vector icons, a single elevation scale, one primary action.
5. Layout and responsiveness: mobile-first, no horizontal scroll, readable measure, safe areas, spacing rhythm.
6. Typography and color: scale, line height, semantic tokens, tested dark mode.
7. Motion: meaningful, short, interruptible, compositor-friendly, consistent.
8. Forms and feedback: visible labels, specific errors beside fields, recovery paths, autosave, undo.
9. Navigation: predictable back, deep links, clear location, consistent placement.
10. Charts and data: right chart for the data, not color alone, text alternative, labeled units.

## 5. Report and change

For each finding record severity (blocks a task, hurts a task, polish), where (screen, element, file when known), what a person experiences, evidence (screenshot or measurement) and a specific fix. Separate confirmed problems from hunches needing a test; zero findings in an area is a valid result. Prefer fixing tokens and shared components over per-page overrides. All visible text goes through the project's translation mechanism in every supported language, planning for text 30 to 40 percent longer than English. Do not redesign unrelated screens.

## 6. Verify before delivering

Complete the pre-delivery section of the checklist: render at roughly 320, 375, 768 and 1280 px, in portrait and landscape where relevant, in each color scheme separately, with reduced motion and the largest text setting, and once using only the keyboard. Run the repository's automated accessibility and layout checks if they exist. Report what was viewed, measured and skipped, and any regression elsewhere.

## Provenance

Adapted from the `ui-ux-pro-max` skill (MIT). Its searchable datasets and scripts are not installed here; its priority ordering and rule coverage are restated in new words for web work. See [NOTICE](NOTICE.md).
