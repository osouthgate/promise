"""The fictional walkthrough must preserve failure, missing evidence and scope."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/simulation-prep'


class FictionalPromiseReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name) / 'results'
        result = subprocess.run([sys.executable, str(EXAMPLE / 'run_simulations.py'), '--trial', '--out', str(cls.out)],
                                cwd=ROOT, capture_output=True, text=True, timeout=120)
        if result.returncode:
            cls.temp.cleanup()
            raise AssertionError(result.stdout + result.stderr)
        cls.summary = json.loads((cls.out / 'summary.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def read(self, project, path):
        return json.loads((self.out / project / path).read_text())

    def test_regression_and_unchecked_new_work_survive_replay(self):
        for name in ('reportcheck', 'borrowworks'):
            stages = self.summary['projects'][name]['stages']
            self.assertEqual([s['scriptedFail'] for s in stages], [0, 1, 0])
            self.assertEqual([s['unchecked'] for s in stages], [0, 0, 1])
            self.assertEqual([s['continuations'] for s in stages], [0, 1, 1])
            final = self.read(name, 'new-job-and-recovery/map.json')
            self.assertTrue(all(r['verdict'] == 'not-built' for r in final['rows']))
            trace = self.read(name, 'trace.json')['actualLocalCommands']
            negative = next(x for x in trace if x['label'].startswith('negative control:'))
            self.assertEqual(negative['exit'], 1)
            self.assertIn('1-5', negative['stdout'] + negative['stderr'])

    def test_service_assurance_remains_independent_and_honest(self):
        for name in ('reportcheck', 'borrowworks'):
            initial = self.read(name, 'initial/service-report.json')
            middle = self.read(name, 'extensions-and-regression/service-report.json')
            self.assertTrue(initial['replay'])
            self.assertIn('missing', {t['status'] for t in initial['targets']})
            self.assertIn('acceptable', {t['status'] for t in middle['targets']})
            self.assertIn('unacceptable', {t['status'] for t in middle['targets']})
            for control, expected in [('hard-limit', 'unacceptable'), ('fast-low-quality', 'unacceptable'),
                                      ('capacity-wrong-load', 'unacceptable'), ('stale', 'stale'),
                                      ('missing', 'missing'), ('revision-mismatch', 'invalid-evidence'),
                                      ('availability-zero-traffic', 'insufficient')]:
                report = self.read(name, f'service-controls/{control}.json')
                self.assertIn(expected, {t['status'] for t in report['targets']})
                self.assertTrue(all(t['functionalVerdict'] == 'not-built' for t in report['targets']))

    def test_shared_policy_edit_fans_out_without_copying_definitions(self):
        for name in ('reportcheck', 'borrowworks'):
            final = self.read(name, 'new-job-and-recovery/map.json')
            changed = self.read(name, 'shared-policy-change.json')
            self.assertEqual(len(final['servicePolicies']), 5)
            self.assertEqual(changed['summary']['files'], 1)
            self.assertEqual(changed['summary']['rowsChanged'], len(final['rows']))
            self.assertTrue(all(r['fields'] == ['servicePolicies.accessible-interface'] for r in changed['rows']))

    def test_lane_green_does_not_become_real_scenario_proof(self):
        for name in ('reportcheck', 'borrowworks'):
            control = self.read(name, 'lane-gap-control.json')
            row = next(r for r in control['report']['rows'] if r['id'] == control['row'])
            self.assertEqual(row['computed'], 'proven')
            self.assertIn('not per-scenario proof', control['interpretation'])
            self.assertIn('Fixed synthetic', control['_simulation'])

    def test_relaxed_jobs_preserve_scenarios_and_check_their_own_citations(self):
        for name, jobs, count, links in (('reportcheck', 4, 15, 11), ('borrowworks', 5, 20, 14)):
            with self.subTest(name=name):
                baseline = self.read(name, 'new-job-and-recovery/map.json')
                trial = self.read(name, 'trial/map.json')
                self.assertEqual(len(trial['rows']), jobs)
                self.assertEqual(trial['servicePolicies'], baseline['servicePolicies'])
                self.assertTrue(all('parent' not in row for row in trial['rows']))
                before = [s['fixtureId'] for row in baseline['rows'] for s in row['scenarios']]
                after = [s['fixtureId'] for row in trial['rows'] for s in row['scenarios']]
                self.assertEqual(len(after), count)
                self.assertCountEqual(after, before)
                functional = self.read(name, 'trial/functional-report.json')
                statuses = [s['evidence']['status'] for row in functional['rows'] for s in row['scenarios']]
                self.assertCountEqual(statuses, ['passing'] * (count - 1) + ['unchecked'])
                service = self.read(name, 'trial/service-report.json')
                self.assertTrue(service['replay'])
                self.assertEqual(len(service['targets']), links)
                baseline_service = self.read(name, 'new-job-and-recovery/service-report.json')
                previous_statuses = {(t['row'], t['target']): t['status'] for t in baseline_service['targets']}
                self.assertEqual({(t['row'], t['target']): t['status'] for t in service['targets']},
                                 {key: status for key, status in previous_statuses.items()
                                  if key[0] in {row['id'] for row in trial['rows']}})
                control = self.read(name, 'trial/lane-gap-control.json')
                scenario = next(s for row in control['report']['rows'] for s in row['scenarios']
                                if s['id'] == control['scenario'])
                self.assertTrue(scenario['proven'])  # Legacy lane status stays green.
                self.assertEqual(scenario['evidence']['status'], 'missing-citation')
                page = (self.out / name / 'trial/outcome.html').read_text()
                self.assertIn('Explicit scenario evidence: passing.', page)
                self.assertIn('Historical SLA replay', page)


if __name__ == '__main__':
    unittest.main()
