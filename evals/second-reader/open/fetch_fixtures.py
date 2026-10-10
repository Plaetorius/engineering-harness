#!/usr/bin/env python3
"""Download and verify open-data fixtures listed in manifest.json (stdlib only; never executes downloaded content).
Usage: python3 -I fetch_fixtures.py [source_id ...]
Each download is checked against its sha256 BEFORE it is unpacked; archive members are validated (no absolute paths,
no '..', regular files only, bounded count/size) and unpacked into their own directory under data/<source id>/."""
import hashlib, json, sys, tarfile, urllib.request, zipfile
from pathlib import Path

here = Path(__file__).resolve().parent
manifest = json.loads((here / "manifest.json").read_text())
MAX_MEMBERS, MAX_BYTES = 20000, 600 * 1024 * 1024


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def safe(name):
    return not (name.startswith("/") or ".." in Path(name).parts or "\\" in name)


def unpack_tar(archive, dest, expect_count):
    with tarfile.open(archive) as t:
        members = t.getmembers()
        files = [m for m in members if m.isfile()]
        if len(members) > MAX_MEMBERS or sum(m.size for m in files) > MAX_BYTES:
            sys.exit(f"{archive.name}: archive too large")
        for m in members:
            if not safe(m.name) or not (m.isfile() or m.isdir()):
                sys.exit(f"{archive.name}: unsafe member {m.name!r}")
        if expect_count and abs(len(files) - expect_count) > expect_count * 0.2:
            sys.exit(f"{archive.name}: expected ~{expect_count} files, found {len(files)}")
        t.extractall(dest, members=members, filter="data")
    return len(files)


wanted = set(sys.argv[1:])
for src in manifest["sources"]:
    if wanted and src["id"] not in wanted:
        continue
    d = here / "data" / src["id"]
    d.mkdir(parents=True, exist_ok=True)
    for dl in src["downloads"]:
        name = dl["url"].rsplit("/", 1)[-1].replace("+", "_")
        path = d / name
        if not path.exists() or sha(path) != dl["sha256"]:
            print(f"downloading {dl['url']}")
            urllib.request.urlretrieve(dl["url"], path)
        if sha(path) != dl["sha256"]:
            path.unlink()
            sys.exit(f"{src['id']}: sha256 mismatch for {name} - refusing to use")
        if dl.get("unpack") == "zip":
            with zipfile.ZipFile(path) as z:
                for member, want in dl["expect"].items():
                    if not safe(member):
                        sys.exit("unsafe member name")
                    target = d / member
                    if not target.exists() or sha(target) != want:
                        z.extract(member, d)
                    if sha(target) != want:
                        sys.exit(f"{src['id']}: {member} sha256 mismatch")
        elif dl.get("unpack") == "tar":
            n = unpack_tar(path, d, dl.get("expect_count"))
            print(f"  {name}: {n} files")
    print(f"{src['id']}: OK -> {d}")
