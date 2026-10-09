import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
from harness import Refusal, json_bytes
from packs import Pack, discover, new_pack
from projects import Project, default_profile
from checks import run


class Modular(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'home'; self.home.mkdir()
        self.project = self.root / 'project'; self.project.mkdir()
        self.env = patch.dict(os.environ, {'HOME': str(self.home), 'CODEX_HOME': str(self.home/'.codex'), 'CLAUDE_CONFIG_DIR': str(self.home/'.claude')})
        self.env.start()
        self.repo = self.root / 'repo'; (self.repo/'packs').mkdir(parents=True)
        self.p = Project(self.project, self.repo)
    def tearDown(self):
        self.env.stop(); self.temp.cleanup()
    def pack(self, identifier='example', checks=None, external=False):
        folder = (self.root if external else self.repo/'packs') / identifier
        new_pack(folder, identifier)
        skill = folder/'skills'/f'{identifier}-review'; skill.mkdir()
        (skill/'SKILL.md').write_text(f'---\nname: {identifier}-review\ndescription: Review example fixture work.\n---\n\nRead relevant project guidance.\n')
        manifest = json.loads((folder/'pack.json').read_text())
        manifest['skills'] = [{'name': f'{identifier}-review', 'path': f'skills/{identifier}-review'}]
        manifest['checks'] = checks or []
        (folder/'pack.json').write_bytes(json_bytes(manifest))
        return Pack(folder)
    def activate(self, pack):
        with contextlib.redirect_stdout(io.StringIO()):
            self.p.mutation('activate', str(pack.root), apply=True, trust=[pack.digest])
    def check(self, argv, name='check', **kw):
        return {'id': name, 'description': 'Example check', 'argv': argv, 'cwd': 'project', 'timeout_seconds': 2, **kw}
    def test_core_without_pack(self):
        self.assertEqual(self.p.inspect()['packs'], [])
        self.assertFalse((self.project/'.harness').exists())
    def test_discovery_validation_never_execute(self):
        marker=self.project/'marker'
        pack=self.pack(checks=[self.check([sys.executable,'-c',f'open({str(marker)!r},"w").write("executed")'])])
        self.assertIn(pack.id, discover(self.repo))
        self.assertFalse(marker.exists())
        self.activate(pack)
        run(self.p)
        self.assertFalse(marker.exists())
        self.assertTrue(run(self.p,execute=True)['execution_ok'])
        self.assertTrue(marker.exists())
    def test_invalid_manifest(self):
        pack=self.pack(); data=pack.manifest; data['schema_version']=True
        (pack.root/'pack.json').write_bytes(json_bytes(data))
        with self.assertRaises(Refusal): Pack(pack.root)
    def test_missing_and_escaping_resource(self):
        pack=self.pack(); data=pack.manifest; data['standards']=['../outside.md']
        (pack.root/'pack.json').write_bytes(json_bytes(data))
        with self.assertRaises(Refusal): Pack(pack.root)
    def test_two_packs_and_deactivation_preserve_configuration(self):
        a=self.pack(); b=self.pack('another')
        for folder in self.p.skill_dirs:
            folder.mkdir(parents=True); (folder/'.gitignore').write_text('unrelated\n')
            (folder/'user-skill').mkdir()
        self.activate(a); self.activate(b)
        self.assertEqual(len(self.p.inspect()['packs']),2)
        with contextlib.redirect_stdout(io.StringIO()): self.p.mutation('deactivate',a.id,apply=True)
        for folder in self.p.skill_dirs:
            self.assertFalse((folder/'example-review').exists())
            self.assertTrue((folder/'another-review').is_symlink())
            self.assertTrue((folder/'user-skill').exists())
            self.assertTrue((folder/'.gitignore').read_text().startswith('unrelated\n'))
    def test_skill_collision(self):
        pack=self.pack(); folder=self.p.skill_dirs[0]/'unrelated';folder.mkdir(parents=True)
        (folder/'SKILL.md').write_text('---\nname: example-review\ndescription: Existing user skill.\n---\n')
        with self.assertRaises(Refusal): self.activate(pack)
    def test_external_trust(self):
        pack=self.pack(external=True)
        with self.assertRaises(Refusal): self.p.mutation('activate',str(pack.root),apply=True)
        self.activate(pack);self.assertEqual(self.p.inspect()['packs'][0]['origin'],'external')
    def test_pack_drift_refused(self):
        pack=self.pack();self.activate(pack)
        (pack.root/'workflow.md').write_text('Changed instructions\n')
        with self.assertRaises(Refusal): self.p.inspect()
    def test_modified_link_preserved(self):
        pack=self.pack();self.activate(pack);link=self.p.skill_dirs[0]/'example-review'
        link.unlink();link.symlink_to(self.root/'elsewhere')
        with self.assertRaises(Refusal): self.p.mutation('deactivate',pack.id,apply=True)
        self.assertEqual(os.readlink(link),str(self.root/'elsewhere'))
    def test_profile_commands_require_sync(self):
        pack=self.pack(checks=[self.check([sys.executable,'-c','pass'])]); self.activate(pack)
        profile=self.p.profile();profile['acceptance_criteria']=['Manual review required']
        self.p.profile_path.write_bytes(json_bytes(profile))
        with self.assertRaises(Refusal): run(self.p,execute=True)
        with contextlib.redirect_stdout(io.StringIO()):self.p.mutation('sync',apply=True)
        self.assertTrue(run(self.p,execute=True)['execution_ok'])
    def test_pack_mutations_do_not_approve_unreviewed_commands(self):
        pack=self.pack(checks=[{'id':'named','description':'Named project command',
            'project_command':'test','cwd':'project','timeout_seconds':2}])
        other=self.pack('other')
        self.activate(pack);self.activate(other)
        profile=self.p.profile()
        profile['commands']['test']={'argv':[sys.executable,'-c','pass'],
            'cwd':'.','timeout_seconds':2}
        self.p.profile_path.write_bytes(json_bytes(profile))
        with contextlib.redirect_stdout(io.StringIO()):self.p.mutation('sync',apply=True)
        marker=self.project/'unapproved-command'
        profile['commands']['test']['argv']=[sys.executable,'-c',
            f'from pathlib import Path;Path({str(marker)!r}).write_text("ran")']
        self.p.profile_path.write_bytes(json_bytes(profile))
        for action, selection in (('activate','other'), ('deactivate','other'), ('deactivate','absent')):
            with self.subTest(action=action,selection=selection):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.p.mutation(action,selection,apply=True)
                with self.assertRaises(Refusal):run(self.p,execute=True)
                self.assertFalse(marker.exists())
        with contextlib.redirect_stdout(io.StringIO()):self.p.mutation('sync',apply=True)
        self.assertTrue(run(self.p,execute=True)['execution_ok'])
        self.assertTrue(marker.exists())
    def test_initial_activation_preserves_existing_profile_approval_boundary(self):
        pack=self.pack(checks=[{'id':'named','description':'Named project command',
            'project_command':'test','cwd':'project','timeout_seconds':2}])
        profile=default_profile()
        profile['commands']['test']={'argv':[sys.executable,'-c','pass'],
            'cwd':'.','timeout_seconds':2}
        self.p.profile_path.parent.mkdir()
        self.p.profile_path.write_bytes(json_bytes(profile))
        self.activate(pack)
        with self.assertRaises(Refusal):run(self.p,execute=True)
        with contextlib.redirect_stdout(io.StringIO()):self.p.mutation('sync',apply=True)
        self.assertTrue(run(self.p,execute=True)['execution_ok'])
    def test_clean_pack_mutations_preserve_approved_command_execution(self):
        pack=self.pack(checks=[{'id':'named','description':'Named project command',
            'project_command':'test','cwd':'project','timeout_seconds':2}])
        self.activate(pack)
        profile=self.p.profile()
        profile['commands']['test']={'argv':[sys.executable,'-c','pass'],
            'cwd':'.','timeout_seconds':2}
        self.p.profile_path.write_bytes(json_bytes(profile))
        with contextlib.redirect_stdout(io.StringIO()):self.p.mutation('sync',apply=True)
        self.activate(self.pack('other'))
        self.assertTrue(run(self.p,execute=True)['execution_ok'])
        with contextlib.redirect_stdout(io.StringIO()):self.p.mutation('deactivate','other',apply=True)
        self.assertTrue(run(self.p,execute=True)['execution_ok'])
    def test_broken_pack_removal_preserves_unapproved_profile_changes(self):
        pack=self.pack();other=self.pack('other')
        self.activate(pack);self.activate(other)
        profile=self.p.profile()
        profile['commands']['test']={'argv':[sys.executable,'-c','pass'],
            'cwd':'.','timeout_seconds':2}
        self.p.profile_path.write_bytes(json_bytes(profile))
        shutil.rmtree(other.root)
        with contextlib.redirect_stdout(io.StringIO()):self.p.mutation('deactivate','other',apply=True)
        self.assertNotIn('other',self.p.state()['packs'])
        self.assertEqual(self.p.profile()['commands'],profile['commands'])
        with self.assertRaises(Refusal):run(self.p,execute=True)
        with contextlib.redirect_stdout(io.StringIO()):self.p.mutation('sync',apply=True)
        self.assertTrue(run(self.p,execute=True)['execution_ok'])
    def test_selected_pack_isolated_from_invalid_available_packs(self):
        pack=self.pack();broken=self.pack('broken')
        for contents in ('{}', '{', '{"id":"broken","schema_version":99}'):
            with self.subTest(contents=contents):
                (broken.root/'pack.json').write_text(contents)
                with self.assertRaises(Refusal):discover(self.repo)
                for selection in (pack.id,str(pack.root)):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.p.mutation('activate',selection,apply=True)
                    self.assertEqual(self.p.inspect()['packs'][0]['id'],pack.id)
                with contextlib.redirect_stdout(io.StringIO()):self.p.mutation('sync',apply=True)
        with self.assertRaises(Refusal):self.p.mutation('activate','broken',apply=True)
    def test_invalid_pack_cannot_hide_duplicate_identifier(self):
        pack=self.pack();broken=self.pack('broken')
        (broken.root/'pack.json').write_text('{"id":"example"}')
        for selection in (pack.id,str(pack.root)):
            with self.subTest(selection=selection):
                with self.assertRaisesRegex(Refusal,'Duplicate pack identifier'):
                    self.p.mutation('activate',selection,apply=True)
        self.assertFalse(self.p.profile_path.exists())
    def test_literal_braces_are_preserved_in_command_arguments(self):
        literal='{"configuration":"{unknown}"}'
        pack=self.pack(checks=[self.check([sys.executable,'-c',
            'import sys;print({"count": 1});print(sys.argv[1])',literal])])
        self.activate(pack)
        self.assertEqual(run(self.p)['checks'][0]['argv'][-1],literal)
        report=run(self.p,execute=True)
        self.assertTrue(report['execution_ok'])
        self.assertIn(literal,(self.project/report['results'][0]['stdout']).read_text())
    def test_placeholder_arguments_accept_files_directories_and_roots(self):
        (self.project/'src').mkdir();(self.project/'input.txt').write_text('fixture')
        pack=self.pack(checks=[self.check([sys.executable,'-c',
            'import pathlib,sys;print([pathlib.Path(p).is_dir() for p in sys.argv[1:]])',
            '{project}/src','{project}/input.txt','{pack}/standards','{pack}/workflow.md','{project}','{pack}'])])
        self.activate(pack)
        argv=run(self.p)['checks'][0]['argv']
        self.assertEqual(argv[-6:],[str(self.project/'src'),str(self.project/'input.txt'),
            str(pack.root/'standards'),str(pack.root/'workflow.md'),str(self.project),str(pack.root)])
        report=run(self.p,execute=True)
        self.assertTrue(report['execution_ok'])
        self.assertEqual((self.project/report['results'][0]['stdout']).read_text().strip(),
            '[True, False, True, False, True, True]')
    def test_placeholder_arguments_reject_missing_and_escaping_paths(self):
        (self.project/'outside-link').symlink_to(self.root,target_is_directory=True)
        for index,argument in enumerate(('{project}/missing','{project}/../outside',
                '{project}/outside-link','{pack}/missing','{pack}/../outside')):
            with self.subTest(argument=argument):
                with self.assertRaises(Refusal):
                    pack=self.pack('paths-'+str(index),checks=[self.check([sys.executable,'-c','pass',argument])])
                    self.activate(pack)
                    run(self.p)
                # Clean any successful activation before testing the next path.
                if 'paths-'+str(index) in self.p.state()['packs']:
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.p.mutation('deactivate','paths-'+str(index),apply=True)
    def test_nul_process_arguments_rejected_by_pack_and_project_validation(self):
        with self.assertRaises(Refusal):
            self.pack('invalid',checks=[self.check([sys.executable,'-c','pass','\x00'])])
        # Remove the invalid available fixture; validation of the selected pack
        # is tested separately from isolation of unrelated invalid manifests.
        shutil.rmtree(self.repo/'packs/invalid')
        pack=self.pack();self.activate(pack)
        profile=self.p.profile()
        profile['commands']['test']={'argv':[sys.executable,'-c','pass','\x00'],
            'cwd':'.','timeout_seconds':2}
        self.p.profile_path.write_bytes(json_bytes(profile))
        with self.assertRaises(Refusal):self.p.profile()
        with self.assertRaises(Refusal):run(self.p,execute=True)
        self.assertFalse((self.p.local/'reports').exists())
        import subprocess
        proc=subprocess.run([str(ROOT/'scripts/harness'),'check','run',
            '--project',str(self.project),'--execute'],capture_output=True,text=True)
        self.assertEqual(proc.returncode,1)
        self.assertIn('REFUSED:',proc.stderr)
        self.assertNotIn('Traceback',proc.stderr)
    def test_invalid_launch_arguments_report_execution_error_and_continue(self):
        import subprocess
        pack=self.pack(checks=[self.check([sys.executable,'-c','pass','invalid-fixture'],'invalid'),
            self.check([sys.executable,'-c','print("next check ran")'],'valid')])
        self.activate(pack)
        popen=subprocess.Popen
        def launch(argv,**kwargs):
            if argv[-1]=='invalid-fixture':raise ValueError('Invalid process argument')
            return popen(argv,**kwargs)
        with patch('checks.subprocess.Popen',side_effect=launch):
            report=run(self.p,execute=True)
        self.assertEqual([r['status'] for r in report['results']],['execution-error','success'])
        self.assertFalse(report['execution_ok'])
        stored=list(self.p.local.rglob('result.json'))
        self.assertEqual(len(stored),1)
        self.assertEqual(json.loads(stored[0].read_text()),report)
    def test_check_outcomes_and_reports(self):
        pack=self.pack(checks=[self.check([sys.executable,'-c','print("ok")'],'success'),self.check([sys.executable,'-c','raise SystemExit(2)'],'failure'),self.check(['missing-executable-123'],'error'),self.check([sys.executable,'-c','import time;time.sleep(3)'],'timeout',timeout_seconds=1),{'id':'skip','description':'Optional missing command','project_command':'absent','cwd':'project','timeout_seconds':1}])
        self.activate(pack);report=run(self.p,execute=True)
        self.assertEqual([r['status'] for r in report['results']],['success','failure','execution-error','execution-error','skipped'])
        self.assertFalse(report['execution_ok'])
        self.assertIn('ok',(self.project/report['results'][0]['stdout']).read_text())
    def test_required_unavailable_fails(self):
        pack=self.pack();self.activate(pack);profile=self.p.profile();profile['required_checks']=['example:absent'];self.p.profile_path.write_bytes(json_bytes(profile))
        with contextlib.redirect_stdout(io.StringIO()): self.p.mutation('sync',apply=True)
        self.assertFalse(run(self.p,execute=True)['required_checks_passed'])
    def test_named_command_working_directory(self):
        pack=self.pack(checks=[{'id':'named','description':'Named command','project_command':'test','cwd':'project','timeout_seconds':2}]);self.activate(pack)
        (self.project/'subdir').mkdir();profile=self.p.profile();profile['commands']['test']={'argv':[sys.executable,'-c','import pathlib;print(pathlib.Path.cwd().name)'],'cwd':'subdir','timeout_seconds':2};self.p.profile_path.write_bytes(json_bytes(profile))
        with contextlib.redirect_stdout(io.StringIO()): self.p.mutation('sync',apply=True)
        report=run(self.p,execute=True);self.assertEqual((self.project/report['results'][0]['stdout']).read_text().strip(),'subdir')
    def test_dry_run_preserves_files(self):
        pack=self.pack()
        with contextlib.redirect_stdout(io.StringIO()): self.p.mutation('activate',str(pack.root))
        self.assertFalse((self.project/'.harness').exists())
    def test_adapter_shared_capabilities(self):
        pack=self.pack();self.activate(pack)
        targets=[(folder/'example-review').resolve() for folder in self.p.skill_dirs]
        self.assertEqual(targets,[pack.root/'skills/example-review']*2)
    def test_duplicate_pack_id_refused(self):
        a=self.pack();b=self.pack(external=True)
        with self.assertRaises(Refusal):discover(self.repo,[b.root])
    def test_write_failure_rolls_back_and_retry_works(self):
        pack=self.pack()
        import projects
        original=projects.atomic_write
        failed=[False]
        def fail_profile(path,data,*args):
            if path == self.p.profile_path and not failed[0]:
                failed[0]=True;raise OSError('Injected write failure')
            return original(path,data,*args)
        with patch('projects.atomic_write',side_effect=fail_profile):
            with self.assertRaises(OSError):self.activate(pack)
        self.assertFalse(self.p.profile_path.exists())
        self.assertFalse(self.p.journal.exists())
        for folder in self.p.skill_dirs:self.assertFalse((folder/'example-review').exists())
        self.activate(pack)
        self.assertEqual(len(self.p.inspect()['packs']),1)
    def test_source_removal_allows_deactivation(self):
        pack=self.pack();self.activate(pack);shutil.rmtree(pack.root)
        with contextlib.redirect_stdout(io.StringIO()):self.p.mutation('deactivate',pack.id,apply=True)
        self.assertEqual(self.p.inspect()['packs'],[])
    def test_deactivation_preserves_unrelated_broken_pack(self):
        for problem in ('missing', 'invalid'):
            with self.subTest(problem=problem):
                selected=self.pack('selected-'+problem)
                remaining=self.pack('remaining-'+problem)
                for folder in self.p.skill_dirs:
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder/'user-config').write_text('preserve me\n')
                self.activate(selected);self.activate(remaining)
                record=self.p.state()['packs'][remaining.id]
                pin=next(p for p in self.p.profile()['packs'] if p['id']==remaining.id)
                links={folder:os.readlink(folder/(remaining.id+'-review')) for folder in self.p.skill_dirs}
                if problem=='missing':
                    shutil.rmtree(remaining.root)
                else:
                    (remaining.root/'pack.json').write_text('{}\n')
                before_profile=self.p.profile_path.read_bytes()
                before_state=self.p.state_path.read_bytes()
                with contextlib.redirect_stdout(io.StringIO()):
                    self.p.mutation('deactivate',selected.id)
                self.assertEqual(self.p.profile_path.read_bytes(),before_profile)
                self.assertEqual(self.p.state_path.read_bytes(),before_state)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.p.mutation('deactivate',selected.id,apply=True)
                self.assertNotIn(selected.id,self.p.state()['packs'])
                self.assertEqual(self.p.state()['packs'][remaining.id],record)
                self.assertEqual(next(p for p in self.p.profile()['packs'] if p['id']==remaining.id),pin)
                for folder in self.p.skill_dirs:
                    self.assertFalse((folder/(selected.id+'-review')).is_symlink())
                    self.assertEqual(os.readlink(folder/(remaining.id+'-review')),links[folder])
                    self.assertEqual((folder/'user-config').read_text(),'preserve me\n')
                with self.assertRaises(Refusal):self.p.inspect()
                with contextlib.redirect_stdout(io.StringIO()):
                    self.p.mutation('deactivate',remaining.id,apply=True)
    def test_unowned_destination_refused(self):
        pack=self.pack();folder=self.p.skill_dirs[0];folder.mkdir(parents=True)
        (folder/'example-review').symlink_to(pack.root/'skills/example-review')
        with self.assertRaises(Refusal):self.activate(pack)
    def test_embedded_dynamic_execution_rejected(self):
        pack=self.pack();(pack.root/'workflow.md').write_text('!`echo injected`\n')
        with self.assertRaises(Refusal):Pack(pack.root)
    def test_plugin_payload_rejected(self):
        pack=self.pack();(pack.root/'.claude-plugin').mkdir()
        with self.assertRaises(Refusal):Pack(pack.root)
    def test_recovery_rejects_foreign_paths(self):
        self.p.local.mkdir(parents=True)
        journal={'schema_version':1,'committed':False,'directories':[],'links':[], 'files':[{'path':'../foreign','before':None,'after':None,'mode':384}]}
        self.p.journal.write_bytes(json_bytes(journal))
        with self.assertRaises(Refusal):self.p.recover(True)
    def require(self, ids):
        profile=self.p.profile();profile['required_checks']=ids;self.p.profile_path.write_bytes(json_bytes(profile))
        with contextlib.redirect_stdout(io.StringIO()):self.p.mutation('sync',apply=True)
    def test_mandatory_failure_prevents_successful_gate(self):
        pack=self.pack(checks=[self.check([sys.executable,'-c','raise SystemExit(1)'])]);self.activate(pack)
        self.require(['example:check']);report=run(self.p,execute=True)
        self.assertFalse(report['required_checks_passed']);self.assertFalse(report['execution_ok'])
    def test_mandatory_skipped_command_prevents_successful_gate(self):
        pack=self.pack(checks=[{'id':'check','description':'Required command','project_command':'absent','cwd':'project','timeout_seconds':1}]);self.activate(pack)
        self.require(['example:check']);report=run(self.p,execute=True)
        self.assertEqual(report['results'][0]['status'],'skipped');self.assertFalse(report['execution_ok'])
    def test_subset_selection_cannot_omit_mandatory_failure(self):
        pack=self.pack(checks=[self.check([sys.executable,'-c','pass'],'local'),self.check([sys.executable,'-c','raise SystemExit(1)'],'integration')]);self.activate(pack)
        self.require(['example:integration']);report=run(self.p,execute=True,selected=['example:local'])
        self.assertEqual([r['id'] for r in report['results']],['example:local','example:integration'])
        self.assertFalse(report['execution_ok'])
    def test_cli_required_gate_failure_returns_nonzero(self):
        import subprocess
        pack=self.pack(checks=[self.check([sys.executable,'-c','raise SystemExit(1)'])]);self.activate(pack)
        self.require(['example:check'])
        proc=subprocess.run([str(ROOT/'scripts/harness'),'check','run','--project',str(self.project),'--execute'],capture_output=True,text=True)
        self.assertEqual(proc.returncode,1,proc.stderr)
        self.assertFalse(json.loads(proc.stdout)['required_checks_passed'])
    def role(self, pack, identifier=None):
        identifier=identifier or pack.id+'-auditor'
        path=pack.root/'reviewers'/f'{identifier}.md';path.parent.mkdir(exist_ok=True)
        path.write_text(f'---\nname: {identifier}\ndescription: Synthetic pack review perspective.\n---\n\nCheck example requirements without weakening core evidence.\n')
        data=pack.manifest;data['reviewers']=[{'id':identifier,'path':path.relative_to(pack.root).as_posix()}]
        (pack.root/'pack.json').write_bytes(json_bytes(data))
        return Pack(pack.root)
    def test_pack_role_requires_activation_and_disappears_on_deactivation(self):
        pack=self.role(self.pack())
        self.assertEqual(self.p.inspect()['packs'],[])
        self.activate(pack)
        role=self.p.inspect()['packs'][0]['reviewers'][0]
        self.assertEqual(role['id'],'example-auditor');self.assertTrue(Path(role['path']).is_file())
        with contextlib.redirect_stdout(io.StringIO()):self.p.mutation('deactivate',pack.id,apply=True)
        self.assertEqual(self.p.inspect()['packs'],[])
    def test_reviewer_path_and_metadata_are_validated(self):
        pack=self.role(self.pack());data=pack.manifest;data['reviewers'][0]['path']='../outside.md'
        (pack.root/'pack.json').write_bytes(json_bytes(data))
        with self.assertRaises(Refusal):Pack(pack.root)
    def test_duplicate_role_declarations_are_refused(self):
        pack=self.role(self.pack());data=pack.manifest;data['reviewers']*=2
        (pack.root/'pack.json').write_bytes(json_bytes(data))
        with self.assertRaises(Refusal):Pack(pack.root)
    def test_core_role_identifier_cannot_be_overridden(self):
        with self.assertRaises(Refusal):self.role(self.pack('general'),'general-reviewer')
    def test_cross_pack_role_collision_refused(self):
        first=self.role(self.pack(),'example-long-auditor');second=self.role(self.pack('example-long'),'example-long-auditor')
        self.activate(first)
        with self.assertRaises(Refusal):self.activate(second)
        self.assertEqual(len(self.p.inspect()['packs']),1)
    def test_pack_role_drift_requires_reapproval(self):
        pack=self.role(self.pack());self.activate(pack)
        (pack.root/'reviewers/example-auditor.md').write_text('Changed role instructions\n')
        with self.assertRaises(Refusal):self.p.inspect()
