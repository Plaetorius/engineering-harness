---
name: eval-driven-development
description: Define how a behaviour will be measured before building it, keep that measurement honest (held-out data, recorded outputs, baselines, hallucination counted as failure), and report measured results with their limits. Use for anything whose output is extracted, generated or judged (LLM extraction, classifiers, parsers, ranking), where unit tests alone cannot say whether it works.
---

Interpret ordinary invocation text as the behaviour or feature to evaluate, optionally `--define`, `--run`, or `--report`. With none, infer from the task: new behaviour -> define first; existing work -> run and report. Evaluation is not a ceremony for routine changes: skip it for code with exact, deterministic expected outputs that ordinary tests already pin.

Inspect first: repository instructions, existing tests and evaluation code (reuse them; do not build a second system), available fixtures and answer keys, and any data provenance or licence manifest. State what will be measured, on what data, and how a failure would be recognised.

## 1. Define before building
Write down, in the repository next to the code, before implementing:
- **Capability checks**: what the new behaviour must do, each with an observable pass/fail and the data it runs on.
- **Regression checks**: what must keep working, with a recorded baseline.
- **Cost and limits that matter**: for model-backed work, tokens or time per item, and the failure modes that would be unacceptable (a confident wrong value is worse than an abstention).
Prefer **code graders** (exact comparison against an answer key, constraint checks, round-trip checks) over model graders; use a model grader only for open-ended output, with a written rubric, and a **human grader** for anything consequential or security-relevant. Never let the system that produced an answer grade it alone.

## 2. Keep the measurement honest
- **Split the data by role.** A *dev* set may be used to tune rules, prompts and thresholds. A *sealed* set is written or chosen blind to the implementation, scored once as a baseline, and not tuned against. Once a change is motivated by what the sealed set revealed, say so: from then on its score is a post-fix number, not independent. Plan a fresh blind set for a clean final figure.
- **Answer keys come from outside the implementation** (a person, an independent agent that has not seen the code, or the source document), and are checked for errors; an expectation that disagrees with a stated convention is a bug in the key.
- **A value where the key says "not stated" is a failure** (hallucination), as is an extra item that matches nothing. Do not score only what was found.
- **Score per field and per document**, not one blended number; report which fields drive the average.
- **Record model outputs as fixtures** so re-runs are free, deterministic and reviewable; record which model, prompt version and date produced them. Re-run live only when the prompt, model or input changes.
- **Stochastic components** (LLM calls) need more than one trial when reliability matters: *pass@k* (at least one success in k tries) says whether it can work, *pass^k* (all k succeed) says whether it can be relied on. Report which, and also malformed or incomplete outputs as their own failure class.
- **Datasets carry provenance**: source, licence or terms checked (date), hash, and whether it may be redistributed. Real public data first, generated data to cover traps the real data lacks. Keep downloaded files untrusted and out of version control.

## 3. Run and gate
- One command runs everything cheap and deterministic; slow or expensive evaluations are opt-in and say so.
- A **baseline file** records the last accepted numbers; a run fails when a metric falls more than a stated tolerance below it. Update the baseline deliberately, with the reason, never to make a run pass.
- Keep evaluations fast enough that they are actually run, and version them with the code they measure.
- For sliced work, evaluation results are evidence for the gates in [Vertical Slice Delivery](../../standards/vertical-slice-delivery.md) (local results do not establish integration), and the measurement rules sit with the [verification standard](../../standards/testing.md).
- Mandatory failures block acceptance. Do not widen a tolerance or drop a case to turn a run green; if a case is wrong, fix the key and say why.

## 4. Report
State: what was measured, on which data (dev or sealed, with the independence caveat), results per field, the failures that matter with concrete examples, token/time cost, what was **not** measured, and what the next evaluation should be. Distinguish measured results from expectations. A weak number reported plainly is more useful than a strong number with hidden qualifications.

Worked example in this repository: `../second-reader/tests/` (`evalkit.py` scoring, `eval_heldout.py` dev/sealed sets with recorded model outputs, `run_eval.py` baseline and tolerance, `fixtures/open/manifest.json` provenance, `BASELINE.md` honest labelling).
