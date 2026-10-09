import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('diagram_renderer',ROOT/'skills/architecture-map/scripts/render.py')
renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)


class Capabilities(unittest.TestCase):
    def test_renderer_absence_does_not_download_or_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);source=folder/'source.mmd';source.write_text('flowchart LR\n A["Client"] --> B["API"]\n')
            before=list(folder.iterdir())
            with patch.object(renderer.shutil,'which',return_value=None),patch.object(renderer.subprocess,'run') as run:
                result=renderer.render(source,folder)
            self.assertEqual(result['status'],'unavailable');self.assertFalse(result['syntax_validated'])
            self.assertEqual(list(folder.iterdir()),before);run.assert_not_called()
    def test_renderer_rejects_active_and_external_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);source=folder/'source.mmd'
            for text in ['flowchart LR\nclick A "https://example.test"','%%{init: {}}%%\nflowchart LR\nA --> B','flowchart LR\nA["<img src=x>"]']:
                source.write_text(text)
                with self.assertRaises(ValueError):renderer.render(source,folder)
    def test_local_renderer_protocol_uses_fresh_artifacts_and_strict_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);source=folder/'source.mmd';source.write_text('sequenceDiagram\n participant A\n participant B\n A->>B: request\n')
            def fake(argv,**kwargs):
                self.assertEqual(argv[0],'/trusted/mmdc')
                config=json.loads(Path(argv[argv.index('-c')+1]).read_text())
                self.assertEqual(config['securityLevel'],'strict')
                Path(argv[argv.index('-o')+1]).write_text('<svg/>')
                return type('Result',(),{'returncode':0})()
            with patch.object(renderer.shutil,'which',return_value='/trusted/mmdc'),patch.object(renderer.subprocess,'run',side_effect=fake):
                result=renderer.render(source,folder)
            self.assertEqual(result['status'],'success')
            self.assertEqual(source.read_text(),'sequenceDiagram\n participant A\n participant B\n A->>B: request\n')
            self.assertNotEqual(Path(result['source']),source)
            self.assertTrue(result['png'].endswith('.png'));self.assertTrue(Path(result['png']).is_file())
    def test_open_image_uses_local_opener_and_never_a_url(self):
        calls=[]
        def fake(argv,**kwargs):
            calls.append(argv);return type('Result',(),{'returncode':0})()
        with patch.object(renderer.shutil,'which',return_value='/usr/bin/open'),patch.object(renderer.subprocess,'run',side_effect=fake):
            self.assertTrue(renderer.open_image('/tmp/diagram.png'))
        self.assertEqual(calls,[[ '/usr/bin/open','/tmp/diagram.png']])
        with patch.object(renderer.shutil,'which',return_value=None):
            self.assertFalse(renderer.open_image('/tmp/diagram.png'))
    def test_render_failure_is_not_syntax_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);source=folder/'source.mmd';source.write_text('flowchart LR\nA --> B\n')
            with patch.object(renderer.shutil,'which',return_value='/trusted/mmdc'),patch.object(renderer.subprocess,'run',return_value=type('Result',(),{'returncode':1})()):
                self.assertFalse(renderer.render(source,folder)['syntax_validated'])
    def test_core_review_profiles_have_stable_metadata(self):
        import sys
        sys.path.insert(0,str(ROOT/'scripts/lib'))
        from harness import metadata
        roles=['general-reviewer','software-architect','security-engineer','data-engineer','designer','performance-engineer']
        for role in roles:self.assertEqual(metadata(ROOT/'standards/reviewers'/f'{role}.md')['name'],role)
