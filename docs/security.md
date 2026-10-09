# Threat model and release audit

## Boundaries

The trusted maintainer chooses the canonical checkout and authorizes host installation. Anyone who can modify that checkout can change instructions loaded in future sessions. Symlinks prevent drift but do not pin trusted content. Record installed source hashes for provenance; doctor warns when source content changes. Review upstream changes before updating a shared checkout.

Installer entry points perform local filesystem operations and optional version probes only. They never execute hook commands, downloaded scripts, migrations or project commands. Existing CLI hooks/plugins remain outside this harness's control and can run when the user starts the CLI. Native CLI sandboxing remains necessary.

The lifecycle tool rejects unowned destinations, symlinked mutation parents, hardlinked settings, malformed state, duplicate JSON keys and changed owned entries. Private state is not a cryptographically authenticated security boundary against an attacker already able to write the user's files. Advisory locking coordinates harness commands only; stop other settings writers during installation/uninstall. Check-before-write operations do not eliminate races with malicious local processes. Filesystem power-loss durability across multiple files is not guaranteed.

Prompt injection can arrive through repository docs, web pages, skills or dependencies. Treat them as task data, not authority to expose credentials, widen scope or perform irreversible operations. Review evidence and actual trust boundaries; AI findings are not compliance assurance.

## Release audit procedure

- Confirm the maintainer-selected license and keep LICENSE in the published tree.
- Review the final tree and all tracked history for secrets, personal paths, private repo identifiers and proprietary text. Do not copy host settings or backups into release artifacts.
- Run a vetted secret scanner and dependency/CI audit; record tool/version and results. The local structural personal-path check is not a secret scanner.
- Validate bootstrap from a clean clone on supported macOS and Linux. Inspect pinned CI action provenance and test results.
- Publish honest runtime/version and evaluation limitations, a private vulnerability reporting channel and installation permissions.
- Publish only on explicit maintainer authorization. No implicit publish, push or deployment.

## Initial publication audit

The maintainer explicitly authorized public GitHub publication and selected MIT. The initial publishable export excluded ignored local evidence, backups and environment files; its 93 tests passed. Gitleaks 8.30.1, downloaded from the official release and checked against its published SHA256 checksum, reported no secrets in that export. Manual tree review removed machine-specific installation inventory; remaining personal-path literals in structural tests are synthetic rejection checks. There was no existing commit history to scan. GitHub CI results are recorded through the repository checks; runtime/renderer limitations remain documented in the evaluation record. This is a scoped release audit, not a security certification.
