"""Service assurance stays separate from functional proof, for any service promise."""
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/promise/scripts/service_report.py'
NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def condition(metric, unit, operator, value):
    return {'metric': metric, 'unit': unit, 'operator': operator, 'value': value}


def search_policy():
    return {'id': 'interactive-search', 'kind': 'quantitative', 'revision': '1',
            'boundary': 'submit to complete visible results',
            'workload': '10000 notes, 20 concurrent signed-in users',
            'metric': 'duration', 'unit': 'ms', 'direction': 'lower', 'aggregation': 'each-sample',
            'target': 1000, 'unacceptable': 10000, 'windowSeconds': 3600,
            'minSamples': 2, 'maxAgeSeconds': 300,
            'guardrails': [condition('duration', 'ms', 'at-least', 0),
                           condition('relevance', 'score', 'at-least', 0.8),
                           condition('relevance', 'score', 'at-most', 1),
                           condition('correct', 'boolean', 'at-least', 1),
                           condition('correct', 'boolean', 'at-most', 1)],
            'acceptableWhen': [condition('relevance', 'score', 'at-least', 0.95)]}


def availability_policy():
    policy = search_policy()
    policy.update(id='request-availability', boundary='all completed or timed-out requests at the public API',
                  metric='request-success', unit='%', direction='higher', aggregation='request-success-ratio',
                  target=99.9, unacceptable=99, minSamples=100, guardrails=[], acceptableWhen=[])
    return policy


def capacity_policy():
    policy = search_policy()
    policy.update(id='loaded-throughput', boundary='completed requests per second in each 60-second interval',
                  workload='open-loop offered load of at least 120 requests/s, 10000 records',
                  metric='completed-throughput', unit='requests/s', direction='higher', target=100,
                  unacceptable=80, guardrails=[condition('offered-load', 'requests/s', 'at-least', 120),
                                               condition('p95-duration', 'ms', 'at-most', 1000)], acceptableWhen=[])
    return policy


def accessibility_policy():
    return {'id': 'accessible-interface', 'kind': 'assessment', 'revision': '1',
            'basis': 'The applicable WCAG AA success criteria for the named journeys.',
            'standard': {'name': 'WCAG', 'version': '2.2 AA'},
            'scope': 'search and checkout journeys, desktop and mobile, build example-1',
            'method': 'automated scan plus keyboard and screen-reader assessment',
            'criteria': {'target': 'All applicable AA criteria pass in scope.',
                         'unacceptable': 'Any applicable AA criterion fails in scope.'},
            'maxAgeSeconds': 86400}


def data_for(policy):
    return {'servicePolicies': [policy], 'rows': [{'id': 'CAP-1', 'verdict': 'proven',
                                                  'servicePolicyRefs': [policy['id']]}]}


def observation(policy=None, values=None, count=2):
    policy = policy or search_policy()
    units = {policy['metric']: policy['unit']}
    for group in ('guardrails', 'acceptableWhen'):
        units.update({c['metric']: c['unit'] for c in policy.get(group, [])})
    values = {'duration': 500, 'relevance': 0.9, 'correct': 1} if values is None else values
    return {'row': 'CAP-1', 'target': policy['id'], 'revision': policy['revision'],
            'boundary': policy['boundary'], 'workload': policy['workload'], 'units': units,
            'source': 'illustrative collector export', 'windowStart': '2026-11-04T11:00:00Z',
            'windowEnd': '2026-11-04T12:00:00Z',
            'samples': [{'id': f'sample-{i}', 'at': '2026-11-04T11:30:00Z',
                         'values': copy.deepcopy(values)} for i in range(count)]}


def assessment(policy=None):
    policy = policy or accessibility_policy()
    return {'row': 'CAP-1', 'target': policy['id'], 'revision': policy['revision'],
            'scope': policy['scope'], 'method': policy['method'], 'assessor': 'Example audit team',
            'rationale': 'The cited assessment checked every applicable criterion within scope.',
            'band': 'target', 'observedAt': '2026-11-04T12:00:00Z',
            'evidence': [{'ref': 'audit/example-1', 'description': 'Illustrative manual and automated assessment, not a real audit.'}]}


class ServiceReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('service_report', SCRIPT)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def report(self, obs=None, policy=None, data=None):
        return self.module.report(data or data_for(policy or search_policy()),
                                  {'observations': [] if obs is None else [obs]}, NOW)

    def status(self, obs=None, policy=None):
        return self.report(obs, policy)['targets'][0]['status']

    def test_search_target_middle_band_and_quality_are_paired(self):
        self.assertEqual(self.status(observation()), 'target')
        for latency in (1000, 1500, 2000, 5000, 9999):
            self.assertEqual(self.status(observation(values={'duration': latency, 'relevance': 0.95, 'correct': 1})), 'acceptable')
            self.assertEqual(self.status(observation(values={'duration': latency, 'relevance': 0.94, 'correct': 1})), 'unacceptable')
        for values in ({'duration': 500, 'relevance': 0.79, 'correct': 1},
                       {'duration': 500, 'relevance': 1, 'correct': 0},
                       {'duration': 10000, 'relevance': 1, 'correct': 1}):
            self.assertEqual(self.status(observation(values=values)), 'unacceptable')

    def test_hard_limit_is_not_hidden_by_average_or_other_requests_quality(self):
        obs = observation(values={'duration': 500, 'relevance': 1, 'correct': 1})
        obs['samples'][1]['values'].update(duration=10000)
        self.assertEqual(self.status(obs), 'unacceptable')
        obs['samples'][1]['values'].update(duration=5000, relevance=0.9)
        self.assertEqual(self.status(obs), 'unacceptable')

    def test_dimensions_and_band_counts_remain_separate(self):
        obs = observation(values={'duration': 500, 'relevance': 1, 'correct': 1})
        obs['samples'][1]['values']['duration'] = 5000
        result = self.report(obs)['targets'][0]
        self.assertEqual(result['counts'], {'target': 1, 'acceptable': 1, 'unacceptable': 0})
        self.assertEqual(result['measurements']['duration']['max'], 5000)
        self.assertEqual(result['measurements']['relevance']['min'], 1)

    def test_request_availability_uses_all_requests_not_time_based_uptime(self):
        policy = availability_policy()
        obs = observation(policy, {}, 100)
        for sample in obs['samples']:
            sample['successful'] = True
        self.assertEqual(self.status(obs, policy), 'target')
        obs['samples'][0]['successful'] = False
        self.assertEqual(self.status(obs, policy), 'acceptable')
        result = self.report(obs, policy)['targets'][0]
        self.assertEqual(result['measurements']['request-success'], {'unit': '%', 'value': 99, 'successful': 99, 'total': 100})
        obs['samples'][1]['successful'] = False
        self.assertEqual(self.status(obs, policy), 'unacceptable')
        del obs['samples'][0]['successful']
        self.assertEqual(self.status(obs, policy), 'invalid-evidence')

    def test_capacity_needs_observed_offered_load_and_latency_guardrail(self):
        policy = capacity_policy()
        for throughput, status in ((100, 'target'), (90, 'acceptable'), (80, 'acceptable'), (79, 'unacceptable')):
            obs = observation(policy, {'completed-throughput': throughput, 'offered-load': 120, 'p95-duration': 900})
            self.assertEqual(self.status(obs, policy), status)
        obs = observation(policy, {'completed-throughput': 100, 'offered-load': 10, 'p95-duration': 900})
        self.assertEqual(self.status(obs, policy), 'unacceptable')
        obs = observation(policy, {'completed-throughput': 100, 'offered-load': 120, 'p95-duration': 1001})
        self.assertEqual(self.status(obs, policy), 'unacceptable')

    def test_qualitative_conformance_has_no_invented_middle_band_or_score(self):
        policy = accessibility_policy()
        obs = assessment(policy)
        result = self.report(obs, policy)['targets'][0]
        self.assertEqual(result['status'], 'target')
        self.assertEqual(result['evaluation'], 'supplied-assessment')
        self.assertNotIn('measurements', result)
        obs['band'] = 'acceptable'
        self.assertEqual(self.status(obs, policy), 'invalid-evidence')
        obs['band'] = 'unacceptable'
        self.assertEqual(self.status(obs, policy), 'unacceptable')
        policy['criteria']['acceptable'] = 'Explicitly agreed temporary service exception; not a conformance claim.'
        obs['band'] = 'acceptable'
        self.assertEqual(self.status(obs, policy), 'acceptable')

    def test_assessment_needs_matching_scope_revision_method_evidence_and_freshness(self):
        policy = accessibility_policy()
        for key, value in (('scope', 'only homepage'), ('revision', 'old'), ('method', 'scan only'),
                           ('evidence', []), ('rationale', ''), ('assessor', ''),
                           ('observedAt', '2026-11-05T12:00:00Z')):
            obs = assessment(policy)
            obs[key] = value
            self.assertEqual(self.status(obs, policy), 'invalid-evidence')
        obs = assessment(policy)
        obs['observedAt'] = '2026-11-02T12:00:00Z'
        self.assertEqual(self.status(obs, policy), 'stale')
        self.assertEqual(self.status(policy=policy), 'missing')

    def test_shared_project_policy_is_referenced_without_copying_or_cross_proving(self):
        policy = accessibility_policy()
        data = data_for(policy)
        data['rows'].append({'id': 'CAP-2', 'servicePolicyRefs': [policy['id']]})
        result = self.report(assessment(policy), data=data)
        self.assertEqual([r['status'] for r in result['targets']], ['target', 'missing'])
        self.assertEqual(data['servicePolicies'], [policy])

    def test_missing_stale_short_future_and_wrong_scope_never_pass(self):
        self.assertEqual(self.status(), 'missing')
        obs = observation()
        obs.update(windowStart='2026-11-04T10:00:00Z', windowEnd='2026-11-04T11:00:00Z')
        for sample in obs['samples']:
            sample['at'] = '2026-11-04T10:30:00Z'
        self.assertEqual(self.status(obs), 'stale')
        self.assertEqual(self.status(observation(count=1)), 'insufficient')
        for key, value in (('windowEnd', '2026-11-04T12:01:00Z'), ('boundary', 'server only'),
                           ('revision', 'old'), ('source', ''), ('units', {'duration': 'seconds'})):
            obs = observation()
            obs[key] = value
            self.assertEqual(self.status(obs), 'invalid-evidence')

    def test_bad_policies_and_conditions_never_look_like_missing_evidence(self):
        for key, value in (('target', 10000), ('unacceptable', 500), ('minSamples', 0),
                           ('maxAgeSeconds', True), ('direction', 'unknown'), ('aggregation', 'p95'),
                           ('guardrails', {}), ('acceptableWhen', [None]), ('target', float('inf'))):
            policy = search_policy()
            policy[key] = value
            self.assertEqual(self.status(policy=policy), 'invalid-policy')
        for key in ('boundary', 'unit', 'metric', 'target', 'unacceptable', 'kind', 'revision'):
            policy = search_policy()
            del policy[key]
            self.assertEqual(self.status(policy=policy), 'invalid-policy')
        policy = accessibility_policy()
        policy['standard'] = {'name': 'WCAG'}
        self.assertEqual(self.status(policy=policy), 'invalid-policy')

    def test_malformed_samples_and_duplicates_are_rejected(self):
        for value in (-1, float('nan'), True, [], None):
            obs = observation()
            # Negative is a finite observation, classified against policy guardrails;
            # a quality score below its floor is unacceptable, not missing.
            obs['samples'][0]['values']['relevance'] = value
            self.assertEqual(self.status(obs), 'unacceptable' if value == -1 else 'invalid-evidence')
        obs = observation()
        obs['samples'][1]['id'] = obs['samples'][0]['id']
        self.assertEqual(self.status(obs), 'invalid-evidence')
        for samples in (None, {}, [None]):
            obs = observation()
            obs['samples'] = samples
            self.assertEqual(self.status(obs), 'invalid-evidence')
        obs = observation()
        obs['samples'][0]['at'] = '2026-11-04T10:00:00Z'
        self.assertEqual(self.status(obs), 'invalid-evidence')

    def test_old_maps_are_unconfigured_and_functional_verdict_is_never_changed(self):
        self.assertEqual(self.report(data={'rows': [{'id': 'old', 'verdict': 'proven'}]})['targets'], [])
        data = data_for(search_policy())
        before = copy.deepcopy(data)
        result = self.report(observation(values={'duration': 10000, 'relevance': 1, 'correct': 1}), data=data)
        self.assertEqual(data, before)
        self.assertEqual(result['targets'][0]['functionalVerdict'], 'proven')
        self.assertEqual(result['targets'][0]['status'], 'unacceptable')

    def test_unknown_duplicate_refs_and_unreferenced_bad_policy_are_not_silent(self):
        data = data_for(search_policy())
        for refs in (None, ['missing'], [search_policy()['id'], search_policy()['id']]):
            data['rows'][0]['servicePolicyRefs'] = refs
            self.assertIn('invalid-policy', [r['status'] for r in self.report(data=data)['targets']])
        data = data_for(search_policy())
        bad = accessibility_policy()
        bad['method'] = ''
        data['servicePolicies'].append(bad)
        self.assertIn('invalid-policy', [r['status'] for r in self.report(data=data)['targets']])

    def test_cli_strict_and_malformed_json_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            mp, op = Path(tmp) / 'map.json', Path(tmp) / 'observations.json'
            mp.write_text(json.dumps(data_for(search_policy())))
            for obs, status, code in ((observation(), 'target', 0),
                                      (observation(values={'duration': 10000, 'relevance': 1, 'correct': 1}), 'unacceptable', 1),
                                      (None, 'missing', 1)):
                op.write_text(json.dumps({'observations': [] if obs is None else [obs]}))
                run = subprocess.run([sys.executable, str(SCRIPT), '--map', str(mp), '--observations', str(op),
                                      '--replay', '--now', NOW.isoformat(), '--json', '--strict'], capture_output=True, text=True)
                self.assertEqual(run.returncode, code, run.stderr)
                self.assertEqual(json.loads(run.stdout)['targets'][0]['status'], status)
            op.write_text('{')
            run = subprocess.run([sys.executable, str(SCRIPT), '--map', str(mp), '--observations', str(op)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertNotIn('Traceback', run.stderr)

    def test_ratio_buckets_match_request_evidence_and_all_guardrail_extrema(self):
        policy = availability_policy()
        policy['guardrails'] = [condition('duration', 'ms', 'at-most', 1000)]
        policy['acceptableWhen'] = [condition('quality', 'score', 'at-least', 0.9)]
        obs = observation(policy, {'duration': 500, 'quality': 0.95}, 100)
        for i, sample in enumerate(obs['samples']):
            sample['successful'] = i != 0
        expected = self.report(obs, policy)['targets'][0]
        del obs['samples']
        obs['buckets'] = [{'start': obs['windowStart'], 'end': obs['windowEnd'], 'total': 100, 'successful': 99,
                           'extrema': {'duration': {'min': 500, 'max': 500}, 'quality': {'min': 0.95, 'max': 0.95}}}]
        actual = self.report(obs, policy)['targets'][0]
        for key in ('status', 'counts', 'measurements', 'sampleCount'):
            self.assertEqual(actual[key], expected[key])
        obs['buckets'][0]['extrema']['duration']['max'] = 1001
        self.assertEqual(self.status(obs, policy), 'unacceptable')
        obs['buckets'][0]['extrema']['duration']['max'] = 500
        obs['buckets'][0]['extrema']['quality']['min'] = 0.8
        self.assertEqual(self.status(obs, policy), 'unacceptable')

    def test_large_ratio_cohort_is_bounded_and_empty_traffic_does_not_pass(self):
        policy = availability_policy()
        obs = observation(policy, {})
        del obs['samples']
        obs['buckets'] = [{'start': obs['windowStart'], 'end': obs['windowEnd'],
                           'total': 26000000, 'successful': 25999999, 'extrema': {}}]
        result = self.report(obs, policy)['targets'][0]
        self.assertEqual((result['status'], result['sampleCount'], result['bucketCount']), ('target', 26000000, 1))
        self.assertLess(len(json.dumps(obs)), 1000)
        policy['target'] = 100
        obs['buckets'] = [dict(obs['buckets'][0], total=10**15, successful=10**15 - 1)]
        self.assertEqual(self.status(obs, policy), 'acceptable')
        obs['buckets'][0].update(total=0, successful=0)
        self.assertEqual(self.status(obs, policy), 'insufficient')

    def test_buckets_require_exact_window_counts_and_extrema(self):
        policy = availability_policy()
        base = observation(policy, {})
        del base['samples']
        base['buckets'] = [{'start': base['windowStart'], 'end': base['windowEnd'], 'total': 100, 'successful': 100, 'extrema': {}}]
        for key, value in (('total', True), ('successful', 101), ('successful', -1),
                           ('start', '2026-11-04T11:01:00Z'), ('end', '2026-11-04T11:59:00Z'),
                           ('extrema', {'extra': {'min': 0, 'max': 1}})):
            obs = copy.deepcopy(base)
            obs['buckets'][0][key] = value
            self.assertEqual(self.status(obs, policy), 'invalid-evidence')
        obs = copy.deepcopy(base)
        obs['buckets'] *= 2
        self.assertEqual(self.status(obs, policy), 'invalid-evidence')
        obs = copy.deepcopy(base)
        obs['samples'] = []
        self.assertEqual(self.status(obs, policy), 'invalid-evidence')
        obs = copy.deepcopy(base)
        obs['buckets'] = [dict(base['buckets'][0], end='2026-11-04T11:30:00Z', total=50, successful=50),
                          dict(base['buckets'][0], start='2026-11-04T11:30:00Z', total=50, successful=49)]
        self.assertEqual(self.status(obs, policy), 'acceptable')

    def test_error_details_row_selection_and_evidence_fields_are_bounded(self):
        obs = observation(count=100)
        for sample in obs['samples']:
            sample['at'] = 'invalid'
        result = self.report(obs)['targets'][0]
        self.assertLessEqual(len(result['reasons']), 9)
        self.assertEqual(result['errorCount'], 100)
        obs = observation()
        obs['samples'] = [obs['samples'][0]] * (self.module.MAX_RECORDS + 1)
        self.assertEqual(self.status(obs), 'invalid-evidence')
        policy = accessibility_policy()
        obs = assessment(policy)
        obs['evidence'][0]['untrusted-extra'] = {'private': 'do not copy'}
        result = self.report(obs, policy)['targets'][0]
        self.assertEqual(set(result['evidence'][0]), {'ref', 'description'})
        data = data_for(policy)
        data['rows'].append({'id': 'CAP-2', 'servicePolicyRefs': [policy['id']]})
        result = self.module.report(data, {'observations': [obs]}, NOW, ['CAP-1'])
        self.assertEqual([r['row'] for r in result['targets']], ['CAP-1'])
        self.assertEqual(result['scope']['rows'], ['CAP-1'])
        self.assertIn('unreferenced policies are not assessed', result['scope']['note'])

    def test_default_exit_code_catches_invalid_policy_but_allows_missing_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'map.json'
            for invalid, expected in ((False, 0), (True, 1)):
                policy = search_policy()
                if invalid:
                    policy['target'] = policy['unacceptable']
                path.write_text(json.dumps(data_for(policy)))
                run = subprocess.run([sys.executable, str(SCRIPT), '--map', str(path)], capture_output=True, text=True)
                self.assertEqual(run.returncode, expected, run.stderr)
            path.write_text(json.dumps(data_for(search_policy())))
            export = Path(tmp) / 'oversized-observations.json'
            with export.open('wb') as handle:
                handle.truncate(self.module.MAX_INPUT_BYTES + 1)
            run = subprocess.run([sys.executable, str(SCRIPT), '--map', str(path), '--observations', str(export)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertIn('8 MiB', run.stderr)
            self.assertNotIn('Traceback', run.stderr)

    def test_unique_policy_validation_and_bounded_summary_for_large_shared_map(self):
        from unittest.mock import patch
        data = data_for(search_policy())
        data['rows'] = [dict(data['rows'][0], id=f'CAP-{i}') for i in range(2000)]
        with patch.object(self.module, 'policy_errors', wraps=self.module.policy_errors) as validate:
            result = self.module.policies_summary(data)
        self.assertEqual(validate.call_count, 1)
        self.assertEqual((result['rows'], result['policies'], result['references']), (2000, 1, 2000))
        self.assertLess(len(json.dumps(result)), 500)
        with patch.object(self.module, 'policy_errors', wraps=self.module.policy_errors) as validate:
            self.module.report(data, {'observations': []}, NOW, ['CAP-0'])
        self.assertEqual(validate.call_count, 1)

    def test_fresh_hard_breach_is_not_hidden_by_insufficient_sample_count(self):
        obs = observation(values={'duration': 12000, 'relevance': 1, 'correct': 1}, count=1)
        self.assertEqual(self.status(obs), 'unacceptable')
        policy = availability_policy()
        obs = observation(policy, {}, count=1)
        obs['samples'][0]['successful'] = False
        self.assertEqual(self.status(obs, policy), 'insufficient')
        policy['guardrails'] = [condition('duration', 'ms', 'at-most', 1000)]
        obs = observation(policy, {'duration': 12000}, count=1)
        obs['samples'][0]['successful'] = False
        self.assertEqual(self.status(obs, policy), 'unacceptable')
        del obs['samples']
        obs['buckets'] = [{'start': obs['windowStart'], 'end': obs['windowEnd'],
                           'total': 1, 'successful': 0, 'extrema': {'duration': {'min': 12000, 'max': 12000}}}]
        self.assertEqual(self.status(obs, policy), 'unacceptable')

    def test_supplier_control_text_and_oversized_evidence_are_rejected(self):
        policy = accessibility_policy()
        for key, value in (('assessor', 'audit\x1b[1A\rforged'), ('rationale', 'x' * 1001)):
            obs = assessment(policy)
            obs[key] = value
            self.assertEqual(self.status(obs, policy), 'invalid-evidence')
        obs = assessment(policy)
        obs['evidence'] *= 21
        self.assertEqual(self.status(obs, policy), 'invalid-evidence')
        obs = observation()
        obs['source'] = 'collector\nforged status'
        self.assertEqual(self.status(obs), 'invalid-evidence')
        self.assertNotIn('\x1b', self.module.display('bad\x1b[1A\rstatus'))

    def test_cli_replay_is_explicit_labelled_and_policy_summary_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            mp, op = Path(tmp) / 'map.json', Path(tmp) / 'observations.json'
            mp.write_text(json.dumps(data_for(search_policy())))
            op.write_text(json.dumps({'observations': [observation()]}))
            args = [sys.executable, str(SCRIPT), '--map', str(mp), '--observations', str(op), '--now', NOW.isoformat()]
            run = subprocess.run(args + ['--strict'], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            run = subprocess.run(args + ['--replay', '--strict', '--json'], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)
            self.assertTrue(result['replay'])
            self.assertIn('referenceTime', result)
            self.assertIn('generatedAt', result)
            self.assertNotIn('observedAt', result)
            run = subprocess.run(args + ['--replay'], capture_output=True, text=True)
            self.assertIn('not current compliance', run.stdout)
            data = data_for(search_policy())
            data['rows'] = [dict(data['rows'][0], id=f'CAP-{i}') for i in range(2000)]
            mp.write_text(json.dumps(data))
            run = subprocess.run([sys.executable, str(SCRIPT), '--map', str(mp), '--policies-only', '--json'], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertLess(len(run.stdout), 600)
            run = subprocess.run([sys.executable, str(SCRIPT), '--map', str(mp)], capture_output=True, text=True)
            self.assertLess(len(run.stdout), 5000)

    def test_map_and_export_limits_have_distinct_diagnostics(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'input.json'
            path.write_bytes(b' ' * 33)
            with patch.object(self.module, 'MAX_MAP_BYTES', 32):
                with self.assertRaisesRegex(ValueError, 'capability map.*64 MiB'):
                    self.module.read_json(path, 'map')
            with patch.object(self.module, 'MAX_INPUT_BYTES', 32):
                with self.assertRaisesRegex(ValueError, 'observation export.*8 MiB'):
                    self.module.read_json(path, 'observations')


if __name__ == '__main__':
    unittest.main()
