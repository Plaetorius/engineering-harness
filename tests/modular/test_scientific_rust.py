"""Exercise the shipped research pack through existing lifecycle and checks."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
from harness import json_bytes
from packs import Pack, discover, schema, validate_schema
from projects import Project
from checks import run


class ScientificRust(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'home'; self.home.mkdir()
        self.project = self.root / 'project'; self.project.mkdir()
        self.env = patch.dict(os.environ, {'HOME': str(self.home),
            'CODEX_HOME': str(self.home / '.codex'), 'CLAUDE_CONFIG_DIR': str(self.home / '.claude')})
        self.env.start()
        self.p = Project(self.project)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def mutate(self, action, selection=None):
        with contextlib.redirect_stdout(io.StringIO()):
            self.p.mutation(action, selection, apply=True)

    def test_builtin_discovery_does_not_activate_research(self):
        self.assertIn('scientific-rust', discover(ROOT))
        self.assertEqual(self.p.inspect()['packs'], [])
        self.assertEqual(run(self.p)['checks'], [])
        self.assertFalse((self.project / '.harness').exists())

    def test_shared_skill_and_reviewer_exposure_requires_activation(self):
        pack = Pack(ROOT / 'packs/scientific-rust')
        self.mutate('activate', pack.id)
        inspected = self.p.inspect()['packs'][0]
        self.assertEqual(len(inspected['reviewers']), 3)
        for role in inspected['reviewers']:
            self.assertTrue(Path(role['path']).is_file())
        for entry in pack.manifest['skills']:
            for folder in self.p.skill_dirs:
                link = folder / entry['name']
                self.assertTrue(link.is_symlink())
                self.assertEqual(link.resolve(), pack.root / entry['path'])
        self.mutate('deactivate', pack.id)
        self.assertEqual(self.p.inspect()['packs'], [])
        for entry in pack.manifest['skills']:
            for folder in self.p.skill_dirs:
                self.assertFalse((folder / entry['name']).is_symlink())

    def test_template_missing_scientific_commands_blocks_required_gates(self):
        template = json.loads((ROOT / 'packs/scientific-rust/templates/project-profile.example.json').read_text())
        validate_schema(template, schema('project'))
        self.mutate('activate', 'scientific-rust')
        profile = self.p.profile()
        profile['required_checks'] = template['required_checks']
        profile['acceptance_criteria'] = template['acceptance_criteria']
        self.p.profile_path.write_bytes(json_bytes(profile))
        self.mutate('sync')
        report = run(self.p, execute=True, selected=['scientific-rust:differential'])
        self.assertFalse(report['required_checks_passed'])
        self.assertFalse(report['execution_ok'])
        self.assertTrue(all(r['status'] == 'skipped' for r in report['results']))
        self.assertIn('scientific-rust:invariants', [r['id'] for r in report['results']])

    def test_named_project_check_executes_only_on_request(self):
        self.mutate('activate', 'scientific-rust')
        profile = self.p.profile()
        # This proves command routing, not scientific correctness or benchmarking.
        profile['commands']['scientific-differential'] = {
            'argv': [sys.executable, '-c', 'print("synthetic comparison command")'],
            'cwd': '.', 'timeout_seconds': 2}
        profile['required_checks'] = ['scientific-rust:differential']
        self.p.profile_path.write_bytes(json_bytes(profile))
        self.mutate('sync')
        preview = run(self.p, selected=['scientific-rust:differential'])
        self.assertEqual(preview['checks'][0]['argv'], profile['commands']['scientific-differential']['argv'])
        self.assertFalse((self.p.local / 'reports').exists())
        report = run(self.p, execute=True, selected=['scientific-rust:differential'])
        self.assertTrue(report['execution_ok'])
        output = self.project / report['results'][0]['stdout']
        self.assertIn('synthetic comparison command', output.read_text())

    def test_web_and_research_coexist_and_removal_preserves_user_files(self):
        self.mutate('activate', 'web-typescript')
        before = self.p.state()['packs']['web-typescript']
        for folder in self.p.skill_dirs:
            (folder / 'user-rule').write_text('preserve\n')
        self.mutate('activate', 'scientific-rust')
        self.assertEqual({p['id'] for p in self.p.inspect()['packs']}, {'web-typescript', 'scientific-rust'})
        self.mutate('deactivate', 'scientific-rust')
        self.assertEqual(self.p.state()['packs']['web-typescript'], before)
        for folder in self.p.skill_dirs:
            self.assertTrue((folder / 'web-typescript-review').is_symlink())
            self.assertEqual((folder / 'user-rule').read_text(), 'preserve\n')
