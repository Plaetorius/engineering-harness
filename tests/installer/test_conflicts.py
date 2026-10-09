import json
import os
from pathlib import Path
from support import Fixture, ROOT, harness


class Conflicts(Fixture):
    def test_file_conflict_aborts_whole_install(self):
        self.h.claude.joinpath("skills").mkdir(parents=True)
        foreign = self.h.claude / "skills/debug-root-cause"
        foreign.write_text("user content")
        before = self.snapshot()
        with self.assertRaises(harness.Refusal):
            self.install()
        self.assertEqual(before, self.snapshot())

    def test_dangling_symlink_conflict(self):
        self.h.codex.mkdir()
        (self.h.codex / "AGENTS.md").symlink_to("missing")
        with self.assertRaises(harness.Refusal):
            self.install()

    def test_identical_unowned_symlink_is_not_adopted(self):
        self.h.codex.mkdir()
        dest, source = self.h.links()[0]
        dest.symlink_to(os.path.relpath(source, dest.parent))
        with self.assertRaises(harness.Refusal):
            self.install()
        self.assertTrue(dest.is_symlink())

    def test_global_override_blocks_install(self):
        self.h.codex.mkdir()
        (self.h.codex / "AGENTS.override.md").write_text("override")
        with self.assertRaises(harness.Refusal):
            self.install()

    def test_symlink_parent_is_refused(self):
        other = self.base / "foreign"
        other.mkdir()
        self.h.claude.mkdir()
        (self.h.claude / "skills").symlink_to(other)
        with self.assertRaises(harness.Refusal):
            self.install()
        self.assertEqual(list(other.iterdir()), [])

    def test_unowned_state_is_not_reused(self):
        self.h.state.mkdir()
        (self.h.state / "private.txt").write_text("keep")
        with self.assertRaises(harness.Refusal):
            self.install()

    def test_skill_name_collision_in_different_directory(self):
        other = self.h.claude / "skills/other-name"
        other.mkdir(parents=True)
        (other / "SKILL.md").write_text("---\nname: implement-api\ndescription: collision\n---\n")
        with self.assertRaises(harness.Refusal):
            self.install()

    def test_modified_link_blocks_uninstall_before_any_removal(self):
        self.install()
        dest = self.h.links()[-1][0]
        dest.unlink()
        dest.write_text("user replacement")
        before = self.snapshot()
        with self.assertRaises(harness.Refusal):
            self.quiet(self.h.uninstall, apply=True)
        self.assertEqual(before, self.snapshot())

    def test_tampered_manifest_cannot_target_arbitrary_file(self):
        self.install()
        manifest = json.loads(self.h.manifest.read_text())
        victim = self.home / "keep.txt"
        victim.write_text("keep")
        manifest["links"][0]["path"] = str(victim)
        self.h.manifest.write_text(json.dumps(manifest))
        with self.assertRaises(harness.Refusal):
            self.quiet(self.h.uninstall, apply=True)
        self.assertEqual(victim.read_text(), "keep")

    def test_malformed_manifest_refused(self):
        self.install()
        self.h.manifest.write_text('{"schema":1,"schema":1}')
        with self.assertRaises(harness.Refusal):
            self.quiet(self.h.uninstall, apply=True)

    def test_moved_source_is_detected(self):
        self.install()
        moved = harness.Harness(repo=self.base / "moved")
        with self.assertRaises(harness.Refusal):
            self.quiet(moved.doctor)
        # Uninstall uses recorded link identity, not the source's existence.
        self.quiet(moved.uninstall, apply=True)

    def test_state_context_change_is_refused(self):
        self.install()
        other = harness.Harness(claude_home=self.base / "other", repo=ROOT)
        with self.assertRaises(harness.Refusal):
            self.quiet(other.uninstall, apply=True)

    def test_hardlinked_settings_refused(self):
        self.settings({})
        os.link(self.h.settings, self.home / "alias.json")
        with self.assertRaises(harness.Refusal):
            self.install(both=True)

    def test_overlapping_state_refused(self):
        with self.assertRaises(harness.Refusal):
            harness.Harness(state_dir=self.h.claude)
