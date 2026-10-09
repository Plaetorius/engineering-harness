"""Static accessibility and evaluation assets, not behavioral compliance tests."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]


class VSDResources(unittest.TestCase):
    def test_controlled_scenarios_have_distinct_prompts_and_rubrics(self):
        data=json.loads((ROOT/'tests/fixtures/vsd/scenarios.json').read_text())
        self.assertEqual(data['schema_version'],1)
        required={'routine','capabilities','large-feature','dependencies','independent','ownership','delegation','failed-gate','local-only','blocked','high-risk','non-web'}
        scenarios=data['scenarios']
        ids=[s['id'] for s in scenarios]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(required <= set(ids))
        for case in scenarios:
            self.assertEqual(set(case),{'id','prompt','rubric'})
            self.assertIsInstance(case['prompt'],str);self.assertTrue(case['prompt'].strip())
            self.assertTrue(case['rubric'])
            for criterion in case['rubric']:self.assertIsInstance(criterion,str)
    def test_shared_skills_resolve_one_canonical_policy(self):
        policy=ROOT/'standards/vertical-slice-delivery.md'
        for name in ('plan-feature','implement-api','review-diff','debug-root-cause'):
            skill=ROOT/'skills'/name/'SKILL.md'
            self.assertIn('../../standards/vertical-slice-delivery.md',skill.read_text())
            self.assertEqual((skill.parent/'../../standards/vertical-slice-delivery.md').resolve(),policy)
        self.assertIn('<harness>/standards/vertical-slice-delivery.md',(ROOT/'core/global-instructions.md').read_text())
    def test_template_is_portable_without_a_pack_profile(self):
        template=(ROOT/'templates/slice.md').read_text()
        for field in ('Outcome','Scope and non-goals','Dependencies and contracts','Acceptance criteria','Verification','Risk and ownership','Status and evidence'):
            self.assertIn('## '+field,template)
        self.assertTrue((ROOT/'templates/../standards/vertical-slice-delivery.md').is_file())
        self.assertNotIn('web-typescript',template)
