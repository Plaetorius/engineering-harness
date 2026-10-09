"""Explicit project profiles and reversible native skill projections."""
import base64
import copy
import fcntl
import os
from pathlib import Path
import re

from harness import (Refusal, atomic_write, decode_json, digest, exists, json_bytes,
                     parents_safe, regular_bytes, runtime_adapters)
from packs import Pack, REPO, discover, relative_path, schema, validate_schema

BEGIN = b"# BEGIN engineering-harness generated skills\n"
END = b"# END engineering-harness generated skills\n"


def default_profile():
    return {"schema_version": 1, "packs": [], "rules": [], "documentation": [],
            "commands": {}, "required_checks": [], "acceptance_criteria": []}


def ignore_block(names):
    return BEGIN + b"".join(("/" + n + "\n").encode() for n in sorted(names)) + END


def read_link(path):
    parents_safe(path)
    if not exists(path):
        return None
    if not path.is_symlink():
        raise Refusal("Unowned or modified project destination is not a symlink")
    return os.readlink(path)


def encode(data):
    return None if data is None else base64.b64encode(data).decode()


def decode(value):
    if value is None:
        return None
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise Refusal("Invalid recovery file payload") from None


class Project:
    def __init__(self, root, repo=REPO):
        self.root = Path(root).absolute()
        parents_safe(self.root / "entry")
        if not self.root.is_dir():
            raise Refusal("Project directory must already exist")
        self.root = self.root.resolve()
        self.repo = Path(repo).resolve()
        self.profile_path = self.root / ".harness/project.json"
        self.local = self.root / ".harness/local"
        self.state_path = self.local / "ownership.json"
        self.journal = self.local / "journal.json"
        self.layouts = runtime_adapters()
        self.skill_dirs = [self.root / a["project_skills_path"] for a in self.layouts]
        for path in [self.local, *self.skill_dirs]:
            parents_safe(path / "entry")

    def profile(self):
        raw = regular_bytes(self.profile_path)
        value = decode_json(raw, "project profile") if raw is not None else default_profile()
        validate_schema(value, schema("project"), "project")
        ids = [p["id"] for p in value["packs"]]
        if len(set(ids)) != len(ids):
            raise Refusal("Duplicate project pack identifiers")
        for key in ("rules", "documentation"):
            for path in value[key]:
                relative_path(self.root, path)
        for name, command in value["commands"].items():
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
                raise Refusal("Invalid named project command")
            relative_path(self.root, command["cwd"], directory=True)
        return value

    def expected_links(self, records):
        result = {}
        for record in records.values():
            source = Path(record["source"])
            for entry in record["skills"]:
                for folder in self.skill_dirs:
                    path = folder / entry["name"]
                    result[path.relative_to(self.root).as_posix()] = os.path.relpath(source / entry["path"], folder)
        return result

    def state(self):
        raw = regular_bytes(self.state_path)
        if raw is None:
            return {"schema_version": 1, "packs": {}, "profile_digest": None, "created_ignores": []}
        value = decode_json(raw, "project ownership")
        try:
            if set(value) != {"schema_version", "packs", "profile_digest", "created_ignores"} or value["schema_version"] != 1:
                raise ValueError()
            if not isinstance(value["packs"], dict):
                raise ValueError()
            for identifier, record in value["packs"].items():
                if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", identifier):
                    raise ValueError()
                if set(record) != {"source", "version", "digest", "origin", "skills"}:
                    raise ValueError()
                if not Path(record["source"]).is_absolute() or record["origin"] not in ("builtin", "external"):
                    raise ValueError()
                if not re.fullmatch(r"sha256:[a-f0-9]{64}", record["digest"]) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", record["version"]):
                    raise ValueError()
                seen = set()
                for entry in record["skills"]:
                    if set(entry) != {"name", "path"} or entry["name"] in seen or len(entry["name"]) > 64 or not re.fullmatch(re.escape(identifier) + r"-[a-z0-9]+(?:-[a-z0-9]+)*", entry["name"]):
                        raise ValueError()
                    relative_path(Path(record["source"]), entry["path"], must_exist=False)
                    seen.add(entry["name"])
            if value["profile_digest"] is not None and not re.fullmatch(r"[a-f0-9]{64}", value["profile_digest"]):
                raise ValueError()
            allowed_ignores = {p.relative_to(self.root).as_posix() + "/.gitignore" for p in self.skill_dirs}
            if not isinstance(value["created_ignores"], list) or not set(value["created_ignores"]) <= allowed_ignores:
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise Refusal("Invalid project ownership state; no changes applied") from None
        return value

    def verified_packs(self, execution=False):
        if exists(self.journal):
            raise Refusal("Pending project transaction; use project recover")
        profile = self.profile()
        state = self.state()
        if {p["id"] for p in profile["packs"]} != set(state["packs"]):
            raise Refusal("Profile activation differs from local approvals; use project sync")
        if execution and (profile["packs"] or profile["commands"] or exists(self.profile_path)) and state["profile_digest"] != digest(regular_bytes(self.profile_path) or json_bytes(profile)):
            raise Refusal("Project commands/profile changed since approval; preview project sync")
        result = []
        for selection in profile["packs"]:
            record = state["packs"][selection["id"]]
            pack = Pack(record["source"])
            pack.compatible()
            if pack.descriptor() != {k: selection[k] for k in ("id", "version", "digest")} or pack.version != record["version"] or pack.digest != record["digest"]:
                raise Refusal("Pack content/version differs from approved profile; explicit reactivation required")
            if pack.manifest["skills"] != record["skills"]:
                raise Refusal("Approved skill declarations changed")
            result.append(pack)
        roles = [r["id"] for p in result for r in p.manifest.get("reviewers", [])]
        if len(roles) != len(set(roles)):
            raise Refusal("Conflicting reviewer identifiers across active packs")
        for path, target in self.expected_links(state["packs"]).items():
            if read_link(self.root / path) != target or not (self.root / path).exists():
                raise Refusal("Project skill link missing, modified or broken")
        return profile, state, result

    def inspect(self):
        profile, state, active = self.verified_packs()
        return {"schema_version": 1, "profile": profile,
                "packs": [{**p.descriptor(), "origin": state["packs"][p.id]["origin"],
                           "standards": [str(p.root / x) for x in p.manifest["standards"]],
                           "workflows": [str(p.root / x) for x in p.manifest["workflows"]],
                           "skills": p.manifest["skills"],
                           "reviewers": [{"id": r["id"], "path": str(p.root / r["path"])} for r in p.manifest.get("reviewers", [])],
                           "checks": [p.id + ":" + c["id"] for c in p.manifest["checks"]]} for p in active]}

    def selected(self, selection, roots):
        path = Path(selection)
        pack = Pack(path) if path.is_dir() else None
        choices = discover(self.repo, [*roots, *([path] if pack else [])],
                           selected=pack.id if pack else selection)
        if pack:
            if choices.get(pack.id).root != pack.root:
                raise Refusal("Pack source conflicts with available identifier")
            return pack
        if selection not in choices:
            raise Refusal("Pack not found; supply its local directory or --pack-root")
        return choices[selection]

    def mutation(self, action, selection=None, roots=(), trust=(), apply=False):
        if exists(self.journal):
            raise Refusal("Pending transaction; use project recover")
        original = self.profile()
        old = self.state()
        desired = copy.deepcopy(original)
        records = copy.deepcopy(old["packs"])
        if action == "activate":
            pack = self.selected(selection, roots)
            pack.compatible()
            origin = "builtin" if pack.root.is_relative_to(self.repo / "packs") else "external"
            previous = old["packs"].get(pack.id)
            if origin == "external" and not (previous and previous["source"] == str(pack.root) and previous["digest"] == pack.digest) and pack.digest not in trust:
                raise Refusal("External pack instructions require --trust-pack " + pack.digest)
            entry = pack.descriptor()
            prior = next((p for p in desired["packs"] if p["id"] == pack.id), None)
            if prior and "config" in prior:
                entry["config"] = prior["config"]
            desired["packs"] = [p for p in desired["packs"] if p["id"] != pack.id] + [entry]
            records[pack.id] = {"source": str(pack.root), "version": pack.version, "digest": pack.digest,
                                "origin": origin, "skills": pack.manifest["skills"]}
        elif action == "deactivate":
            desired["packs"] = [p for p in desired["packs"] if p["id"] != selection]
            records.pop(selection, None)
        elif action == "sync":
            records = {}
            for entry in desired["packs"]:
                previous = old["packs"].get(entry["id"])
                source = previous["source"] if previous else entry["id"]
                pack = self.selected(source, roots)
                pack.compatible()
                if pack.descriptor() != {k: entry[k] for k in ("id", "version", "digest")}:
                    raise Refusal("Profile pin does not match available pack")
                origin = "builtin" if pack.root.is_relative_to(self.repo / "packs") else "external"
                if origin == "external" and not (previous and previous["digest"] == pack.digest) and pack.digest not in trust:
                    raise Refusal("External pack requires --trust-pack " + pack.digest)
                records[pack.id] = {"source": str(pack.root), "version": pack.version, "digest": pack.digest,
                                    "origin": origin, "skills": pack.manifest["skills"]}
        else:
            raise Refusal("Unsupported project mutation")
        names = [s["name"] for r in records.values() for s in r["skills"]]
        if len(set(names)) != len(names):
            raise Refusal("Conflicting skill identifiers across active packs")
        # Removing a pack cannot introduce reviewer collisions. Use ownership
        # records for removal even when an unrelated payload is unavailable.
        if action != "deactivate":
            role_ids = [r["id"] for record in records.values()
                        for r in Pack(record["source"]).manifest.get("reviewers", [])]
            if len(role_ids) != len(set(role_ids)):
                raise Refusal("Conflicting reviewer identifiers across active packs")
        self.audit_collisions(names, old)
        links_before = self.expected_links(old["packs"])
        links_after = self.expected_links(records)
        operations = []
        for path in sorted(set(links_before) | set(links_after)):
            actual = read_link(self.root / path)
            before = links_before.get(path)
            if actual != before:
                raise Refusal("Existing project destination is unowned, modified or missing: " + path)
            after = links_after.get(path)
            if before != after:
                operations.append({"path": path, "before": before, "after": after})
        newstate = {"schema_version": 1, "packs": records, "profile_digest": None,
                    "created_ignores": list(old["created_ignores"])}
        files = []
        for folder in self.skill_dirs:
            path = folder / ".gitignore"
            rel = path.relative_to(self.root).as_posix()
            raw = regular_bytes(path)
            oldnames = [s["name"] for r in old["packs"].values() for s in r["skills"]]
            newnames = names
            value = raw or b""
            if oldnames:
                block = ignore_block(oldnames)
                if value.count(block) != 1:
                    raise Refusal("Generated ignore block changed; preserve edits and resolve explicitly")
                value = value.replace(block, b"")
            elif BEGIN in value or END in value:
                raise Refusal("Unowned harness ignore block exists")
            if newnames:
                if value and not value.endswith(b"\n"):
                    value += b"\n"
                value += ignore_block(newnames)
                if raw is None and rel not in newstate["created_ignores"]:
                    newstate["created_ignores"].append(rel)
            elif rel in newstate["created_ignores"] and not value:
                value = None
                newstate["created_ignores"].remove(rel)
            if raw != value and not (raw is None and value == b""):
                files.append(self.file_operation(rel, raw, value))
        before_profile = regular_bytes(self.profile_path)
        after_profile = before_profile if desired == original and before_profile is not None else json_bytes(desired)
        # Pack lifecycle approval covers only the pack changes. Never bless
        # unrelated profile drift, including on a subsequent no-op mutation.
        approved = (before_profile is not None and old["profile_digest"] == digest(before_profile))
        fresh = before_profile is None and not old["packs"] and old["profile_digest"] is None
        if action == "sync" or approved or fresh:
            newstate["profile_digest"] = digest(after_profile)
        if before_profile != after_profile:
            files.insert(0, self.file_operation(".harness/project.json", before_profile, after_profile))
        before_state = regular_bytes(self.state_path)
        after_state = json_bytes(newstate)
        if before_state != after_state:
            files.append(self.file_operation(".harness/local/ownership.json", before_state, after_state))
        for op in operations:
            print(("REMOVE" if op["after"] is None else "LINK") + " " + op["path"])
        for op in files:
            print(("REMOVE" if op["after"] is None else "WRITE") + " " + op["path"])
        if action == "deactivate" and any(c.startswith(selection + ":") for c in desired["required_checks"]):
            print("NOTE: retained required checks for this pack remain unsatisfied until explicitly revised")
        if newstate["profile_digest"] is None:
            print("NOTE: unapproved profile changes retained; explicit project sync required before check execution")
        print("Pack instructions approved for exposure; checks still require explicit --execute")
        if not operations and not files:
            print("NO CHANGES")
            return
        if not apply:
            print("DRY RUN: no project writes")
            return
        self.transaction(operations, files)

    def audit_collisions(self, names, old):
        owned = set(self.expected_links(old["packs"]))
        from harness import SKILLS
        seen = set(SKILLS)
        roots = [*self.skill_dirs, Path.home() / ".agents/skills", Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / "skills", Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills"]
        # Include ancestor native skill roots through the enclosing Git root.
        for parent in ([] if (self.root / ".git").exists() else self.root.parents):
            for layout in self.layouts:
                roots.append(parent / layout["project_skills_path"])
            if (parent / ".git").exists():
                break
        for root in set(roots):
            if not root.is_dir():
                continue
            for child in root.iterdir():
                path = child / "SKILL.md"
                if not path.is_file():
                    continue
                if child.is_relative_to(self.root) and child.relative_to(self.root).as_posix() in owned:
                    continue
                text = path.read_text()
                match = re.search(r"(?m)^name:\s*[\"']?([a-z0-9-]+)", text[:8192])
                if match:
                    seen.add(match.group(1))
        if seen.intersection(names):
            raise Refusal("Skill identifier conflicts with existing core/user/project skills")

    def file_operation(self, path, before, after):
        current = self.root / path
        return {"path": path, "before": encode(before), "after": encode(after),
                "mode": current.stat().st_mode & 0o777 if before is not None else 0o600}

    def allowed_directories(self):
        return {".harness", ".harness/local", *[p.relative_to(self.root).as_posix() for p in self.skill_dirs],
                *[p.parent.relative_to(self.root).as_posix() for p in self.skill_dirs]}

    def lock(self):
        path = self.local / "lock"
        parents_safe(path)
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        import stat
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            os.close(fd)
            raise Refusal("Invalid project lock")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise Refusal("Project lifecycle operation already running") from None
        return fd

    def transaction(self, links, files):
        if exists(self.local) and not exists(self.state_path):
            raise Refusal("Unowned private project state directory exists")
        created = []
        for path in (self.root / ".harness", self.local):
            parents_safe(path / "entry")
            if not exists(path):
                path.mkdir(mode=0o700)
                created.append(path.relative_to(self.root).as_posix())
        private_ignore = self.local / ".gitignore"
        if not exists(private_ignore):
            from harness import exclusive_write
            exclusive_write(private_ignore, b"*\n!.gitignore\n")
        fd = self.lock()
        journal = {"schema_version": 1, "links": links, "files": files, "directories": created,
                   "committed": False}
        try:
            if exists(self.journal):
                raise Refusal("Project transaction appeared during preflight")
            self.compare(journal, before=True)
            atomic_write(self.journal, json_bytes(journal))
            try:
                for op in links:
                    path = self.root / op["path"]
                    for parent in (path.parent.parent, path.parent):
                        if not exists(parent):
                            journal["directories"].append(parent.relative_to(self.root).as_posix())
                            atomic_write(self.journal, json_bytes(journal))
                            parents_safe(parent / "entry")
                            parent.mkdir(mode=0o700)
                    if read_link(path) != op["before"]:
                        raise Refusal("Link changed during apply")
                    if op["before"] is not None:
                        path.unlink()
                    if op["after"] is not None:
                        path.symlink_to(op["after"])
                for op in files:
                    path = self.root / op["path"]
                    if regular_bytes(path) != decode(op["before"]):
                        raise Refusal("File changed during apply")
                    data = decode(op["after"])
                    if data is None:
                        path.unlink()
                    else:
                        atomic_write(path, data, op["mode"])
                journal["committed"] = True
                atomic_write(self.journal, json_bytes(journal))
                self.journal.unlink()
            except BaseException:
                if not journal["committed"]:
                    try:
                        self.rollback(journal)
                        self.journal.unlink()
                        if not exists(self.state_path):
                            atomic_write(self.state_path, json_bytes({"schema_version": 1, "packs": {}, "profile_digest": None, "created_ignores": []}))
                    except (OSError, Refusal):
                        print("Rollback incomplete; project recovery journal retained")
                raise
        finally:
            os.close(fd)
        print("APPLIED: project profile and owned skill projections updated")

    def compare(self, journal, before):
        key = "before" if before else "after"
        for op in journal["links"]:
            if read_link(self.root / op["path"]) != op[key]:
                raise Refusal("Project link identity differs from transaction")
        for op in journal["files"]:
            if regular_bytes(self.root / op["path"]) != decode(op[key]):
                raise Refusal("Project file content differs from transaction")

    def rollback(self, journal):
        # Verify all entries before reverting any: refuse newer user content.
        for op in journal["links"]:
            current = read_link(self.root / op["path"])
            if current not in (op["before"], op["after"], None):
                raise Refusal("Modified project link prevents recovery")
        for op in journal["files"]:
            current = regular_bytes(self.root / op["path"])
            if current not in (decode(op["before"]), decode(op["after"])):
                raise Refusal("Modified project file prevents recovery")
        for op in reversed(journal["files"]):
            path = self.root / op["path"]
            before = decode(op["before"])
            if regular_bytes(path) == before:
                continue
            if before is None:
                path.unlink()
            else:
                atomic_write(path, before, op["mode"])
        for op in reversed(journal["links"]):
            path = self.root / op["path"]
            if read_link(path) == op["before"]:
                continue
            if exists(path):
                path.unlink()
            if op["before"] is not None:
                path.symlink_to(op["before"])
        for value in sorted(journal["directories"], key=len, reverse=True):
            path = self.root / value
            if path != self.local and not path.is_symlink():
                try:
                    path.rmdir()
                except OSError:
                    pass

    def recover(self, apply=False):
        raw = regular_bytes(self.journal)
        if raw is None:
            print("NO CHANGES: no project journal")
            return
        journal = decode_json(raw, "project journal")
        allowed_files = {".harness/project.json", ".harness/local/ownership.json", *[p.relative_to(self.root).as_posix() + "/.gitignore" for p in self.skill_dirs]}
        try:
            if set(journal) != {"schema_version", "committed", "directories", "files", "links"} or type(journal["schema_version"]) is not int or journal["schema_version"] != 1 or type(journal["committed"]) is not bool:
                raise ValueError()
            if not set(journal["directories"]) <= self.allowed_directories():
                raise ValueError()
            if len({op["path"] for op in journal["files"]}) != len(journal["files"]) or len({op["path"] for op in journal["links"]}) != len(journal["links"]):
                raise ValueError()
            for op in journal["files"]:
                if set(op) != {"path", "before", "after", "mode"}:
                    raise ValueError()
                if op["path"] not in allowed_files or type(op["mode"]) is not int or not 0 <= op["mode"] <= 0o777:
                    raise ValueError()
                decode(op["before"]); decode(op["after"])
            for op in journal["links"]:
                path = Path(op["path"])
                if path.parent.as_posix() not in {p.relative_to(self.root).as_posix() for p in self.skill_dirs} or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", path.name):
                    raise ValueError()
                if any(op[k] is not None and not isinstance(op[k], str) for k in ("before", "after")):
                    raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise Refusal("Invalid project recovery journal") from None
        print("RECOVERY: preserve committed state" if journal["committed"] else "RECOVERY: restore pre-transaction profile/files/links")
        if not apply:
            print("DRY RUN: no project writes")
            return
        fd = self.lock()
        try:
            if regular_bytes(self.journal) != raw:
                raise Refusal("Journal changed before recovery")
            if journal["committed"]:
                self.compare(journal, before=False)
            else:
                self.rollback(journal)
            self.journal.unlink()
            if not exists(self.state_path):
                atomic_write(self.state_path, json_bytes({"schema_version": 1, "packs": {}, "profile_digest": None, "created_ignores": []}))
        finally:
            os.close(fd)
        print("RECOVERED")
