# Developing Engineering Harness

Keep runtime-neutral policy canonical in `core/`, `standards/`, `skills/`; explicitly activated domain policy belongs in `packs/` and project selections in `.harness/project.json`. CLI-specific discovery/configuration belongs in adapters and the installer. No runtime framework, network installer, implicit commit/push/deploy, or default hook.

Run `scripts/verify` for changes to scripts, manifests or discovery references. Installer tests must use temporary HOME, config homes and state paths; never exercise lifecycle mutations against the real host in tests. Treat ownership, conflict refusal, rollback and preservation of unrelated configuration as product behavior.

Skill descriptions must discriminate tasks; routine edits must remain lightweight. Test actual failure scenarios rather than matching prose. Record model evaluations honestly, distinguishing filesystem validity, runtime discovery and behavioral quality.

Personal paths, credentials, transcripts, backup contents and private project identifiers do not belong in this repository. Public release needs an explicit maintainer audit and license choice. User-authorized host installation is separate from fixture testing.
