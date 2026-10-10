import json
import os
from pathlib import Path
import subprocess
import shutil
from unittest.mock import patch
from support import Fixture, ROOT, harness


class Lifecycle(Fixture):
    def test_canonical_update_refreshes_provenance_without_replacing_links(self):
        repo = self.base / "source"
        repo.mkdir()
        for name in ("core", "skills", "standards", "profiles"):
            shutil.copytree(ROOT / name, repo / name)
        other = harness.Harness(repo=repo)
        self.quiet(other.install, apply=True)
        previous = other.load(other.manifest)
        core = repo / "core/global-instructions.md"
        core.write_text(core.read_text() + "\nFixture-only policy update.\n")
        self.quiet(other.install, apply=True)
        current = other.load(other.manifest)
        self.assertEqual(previous["links"], current["links"])
        self.assertNotEqual(previous["source_hashes"], current["source_hashes"])
        self.assertEqual(current["source_hashes"], other.source_hashes())

    def test_dry_run_does_not_write(self):
        before = self.snapshot()
        self.quiet(self.h.install)
        self.assertEqual(before, self.snapshot())

    def test_fresh_install_and_doctor(self):
        self.install()
        self.quiet(self.h.doctor)
        manifest = self.h.load(self.h.manifest)
        self.assertEqual(len(manifest["links"]), 2 + 2 * len(harness.SKILLS))
        for dest, source in self.h.links():
            self.assertTrue(dest.is_symlink())
            self.assertEqual(dest.resolve(), source.resolve())
            self.assertFalse(os.path.isabs(os.readlink(dest)))

    def test_repeat_is_byte_identical(self):
        self.install(both=True)
        before = self.snapshot()
        self.install(both=True)
        self.assertEqual(before, self.snapshot())

    def test_uninstall_preview_does_not_write(self):
        self.install()
        before = self.snapshot()
        self.quiet(self.h.uninstall)
        self.assertEqual(before, self.snapshot())

    def test_uninstall_preserves_user_files_and_supports_reinstall(self):
        raw = self.settings({"model": "fixture-model", "hooks": {"Stop": []}})
        self.install()
        extra = self.h.claude / "skills/user-added.txt"
        extra.write_text("keep")
        self.quiet(self.h.uninstall, apply=True)
        for dest, _ in self.h.links():
            self.assertFalse(harness.exists(dest))
        self.assertEqual(self.h.settings.read_bytes(), raw)
        self.assertEqual(extra.read_text(), "keep")
        self.install()
        self.quiet(self.h.doctor)

    def test_alternate_config_homes_and_state(self):
        other = harness.Harness(home=self.home, codex_home=self.base / "isolated/codex",
                                claude_home=self.base / "isolated/claude", state_dir=self.base / "state", repo=ROOT)
        self.quiet(other.install, apply=True)
        self.quiet(other.doctor)
        self.assertTrue((self.home / ".agents/skills/review-diff").is_symlink())
        self.assertFalse((self.home / ".codex").exists())
        self.quiet(other.uninstall, apply=True)

    def test_entrypoint_is_dry_run_by_default(self):
        before = self.snapshot()
        proc = subprocess.run(["bash", str(ROOT / "scripts/install")], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("DRY RUN", proc.stdout)
        self.assertNotIn(str(self.home), proc.stdout)
        self.assertEqual(before, self.snapshot())

    def test_doctor_missing_install_fails(self):
        with self.assertRaises(harness.Refusal):
            self.quiet(self.h.doctor)

    def test_missing_cli_versions_reported_without_failure(self):
        self.install()
        with patch.object(harness.subprocess, "run", side_effect=FileNotFoundError):
            self.quiet(self.h.doctor, versions=True)

    def test_manifest_is_private(self):
        self.install()
        self.assertEqual(self.h.manifest.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.h.state.stat().st_mode & 0o777, 0o700)
    def test_both_adapters_expose_vsd_and_shared_skill_references(self):
        self.install()
        policy=ROOT/'standards/vertical-slice-delivery.md'
        for dest, source in self.h.links():
            if source == ROOT/'core/global-instructions.md':
                self.assertIn('<harness>/standards/vertical-slice-delivery.md',dest.read_text())
                self.assertEqual(dest.resolve().parent.parent/'standards/vertical-slice-delivery.md',policy)
            else:
                target=dest.resolve()
                self.assertIn('../../standards/vertical-slice-delivery.md',(dest/'SKILL.md').read_text())
                self.assertEqual((target/'../../standards/vertical-slice-delivery.md').resolve(),policy)
    def test_upgrade_preserves_legacy_links_and_adds_new_skills(self):
        legacy=harness.SKILLS[:4]
        with patch.object(harness,'SKILLS',legacy):self.install()
        previous=self.h.load(self.h.manifest)
        self.install()
        current=self.h.load(self.h.manifest)
        self.assertEqual(len(current['links']),2+2*len(harness.SKILLS))
        self.assertTrue(all(link in current['links'] for link in previous['links']))
        self.quiet(self.h.uninstall,apply=True)
        for path,_ in self.h.links():self.assertFalse(harness.exists(path))
    def test_upgrade_conflict_preserves_existing_installation(self):
        with patch.object(harness,'SKILLS',harness.SKILLS[:4]):self.install()
        conflict=self.h.home/'.agents/skills/architecture-map';conflict.mkdir()
        (conflict/'user-file').write_text('keep')
        before=self.snapshot()
        with self.assertRaises(harness.Refusal):self.install()
        self.assertEqual(before,self.snapshot())
