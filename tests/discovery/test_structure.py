import importlib.util
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("harness", ROOT / "scripts/lib/harness.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class Structure(unittest.TestCase):
    def test_failure_fixture_reproduces_expected_bug(self):
        proc = subprocess.run(["python3", "-m", "unittest", "-v"],
                              cwd=ROOT / "tests/fixtures/failing-test", capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("-1900 != 80", proc.stderr)
    def test_portable_metadata_and_directory_names(self):
        for name in harness.SKILLS:
            metadata = harness.metadata(ROOT / "skills" / name / "SKILL.md")
            self.assertEqual(metadata["name"], name)

    def test_skill_profile_and_core_references(self):
        paths = list((ROOT / "skills").rglob("*.md")) + list((ROOT / "profiles").glob("*.md"))
        for path in paths:
            for link in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" not in link:
                    self.assertTrue((path.parent / link.split("#")[0]).is_file(), (path, link))
        self.assertLess(len((ROOT / "core/global-instructions.md").read_bytes()), 4096)

    def test_portable_content_has_no_runtime_only_execution(self):
        for root in ("core", "skills", "standards", "profiles"):
            for p in (ROOT / root).rglob("*.md"):
                text = p.read_text()
                self.assertNotIn("!`", text, p)
                self.assertNotIn("/Users/", text, p)
                self.assertNotIn("mcp__", text, p)
                self.assertNotIn("CLAUDE_PLUGIN_ROOT", text, p)

    def test_repository_docs_have_no_personal_paths_or_broken_links(self):
        for path in ROOT.rglob("*.md"):
            if ".local" in path.parts:
                continue
            text = path.read_text()
            self.assertNotIn("/Users/", text, path)
            self.assertEqual(text.count("```") % 2, 0, path)
            for link in re.findall(r"\]\(([^)]+)\)", text):
                if "://" not in link and not link.startswith("#"):
                    self.assertTrue((path.parent / link.split("#")[0]).exists(), (path, link))
