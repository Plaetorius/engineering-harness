---
name: debug-root-cause
description: Diagnose a reproducible bug, failed CI or recurring compiler/test failure using reproduction and competing hypotheses before changing code.
---

For a slice failure use [Vertical Slice Delivery](../../standards/vertical-slice-delivery.md) to retain scope and identify the failed gate. Reproduce and isolate within the current slice; escalate unresolved dependency, shared-contract or ownership problems and invariant uncertainty. Leave blocked or failing work explicitly incomplete; repeated failures without new evidence require reassessment.

Collect the failure, environment/version context and expected behavior; inspect relevant instructions and code. Read [testing](../../standards/testing.md) for verification and relevant domain guidance only as needed.

Reproduce with the smallest trustworthy command or input. Separate observations from hypotheses; consider competing explanations and choose a discriminating experiment. If reproduction is unavailable, report what evidence is missing and avoid presenting a guess as established root cause.

Trace the first incorrect state to its cause before fixing downstream symptoms. Implement the smallest safe fix and a regression test when appropriate. Run the reproduction and relevant checks again. After unsuccessful changes, reassess the hypothesis and environment rather than patch blindly; choose escalation from failure type, not an arbitrary retry count.

Deliver reproduction steps, observations, hypotheses tested, root cause/evidence, fix, regression coverage and actual validation results. Stop for missing essential evidence or before an unapproved destructive/production action.
