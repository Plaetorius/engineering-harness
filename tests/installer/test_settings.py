import json
from unittest.mock import patch
from support import Fixture, harness


class Settings(Fixture):
    def test_patch_preserves_values_and_restores_exact_bytes(self):
        original = {"hooks": {"Stop": [{"command": "fixture-only"}]}, "env": {"FIXTURE": "not-a-secret"},
                    "permissions": {"allow": ["Read"]}, "pluginConfigs": {"other": {"options": {"x": 1}}}}
        before = self.settings(original)
        self.install(both=True)
        current = json.loads(self.h.settings.read_bytes())
        current["pluginConfigs"].pop(harness.PLUGIN)
        self.assertEqual(current, original)
        manifest = self.h.load(self.h.manifest)
        backup = harness.Path(manifest["settings_patch"]["backup"])
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.quiet(self.h.uninstall, apply=True)
        self.assertEqual(self.h.settings.read_bytes(), before)
        self.assertFalse(backup.exists())

    def test_patch_missing_settings_uninstalls_created_file(self):
        self.install(both=True)
        self.assertTrue(self.h.settings.is_file())
        self.quiet(self.h.uninstall, apply=True)
        self.assertFalse(self.h.settings.exists())

    def test_optional_patch_not_default(self):
        before = self.settings({"model": "fixture"})
        self.install()
        self.assertEqual(before, self.h.settings.read_bytes())

    def test_later_opt_in_patch(self):
        self.install()
        self.install(both=True)
        self.assertEqual(json.loads(self.h.settings.read_text())["pluginConfigs"][harness.PLUGIN]["options"]["instructionFiles"], harness.MODE)
        self.quiet(self.h.uninstall, apply=True)

    def test_explicit_mode_conflict_both_ids(self):
        for name in (harness.PLUGIN, harness.LEGACY_PLUGIN):
            with self.subTest(name=name):
                self.settings({"pluginConfigs": {name: {"options": {"instructionFiles": "managed-only"}}}})
                with self.assertRaises(harness.Refusal):
                    self.install(both=True)

    def test_disabled_plugin_refused(self):
        self.settings({"enabledPlugins": {harness.PLUGIN: False}})
        with self.assertRaises(harness.Refusal):
            self.install(both=True)

    def test_existing_same_mode_remains_unowned(self):
        raw = self.settings({"pluginConfigs": {harness.PLUGIN: {"options": {"instructionFiles": harness.MODE}}}})
        self.install(both=True)
        self.assertIsNone(self.h.load(self.h.manifest)["settings_patch"])
        self.quiet(self.h.uninstall, apply=True)
        self.assertEqual(raw, self.h.settings.read_bytes())

    def test_user_edit_after_patch_refuses_restore(self):
        self.install(both=True)
        value = json.loads(self.h.settings.read_text())
        value["theme"] = "user-choice"
        self.h.settings.write_text(json.dumps(value))
        before = self.snapshot()
        with self.assertRaises(harness.Refusal):
            self.quiet(self.h.uninstall, apply=True)
        self.assertEqual(before, self.snapshot())

    def test_invalid_settings_shapes_refused(self):
        for value in ({"pluginConfigs": []}, {"pluginConfigs": {harness.PLUGIN: None}}, {"enabledPlugins": []}):
            self.settings(value)
            with self.assertRaises(harness.Refusal):
                self.install(both=True)

    def test_missing_or_old_cli_refuses_patch(self):
        with patch.object(harness.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaises(harness.Refusal):
                self.quiet(self.h.install, both=True, apply=True)
        response = harness.subprocess.CompletedProcess([], 0, "2.1.284 (Claude Code)\n", "")
        with patch.object(harness.subprocess, "run", return_value=response):
            with self.assertRaises(harness.Refusal):
                self.quiet(self.h.install, both=True, apply=True)

    def test_valid_cli_accepts_patch(self):
        response = harness.subprocess.CompletedProcess([], 0, "2.1.293 (Claude Code)\n", "")
        with patch.object(harness.subprocess, "run", return_value=response):
            self.quiet(self.h.install, both=True)
        self.assertFalse(self.h.settings.exists())
    def test_preserved_settings_upgrade_never_changes_backup_or_settings(self):
        with patch.object(harness,'SKILLS',harness.SKILLS[:4]):self.install(both=True)
        previous=self.h.load(self.h.manifest);record=previous['settings_patch']
        backup=harness.Path(record['backup']);backup_bytes=backup.read_bytes()
        value=json.loads(self.h.settings.read_text());value['theme']='user-choice'
        self.h.settings.write_text(json.dumps(value));edited=self.h.settings.read_bytes()
        with self.assertRaises(harness.Refusal):self.install()
        self.quiet(self.h.install,apply=True,preserve_settings=True)
        self.assertEqual(self.h.settings.read_bytes(),edited);self.assertEqual(backup.read_bytes(),backup_bytes)
        self.assertEqual(self.h.load(self.h.manifest)['settings_patch'],record)
        self.quiet(self.h.doctor,preserve_settings=True)
        with self.assertRaises(harness.Refusal):self.quiet(self.h.uninstall,apply=True)
        self.assertEqual(self.h.settings.read_bytes(),edited)
