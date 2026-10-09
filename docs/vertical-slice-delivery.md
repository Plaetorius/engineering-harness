# Delivering vertical slices

Vertical Slice Delivery (VSD) completes small, independently demonstrable capabilities across their necessary components. Substantial work uses the [core policy](../standards/vertical-slice-delivery.md) and [compact slice template](../templates/slice.md) inside its existing plan. A slice is an outcome, not a file list or technical layer. Small low-risk changes still proceed directly. Classify risk by failure consequences and blast radius: a one-line authorization change can need stronger controls than a large isolated presentation change.

Specify dependencies, shared contracts, one accountable owner, acceptance criteria and checks before implementation. Prefer completing and integrating ready work before adding more unfinished work. Use native delegation only when it benefits independent work. Concurrent writers need isolated workspaces and explicit file/resource ownership; research/review often needs no worktree. A worktree does not isolate shared services or data. Sequence unstable shared contracts and conflicting writes, not every independent activity.

The lifecycle is Specified, Ready, In Progress, Locally Verified, Integrated, Accepted. Record evidence for each achieved milestone; Blocked, Failed verification, Needs rework and Cancelled or superseded are not completion states. Local passing tests do not establish target-baseline integration. Integration does not automatically establish acceptance. Required checks and relevant risk-based review must complete; unavailable mandatory checks block acceptance. An explicitly authorized waiver is documented separately and does not turn a skip into a pass.

Use `project inspect` to resolve activated packs and project requirements, and `check list`/`check run --execute` for pack checks when applicable. Repository commands also work without a profile. Existing result reports are software evidence; they do not certify human criteria or lifecycle status. Packs may add relevant checks, but cannot silently weaken core gates. Record actual commands, outcomes, report paths, tested baseline/workspace, independent reviews, limitations and deferred work in the plan.

## Web example: bounded document sharing

A request for document editing, sharing and activity history is too broad to label one slice automatically. An existing editor and identity contract allow these bounded outcomes:

| Slice | Outcome and scope | Dependencies | Checks and risk |
| --- | --- | --- | --- |
| SHARE-01 | Owner grants read access to one existing document; recipient opens it through the existing UI/API/storage paths. No public links or bulk sharing. | Stable identity, document ownership and permission contract. | Grant/read integration, unauthenticated and cross-document denial, duplicate grant behavior, applicable static/browser checks; high risk. |
| SHARE-02 | Owner revokes a grant and recipient loses access, including alternate access paths. | SHARE-01 integrated; stable cache/session semantics. | Revocation, stale cache, denial and regression checks on combined baseline; high risk. |
| HISTORY-01 | User views existing authorized document activity records. No new grant mutation or audit-event schema. | Existing activity query/authorization contract. | Query/permission tests and display states; classify from actual data sensitivity. |

Assign one owner to each slice. SHARE-01 and HISTORY-01 can proceed in isolated workspaces if their contracts/resources are stable and modified files do not conflict. SHARE-02 follows SHARE-01. If both ready slices need to redefine permission semantics, establish that shared contract first or serialize implementation. The active web pack can add browser, database or deployment-readiness requirements; do not deploy or migrate production merely to claim integration.

For SHARE-01: local results cover the UI-to-storage flow and denial cases in its workspace. The coordinator then incorporates authorized changes into the target baseline and runs combined regression checks. Acceptance records usability evidence, security review where appropriate, actual check results and deferred bulk/public-link work. A failed mandatory authorization test means Failed verification or Needs rework, never Accepted.

## Non-web example: command-line archive tooling

An archive tool needs inspection, extraction and integrity reporting. First establish the entry-name, byte-stream and error contracts through bounded foundation work. Explain that this foundation has no independently usable capability yet.

| Slice | Outcome and non-goals | Dependencies | Checks and risk |
| --- | --- | --- | --- |
| ARC-01 | User lists entries from an existing archive format, including stable malformed-input errors. No extraction. | Stable reader/error contract. | Known reference archives, truncated/corrupt input and CLI output tests. |
| ARC-02 | User extracts one selected entry into a chosen directory without escaping it. No format conversion. | Stable reader/path contract; ARC-01 if its selection interface is reused. | Traversal/symlink denial, overwrite policy, partial failure and reference byte comparisons; high risk because filesystem writes can damage unrelated data. |
| ARC-03 | User verifies checksums using existing metadata and receives a clear mismatch result. No performance engine. | Stable reader/metadata contract. | Independent known checksums, corruption/mismatch and CLI exit behavior. |

ARC-01 and ARC-03 can run concurrently with distinct command modules and an agreed reader contract. A shared dispatch file needs one owner or sequential integration. ARC-02 is not Ready if its overwrite or selection contract is unresolved; approved test doubles may permit bounded development but not final integration claims. No web pack or particular language is required.

Research, inseparable refactors and shared foundations can use other bounded plans when slicing adds artificial complexity. Document why and retain acceptance/verification discipline. Do not force a blocked slice forward: name its resume condition, reassess repeated unexplained failures, and advance other ready work only when safe.
