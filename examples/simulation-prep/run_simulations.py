#!/usr/bin/env python3
"""Replay fixed fictional workflows through real, local Promise tools. No app or eval."""
import argparse
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tarfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRIPTS = REPO / 'skills/promise/scripts'
CURRENT_SKILL = SCRIPTS.parent
CLOCK = '2026-11-04T12:00:00Z'
DATE = '2026-11-04'
LANES = {'data': 'tests', 'response': 'tests', 'perception': 'e2eTests', 'judgement': 'evalTests'}
JOBS = {
    'reportcheck': {
        'import-batch': ('Import a review batch', 'A teacher imports a batch so that every submitted report is accounted for.'),
        'review-findings': ('Review report findings', 'A head of year reviews findings so that teachers receive useful corrections.'),
        'teacher-feedback': ('Prepare teacher feedback', 'A head of year prepares teacher feedback so that each teacher can act on their own review decisions.'),
        'year-summary': ('Prepare a year-wide review summary', 'A principal prepares a year-wide summary so that they can direct review support.')},
    'borrowworks': {
        'reserve': ('Reserve equipment', 'A member reserves equipment so that they can rely on a usable booking.'),
        'decide': ('Decide a restricted booking', 'A coordinator decides a booking so that only eligible members receive restricted equipment.'),
        'complete-loan': ('Complete a loan', 'A coordinator records a loan so that each item remains accounted for.'),
        'maintain': ('Keep unsafe equipment out of circulation', 'Maintenance staff quarantine equipment so that unsafe items are not lent.'),
        'utilisation': ('Prepare a utilisation report', 'A manager prepares a utilisation report so that equipment purchases can be planned.')}
}


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.name in ('functional-report.json', 'service-report.json', 'lane-gap-control.json', 'shared-policy-change.json', 'changed-rows.json') or path.parent.name == 'service-controls':
        data = dict(data, _simulation='Fixed synthetic product outcomes; real local parser execution; never product assurance.')
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


class Run:
    def __init__(self, project, out, commit):
        self.project, self.out, self.trace = project, out, []
        self.commit = commit
        self.seq = 0

    def command(self, args, expected=(0,), label=None):
        args = [str(a) for a in args]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                   GIT_AUTHOR_DATE='2026-11-04T12:00:00+00:00',
                   GIT_COMMITTER_DATE='2026-11-04T12:00:00+00:00')
        result = subprocess.run(args, cwd=self.project, env=env, capture_output=True, text=True, timeout=90)
        self.seq += 1
        clean = lambda s: s.replace(str(self.project), '<project>').replace(str(SCRIPTS), '<pinned-promise-tools>').replace(str(REPO), '<promise-repo>')
        self.trace.append({'step': self.seq, 'label': label or Path(args[1] if args[0] == 'python3' else args[0]).name,
                           'argv': [clean(a) for a in args], 'exit': result.returncode,
                           'stdout': clean(result.stdout), 'stderr': clean(result.stderr)})
        if result.returncode not in expected:
            raise RuntimeError(f'{label or args}: unexpected exit {result.returncode}\n{result.stdout}\n{result.stderr}')
        return result.stdout

    def tool(self, name, *args, expected=(0,), label=None):
        return self.command(['python3', SCRIPTS / name, *args], expected, label or name)

    def save_trace(self):
        dump(self.out / 'trace.json', {'syntheticProduct': True, 'promiseCommit': self.commit,
                                      'actualLocalCommands': self.trace})


def doc_text(title, story, scenarios, rule_tags, row_for, agreed=False):
    """A fictional owner's words are fixture inputs, never Oliver's agreement."""
    rules = '\n'.join(f'- The named case produces its stated outcome. → {at}' for at in rule_tags)
    rows = '\n'.join(f"| {s['at']} | {s['given']} | {s['when']} | {s['then']} | {s['altitude']} | {row_for[s['fixtureId']]} |" for s in scenarios)
    snapshot = f'\nSnapshot taken at `agreed` on {DATE}; the map is the source of these scenarios from here on.\n' if agreed else ''
    return f'''# {title}

This is a synthetic exercise fixture. No real owner agreement or product proof is recorded.

Status: {'agreed' if agreed else 'draft'}
Owner: Fictional exercise owner        Last decision: {DATE}
Decision policy: spec
Supersedes: —

Contents: [0. TLDR](#0-tldr) · [1. Problem](#1-problem) · [2. Outcome](#2-outcome) · [3. Worked examples](#3-worked-examples) · [4. Invariants](#4-invariants) · [5. Mechanism](#5-mechanism) · [6. Acceptance](#6-acceptance) · [7. Build phases](#7-build-phases) · [8. Decisions](#8-decisions) · [9. Open questions](#9-open-questions) · [10. Out of scope](#10-out-of-scope)

## 0. TLDR
*(author: Fictional exercise owner, {DATE} — synthetic owner input, not Oliver's agreement)*

**Outcome:** {story}
**Rules:**
{rules}
**How we'll know:** Fixed synthetic cases show the scripted result and keep failures or missing outcomes visible.
**Scenarios:** {len(scenarios)} acceptance rows (§6), 3 worked examples (§3).

Agent notes:
1. This entire document is a fictional fixture. Status changes do not grant real permission or establish product proof.

## 1. Problem
The fictional actor needs the workflow in the project PRD to complete a user job.

## 2. Outcome
**After this ships, it is true that:** the fictional actor completes the named job.
**Why we need it:** the actor can act on the outcome described above.

## 3. Worked examples
**Ana completes the job.** Given the named input, Ana takes the stated action and gets the expected result.
**Ana reverses a decision.** A cancellation or dismissal keeps the original context visible.
**Ben has another role.** An out-of-scope action is refused rather than shown as successful.

## 4. Invariants
A fictional result must never be labelled real product evidence. Enforcement: exercise provenance checks; strength: example. Boundary: no product runs here.
Why — what breaks without it: canned results could be mistaken for real assurance.

## 5. Mechanism
This is a proposed fictional workflow, not an application description. The fixed outcome stub is the only executable behaviour.
Shared service policies live in the map; their references do not become new user jobs.
Why — what breaks without it: implementation details and shared conditions would become separate capabilities.

## 6. Acceptance
| # | Given | When | Then | Altitude | Row |
|---|---|---|---|---|---|
{rows}
{snapshot}
Why — what breaks without it: a job could hide a missing case or a failed result.

## 7. Build phases
Exercise the listed acceptance rows with fixed outcomes only. Do not implement the fictional product.
Why — what breaks without it: simulation scope could turn into an application build.

## 8. Decisions
| # | Date | Decision | Owner | Why |
|---|---|---|---|---|
| 1 | {DATE} | The exercise uses fixed outcomes and shared service policies. | Fictional exercise owner | Synthetic fixture input, not a real approval. |

## 9. Open questions
No unresolved fictional questions. Real framework recommendations remain for Oliver to decide.

## 10. Out of scope
Application implementation, real evals, real accessibility audits, production traffic and real owner permissions.
'''


def policies(project, candidates):
    base = json.loads((SCRIPTS.parents[2] / 'examples/service-targets/map.json').read_text())['servicePolicies']
    result = copy.deepcopy(base)
    result[0]['id'] = 'interactive-result'
    result[0]['target'] = candidates['targetBelowMs']
    result[0]['unacceptable'] = candidates['hardLimitAtMs']
    result[0]['guardrails'][1]['value'] = candidates['baseQualityAtLeast']
    result[0]['acceptableWhen'][0]['value'] = candidates['slowerQualityAtLeast']
    result[0]['workload'] = f'{project} synthetic cohort, 10000 records, 20 concurrent requests'
    result[1]['workload'] = result[0]['workload']
    result[3]['standard'] = {'name': 'Fictional keyboard checklist', 'version': 'fixture-v1'}
    result[3]['basis'] = 'Fictional keyboard-access requirement; this is not a WCAG audit.'
    result[3]['scope'] = f'{project} named interactive journeys, fixture-build-1'
    result[3]['method'] = 'scripted fictional reviewer outcome, no interface or audit run'
    result[3]['criteria'] = {'target': 'Every item in the fictional checklist passes.',
                             'unacceptable': 'Any item in the fictional checklist fails.'}
    result.append({'id': 'delivery-deadline', 'revision': '1', 'kind': 'assessment', 'maxAgeSeconds': 86400,
                   'basis': 'Fictional feedback or reservation notice is prepared within its deadline.',
                   'scope': f'{project} prepared output, no real messages sent',
                   'method': 'scripted fixed deadline check',
                   'criteria': {'target': 'The declared deadline is met.', 'unacceptable': 'The deadline is missed.'}})
    return result


def refs_for(job):
    refs = ['request-availability', 'accessible-interface']
    if job in ('review-findings', 'reserve', 'decide'):
        refs.append('interactive-result')
    if job in ('import-batch', 'reserve'):
        refs.append('loaded-throughput')
    if job in ('teacher-feedback', 'reserve'):
        refs.append('delivery-deadline')
    return refs


def observations(data, stage, declared):
    """Translate declared synthetic cases into the merged service-policy schema."""
    out = []
    seeds = {item['policyIdea']: item for item in declared}
    for row in data['rows']:
        for ref in row['servicePolicyRefs']:
            p = next(p for p in data['servicePolicies'] if p['id'] == ref)
            obs = {'row': row['id'], 'target': ref, 'revision': p['revision']}
            if p['kind'] == 'assessment':
                if ref == 'accessible-interface' and seeds['inclusive-use']['observed'] is None:
                    continue
                obs.update(scope=p['scope'], method=p['method'], assessor='Synthetic fixture assessor',
                           rationale='Predetermined exercise input; no product assessment ran.',
                           band='unacceptable' if ref == 'accessible-interface' and not seeds['inclusive-use']['observed']['conforms'] else 'target',
                           observedAt=CLOCK, evidence=[{'ref': 'fixture:fixed-assessment',
                           'description': 'Synthetic fixed assessment only; not an audit or independent verification.'}])
            else:
                obs.update(boundary=p['boundary'], workload=p['workload'], source='Synthetic fixed collector fixture',
                           windowStart='2026-11-04T11:00:00Z', windowEnd=CLOCK,
                           units={p['metric']: p['unit']})
                if ref == 'request-availability':
                    obs['buckets'] = [{'start': obs['windowStart'], 'end': CLOCK,
                                       'successful': seeds['service-access']['observed']['successes'], 'total': seeds['service-access']['observed']['attempts'], 'extrema': {}}]
                else:
                    for condition in p.get('guardrails', []) + p.get('acceptableWhen', []):
                        obs['units'][condition['metric']] = condition['unit']
                    values = {'duration': seeds['interactive-result']['observed']['elapsedMs'],
                              'relevance': seeds['interactive-result']['observed']['quality'], 'correct': 1}
                    if ref == 'loaded-throughput':
                        values = {'completed-throughput': seeds['peak-work']['observed']['completedRequestsPerSecond'],
                                  'offered-load': seeds['peak-work']['observed']['offeredLoadRequestsPerSecond'],
                                  'p95-duration': seeds['peak-work']['observed']['p95ElapsedMs']}
                    obs['samples'] = [{'id': f'synthetic-{i}', 'at': f'2026-11-04T11:{15 + i*30}:00Z', 'values': values} for i in range(2)]
            out.append(obs)
    return {'synthetic': True, 'notice': 'Historical fictional replay, never current compliance.', 'observations': out}


def write_stub_test(project, results):
    dump(project / 'fixed-results.json', results)
    target = project / 'tests/test_fixed_outcomes.py'
    target.parent.mkdir(exist_ok=True)
    target.write_text('''"""All results scripted: no app, rendered surface or model is exercised."""
import json
from pathlib import Path
import unittest
RESULTS = json.loads((Path(__file__).resolve().parents[1] / 'fixed-results.json').read_text())
class ScriptedOutcomes(unittest.TestCase):
    pass

def fixed_case(value):
    def check(self):
        if value is None:
            self.skipTest('Synthetic unchecked work; no result supplied')
        self.assertTrue(value, 'Predetermined synthetic failure; not a discovered product defect')
    return check
for scenario, value in RESULTS.items():
    setattr(ScriptedOutcomes, 'test_' + scenario.replace('-', '_').replace('.', '_'), fixed_case(value))
''')


def citation(sid):
    return 'tests/test_fixed_outcomes.py::test_' + sid.replace('-', '_').replace('.', '_')


def trial_grouping(run, out, relaxed, roots, config_path):
    """Run today's tools on the same fictional jobs and final stub results."""
    for row in relaxed['rows']:
        row['grouping'] = 'job'
        row['doc'] = roots[row['id']]['doc']
        for index, scenario in enumerate(row['scenarios'], start=1):
            scenario['id'] = f"{row['id']}.{index}"
            scenario['evidence'] = [citation(scenario['fixtureId'])]
    # Keep the map at the same depth for docRoot without adding it to final-project/docs.
    trial_path = run.project / 'scratch/trial/map.json'
    dump(trial_path, relaxed)
    run.command(['python3', CURRENT_SKILL / 'templates/starter-map/capability_find.py',
                 '--map', trial_path, '--check'])
    report_args = ['python3', CURRENT_SKILL / 'scripts/map_report.py', '--map', trial_path,
                   '--config', config_path, '--junit', run.project / 'stub-results.xml', '--json', '--strict']
    report = json.loads(run.command(report_args))

    # Reuse only the observations that already belong to surviving job identities.
    retained = {row['id'] for row in relaxed['rows']}
    export = json.loads((run.project / 'service-observations.json').read_text())
    export['observations'] = [item for item in export['observations'] if item['row'] in retained]
    trial_export = run.project / 'trial-observations.json'
    dump(trial_export, export)
    services = json.loads(run.command(['python3', CURRENT_SKILL / 'scripts/service_report.py',
                                       '--map', trial_path, '--observations', trial_export,
                                       '--replay', '--now', CLOCK, '--json', '--strict']))
    dump(out / 'trial/map.json', relaxed)
    dump(out / 'trial/functional-report.json', report)
    dump(out / 'trial/service-report.json', services)
    expanded = next(row for row in relaxed['rows'] if len(row['scenarios']) > 5)
    preview = run.project / 'trial-outcome.html'
    run.command(['python3', CURRENT_SKILL / 'scripts/render_view.py', expanded['doc'],
                 '--map-report', out / 'trial/functional-report.json',
                 '--service-report', out / 'trial/service-report.json',
                 '--out', preview])
    shutil.copyfile(preview, out / 'trial/outcome.html')

    # Remove the explicit link while leaving the row citation and the green lane intact.
    gap = next(scenario for row in report['rows'] for scenario in row['scenarios'] if scenario['proven'])
    missing = next(s for row in relaxed['rows'] for s in row['scenarios'] if s['id'] == gap['id'])
    missing.pop('evidence')
    dump(trial_path, relaxed)
    rejected = json.loads(run.command(report_args, expected=(1,), label='trial rejects a lane-green citation gap'))
    dump(out / 'trial/lane-gap-control.json', {'scenario': gap['id'], 'report': rejected})


def git(run, *args):
    return run.command(['git', *args], label='sandbox git ' + args[0])


def main():
    global SCRIPTS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=HERE / 'results')
    parser.add_argument('--trial', action='store_true', help='also exercise opt-in job grouping with current tools')
    args = parser.parse_args()
    args.out = args.out.resolve()
    # Use a committed snapshot so the replay can be reproduced from its recorded revision.
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    toolbox = tempfile.TemporaryDirectory(prefix='promise-pinned-tools-')
    archive = subprocess.run(['git', 'archive', commit, 'skills/promise', 'examples/service-targets/map.json'],
                             cwd=REPO, capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        source.extractall(toolbox.name, filter='data')
    SCRIPTS = Path(toolbox.name) / 'skills/promise/scripts'
    spec = importlib.util.spec_from_file_location('prep_stubs', HERE / 'stubs.py')
    stubs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stubs)
    fixtures = stubs.load_fixture()
    stubs.check_fixture(fixtures)
    summary = {'promiseCommit': commit, 'skillVersion': (SCRIPTS.parent / 'VERSION').read_text().strip(),
               'syntheticProduct': True, 'fullApplicationImplemented': False, 'realEvalsRun': False, 'projects': {}}
    for name, fixture in fixtures['projects'].items():
        out = args.out / name
        out.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='promise-fiction-') as temp:
            project = Path(temp)
            run = Run(project, out, commit)
            try:
                git(run, 'init', '-q', '-b', 'main')
                git(run, 'config', 'user.name', 'Synthetic Fixture')
                git(run, 'config', 'user.email', 'synthetic@example.invalid')
                run.tool('adopt.py', '--cwd', project, '--docs-home', 'docs/designs', '--no-claude-md')
                run.tool('start_map.py', '--cwd', project)
                config_path = project / '.claude/promise.config.json'
                config = json.loads(config_path.read_text())
                (project / 'tools').mkdir()
                shutil.copyfile(SCRIPTS / 'junit_unittest.py', project / 'tools/junit_unittest.py')
                config.pop('run', None)
                config['commands'] = {'typeCheck': None, 'test': 'python3 tools/junit_unittest.py --out stub-results.xml -s tests --cwd .', 'lint': None}
                config['map'].update(file='docs/capabilities/map.json', junit=['stub-results.xml'])
                dump(config_path, config)
                run.tool('adapter.py', '--cwd', project, 'show', label='configured command disclosure; bounded fixture commands authorised')
                run.tool('orient.py', label='orient adopted fixture project')
                map_path = project / 'docs/capabilities/map.json'
                data = json.loads(map_path.read_text())
                data.update(synthetic=True, notice='Not-built functional verdicts are never promoted by fixed stubs.', servicePolicies=policies(name, stubs.fixed_service_observations(name, 'initial')[0]['candidateCriteria']))
                rows_by_job, doc_scenarios, stage_results = {}, {}, []
                previous_manifest = {}
                for index, stage in enumerate(fixture['stages']):
                    stage_id = stage['id']
                    stage_dir = out / stage_id
                    stage_dir.mkdir(exist_ok=True)
                    before = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts}
                    classification = []
                    for job, ids in stage['jobs'].items():
                        new_job = job not in rows_by_job
                        if new_job:
                            rows_by_job[job] = []
                            doc_scenarios[job] = []
                            title, story = JOBS[name][job]
                            run.tool('render_outcome.py', '--cwd', project, '--title', title, '--owner', 'Fictional exercise owner', '--date', DATE, '--policy', 'spec', '--docs-home', 'docs/designs', '--create-docs-home', '--slug', job, '--json')
                        prior = set(previous_manifest.get(job, []))
                        for n, sid in enumerate(ids):
                            chunk = n // 5
                            if chunk >= len(rows_by_job[job]):
                                raw = json.loads(run.tool('adapter.py', '--cwd', project, '--json', 'next-id'))
                                rid = raw['stdout'].strip()
                                row = {'id': rid, 'title': JOBS[name][job][0] + (f' continued {chunk+1}' if chunk else ''),
                                       'story': JOBS[name][job][1], 'doc': f'docs/designs/{job}.md' if new_job else None,
                                       'scenarios': [], 'tests': [], 'e2eTests': [], 'evalTests': [], 'siblingTests': [],
                                       'verdict': 'not-built', 'servicePolicyRefs': refs_for(job), 'synthetic': True}
                                if chunk:
                                    row['parent'] = rows_by_job[job][0]['id']
                                rows_by_job[job].append(row)
                                data['rows'].append(row)
                                dump(map_path, data)
                            row = rows_by_job[job][chunk]
                            if sid in prior:
                                continue
                            scenario = {'id': f"{row['id']}.{len(row['scenarios'])+1}", 'at': f'AT-{n+1}' if new_job else None,
                                        'given': f'A fictional {name} actor uses a fixed synthetic case',
                                        'when': 'the scripted workflow outcome is requested',
                                        'then': fixture['scenarioCatalogue'][sid]['title'], 'altitude': fixture['scenarioCatalogue'][sid]['altitude'],
                                        'fixtureId': sid}
                            row['scenarios'].append(scenario)
                            row[LANES[scenario['altitude']]].append(citation(sid))
                            if new_job:
                                doc_scenarios[job].append(scenario)
                            classification.append({'scenario': sid, 'route': 'NEW-JOB' if new_job else 'EXTEND', 'row': row['id'],
                                                   'newContinuation': bool(not new_job and len(row['scenarios']) == 1)})
                        if new_job:
                            row_for = {s['fixtureId']: r['id'] for r in rows_by_job[job] for s in r['scenarios']}
                            doc = project / f'docs/designs/{job}.md'
                            doc.write_text(doc_text(JOBS[name][job][0], JOBS[name][job][1], doc_scenarios[job],
                                                    [s['at'] for s in doc_scenarios[job]], row_for, agreed=True))
                    dump(map_path, data)
                    write_stub_test(project, stage['stubResults'])
                    evidence = observations(data, index, stubs.fixed_service_observations(name, stage_id))
                    dump(project / 'service-observations.json', evidence)
                    run.tool('adapter.py', '--cwd', project, '--json', 'checks')
                    # Functional tests use fixed booleans even for judgement/perception; no eval/render run.
                    run.tool('adapter.py', '--cwd', project, '--json', 'verify', expected=(0, 1), label='run scripted unittest outcomes, never a model eval')
                    for doc in sorted((project / 'docs/designs').glob('*.md')):
                        run.tool('lint_outcome.py', doc, '--json')
                        run.tool('bridge_validate.py', '--cwd', project, '--strict', '--linking', '--json', doc)
                    report = json.loads(run.tool('map_report.py', '--map', map_path, '--config', config_path, '--junit', project / 'stub-results.xml', '--json', '--strict', expected=(0, 1)))
                    dump(stage_dir / 'functional-report.json', report)
                    srv = json.loads(run.tool('service_report.py', '--map', map_path, '--observations', project / 'service-observations.json', '--replay', '--now', CLOCK, '--json', '--strict', expected=(0, 1)))
                    dump(stage_dir / 'service-report.json', srv)
                    dump(stage_dir / 'map.json', data)
                    dump(stage_dir / 'service-observations.json', evidence)
                    shutil.copyfile(project / 'stub-results.xml', stage_dir / 'stub-results.xml')
                    if index:
                        classification.append({'route': 'DEFECT' if index == 1 else 'RECOVERY',
                                               'scenario': next(s for s, v in fixture['stages'][1]['stubResults'].items() if v is False),
                                               'newCapability': False, 'evidence': 'scripted outcome switch, not a real defect or kill witness'})
                        query = project / 'query.txt'
                        query.write_text('review copied report findings' if name == 'reportcheck' else 'reserve a waiting equipment booking')
                        run.tool('adapter.py', '--cwd', project, '--json', 'find', '--query-file', query)
                        run.tool('adapter.py', '--cwd', project, '--json', 'row', data['rows'][0]['id'])
                    after = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts}
                    edited = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
                    git(run, 'add', '.')
                    git(run, 'commit', '-q', '-m', f'Synthetic {name} {stage_id}')
                    if index:
                        changed = json.loads(run.tool('changed_rows.py', '--cwd', project, '--base', 'HEAD~1', '--head', 'HEAD', '--json'))
                        dump(stage_dir / 'changed-rows.json', changed)
                    counts = {v: sum(result is v for result in stage['stubResults'].values()) for v in (True, False, None)}
                    item = {'stage': stage_id, 'jobs': len(stage['jobs']), 'scenarios': sum(map(len, stage['jobs'].values())),
                            'detailRows': sum(map(len, stage['jobs'].values())), 'currentRows': len(data['rows']),
                            'continuations': sum('parent' in r for r in data['rows']), 'relaxedRowsHypothesis': len(stage['jobs']),
                            'servicePolicyDefinitions': len(data['servicePolicies']),
                            'servicePolicyReferences': sum(len(r['servicePolicyRefs']) for r in data['rows']),
                            'scriptedPass': counts[True], 'scriptedFail': counts[False], 'unchecked': counts[None],
                            'editedFiles': edited,
                            'authoredInputEdits': [p for p in edited if p not in ('stub-results.xml', 'query.txt')],
                            'classification': classification}
                    dump(stage_dir / 'stage-summary.json', item)
                    stage_results.append(item)
                    previous_manifest = copy.deepcopy(stage['jobs'])
                # Extra service controls exercise hard boundaries without changing primary snapshots.
                controls = []
                target_row = next(r for r in data['rows'] if 'interactive-result' in r['servicePolicyRefs'])
                for name_control in ('hard-limit', 'fast-low-quality', 'missing', 'stale', 'capacity-wrong-load', 'revision-mismatch', 'availability-zero-traffic'):
                    altered = copy.deepcopy(evidence)
                    if name_control in ('hard-limit', 'fast-low-quality'):
                        obs = next(o for o in altered['observations'] if o['row'] == target_row['id'] and o['target'] == 'interactive-result')
                        obs['samples'][0]['values'].update(duration=10000 if name_control == 'hard-limit' else 500, relevance=1 if name_control == 'hard-limit' else .5)
                    elif name_control == 'missing':
                        altered['observations'] = []
                    elif name_control == 'stale':
                        for obs in altered['observations']:
                            if 'observedAt' in obs:
                                obs['observedAt'] = '2026-11-01T12:00:00Z'
                            else:
                                obs['windowStart'] = '2026-11-01T11:00:00Z'; obs['windowEnd'] = '2026-11-01T12:00:00Z'
                                for s in obs.get('samples', []): s['at'] = s['at'].replace('11-04', '11-01')
                                for b in obs.get('buckets', []):
                                    b['start'] = b['start'].replace('11-04', '11-01'); b['end'] = b['end'].replace('11-04', '11-01')
                    elif name_control == 'capacity-wrong-load':
                        obs = next(o for o in altered['observations'] if o['target'] == 'loaded-throughput')
                        for s in obs['samples']: s['values']['offered-load'] = 10
                    elif name_control == 'revision-mismatch':
                        altered['observations'][0]['revision'] = 'obsolete'
                    else:
                        for obs in altered['observations']:
                            if obs['target'] == 'request-availability':
                                for bucket in obs['buckets']:
                                    bucket.update(successful=0, total=0)
                    path = project / 'control-observations.json'
                    dump(path, altered)
                    control = json.loads(run.tool('service_report.py', '--map', map_path, '--observations', path, '--replay', '--now', CLOCK, '--json', '--strict', expected=(1,)))
                    statuses = {t['status'] for t in control['targets']}
                    expected_status = {'hard-limit': 'unacceptable', 'fast-low-quality': 'unacceptable',
                        'capacity-wrong-load': 'unacceptable', 'revision-mismatch': 'invalid-evidence',
                        'missing': 'missing', 'stale': 'stale', 'availability-zero-traffic': 'insufficient'}[name_control]
                    if expected_status not in statuses:
                        raise RuntimeError(f'{name_control} did not preserve {expected_status}: {statuses}')
                    dump(out / 'service-controls' / f'{name_control}.json', control)
                    controls.append(name_control)
                # Compare lane-level computation with a deliberately uncited same-lane scenario.
                gap_map = copy.deepcopy(data)
                gap_row = next(r for r in gap_map['rows'] if sum(s['altitude'] == 'response' for s in r['scenarios']) >= 2)
                gap_scenario = next(s for s in gap_row['scenarios'] if s['altitude'] == 'response')
                gap_row['tests'].remove(citation(gap_scenario['fixtureId']))
                gap_path = project / 'lane-gap-map.json'
                dump(gap_path, gap_map)
                gap_report = json.loads(run.tool('map_report.py', '--map', gap_path, '--config', config_path,
                    '--junit', project / 'stub-results.xml', '--json', '--strict'))
                dump(out / 'lane-gap-control.json', {'missingScenarioCitation': gap_scenario['fixtureId'],
                    'row': gap_row['id'], 'report': gap_report,
                    'interpretation': 'Lane-level computation is not per-scenario proof; never promote fixed stubs.'})
                # A real change report must fan a shared policy revision out to every referring row.
                shared = copy.deepcopy(data)
                policy = next(p for p in shared['servicePolicies'] if p['id'] == 'accessible-interface')
                policy['revision'] = '2'
                policy['criteria']['target'] = 'Every fictional checklist item passes, including the new navigation case.'
                dump(map_path, shared)
                git(run, 'add', 'docs/capabilities/map.json')
                git(run, 'commit', '-q', '-m', 'Synthetic shared policy revision')
                shared_changes = json.loads(run.tool('changed_rows.py', '--cwd', project, '--base', 'HEAD~1', '--head', 'HEAD', '--json'))
                dump(out / 'shared-policy-change.json', shared_changes)
                dump(map_path, data)  # restore canonical exercise inputs, never change evidence to pass
                # Structurally valid does not mean sensibly grouped: an atomised map is accepted too.
                detail = copy.deepcopy(data)
                detail['rows'] = []
                for original in data['rows']:
                    for scenario in original['scenarios']:
                        row = copy.deepcopy(original)
                        row['id'] = f"CAP-{100+len(detail['rows'])}"
                        row.pop('parent', None)
                        row['doc'] = None
                        row['title'] = scenario['then']
                        only = copy.deepcopy(scenario)
                        only.update(id=row['id']+'.1', at=None)
                        row['scenarios'] = [only]
                        for lane in set(LANES.values()): row[lane] = []
                        row[LANES[scenario['altitude']]] = [citation(scenario['fixtureId'])]
                        detail['rows'].append(row)
                detail_path = project / 'one-detail-per-row.json'
                dump(detail_path, detail)
                run.command(['python3', project / 'docs/capabilities/capability_find.py', '--map', detail_path, '--check'], label='control: over-fragmented map passes structural checks')
                dump(out / 'one-detail-per-row.json', detail)
                # A negative control demonstrates the relaxed grouping is not current valid Promise.
                relaxed = copy.deepcopy(data)
                relaxed['rows'] = []
                for job, group in rows_by_job.items():
                    row = copy.deepcopy(group[0])
                    row['scenarios'] = [copy.deepcopy(s) for r in group for s in r['scenarios']]
                    row['doc'] = None
                    for lane in set(LANES.values()): row[lane] = [t for r in group for t in r[lane]]
                    relaxed['rows'].append(row)
                relaxed_path = project / 'relaxed-hypothesis.json'
                dump(relaxed_path, relaxed)
                run.command(['python3', project / 'docs/capabilities/capability_find.py', '--map', relaxed_path, '--check'], expected=(1,), label='negative control: relaxed rows violate existing ceiling')
                dump(out / 'relaxed-hypothesis.json', relaxed)
                if args.trial:
                    roots = {group[0]['id']: group[0] for group in rows_by_job.values()}
                    trial_grouping(run, out, relaxed, roots, config_path)
                # Keep one final usable snapshot, not duplicate outcome docs per stage.
                final = out / 'final-project'
                for rel in ('.claude/promise.config.json', 'fixed-results.json', 'tests/test_fixed_outcomes.py', 'tools/junit_unittest.py', 'docs'):
                    src, dst = project / rel, final / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if src.is_dir(): shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
                    else: shutil.copyfile(src, dst)
                summary['projects'][name] = {'stages': stage_results, 'serviceControlsRun': controls}
            finally:
                run.save_trace()
    dump(args.out / 'summary.json', summary)
    toolbox.cleanup()
    print('Two synthetic Promise workflows replayed; no application or real eval ran.')


if __name__ == '__main__':
    main()
