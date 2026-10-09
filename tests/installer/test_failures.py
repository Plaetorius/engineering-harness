import copy
import json
from unittest.mock import patch
from support import Fixture, harness


class Failures(Fixture):
    def test_link_failure_rolls_back(self):
        original = harness.Path.symlink_to
        counter = 0
        def fail_second(path, *args, **kwargs):
            nonlocal counter
            counter += 1
            if counter == 2:
                raise OSError("simulated write failure")
            return original(path, *args, **kwargs)
        with patch.object(harness.Path, "symlink_to", fail_second):
            with self.assertRaises(OSError):
                self.install()
        for p, _ in self.h.links():
            self.assertFalse(harness.exists(p))
        self.assertFalse(self.h.journal.exists())

    def test_settings_write_failure_rolls_back_links(self):
        raw = self.settings({"theme": "fixture"})
        original = harness.atomic_write
        def failure(path, *args, **kwargs):
            if path == self.h.settings:
                raise OSError("simulated settings write failure")
            return original(path, *args, **kwargs)
        with patch.object(harness, "atomic_write", failure):
            with self.assertRaises(OSError):
                self.install(both=True)
        self.assertEqual(raw, self.h.settings.read_bytes())
        for p, _ in self.h.links():
            self.assertFalse(harness.exists(p))

    def test_interrupted_install_recovers_only_matching_entries(self):
        self.install()
        state = self.h.load(self.h.manifest)
        state["phase"] = "installing"
        self.h.manifest.unlink()
        self.h.journal.write_text(json.dumps(state))
        with self.assertRaises(harness.Refusal):
            self.install()
        self.quiet(self.h.uninstall, apply=True, recover=True)
        for p, _ in self.h.links():
            self.assertFalse(harness.exists(p))

    def test_crash_after_commit_retains_install(self):
        self.install()
        state = self.h.load(self.h.manifest)
        state["phase"] = "installing"
        self.h.journal.write_text(json.dumps(state))
        self.quiet(self.h.uninstall, apply=True, recover=True)
        self.quiet(self.h.doctor)

    def test_interrupted_uninstall_is_resumable(self):
        raw = self.settings({"fixture": "keep"})
        self.install(both=True)
        state = self.h.load(self.h.manifest)
        state["phase"] = "uninstalling"
        self.h.journal.write_text(json.dumps(state))
        self.h.cleanup(state)
        # Simulate crash after links and backup removal, before manifest cleanup.
        self.quiet(self.h.uninstall, apply=True, recover=True)
        self.assertEqual(raw, self.h.settings.read_bytes())
        self.assertFalse(self.h.journal.exists())

    def test_recovery_refuses_user_replacement(self):
        self.install()
        state = self.h.load(self.h.manifest)
        state["phase"] = "installing"
        self.h.manifest.unlink()
        self.h.journal.write_text(json.dumps(state))
        p = self.h.links()[0][0]
        p.unlink()
        p.write_text("replacement")
        before = self.snapshot()
        with self.assertRaises(harness.Refusal):
            self.quiet(self.h.uninstall, apply=True, recover=True)
        self.assertEqual(before, self.snapshot())

    def test_lock_prevents_parallel_lifecycle(self):
        self.install()
        fd = self.h.lock()
        try:
            with self.assertRaises(harness.Refusal):
                self.h.lock()
        finally:
            harness.os.close(fd)
    def test_failed_upgrade_preserves_preexisting_links_and_manifest(self):
        with patch.object(harness,'SKILLS',harness.SKILLS[:4]):self.install()
        before=self.snapshot()
        with patch.object(harness.Path,'symlink_to',side_effect=OSError('Injected upgrade failure')):
            with self.assertRaises(OSError):self.install()
        self.assertEqual(before,self.snapshot())
