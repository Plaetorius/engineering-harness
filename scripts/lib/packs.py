"""Pack discovery and validation. Reading a pack never runs its code."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

from harness import Refusal, decode_json, metadata, regular_bytes, SKILLS

REPO = Path(__file__).resolve().parents[2]


def validate_schema(value, schema, at="document"):
    """The documented schema subset; no network or external schema references."""
    types = {"object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
             "string": lambda v: isinstance(v, str), "integer": lambda v: type(v) is int,
             "number": lambda v: type(v) in (int, float), "boolean": lambda v: type(v) is bool,
             "null": lambda v: v is None}
    expected = schema.get("type")
    if expected and not any(types[t](value) for t in ([expected] if isinstance(expected, str) else expected)):
        raise Refusal(f"{at}: incorrect value type")
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        raise Refusal(f"{at}: unsupported value/version")
    if "enum" in schema and value not in schema["enum"]:
        raise Refusal(f"{at}: unsupported value")
    if isinstance(value, dict):
        if any(key not in value for key in schema.get("required", [])):
            raise Refusal(f"{at}: required field missing")
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                validate_schema(item, properties[key], f"{at}.{key}")
            elif extra is False:
                raise Refusal(f"{at}: unsupported field {key}")
            elif isinstance(extra, dict):
                validate_schema(item, extra, f"{at}.{key}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", float("inf")):
            raise Refusal(f"{at}: invalid string length")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise Refusal(f"{at}: invalid string format")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            raise Refusal(f"{at}: invalid array length")
        if schema.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            raise Refusal(f"{at}: duplicate entries")
        for i, item in enumerate(value):
            validate_schema(item, schema.get("items", {}), f"{at}[{i}]")
    if type(value) in (int, float):
        if value < schema.get("minimum", -float("inf")) or value > schema.get("maximum", float("inf")):
            raise Refusal(f"{at}: numeric value outside allowed range")
    if "oneOf" in schema:
        matched = 0
        for branch in schema["oneOf"]:
            try:
                validate_schema(value, branch, at)
                matched += 1
            except Refusal:
                pass
        if matched != 1:
            raise Refusal(f"{at}: specify exactly one command form")
    if "not" in schema:
        try:
            validate_schema(value, schema["not"], at)
        except Refusal:
            return
        raise Refusal(f"{at}: forbidden combination")


def schema(name):
    return decode_json((REPO / "schemas" / (name + ".schema.json")).read_bytes(), name)


def relative_path(root, value, directory=False, must_exist=True):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise Refusal("Resource path must be a portable relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", value):
        raise Refusal("Resource path escapes its owner")
    candidate = root / path
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise Refusal("Resolved resource path escapes its owner")
    if must_exist:
        if directory is None:
            valid, kind = candidate.is_file() or candidate.is_dir(), "path"
        else:
            valid = candidate.is_dir() if directory else candidate.is_file()
            kind = "directory" if directory else "file"
        if not valid:
            raise Refusal(f"Referenced {kind} missing: {value}")
    return candidate


def fingerprint(root):
    hash_ = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(p in (".git", "__pycache__", ".DS_Store") for p in rel.parts):
            continue
        if path.is_symlink():
            raise Refusal("Pack payload may not contain symlinks")
        if path.is_file():
            data = regular_bytes(path)
            name = rel.as_posix().encode()
            hash_.update(len(name).to_bytes(8, "big") + name)
            hash_.update(len(data).to_bytes(8, "big") + data)
        elif not path.is_dir():
            raise Refusal("Pack payload contains a special file")
    return "sha256:" + hash_.hexdigest()


class Pack:
    def __init__(self, root):
        self.root = Path(root).resolve()
        raw = regular_bytes(self.root / "pack.json")
        if raw is None:
            raise Refusal("Pack manifest missing")
        self.manifest = decode_json(raw, "pack.json")
        validate_schema(self.manifest, schema("pack"), "pack")
        self.id = self.manifest["id"]
        self.version = self.manifest["version"]
        skills = self.manifest["skills"]
        names = set()
        for entry in skills:
            name = entry["name"]
            if not name.startswith(self.id + "-") or name in names or name in SKILLS:
                raise Refusal("Skill identifier must be unique and carry its pack prefix")
            path = relative_path(self.root, entry["path"], directory=True)
            if path.name != name or metadata(path / "SKILL.md")["name"] != name:
                raise Refusal("Declared skill name, directory and manifest must match")
            names.add(name)
        role_ids = set()
        for entry in self.manifest.get("reviewers", []):
            identifier = entry["id"]
            if (not identifier.startswith(self.id + "-") or identifier in role_ids
                    or (REPO / "standards/reviewers" / (identifier + ".md")).is_file()):
                raise Refusal("Reviewer identifier must be unique and carry its pack prefix")
            path = relative_path(self.root, entry["path"])
            if path.suffix != ".md" or path.stem != identifier or metadata(path)["name"] != identifier:
                raise Refusal("Reviewer identifier, Markdown filename and frontmatter must match")
            role_ids.add(identifier)
        ids = [c["id"] for c in self.manifest["checks"]]
        if len(set(ids)) != len(ids):
            raise Refusal("Duplicate pack check identifiers")
        for check in self.manifest["checks"]:
            if check.get("project_command") and check["cwd"] != "project":
                raise Refusal("Named project commands must run from the project")
            if check.get("cwd_subdir"):
                relative_path(self.root, check["cwd_subdir"], directory=True,
                              must_exist=check["cwd"] == "pack")
            for arg in check.get("argv", []):
                if arg == "{pack}" or arg.startswith("{pack}/"):
                    relative_path(self.root, arg[len("{pack}"):].lstrip("/") or ".", directory=None)
        for key in ("standards", "workflows", "templates", "tools"):
            for value in self.manifest.get(key, []):
                relative_path(self.root, value)
        # No embedded runtime plugins or command interpolation. Plain scripts
        # remain allowed resources; activation/execution is a separate boundary.
        for path in self.root.rglob("*"):
            if any(p in (".git", "__pycache__") for p in path.relative_to(self.root).parts):
                continue
            if path.name in (".claude-plugin", ".codex-plugin", "plugin.json"):
                raise Refusal("Native runtime plugin bundles are not portable pack skills")
            if path.suffix == ".md" and path.is_file():
                text = path.read_text()
                if re.search(r"!`", text):
                    raise Refusal("Automatic shell interpolation is not allowed in pack instructions")
                for link in re.findall(r"\]\(([^)]+)\)", text):
                    if "://" not in link and not link.startswith("#"):
                        candidate = path.parent / link.split("#")[0]
                        if not candidate.resolve().is_relative_to(self.root) or not candidate.exists():
                            raise Refusal("Pack documentation reference is missing or outside its pack")
        self.digest = fingerprint(self.root)

    def compatible(self, runtimes=("codex", "claude")):
        c = self.manifest["compatibility"]
        if sys.platform not in c["platforms"] or not set(runtimes) <= set(c["runtimes"]):
            raise Refusal("Pack is incompatible with this platform or selected runtimes")

    def descriptor(self):
        return {"id": self.id, "version": self.version, "digest": self.digest}


def discover(repo=REPO, roots=(), selected=None):
    locations = [Path(repo) / "packs"] + [Path(p).resolve() for p in roots]
    found = {}
    seen = set()
    declared = set()
    pending = []
    for location in locations:
        if not location.exists():
            continue
        candidates = [location] if (location / "pack.json").exists() else [p.parent for p in location.glob("*/pack.json")]
        for path in sorted(candidates):
            if path.resolve() in seen:
                continue
            seen.add(path.resolve())
            # Index readable identifiers before validating payloads so an
            # invalid duplicate cannot shadow a selected, otherwise valid pack.
            try:
                raw = regular_bytes(path.resolve() / "pack.json")
                if raw is None:
                    raise Refusal("Pack manifest missing")
                identifier = decode_json(raw, "pack.json").get("id")
            except (Refusal, OSError):
                if selected is None:
                    raise
                continue
            if isinstance(identifier, str):
                if identifier in declared:
                    raise Refusal("Duplicate pack identifier across discovery roots: " + identifier)
                declared.add(identifier)
            if selected is not None and identifier != selected:
                continue
            pending.append(path)
    for path in pending:
        pack = Pack(path)
        if pack.id in found:
            raise Refusal("Duplicate pack identifier across discovery roots: " + pack.id)
        found[pack.id] = pack
    return found


def new_pack(path, identifier):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", identifier) or len(identifier) > 64:
        raise Refusal("Invalid pack identifier")
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise Refusal("Pack destination already exists")
    from harness import parents_safe, exclusive_write, json_bytes
    parents_safe(path / "entry")
    if not path.parent.is_dir():
        raise Refusal("Pack parent directory must already exist")
    path.mkdir()
    try:
        for name in ("standards", "skills", "checks", "templates", "tools"):
            (path / name).mkdir()
        manifest = {"schema_version": 1, "id": identifier, "version": "0.1.0",
                    "description": "Describe the domain and activation boundary.", "skills": [],
                    "standards": [], "workflows": ["workflow.md"], "checks": [], "templates": [], "tools": [],
                    "compatibility": {"harness_schema": 1, "runtimes": ["codex", "claude"], "platforms": ["darwin", "linux"]}}
        exclusive_write(path / "pack.json", json_bytes(manifest))
        exclusive_write(path / "workflow.md", b"# Pack workflow\n\nApply only after explicit project activation. Describe domain decisions here.\n")
        Pack(path)
    except BaseException:
        # Only our freshly created empty skeleton is removed on failure.
        import shutil
        shutil.rmtree(path)
        raise
