#!/usr/bin/env python3
"""Freeze analytical raw-file fixtures; never import or invoke product code."""
import copy
import csv
import hashlib
import io
import json
import runpy
from datetime import datetime, timedelta, timezone
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORACLE = HERE.parent / 'paired-water-service' / 'independent-oracle.py'
independent = runpy.run_path(str(ORACLE))
q, exact = independent['q'], independent['exact']
START = datetime(2026, 7, 1, tzinfo=timezone.utc)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def iso(time):
    return time.isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def retained(name, text):
    return {'name': name, 'text': text, 'sha256': sha(text)}


def json_text(value):
    return json.dumps(value, allow_nan=False, separators=(',', ':')) + '\n'


def csv_text(headers, rows):
    output = io.StringIO(newline='')
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def spec(hours=24, **changes):
    value = dict(hours=hours, control=[1] * hours, candidate=[1] * hours,
                 demand=[1] * hours, actual=[100] * hours,
                 candidate_forecast=[100] * hours, control_forecast=[101] * hours,
                 tariffs=[1] * hours, capacity=100, reserve=0, initial=10,
                 target=10, unitCapacity=4, demand_multiplier=1,
                 production_multiplier=1, outages=[], sec=2)
    value.update(changes)
    assert hours % 24 == 0
    assert all(len(value[k]) == hours for k in ('control', 'candidate', 'demand',
               'actual', 'candidate_forecast', 'control_forecast', 'tariffs'))
    return value


def case_input(s):
    times = [iso(START + timedelta(hours=i)) for i in range(s['hours'])]
    return {'blocks': [{'times': times[i:i + 24], 'production': s['control'][i:i + 24],
                       'demand': s['demand'][i:i + 24]} for i in range(0, s['hours'], 24)],
            **{k: s[k] for k in ('capacity', 'reserve', 'initial', 'target', 'unitCapacity')},
            'scenario': {k: s[k] for k in ('demand_multiplier', 'production_multiplier')},
            'outages': [{'start': iso(START + timedelta(hours=a)),
                         'end': iso(START + timedelta(hours=b))} for a, b in s['outages']]}


def packet(s, identity):
    source = case_input(s)
    times = [t for block in source['blocks'] for t in block['times']]
    files = {'case': retained(identity + '-case.json', json_text(source))}
    files['returned'] = retained(identity + '-returned.csv', csv_text(
        ['case_sha256', 'time', 'production_m3'],
        zip([files['case']['sha256']] * len(times), times, s['candidate'])))
    for role, header, values in [('weather', 'radiation_w_m2', s['actual']),
                                 ('candidate_forecast', 'predicted_radiation_w_m2', s['candidate_forecast']),
                                 ('control_forecast', 'predicted_radiation_w_m2', s['control_forecast']),
                                 ('tariffs', 'eur_kwh', s['tariffs'])]:
        files[role] = retained(identity + '-' + role + '.csv', csv_text(['time', header], zip(times, values)))
    common = {'case_sha256': files['case']['sha256'], 'tariffs_sha256': files['tariffs']['sha256'],
              'controller_sha256': sha('illustrative fixed controller'),
              'settings_sha256': sha('illustrative fixed settings'), 'randomness': 'deterministic',
              'forecast_issue_time': '2026-06-30T15:00:00Z',
              'forecast_first_observed_time': '2026-06-30T15:01:00Z',
              'features_available_time': '2026-06-30T14:59:00Z',
              'plan_first_observed_time': '2026-06-30T15:02:00Z'}
    declaration = {'schema': 1, 'kind': 'forecast_decision_declaration',
                   'source_kind': 'illustrative_scenario', 'source_label': identity,
                   'decision_cutoff': '2026-06-30T18:00:00Z',
                   'specific_energy_kwh_m3': s['sec']}
    for arm, role in [('candidate', 'returned'), ('control', 'case')]:
        declaration[arm] = {**common, 'forecast_sha256': files[arm + '_forecast']['sha256'],
                            'plan_sha256': files[role]['sha256']}
    return {'schema': 1, 'kind': 'forecast_decision_review',
            'declaration_file': retained(identity + '-declaration.json', json_text(declaration)),
            'files': files}


def change_declaration(p, edit):
    declaration = json.loads(p['declaration_file']['text'])
    edit(declaration)
    p['declaration_file'] = retained(p['declaration_file']['name'], json_text(declaration))


def change_file(p, role, edit):
    old = p['files'][role]
    p['files'][role] = retained(old['name'], edit(old['text']))
    new_sha = p['files'][role]['sha256']
    def links(d):
        if role in ('candidate_forecast', 'control_forecast'):
            d[role.split('_')[0]]['forecast_sha256'] = new_sha
        elif role == 'returned':
            d['candidate']['plan_sha256'] = new_sha
        elif role == 'tariffs':
            for arm in ('candidate', 'control'):
                d[arm]['tariffs_sha256'] = new_sha
    change_declaration(p, links)


def exact_model(s, arm):
    segments = []
    for hour, production in enumerate(s[arm]):
        cuts = sorted({F(hour), F(hour + 1)} |
                      {q(t) for interval in s['outages'] for t in interval if hour < t < hour + 1})
        for a, b in zip(cuts, cuts[1:]):
            unavailable = any(q(x) <= (a + b) / 2 < q(y) for x, y in s['outages'])
            segments.append({'from': float(a), 'to': float(b),
                             'production': 0 if unavailable else production * s['production_multiplier'],
                             'demand': s['demand'][hour] * s['demand_multiplier']})
    return {'start_epoch': int(START.timestamp() * 1000), 'start_hour': 0,
            'end_hour': s['hours'], **{k: s[k] for k in ('initial', 'capacity', 'reserve', 'target')},
            'segments': segments}


def expectations(s):
    models = {arm: exact_model(s, arm) for arm in ('candidate', 'control')}
    expected = {'water_service.status': independent['oracle']({
        'original': models['control'], 'revised': models['candidate']})['status'],
        'method.status': 'same_declared_method', 'timing.status': 'declared_before_cutoff',
        'forecast_attribution.status': 'not_established'}
    costs, electricity = {}, {}
    for arm, model in models.items():
        trajectory, final = independent['trajectory'](independent['model'](model))
        unmet = sum(((b - a) * rate for a, b, x, y, rate in trajectory), F(0))
        minimum = min([q(s['initial'])] + [min(x, y) for a, b, x, y, rate in trajectory])
        status = 'modeled_requirements_met' if unmet == 0 and minimum >= q(s['reserve']) and final >= q(s['target']) else 'modeled_requirements_failed'
        expected['adequacy.' + arm + '.status'] = status
        for label, value in [('unmet_m3', unmet), ('min_storage_m3', minimum), ('final_storage_m3', final)]:
            expected['adequacy.' + arm + '.' + label + '.exact'] = exact(value)
        expected['forecast.' + arm + '.mae'] = float(sum(
            (abs(q(a) - q(b)) for a, b in zip(s[arm + '_forecast'], s['actual'])), F(0)) / s['hours'])
        if s['sec'] is not None:
            electricity[arm] = sum(((q(row['to']) - q(row['from'])) * q(row['production']) *
                q(s['sec']) for row in model['segments']), F(0))
            costs[arm] = sum(((q(row['to']) - q(row['from'])) * q(row['production']) *
                q(s['sec']) * q(s['tariffs'][int(row['from'])]) for row in model['segments']), F(0))
    if costs:
        expected['energy.cost_eur.candidate'] = float(costs['candidate'])
        expected['energy.cost_eur.control'] = float(costs['control'])
        expected['energy.cost_eur.delta'] = float(costs['candidate'] - costs['control'])
        for arm in ('candidate', 'control'):
            expected['energy.electricity_kwh.' + arm] = float(electricity[arm])
        expected['energy.electricity_kwh.delta'] = float(electricity['candidate'] - electricity['control'])
    else:
        expected['energy.cost_eur'] = None
        expected['energy.electricity_kwh'] = None
    return expected


cases = []


def accepted(identity, rationale, s=None, edit=None, overrides=None):
    s = spec() if s is None else s
    p, expected = packet(s, identity), expectations(s)
    if edit:
        edit(p)
    expected.update(overrides or {})
    cases.append({'id': identity, 'rationale': rationale, 'packet': p, 'expected': expected})


def rejected(identity, rationale, edit, pattern, s=None):
    p = packet(spec() if s is None else s, identity)
    edit(p)
    cases.append({'id': identity, 'rationale': rationale, 'packet': p, 'rejection_regex': pattern})


accepted('better-error-worse-water', 'Lower MAE does not compensate for unmet demand and depleted ending stock.', spec(candidate=[0] * 12 + [1] * 12))
accepted('better-error-worse-cost', 'Lower MAE accompanies a costlier equal-volume adequate schedule.', spec(
    control=[2, 0] * 12, candidate=[0, 2] * 12, tariffs=[1, 3] * 12))
accepted('matching-declarations-no-authority', 'Matching declarations and timely values do not authenticate execution or forecast causality.')
accepted('identical-plans-better-error', 'Improved forecast error with identical plans gives zero operating difference.')
accepted('cheaper-lower-ending-stock', 'One omitted unit lowers cost and ending stock without additional unmet demand.', spec(candidate=[1] * 23 + [0]))
accepted('equal-inadequate-plans', 'Relative nonregression cannot turn two unmet-demand failures into adequate plans.', spec(
    control=[0] * 24, candidate=[0] * 24, initial=0, target=0))
accepted('adequate-equal-water-retiming', 'Equal production and adequate water service; supplied tariff timing gives a cost reduction.', spec(
    control=[2, 0] * 12, candidate=[0, 2] * 12, tariffs=[3, 1] * 12))
accepted('specific-energy-unknown', 'Unknown SEC means cost is unknown, including when plans are equal.', spec(sec=None))
accepted('known-zero-tariffs', 'Known zero tariffs give numerical zero, not missing cost.', spec(tariffs=[0] * 24))
accepted('spilled-production-still-costs', 'All effective production consumes modeled electricity, including spilled water.', spec(
    demand=[0] * 24, candidate=[2] * 24, capacity=10))
accepted('fractional-outage', 'Quarter-hour boundaries remove half of the control first-hour production; candidate avoids the outage.', spec(
    control=[2] + [0] * 23, candidate=[0, 2] + [0] * 22, demand=[1] + [0] * 23,
    initial=1, target=1, outages=[(.25, .75)]))
accepted('two-day-carry', 'Day-one deficit carries into day two; no midnight inventory reset.', spec(48,
    control=[1] * 48, candidate=[0] * 24 + [1] * 24, initial=10, target=10))
accepted('two-day-cross-midnight-outage', 'A shared fractional outage crosses the day boundary while inventory remains continuous.', spec(48,
    control=[1] * 48, candidate=[1] * 48, initial=10, target=8, outages=[(23.5, 24.5)]))
accepted('derating-common-realization', 'Common binary-exact derating changes effective output and modeled cost for both plans.', spec(
    production_multiplier=.5, control=[2] * 24, candidate=[2] * 24))
tiny = float.fromhex('0x0.0000000000001p-1022')
for label, reserve, target in [('reserve', 1, 0), ('terminal', 0, 1), ('reserve-and-terminal', 1, 1)]:
    accepted('subnormal-' + label, 'Exact stock loses the least positive binary64 unit although floating subtraction rounds to one.', spec(
        control=[tiny] + [0] * 23, candidate=[0] * 24, demand=[tiny] + [0] * 23,
        initial=1, reserve=reserve, target=target, sec=None))
accepted('half-hour-subnormal-production', 'An exact half-subnormal water quantity times large SEC has representable positive energy and cost.', spec(
    control=[tiny] + [0] * 23, candidate=[tiny] + [0] * 23, demand=[0] * 24,
    initial=1, target=1, outages=[(0, .5)], sec=1e300))
for field in ('controller_sha256', 'settings_sha256', 'case_sha256', 'tariffs_sha256', 'randomness'):
    value = 'another-seed' if field == 'randomness' else sha('different declared ' + field)
    accepted('different-declared-' + field, 'Same realized inputs remain numerically comparable, but the declared method is confounded.',
        spec(candidate_forecast=[100] * 24, control_forecast=[100] * 24),
        lambda p, f=field, v=value: change_declaration(p, lambda d: d['candidate'].__setitem__(f, v)),
        {'method.status': 'confounded_declaration'})
for field in ('forecast_issue_time', 'forecast_first_observed_time', 'features_available_time', 'plan_first_observed_time'):
    def late(p, f=field):
        def update(d):
            d['candidate'][f] = '2026-06-30T19:00:00Z'
            if f == 'forecast_issue_time':
                d['candidate']['forecast_first_observed_time'] = '2026-06-30T19:01:00Z'
        change_declaration(p, update)
    accepted('late-' + field, 'Evidence after the decision cutoff is late even though it precedes the target horizon.',
             edit=late, overrides={'timing.status': 'late_declared'})
for field in ('forecast_issue_time', 'forecast_first_observed_time', 'features_available_time', 'plan_first_observed_time'):
    accepted('missing-' + field, 'Missing declared timing prevents timing eligibility.',
        edit=lambda p, f=field: change_declaration(p, lambda d: d['candidate'].__setitem__(f, None)),
        overrides={'timing.status': 'not_established'})
accepted('late-and-missing-times', 'A known late timestamp remains late when a separate timestamp is missing.',
    edit=lambda p: change_declaration(p, lambda d: d['candidate'].update(
        features_available_time='2026-06-30T19:00:00Z', plan_first_observed_time=None)),
    overrides={'timing.status': 'late_declared'})
accepted('all-times-at-cutoff', 'The timing boundary includes times exactly equal to cutoff.',
    edit=lambda p: change_declaration(p, lambda d: [d[arm].update({field: d['decision_cutoff'] for field in
        ('forecast_issue_time', 'forecast_first_observed_time', 'features_available_time', 'plan_first_observed_time')}) for arm in ('candidate', 'control')]))

rejected('raw-hash-mismatch', 'Changing retained weather bytes without updating SHA must reject.',
    lambda p: p['files']['weather'].__setitem__('text', p['files']['weather']['text'] + '\n'), 'hash|SHA|identity|bytes')
rejected('declaration-hash-mismatch', 'Declaration text also requires exact retained-byte identity.',
    lambda p: p['declaration_file'].__setitem__('text', p['declaration_file']['text'] + '\n'), 'hash|SHA|identity|bytes')
for arm in ('candidate', 'control'):
    for field in ('forecast_sha256', 'plan_sha256'):
        rejected('wrong-' + arm + '-' + field, 'A run cannot link another supplied forecast or plan.',
            lambda p, a=arm, f=field: change_declaration(p, lambda d: d[a].__setitem__(f, sha('wrong link'))),
            'hash|SHA|link|match|identity')
for role in ('weather', 'candidate_forecast', 'control_forecast', 'tariffs', 'returned'):
    rejected('missing-hour-' + role, 'Every common horizon hour must be present exactly once.',
        lambda p, r=role: change_file(p, r, lambda text: '\n'.join(text.splitlines()[:-1]) + '\n'),
        'hour|row|support|horizon|missing|complete|count|expected')
    rejected('duplicate-hour-' + role, 'Duplicate support cannot substitute for the final required hour.',
        lambda p, r=role: change_file(p, r, lambda text: '\n'.join(text.splitlines()[:-1] + [text.splitlines()[1]]) + '\n'),
        'duplicate|hour|support|repeated|unique')
rejected('wrong-case-bound-return', 'Every candidate return row binds the complete retained case.',
    lambda p: change_file(p, 'returned', lambda text: text.replace(p['files']['case']['sha256'], sha('another case'), 1)),
    'case|hash|SHA|match|identity')
rejected('receipt-before-issue', 'First observation cannot precede the declared issuance.',
    lambda p: change_declaration(p, lambda d: d['candidate'].__setitem__('forecast_first_observed_time', '2026-06-30T14:00:00Z')),
    'observ|issue|recei|before')
rejected('cutoff-at-horizon', 'Decision cutoff must precede the first evaluated hour.',
    lambda p: change_declaration(p, lambda d: d.__setitem__('decision_cutoff', iso(START))), 'cutoff|horizon|before|precede')
rejected('unknown-declaration-field', 'Exact declaration fields prevent hidden alternative conditions.',
    lambda p: change_declaration(p, lambda d: d.__setitem__('cached_approval', True)), 'field|unknown|unexpected|unsupported')
rejected('unknown-csv-column', 'CSV columns have a closed contract.',
    lambda p: change_file(p, 'weather', lambda text: text.replace('radiation_w_m2\n', 'radiation_w_m2,other\n', 1)),
    'column|header|field')
rejected('radiation-out-of-range', 'Radiation above the declared physical input range rejects.',
    lambda p: change_file(p, 'candidate_forecast', lambda text: text.replace(',100\n', ',2001\n', 1)), 'radiation|range|2000|invalid|between')
rejected('negative-tariff', 'Negative declared tariffs are outside this contract.',
    lambda p: change_file(p, 'tariffs', lambda text: text.replace(',1\n', ',-1\n', 1)), 'tariff|negative|nonnegative|range|invalid')
rejected('numeric-underflow-radiation', 'Lexically positive radiation cannot silently become zero.',
    lambda p: change_file(p, 'weather', lambda text: text.replace(',100\n', ',1e-400\n', 1)), 'underflow|numeric|number|positive|finite|invalid')
rejected('numeric-underflow-returned', 'Lexically positive returned production cannot silently become zero.',
    lambda p: change_file(p, 'returned', lambda text: text.replace(',1\n', ',1e-400\n', 1)), 'underflow|numeric|number|positive|finite|invalid|production')
rejected('nonfinite-tariff', 'Nonfinite monetary input rejects.',
    lambda p: change_file(p, 'tariffs', lambda text: text.replace(',1\n', ',Infinity\n', 1)), 'finite|numeric|number|tariff|invalid')
rejected('modeled-cost-overflow', 'Finite declared operands must not produce infinite modeled cost.', lambda p: None,
    'overflow|finite|range|represent', spec(sec=1e308, tariffs=[2] * 24))
rejected('modeled-cost-positive-underflow', 'A positive whole-horizon cost below binary64 display range must not silently become zero.', lambda p: None,
    'underflow|positive|represent|range', spec(control=[1] + [0] * 23, candidate=[1] + [0] * 23,
    demand=[0] * 24, sec=tiny, tariffs=[.5] + [0] * 23))
for label, value in [('zero', 0), ('negative', -1)]:
    rejected(label + '-specific-energy', 'Specific energy must be positive or explicitly unknown.',
        lambda p, v=value: change_declaration(p, lambda d: d.__setitem__('specific_energy_kwh_m3', v)),
        'specific|energy|positive|range|invalid')

# Independent anchors protect the generator, not just the product-facing labels.
by_id = {case['id']: case for case in cases}
def anchor(identity, path, expected):
    actual = by_id[identity]['expected'][path]
    assert actual == expected, (identity, path, actual, expected)

anchor('better-error-worse-water', 'adequacy.candidate.unmet_m3.exact', exact(F(2)))
anchor('better-error-worse-cost', 'energy.cost_eur.delta', 96)
anchor('adequate-equal-water-retiming', 'energy.cost_eur.delta', -96)
anchor('spilled-production-still-costs', 'energy.cost_eur.candidate', 96)
anchor('fractional-outage', 'energy.cost_eur.control', 2)
anchor('fractional-outage', 'energy.cost_eur.candidate', 4)
anchor('two-day-carry', 'adequacy.candidate.unmet_m3.exact', exact(F(14)))
anchor('two-day-cross-midnight-outage', 'adequacy.control.final_storage_m3.exact', exact(F(9)))
anchor('subnormal-terminal', 'adequacy.candidate.final_storage_m3.exact', exact(F(1) - q(tiny)))
anchor('subnormal-reserve', 'adequacy.candidate.status', 'modeled_requirements_failed')
anchor('equal-inadequate-plans', 'water_service.status', 'no_modeled_regression')
anchor('equal-inadequate-plans', 'adequacy.candidate.unmet_m3.exact', exact(F(24)))
anchor('half-hour-subnormal-production', 'energy.cost_eur.candidate', float(q(tiny) * q(1e300) / 2))
assert len(by_id) == len(cases)
assert all(c.get('expected', {}).get('forecast_attribution.status', 'not_established') == 'not_established' for c in cases)
artifact = {'schema': 1, 'kind': 'independent_forecast_decision_fixtures',
    'protocol_sha256': hashlib.sha256((HERE / 'PROTOCOL.md').read_bytes()).hexdigest(),
    'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'water_oracle_sha256': hashlib.sha256(ORACLE.read_bytes()).hexdigest(),
    'method': 'Raw analytical supplied scenarios; independent Fraction.from_float water trajectories and arithmetic. No product imports or calls.',
    'limits': 'Selected counterexamples, not prevalence, authenticated execution, forecasting quality on field data, or causal operating benefit.',
    'analytical_anchor_count': 13, 'cases': cases}
target = HERE / 'independent-inputs-v1.json'
target.write_text(json.dumps(artifact, indent=2, allow_nan=False) + '\n')
print(json.dumps({'path': str(target), 'cases': len(cases),
    'accepted': sum('expected' in c for c in cases), 'rejected': sum('rejection_regex' in c for c in cases),
    'anchors': artifact['analytical_anchor_count'], 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
    'generator_sha256': artifact['generator_sha256'], 'bytes': target.stat().st_size}))
