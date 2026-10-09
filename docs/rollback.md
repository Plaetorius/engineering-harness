# Rollback and uninstall

```sh
bash scripts/uninstall
# After reviewing the removal/restore plan:
bash scripts/uninstall --apply
```

Use the same HOME, config-home and state-directory arguments as installation. Uninstall verifies every owned link before removal, restores an optional settings patch only if current content matches its installed hash, and preserves unrelated files. It removes owned directories only when empty. A small private state directory, lock and empty ownership marker remain so repeat installation remains safe.

If settings changed since installation, automatic restore refuses rather than losing edits. The original backup is private at the path recorded in the manifest. Review both documents locally and merge only the instruction-mode subtree. Never publish the backup or whole settings diff. Resolve modified links explicitly before retrying.

Interrupted transaction:

```sh
bash scripts/uninstall --recover
bash scripts/uninstall --recover --apply
```

Recovery removes only matching recorded entries and restores matching settings, or preserves an installation that had already committed. If rollback cannot finish, its journal remains for inspection. A crash before the first journal is written can leave an empty private state directory: inspect it and select a new state path or explicitly remove only that empty directory. No blanket recursive removal is part of rollback.

Once fully uninstalled, the private state directory may be removed by the maintainer after checking it contains only an empty manifest and lock. Do not remove it while another harness process is running.
