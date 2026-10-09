import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("harness", ROOT / "scripts/lib/harness.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="harness-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home with spaces"
        self.home.mkdir()
        self.env = patch.dict(os.environ, {"HOME": str(self.home), "CODEX_HOME": str(self.home / ".codex"),
                                          "CLAUDE_CONFIG_DIR": str(self.home / ".claude")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.h = harness.Harness(repo=ROOT)

    def quiet(self, method, *args, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return method(*args, **kwargs)

    def install(self, both=False):
        with patch.object(self.h, "version_check"):
            self.quiet(self.h.install, both=both, apply=True)

    def settings(self, value):
        self.h.settings.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(value, separators=(",", ":")) + "\n").encode()
        self.h.settings.write_bytes(raw)
        return raw

    def snapshot(self):
        result = {}
        for p in self.base.rglob("*"):
            name = str(p.relative_to(self.base))
            result[name] = ("link", os.readlink(p)) if p.is_symlink() else ("dir",) if p.is_dir() else ("file", p.read_bytes())
        return result
