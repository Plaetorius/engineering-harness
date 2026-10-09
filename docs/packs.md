# Authoring and using packs

Run commands from this checkout, or use the absolute path to its `scripts/harness`. No PATH modification is required.

```sh
scripts/harness pack list
scripts/harness pack new example --directory ./example
scripts/harness pack validate ./example
scripts/harness pack activate web-typescript --project /path/to/repository
scripts/harness pack activate web-typescript --project /path/to/repository --apply
scripts/harness project inspect --project /path/to/repository
scripts/harness check list --project /path/to/repository
scripts/harness check run --project /path/to/repository --execute
scripts/harness pack deactivate web-typescript --project /path/to/repository --apply
scripts/harness doctor --project /path/to/repository
```

`pack new` creates a local skeleton immediately and refuses an existing destination. All lifecycle mutations otherwise preview by default. `pack list --pack-root <directory>` discovers additional local packs; discovery does not install, approve or execute them. Validate and review external content, then supply the exact printed `--trust-pack sha256:<digest>` to activation. `--apply` approves the displayed project changes; `--trust-pack` separately approves external instructions. Re-preview after changing content.

## Manifest

[pack.schema.json](../schemas/pack.schema.json) is the versioned contract. Unknown fields are rejected. No dependencies or network schema resolution are supported. Example:

```json
{
  "schema_version": 1,
  "id": "example",
  "version": "1.0.0",
  "description": "Example domain conventions",
  "skills": [{"name": "example-review", "path": "skills/example-review"}],
  "standards": ["standards/conventions.md"],
  "workflows": ["workflow.md"],
  "checks": [{"id": "test", "description": "Run project tests", "project_command": "test", "cwd": "project", "timeout_seconds": 120}],
  "compatibility": {"harness_schema": 1, "runtimes": ["codex", "claude"], "platforms": ["darwin", "linux"]}
}
```

Create all referenced files before validation. IDs use lowercase words separated by hyphens. Versions use three numeric components. Skill names must start with `<pack-id>-`, match their directory and SKILL.md frontmatter name, and avoid existing core/user/project names. A portable SKILL.md begins with `name` and `description`; put supporting Markdown and scripts inside its pack. Relative Markdown references must resolve inside the pack. Optional `templates` and `tools` are arrays of relative file paths. Declaring a tool makes it available for review, never autoexecutes it.

Checks choose exactly one of `argv` (a nonempty string array) or `project_command` (a named command in the profile). Every check declares `id`, `description`, `cwd` (`pack` or `project`) and `timeout_seconds` (1–86400). Named project commands require `cwd: project`; their own cwd/timeout applies, with the smaller timeout winning. Direct argv checks may specify `cwd_subdir`. An argv element beginning with `{pack}/` or `{project}/` resolves a confined existing path; shell expansion, quoting, pipes and substitution are not interpreted. Other argv elements remain literal. Executable files must be invoked appropriately, for example through a locally available interpreter.

Pack payloads cannot contain symlinks, hardlinked files, special files, embedded native plugins or dynamic shell directives in Markdown. Validation checks paths, compatibility metadata, skill definitions, check declarations and payload integrity. A valid manifest is not a trust guarantee. Only the selected pack is activated; code execution additionally requires an explicit check-run request.

## Project profiles

[project.schema.json](../schemas/project.schema.json) defines `.harness/project.json`. Activation creates it with exact `id`, `version` and SHA256 content pins. Optional pack `config` is opaque JSON for domain instructions/tools; the core does not interpret it. Profiles reference project `rules` and `documentation` through existing relative files. They do not duplicate standards.

Declare commands discovered from the repository, for example:

```json
{
  "test": {"argv": ["npm", "run", "test"], "cwd": ".", "timeout_seconds": 120}
}
```

This is only an example, not a package-manager default. Edit the profile's `commands` object, `required_checks` (qualified `pack-id:check-id` names) and `acceptance_criteria` (human-readable conditions), then preview/apply `scripts/harness project sync --project <repository>`. Sync approves changed command/profile bytes and checks exact pack pins. External approvals must be repeated for changed content. For a pack update, explicitly reactivate to update the version/fingerprint pin; sync never silently upgrades it.

Local links and approvals are ignored with narrowly owned native skill ignore blocks and `.harness/local/.gitignore`. Commit the profile and intended native user files normally. Fresh project checkouts need sync before native pack discovery. Do not commit local ownership, backups, reports or absolute source paths. After lifecycle changes, start fresh CLI sessions so native skill catalogs refresh.

## Results and recovery

[check-result.schema.json](../schemas/check-result.schema.json) specifies results under `.harness/local/reports/<run-id>/result.json`. Each check records a stable qualified ID, pack pin, status, duration, exit code/reason and project-relative stdout/stderr paths. Statuses are `success`, `failure`, `skipped` and `execution-error`. Missing named commands/checks skip; timeout/launch errors are execution errors. Required checks must succeed, including when a subset is selected with `--check`; optional skips are reported. Failure/error or an unsatisfied required check produces nonzero CLI exit status. Human acceptance criteria still need assessment. Captured output may contain application secrets; it remains local and ignored.

Interrupted lifecycle operations block further changes. Preview `scripts/harness project recover --project <repository>`, then apply with `--apply`. Recovery restores pre-transaction owned content or finishes cleanup of committed state, refusing newer unrelated edits. Removed source packs can still be deactivated. Deactivation uses ownership records and does not require unrelated pack sources to be present or valid; their pins and skill links remain unchanged. Project inspection and checks continue to refuse missing or invalid active packs until repaired or explicitly deactivated. Global uninstall is unchanged; deactivate project packs separately before removing their source checkout.

## Boundaries

Supported local systems are macOS/Linux with Python 3.9+ and Bash. Native symlinks and POSIX locks are required. No Windows support, automatic download, telemetry, permission changes or backend exists. Explicitly executed code inherits user permissions; cwd confinement and validation are not a sandbox. Scripts may spawn children or access external resources; review trust accordingly. Fingerprints protect CLI resolution/execution, but native agents can read a changed symlink payload before reactivation, so maintain approved source directories securely. Concurrent adversarial same-account writers are outside this local ownership model.

Both runtimes use the same skill payloads through their native paths. Their instruction precedence and plugin behavior differ; adapters do not normalize those internals. Collision checks cover core and visible native user/project skill directories; third-party plugin-generated skill names may need manual review. Global doctor checks installation ownership; project doctor checks profile pins, links and pack compatibility. Version probes remain available with `scripts/doctor --versions`.

Reviewer perspectives are an optional pack capability; see [reviewer extension declarations](architecture-map-review.md#pack-reviewer-extensions). They use the existing validation, activation and fingerprint trust boundary.
