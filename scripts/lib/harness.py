#!/usr/bin/env python3
"""Offline, additive user installation. No third-party Python dependencies."""

import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import uuid

SKILLS = ("plan-feature", "implement-api", "review-diff", "debug-root-cause", "architecture-map", "review")
MODE = "claude-md-and-agents-md"
PLUGIN = "cc-plugin-agents-md@builtin"
LEGACY_PLUGIN = "agents-md@builtin"
SCHEMA = 1


class Refusal(Exception):
    pass


def exists(path):
    return os.path.lexists(path)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def absolute(value):
    return Path(os.path.abspath(os.path.expanduser(str(value))))


def parents_safe(path):
    """Never traverse user-controlled symlink parents for host mutations."""
    for p in reversed(path.parents):
        if p.is_symlink():
            raise Refusal(f"Symlinked parent requires an explicit canonical path: {p}")
        if exists(p) and not p.is_dir():
            raise Refusal(f"Parent is not a directory: {p}")


def regular_bytes(path):
    parents_safe(path)
    if path.is_symlink() or (exists(path) and not path.is_file()):
        raise Refusal(f"Expected a regular file: {path}")
    if not exists(path):
        return None
    # Refuse special files and hardlinks for settings/state as well as symlinks.
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise Refusal(f"Expected an unlinked regular file: {path}")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(fd)


def decode_json(data, path):
    def invalid_constant(value):
        raise ValueError("non-finite JSON number")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    try:
        value = json.loads(data, object_pairs_hook=unique, parse_constant=invalid_constant)
    except (ValueError, UnicodeError):
        raise Refusal(f"Invalid or duplicate-key JSON (contents omitted): {path}") from None
    if not isinstance(value, dict):
        raise Refusal(f"Expected a JSON object: {path}")
    return value


def runtime_adapters():
    """Trusted runtime layouts live outside portable engineering content."""
    root = Path(__file__).resolve().parents[2] / "adapters"
    result = []
    for name in ("codex", "claude"):
        data = decode_json((root / name / "discovery.json").read_bytes(), name + " adapter")
        if data.get("schema_version") != 1 or data.get("runtime") != name:
            raise Refusal("Invalid runtime adapter")
        for key in ("global_instruction_root", "global_skills_root"):
            if data.get(key) not in ("home", "codex_home", "claude_home"):
                raise Refusal("Invalid adapter root")
        for key in ("global_instruction_path", "global_skills_path", "project_skills_path"):
            value = data.get(key)
            if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts or "\\" in value:
                raise Refusal("Invalid adapter discovery path")
        result.append(data)
    return result


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=False) + "\n").encode()


def atomic_write(path, data, mode=0o600):
    parents_safe(path)
    fd, name = tempfile.mkstemp(prefix=".harness-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.lexists(name):
            os.unlink(name)


def exclusive_write(path, data):
    parents_safe(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def metadata(path):
    try:
        text = path.read_text()
    except (OSError, UnicodeError):
        raise Refusal(f"Unreadable skill manifest: {path}") from None
    match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", text, re.S)
    if not match:
        raise Refusal(f"Missing skill frontmatter: {path}")
    fields = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            raise Refusal(f"Portable frontmatter requires scalar key/value lines: {path}")
        key, value = line.split(":", 1)
        if key in fields:
            raise Refusal(f"Duplicate frontmatter key: {path}")
        fields[key] = value.strip().strip("\"'")
    if set(fields) != {"name", "description"}:
        raise Refusal(f"Portable skills require name and description only: {path}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", fields["name"]) or len(fields["name"]) > 64:
        raise Refusal(f"Invalid skill name: {path}")
    if not fields["description"] or len(fields["description"]) > 1024:
        raise Refusal(f"Invalid skill description: {path}")
    return fields


class Harness:
    def __init__(self, home=None, codex_home=None, claude_home=None, state_dir=None, repo=None):
        self.home = absolute(home or os.environ.get("HOME", str(Path.home()))).resolve()
        self.codex = absolute(codex_home or os.environ.get("CODEX_HOME", self.home / ".codex"))
        self.claude = absolute(claude_home or os.environ.get("CLAUDE_CONFIG_DIR", self.home / ".claude"))
        self.state = absolute(state_dir or self.home / ".engineering-harness")
        self.repo = absolute(repo or Path(__file__).resolve().parents[2])
        self.manifest = self.state / "manifest.json"
        self.journal = self.state / "journal.json"
        self.settings = self.claude / "settings.json"
        if not self.home.is_dir():
            raise Refusal("Selected HOME must already exist")
        roots = (self.codex, self.claude, self.home / ".agents", self.state)
        for root in roots:
            parents_safe(root / "entry")
        for other in roots[:-1]:
            if self.state == other or self.state.is_relative_to(other) or other.is_relative_to(self.state):
                raise Refusal("State directory must be separate from CLI discovery roots")
        if self.state == self.home or self.state == self.repo or self.repo.is_relative_to(self.state):
            raise Refusal("State directory must not own HOME or the source checkout")

    def display(self, path):
        result = str(path)
        for prefix, replacement in sorted(((str(self.repo), "$REPO"), (str(self.home), "~"),
                                           (str(self.codex), "$CODEX_HOME"),
                                           (str(self.claude), "$CLAUDE_CONFIG_DIR"),
                                           (str(self.state), "$STATE")), key=lambda v: -len(v[0])):
            if result == prefix or result.startswith(prefix + "/"):
                return replacement + result[len(prefix):]
        return "<external-path>/" + Path(result).name

    def context(self):
        return {"home": str(self.home), "codex_home": str(self.codex),
                "claude_home": str(self.claude), "state_dir": str(self.state)}

    def links(self, repo=None):
        source = Path(repo or self.repo)
        roots = {"home": self.home, "codex_home": self.codex, "claude_home": self.claude}
        adapters = runtime_adapters()
        result = [(roots[a["global_instruction_root"]] / a["global_instruction_path"],
                   source / "core/global-instructions.md") for a in adapters]
        result += [(roots[a["global_skills_root"]] / a["global_skills_path"] / n,
                    source / "skills" / n) for a in adapters for n in SKILLS]
        if len({p for p, _ in result}) != len(result):
            raise Refusal("CLI destinations overlap")
        return result

    def allowed_dirs(self):
        result = set()
        for path, _ in self.links():
            result.add(path.parent)
        result.update((self.codex, self.claude, self.home / ".agents", self.state, self.state / "backups"))
        # Explicit external config/state paths may have missing parents. Own only
        # newly created directories, never the existing filesystem anchor.
        for path in list(result):
            for parent in path.parents:
                if parent == self.home or parent == Path("/"):
                    break
                result.add(parent)
        return result

    def load(self, path):
        raw = regular_bytes(path)
        if raw is None:
            return None
        value = decode_json(raw, path)
        try:
            if value["schema"] != SCHEMA or value["context"] != self.context():
                raise ValueError()
            repo = Path(value["repository"])
            if not repo.is_absolute():
                raise ValueError()
            expected = {str(p): os.path.relpath(s, p.parent) for p, s in self.links(repo)}
            seen = set()
            for entry in value["links"]:
                if entry["path"] in seen or expected.get(entry["path"]) != entry["target"]:
                    raise ValueError()
                seen.add(entry["path"])
            dirs = [Path(p) for p in value["directories"]]
            if len(set(dirs)) != len(dirs) or not set(dirs) <= self.allowed_dirs():
                raise ValueError()
            patch = value.get("settings_patch")
            if patch:
                backup = Path(patch["backup"])
                if (Path(patch["path"]) != self.settings or backup.parent != self.state / "backups"
                        or not re.fullmatch(r"[a-f0-9]{32}\.json", backup.name)
                        or not re.fullmatch(r"[a-f0-9]{64}", patch["after_hash"])
                        or (patch["before_hash"] is not None and not re.fullmatch(r"[a-f0-9]{64}", patch["before_hash"]))
                        or type(patch["before_mode"]) is not int
                        or not 0 <= patch["before_mode"] <= 0o777):
                    raise ValueError()
            if "phase" in value and value["phase"] not in ("installing", "uninstalling"):
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise Refusal(f"Invalid or mismatched ownership state (contents omitted): {path}") from None
        return value

    def validate_source(self):
        core = self.repo / "core/global-instructions.md"
        if not core.is_file() or not core.read_text().strip():
            raise Refusal("Canonical core missing; restore the checkout or select its new location")
        for n in SKILLS:
            if metadata(self.repo / "skills" / n / "SKILL.md")["name"] != n:
                raise Refusal("Canonical skill name differs from directory")

    def source_hashes(self):
        paths = [self.repo / "core/global-instructions.md"]
        paths += list((self.repo / "standards").rglob("*.md"))
        paths += list((self.repo / "profiles").glob("*.md"))
        paths += [p for n in SKILLS for p in (self.repo / "skills" / n).rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts]
        return {str(p.relative_to(self.repo)): digest(p.read_bytes()) for p in sorted(paths)}

    def verify_owned(self, manifest, preserve_settings=False):
        for entry in manifest["links"]:
            path = Path(entry["path"])
            parents_safe(path)
            if not path.is_symlink() or os.readlink(path) != entry["target"]:
                raise Refusal(f"Owned destination changed or missing: {self.display(path)}")
        patch = manifest.get("settings_patch")
        if patch:
            raw = regular_bytes(self.settings)
            if raw is None or digest(raw) != patch["after_hash"]:
                if not preserve_settings:
                    raise Refusal("Claude settings changed after install; preserve them and review a manual merge")
                if raw is not None:
                    decode_json(raw, "Claude settings")
                print("NOTE: preserving edited Claude settings; original rollback ownership/backup retained; automatic restore remains guarded")
            backup = regular_bytes(Path(patch["backup"]))
            if backup is None or digest(backup) != (patch["before_hash"] or digest(b"")):
                raise Refusal("Settings backup changed or missing; automatic restore refused")

    def collision_audit(self):
        owned_paths = {str(p) for p, _ in self.links()}
        roots = (self.home / ".agents/skills", self.codex / "skills", self.claude / "skills",
                 self.codex / "plugins", self.claude / "plugins")
        for root in roots:
            if not root.exists():
                continue
            # Path.rglob does not traverse directory symlinks by default. Handle
            # symlinked top-level skills explicitly and recurse plugin caches.
            manifests = set(root.rglob("SKILL.md"))
            if root.name == "skills":
                manifests.update(p / "SKILL.md" for p in root.iterdir() if (p / "SKILL.md").is_file())
            for path in manifests:
                if str(path.parent) in owned_paths:
                    continue
                try:
                    text = path.read_text()
                except (OSError, UnicodeError):
                    raise Refusal("Unreadable existing skill; collision audit incomplete") from None
                m = re.search(r"(?m)^name:\s*[\"']?([a-z0-9-]+)", text[:8192])
                if m and m.group(1) in SKILLS:
                    raise Refusal(f"Existing skill manifest name conflicts: {m.group(1)} (private source omitted)")

    def version_check(self):
        try:
            proc = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            raise Refusal("Claude version unavailable; optional settings patch requires CLI 2.1.285+") from None
        m = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", proc.stdout)
        if proc.returncode or not m or tuple(map(int, m.groups())) < (2, 1, 285):
            raise Refusal("Optional settings patch requires verified Claude CLI 2.1.285+")

    def proposed_patch(self):
        self.version_check()
        before = regular_bytes(self.settings)
        settings = decode_json(before, self.settings) if before is not None else {}
        proposed = copy.deepcopy(settings)
        try:
            enabled = proposed.get("enabledPlugins", {})
            for key in (PLUGIN, LEGACY_PLUGIN):
                if enabled.get(key) is False:
                    raise Refusal("AGENTS built-in plugin explicitly disabled; refusing to enable silently")
            configs = proposed.setdefault("pluginConfigs", {})
            for key in (PLUGIN, LEGACY_PLUGIN):
                value = configs.get(key, {}).get("options", {}).get("instructionFiles")
                if value is not None and value != MODE:
                    raise Refusal("Existing Claude instructionFiles setting conflicts with requested mode")
            options = configs.setdefault(PLUGIN, {}).setdefault("options", {})
            if options.get("instructionFiles") == MODE:
                return None
            options["instructionFiles"] = MODE
        except (AttributeError, TypeError):
            raise Refusal("Claude settings subtree has unexpected types (contents omitted)") from None
        return before, json_bytes(proposed)

    def plan(self, both=False, preserve_settings=False):
        self.validate_source()
        if exists(self.journal):
            raise Refusal("Interrupted transaction found; preview scripts/uninstall --recover first")
        manifest = self.load(self.manifest)
        if manifest:
            self.verify_owned(manifest, preserve_settings)
            if manifest["repository"] != str(self.repo):
                raise Refusal("Checkout moved; uninstall the recorded installation before reinstalling")
        if exists(self.codex / "AGENTS.override.md"):
            raise Refusal("Global AGENTS.override.md could shadow the harness; resolve explicitly")
        self.collision_audit()
        owned = {e["path"]: e for e in manifest["links"]} if manifest else {}
        additions = []
        for path, source in self.links():
            parents_safe(path)
            if exists(path):
                if str(path) not in owned:
                    raise Refusal(f"Unowned destination exists; no replacement: {self.display(path)}")
            else:
                additions.append({"path": str(path), "target": os.path.relpath(source, path.parent)})
        if not manifest and exists(self.state):
            raise Refusal("Unowned state directory exists; select another state directory")
        patch = self.proposed_patch() if both and not (manifest and manifest.get("settings_patch")) else None
        return manifest, additions, patch

    def preview(self, additions, patch, refresh=False):
        for entry in additions:
            target = absolute(Path(entry["path"]).parent / entry["target"])
            print(f"CREATE LINK {self.display(entry['path'])} -> {self.display(target)}")
        missing = set()
        for entry in additions:
            p = Path(entry["path"]).parent
            while not exists(p):
                missing.add(p)
                p = p.parent
        for p in sorted(missing, key=lambda p: (len(p.parts), str(p))):
            print(f"CREATE DIRECTORY {self.display(p)}")
        if not exists(self.manifest):
            print("CREATE PRIVATE STATE $STATE/{manifest.json,lock}; transient journal during apply")
        if patch:
            print("BACKUP Claude settings in $STATE/backups/<transaction>.json (mode 0600)")
            print(f"PATCH {self.display(self.settings)}: pluginConfigs.{PLUGIN}.options.instructionFiles = {MODE}")
            print("JSON formatting will be normalized; all unrelated values preserved")
        if refresh:
            print("REFRESH private source hashes: linked canonical content changed since installation")
        if not additions and not patch and not refresh:
            print("NO CHANGES: installation is already owned and current")

    def ensure_dir(self, path, state):
        parents_safe(path / "entry")
        if exists(path):
            return
        self.ensure_dir(path.parent, state)
        state["directories"].append(str(path))
        atomic_write(self.journal, json_bytes(state))
        path.mkdir(mode=0o700)

    def lock(self):
        path = self.state / "lock"
        parents_safe(path)
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            os.close(fd)
            raise Refusal("Invalid state lock file")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise Refusal("Another harness lifecycle command is running") from None
        return fd

    def install(self, both=False, apply=False, preserve_settings=False):
        if both and preserve_settings:
            raise Refusal("A settings patch cannot be combined with preserve-settings")
        manifest, additions, patch = self.plan(both, preserve_settings)
        refresh = bool(manifest and manifest.get("source_hashes") != self.source_hashes())
        self.preview(additions, patch, refresh)
        if not apply:
            print("DRY RUN: no filesystem writes")
            return
        if not additions and not patch and not refresh:
            return
        # State bootstrap only creates exclusive directories; a crash before
        # journal creation leaves empty private state and is reported/refused.
        bootstrap = []
        path = self.state
        while not exists(path):
            bootstrap.append(path)
            path = path.parent
        for p in reversed(bootstrap):
            p.mkdir(mode=0o700)
        fd = None
        state = None
        try:
            fd = self.lock()
            # Repeat preflight after acquiring the state lock.
            if exists(self.journal):
                raise Refusal("Transaction appeared during preflight")
            if self.load(self.manifest) != manifest:
                raise Refusal("Ownership changed during preflight")
            state = {"schema": SCHEMA, "context": self.context(), "repository": str(self.repo),
                     "links": [], "directories": [str(p) for p in reversed(bootstrap)],
                     "settings_patch": None, "phase": "installing"}
            atomic_write(self.journal, json_bytes(state))
            for entry in additions:
                path = Path(entry["path"])
                self.ensure_dir(path.parent, state)
                if exists(path):
                    raise Refusal(f"Destination appeared during apply: {self.display(path)}")
                state["links"].append(entry)
                atomic_write(self.journal, json_bytes(state))
                parents_safe(path)
                path.symlink_to(entry["target"])
            if patch:
                before, after = patch
                if regular_bytes(self.settings) != before:
                    raise Refusal("Claude settings changed during preflight")
                self.ensure_dir(self.settings.parent, state)
                self.ensure_dir(self.state / "backups", state)
                backup = self.state / "backups" / (uuid.uuid4().hex + ".json")
                exclusive_write(backup, before if before is not None else b"")
                state["settings_patch"] = {"path": str(self.settings), "backup": str(backup),
                    "before_hash": digest(before) if before is not None else None,
                    "after_hash": digest(after), "before_mode": stat.S_IMODE(self.settings.stat().st_mode) if before is not None else 0o600}
                atomic_write(self.journal, json_bytes(state))
                if regular_bytes(self.settings) != before:
                    raise Refusal("Claude settings changed before patch")
                atomic_write(self.settings, after, state["settings_patch"]["before_mode"])
            result = copy.deepcopy(manifest) if manifest else {"schema": SCHEMA, "context": self.context(),
                      "repository": str(self.repo), "links": [], "directories": [], "settings_patch": None}
            result["links"].extend(state["links"])
            result["directories"].extend(p for p in state["directories"] if p not in result["directories"])
            if state["settings_patch"]:
                result["settings_patch"] = state["settings_patch"]
            result["source_hashes"] = self.source_hashes()
            atomic_write(self.manifest, json_bytes(result))
            self.journal.unlink()
            print("APPLIED: owned links and private manifest recorded")
        except BaseException:
            if state is not None:
                # If commit already succeeded, recovery keeps the installation.
                committed = self.load(self.manifest)
                if committed and all(e in committed["links"] for e in state["links"]) and committed.get("settings_patch") == (state.get("settings_patch") or (manifest or {}).get("settings_patch")):
                    raise
                try:
                    self.cleanup(state, recovering=True)
                    if exists(self.journal):
                        self.journal.unlink()
                except (OSError, Refusal):
                    print("Rollback incomplete; journal retained for --recover", file=sys.stderr)
            raise
        finally:
            if fd is not None:
                os.close(fd)
            if state and not exists(self.journal) and not exists(self.manifest):
                self.remove_dirs(state["directories"])

    def cleanup(self, state, recovering=False):
        # Preflight every removal before touching any entry.
        for entry in state["links"]:
            path = Path(entry["path"])
            parents_safe(path)
            if not exists(path) and recovering:
                continue
            if not path.is_symlink() or os.readlink(path) != entry["target"]:
                raise Refusal(f"Refusing to remove modified entry: {self.display(path)}")
        patch = state.get("settings_patch")
        restore = False
        if patch:
            raw = regular_bytes(self.settings)
            current_hash = digest(raw) if raw is not None else None
            if current_hash == patch["after_hash"]:
                restore = True
            elif not recovering or current_hash != patch["before_hash"]:
                raise Refusal("Settings edited after install; automatic restore refused")
            backup = regular_bytes(Path(patch["backup"]))
            if backup is None and recovering and current_hash == patch["before_hash"]:
                pass  # Restore completed before an uninstall interruption.
            elif backup is None or digest(backup) != (patch["before_hash"] or digest(b"")):
                raise Refusal("Settings backup missing or modified")
        if restore:
            if patch["before_hash"] is None:
                self.settings.unlink()
            else:
                atomic_write(self.settings, backup, patch["before_mode"])
        for entry in reversed(state["links"]):
            path = Path(entry["path"])
            if exists(path):
                # Recheck immediately before removing; active concurrent writers
                # must be stopped (see installation docs).
                if not path.is_symlink() or os.readlink(path) != entry["target"]:
                    raise Refusal("Destination changed during uninstall")
                path.unlink()
        if patch and exists(Path(patch["backup"])):
            Path(patch["backup"]).unlink()

    def remove_dirs(self, directories):
        for p in sorted((Path(p) for p in directories), key=lambda p: len(p.parts), reverse=True):
            if p == self.state:
                continue
            if p.is_symlink():
                continue
            try:
                p.rmdir()
            except (FileNotFoundError, OSError):
                pass  # Keep nonempty directories/user additions.

    def uninstall(self, apply=False, recover=False):
        state = self.load(self.journal if recover else self.manifest)
        if state is None:
            print("NO CHANGES: no " + ("recovery journal" if recover else "owned installation"))
            return
        if not recover and exists(self.journal):
            raise Refusal("Interrupted transaction exists; --recover first")
        if not recover:
            self.verify_owned(state)
        for entry in state["links"]:
            print(f"REMOVE OWNED LINK {self.display(entry['path'])}")
        if state.get("settings_patch"):
            print("RESTORE original Claude settings only if the installed hash still matches")
        if not apply:
            print("DRY RUN: no filesystem writes")
            return
        fd = self.lock()
        try:
            current = self.load(self.journal if recover else self.manifest)
            if current != state:
                raise Refusal("Ownership changed during uninstall")
            if recover:
                committed = self.load(self.manifest)
                if state.get("phase") == "installing" and committed and all(e in committed["links"] for e in state["links"]) and (not state.get("settings_patch") or committed.get("settings_patch") == state["settings_patch"]):
                    self.verify_owned(committed)
                    self.journal.unlink()
                    print("RECOVERED: committed installation retained")
                    return
            else:
                state = copy.deepcopy(state)
                state["phase"] = "uninstalling"
                atomic_write(self.journal, json_bytes(state))
            self.cleanup(state, recovering=recover)
            if not recover or state.get("phase") == "uninstalling":
                if exists(self.manifest):
                    self.manifest.unlink()
            if exists(self.journal):
                self.journal.unlink()
            self.remove_dirs(state["directories"])
            print("RECOVERED" if recover else "UNINSTALLED: unrelated entries preserved")
        finally:
            os.close(fd)
        # Keep a small private state directory and lock for lifecycle locking.
        # Reinstallation accepts this only through the empty ownership marker.
        if not exists(self.manifest):
            atomic_write(self.manifest, json_bytes({"schema": SCHEMA, "context": self.context(),
                "repository": str(self.repo), "links": [], "directories": [], "settings_patch": None}))

    def doctor(self, versions=False, preserve_settings=False):
        self.validate_source()
        if exists(self.journal):
            raise Refusal("Interrupted transaction: run uninstall --recover preview")
        manifest = self.load(self.manifest)
        if not manifest or len(manifest["links"]) != len(self.links()):
            raise Refusal("Shared core/skills are not fully installed")
        self.verify_owned(manifest, preserve_settings)
        if manifest["repository"] != str(self.repo):
            raise Refusal("Recorded checkout differs from current checkout")
        if exists(self.codex / "AGENTS.override.md"):
            raise Refusal("Global override shadows the installed core")
        for path, source in self.links():
            if not path.exists() or path.resolve() != source.resolve():
                raise Refusal(f"Broken or redirected link: {self.display(path)}")
        self.collision_audit()
        print(f"PASS: two core links and {len(SKILLS) * 2} skill links resolve to canonical sources")
        if manifest.get("source_hashes") != self.source_hashes():
            print("NOTE: canonical content changed since installation; links load the current checkout")
        raw = regular_bytes(self.settings)
        settings = decode_json(raw, self.settings) if raw is not None else {}
        try:
            mode = settings.get("pluginConfigs", {}).get(PLUGIN, {}).get("options", {}).get("instructionFiles")
            if mode is None:
                mode = settings.get("pluginConfigs", {}).get(LEGACY_PLUGIN, {}).get("options", {}).get("instructionFiles")
            disabled = any(settings.get("enabledPlugins", {}).get(key) is False for key in (PLUGIN, LEGACY_PLUGIN))
        except AttributeError:
            raise Refusal("Claude instruction settings have unexpected types") from None
        if disabled:
            print("NOTE: AGENTS built-in plugin disabled; both-mode may be ineffective")
        print("Claude project instructions: both-mode configured" if mode == MODE else "NOTE: both-mode not configured; ancestor CLAUDE files may suppress AGENTS")
        if (self.home / "CLAUDE.md").exists():
            print("NOTE: ancestor ~/CLAUDE.md exists; semantic conflicts require review")
        print("NOTE: existing instructions/plugins/hooks coexist; runtime discovery and behavior need CLI evaluation")
        if versions:
            for name in ("codex", "claude"):
                try:
                    p = subprocess.run([name, "--version"], capture_output=True, text=True, timeout=15)
                    m = re.search(r"\b\d+\.\d+\.\d+\b", p.stdout)
                    print(name + ": " + (m.group(0) if p.returncode == 0 and m else "unavailable"))
                except (OSError, subprocess.TimeoutExpired):
                    print(name + ": unavailable")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("install", "doctor", "uninstall"))
    parser.add_argument("--apply", action="store_true", help="apply an already reviewed installation/uninstall plan")
    parser.add_argument("--preserve-settings", action="store_true", help="install/doctor only: retain edited Claude settings and original guarded rollback record")
    parser.add_argument("--home", help="selected user home; must already exist")
    parser.add_argument("--codex-home")
    parser.add_argument("--claude-home")
    parser.add_argument("--state-dir")
    parser.add_argument("--claude-project-instructions", choices=("both",), help="separately authorized Claude settings patch")
    parser.add_argument("--recover", action="store_true", help="undo incomplete transaction; uninstall only")
    parser.add_argument("--versions", action="store_true", help="doctor only: probe CLI versions (startup may have side effects)")
    args = parser.parse_args(argv)
    if (args.preserve_settings and args.command == "uninstall") or (args.preserve_settings and args.claude_project_instructions) or (args.recover and args.command != "uninstall") or (args.versions and args.command != "doctor") or (args.claude_project_instructions and args.command != "install") or (args.apply and args.command == "doctor"):
        parser.error("option is not valid for this command")
    harness = None
    try:
        harness = Harness(args.home, args.codex_home, args.claude_home, args.state_dir)
        if args.command == "install":
            harness.install(args.claude_project_instructions == "both", args.apply, args.preserve_settings)
        elif args.command == "doctor":
            harness.doctor(args.versions, args.preserve_settings)
        else:
            harness.uninstall(args.apply, args.recover)
    except (Refusal, OSError) as exc:
        message = str(exc)
        if harness:
            for root in (harness.repo, harness.home, harness.codex, harness.claude, harness.state):
                message = message.replace(str(root), harness.display(root))
        else:
            message = re.sub(r"/[^\s:]+", "<path>", message)
        print("REFUSED: " + message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
