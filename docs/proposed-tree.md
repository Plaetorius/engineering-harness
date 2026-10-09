# Repository boundaries

See [architecture](architecture.md) for the implemented boundaries and [pack authoring](packs.md) for extension contracts.

```text
core/                       shared instructions
skills/                     six portable skill entry points
standards/                  portable principles, review perspectives and migration notices
packs/web-typescript/       first explicitly activated vertical
schemas/                    pack, project and result contracts
adapters/{codex,claude}/     runtime discovery data
scripts/lib/                installer, packs, projects, checks and CLI
.harness/project.json       per-project portable selections (when present)
.harness/local/             ignored approvals, journal and reports
tests/                      installer, discovery and synthetic pack tests
```
