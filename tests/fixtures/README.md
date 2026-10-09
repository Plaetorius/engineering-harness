# Behavioral evaluation tasks

Copy one fixture into an isolated temporary working directory. These are synthetic examples, not deployable apps. `endpoint-auth` and `failing-test` deliberately contain bugs; `seeded-diff` contains a proposed regression. Do not include the evaluation rubric in the agent's prompt.

Use each `task.md` verbatim for comparable manual runs. Record CLI version, model, loaded instructions/skill, permitted tools, wall time, interventions and outcome. Baseline runs use an isolated uninstalled user home; harness runs use an isolated installed home. Avoid host hooks/plugins and credentials in exported results. Authentication should be handled through an authorized runtime, never copied into fixtures.

The intentionally failing test is checked by the harness structural suite as an expected reproduction. It must not make the harness self-tests fail.
