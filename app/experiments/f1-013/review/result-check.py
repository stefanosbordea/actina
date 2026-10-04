"""Independent frozen-result audit. Never imports production experiment helpers."""
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
from fractions import Fraction as F
import gzip
import hashlib
from itertools import product
import json
from pathlib import Path
import resource
import sys
import time
import numpy as np

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
ROOT = EXPERIMENT.parents[2]
OUT = EXPERIMENT / 'result'
PREVIOUS = ROOT / 'app/experiments/physical-012/result'
checks, candidate_count = 0, 0
start, cpu = time.perf_counter(), time.process_time()
STAGES = ('validation', 'test')
METHODS = ('raw_nwp', 'recency_robust', 'recency_pooled', 'conditional_robust', 'conditional_pooled')
COUNTS = {'validation': (150, 3566, 3419), 'test': (149, 3567, 3517)}
CUTOFF = {'validation': datetime(2025, 12, 4), 'test': datetime(2026, 5, 2)}


def check(condition, label):
    global checks
    checks += 1
    if not condition:
        raise AssertionError(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(value):
    if isinstance(value, dict) and set(value) == {'numerator', 'denominator', 'value'}:
        result = F(value['numerator'], value['denominator'])
        check(result.numerator == value['numerator'] and result.denominator == value['denominator'], 'canonical Fraction encoding')
        check(float(result) == value['value'], 'display value agrees with exact Fraction')
        return result
    return value


def load(path):
    return json.loads(path.read_text(), object_hook=exact)


def csv_rows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def keyed(records, key):
    answer = {row[key]: row for row in records}
    check(len(answer) == len(records), 'unique source identity: ' + key)
    return answer


def mask(values):
    return sum((1 << i) for i, value in enumerate(values) if value)


def scores(distributions, action):
    k = action.bit_count()
    answer = []
    for distribution in distributions:
        n = sum(distribution.values())
        active = sum(weight for truth, weight in distribution.items() if truth)
        p, r, f = F(), F(), F()
        for truth, weight in distribution.items():
            size, hits = truth.bit_count(), (truth & action).bit_count()
            if k:
                p += weight * F(hits, k)
            if size:
                r += weight * F(hits, size)
            f += weight * (F(2 * hits, size + k) if size + k else F(1))
        answer.append(dict(precision=p / n if k else None, recall=r / active if active else None, f1=f / n))
    return answer


def failed(metrics, baseline, action, raw):
    failures = ['zero_call_precision'] if raw and not action else []
    for r, (candidate, control) in enumerate(zip(metrics, baseline)):
        for name in ('precision', 'recall', 'f1'):
            if control[name] is not None and (candidate[name] is None or candidate[name] < control[name]):
                failures.append(f'{r}/{name}')
    return failures


def objective(metrics, baseline):
    gains = [m['f1'] - b['f1'] for m, b in zip(metrics, baseline)]
    return dict(robust=min(gains), pooled=sum(gains, F()) / 2)


def measured(truth, predicted):
    check(len(truth) == len(predicted), 'observed aligned lengths')
    cells = Counter(zip(truth, predicted))
    tp, fp, fn, tn = (cells[True, True], cells[False, True], cells[True, False], cells[False, False])
    return dict(hours=len(truth), tp=tp, fp=fp, fn=fn, tn=tn, positive_calls=tp + fp,
                precision=F(tp, tp + fp) if tp + fp else None,
                recall=F(tp, tp + fn) if tp + fn else None,
                f1=F(2 * tp, 2 * tp + fp + fn) if 2 * tp + fp + fn else None)


def compare(a, b):
    differences = {ref + '/' + metric: a[ref][metric] - b[ref][metric] if a[ref][metric] is not None and b[ref][metric] is not None else None
                   for ref in ('weather_full', 'satellite_common') for metric in ('precision', 'recall', 'f1')}
    assessable = all(v is not None for v in differences.values())
    valid = [v for v in differences.values() if v is not None]
    return dict(assessable=assessable, nonregression=assessable and all(v >= 0 for v in valid),
                strict_gain=assessable and any(v > 0 for v in valid), all_six_strict=assessable and all(v > 0 for v in valid),
                passed=assessable and all(v >= 0 for v in valid) and any(v > 0 for v in valid), differences=differences)


pins = load(EXPERIMENT / 'inputs.json')
for name, digest in pins.items():
    check(sha(ROOT / name) == digest, 'immutable input ' + name)
for name, digest in load(OUT / 'outputs.json').items():
    check(sha(OUT / name) == digest, 'retained output ' + name)
freeze = load(OUT / 'planning-freeze.json')
for name, digest in freeze['files_sha256'].items():
    check(sha(OUT / name) == digest, 'planning freeze ' + name)
receipt = load(OUT / 'execution-receipt.json')
check(receipt['status'] == 'COMPLETE' and receipt['exit_code'] == 0, 'successful actual run')
check(receipt['elapsed_seconds'] <= 1800, 'declared runtime budget')
check(receipt['input_lock_sha256'] == sha(EXPERIMENT / 'inputs.json'), 'execution input lock')
check(receipt['protocol_sha256'] == sha(EXPERIMENT / 'PROTOCOL.md'), 'execution protocol')
phase = [json.loads(line) for line in (OUT / 'events.jsonl').read_text().splitlines()]
names = [row['event'] for row in phase]
check(names.count('ALL_DECISIONS_FROZEN') == names.count('SCORING_REFERENCES_OPENED') == 1, 'unique phase boundary')
check(names.index('ALL_DECISIONS_FROZEN') < names.index('SCORING_REFERENCES_OPENED') < names.index('COMPLETE'), 'decision freeze precedes scoring')
check(all(not row.get('outcome_scoring_started', False) for row in phase[:names.index('SCORING_REFERENCES_OPENED')]), 'no earlier scoring phase')
check(all(datetime.fromisoformat(a['at_utc']) <= datetime.fromisoformat(b['at_utc']) for a, b in zip(phase, phase[1:])), 'ordered phase times')

features = csv_rows(ROOT / 'app/experiments/f1-008/result/features.csv')
origins = [datetime.fromisoformat(r['feature_time']) for r in features]
targets = [t + timedelta(hours=24) for t in origins]
forecast = np.asarray([float(r['nwp_day2_radiation']) for r in features])
check(len(set(origins)) == len(origins) == 17832, 'feature identity set')
check(all(b - a == timedelta(hours=1) for a, b in zip(origins, origins[1:])), 'hourly feature sequence')
weather_rows = csv_rows(ROOT / 'app/experiments/f1-006/result/feature-targets.csv')
joined = csv_rows(ROOT / 'app/experiments/reference-training-001/result/joined-reference.csv')
check(len(weather_rows) == len(joined) == len(features), 'reference row count')
weather, satellite = [], []
for i, (a, b) in enumerate(zip(weather_rows, joined)):
    check(all(datetime.fromisoformat(r['feature_time']) == origins[i] and datetime.fromisoformat(r['target_time']) == targets[i] for r in (a, b)), 'reference target clock')
    valid = targets[i].replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc)
    check(datetime.fromisoformat(b['valid_time_utc']) == valid and datetime.fromisoformat(b['interval_start_utc']) == valid - timedelta(hours=1), 'reference UTC interval')
    w, s = float(a['actual']), float(b['satellite_w_m2']) if b['satellite_w_m2'] else None
    check(w == float(b['weather_actual_w_m2']) and int(b['is_missing']) == int(s is None), 'reference value identity')
    weather.append(w)
    satellite.append(s)
report = load(OUT / 'report.json')
comparisons, interpretations = {}, {}
for stage in STAGES:
    days, hours, common_count = COUNTS[stage]
    with np.load(PREVIOUS / stage / 'plans.npz', allow_pickle=False) as archive:
        positions, raw_ghi = archive['target_positions'], archive['raw_forecast_ghi']
    with np.load(PREVIOUS / stage / 'scenario-replay.npz', allow_pickle=False) as archive:
        scenario_ghi = archive['unclipped_ghi'][:, :, 0]
    with np.load(PREVIOUS / stage / 'bank.npz', allow_pickle=False) as archive:
        bank = {k: archive[k] for k in archive.files}
    with np.load(OUT / stage / 'calls.npz', allow_pickle=False) as archive:
        calls, methods, saved_positions = archive['calls'], archive['methods'], archive['target_positions']
    check(calls.shape == (days, 5, 24) and calls.dtype == bool and tuple(methods) == METHODS, 'all method call vectors')
    check(positions.shape == (days, 24) and np.array_equal(positions, saved_positions), 'all padded target positions')
    check(np.array_equal(raw_ghi, forecast[positions]) and np.array_equal(calls[:, 0], raw_ghi > 600), 'raw forecast reconstruction')
    check(len(set(positions.flat)) == positions.size, 'unique horizon positions')
    metadata = csv_rows(PREVIOUS / stage / 'plan-metadata.csv')
    pool_positions = bank['pool_source_positions']
    pool_times = bank['pool_source_target_time']
    pool_days = bank['pool_source_days']
    check(np.array_equal(bank['pool_nwp'], forecast[pool_positions]), 'bank NWP identity')
    check(np.array_equal(pool_times, np.asarray([str(targets[i]) for i in pool_positions.flat]).reshape(pool_positions.shape)), 'historical source clocks')
    check(all(datetime.fromisoformat(t) < CUTOFF[stage] for t in pool_times.flat), 'source cutoff')
    for d, times in enumerate(pool_times):
        start_day = datetime.fromisoformat(pool_days[d])
        check([datetime.fromisoformat(t) for t in times] == [start_day + timedelta(hours=h) for h in range(24)], 'historical whole-day identity')
    with gzip.open(OUT / stage / 'decisions.jsonl.gz', 'rt') as stream:
        records = [json.loads(line, object_hook=exact) for line in stream]
    check(len(records) == 2 * days, 'complete horizon-bank ledger')
    for d in range(days):
        day = targets[positions[d, 0]]
        check(day.hour == 0 and [targets[i] for i in positions[d]] == [day + timedelta(hours=h) for h in range(24)], '24 exact forecast endpoints')
        check(day - timedelta(days=1) >= CUTOFF[stage], 'forecast source chronology')
        check(datetime.fromisoformat(metadata[d]['issue_time']) == day - timedelta(days=1), 'issue-time identity')
        for b, bank_name in enumerate(('recency', 'conditional')):
            row = records[2 * d + b]
            check(row['stage'] == stage and row['day'] == str(day.date()) and row['bank'] == bank_name, 'ledger horizon identity')
            indices = bank['recency_pool_indices'] if b == 0 else bank['conditional_pool_indices'][d]
            check(len(set(indices)) == 64 and np.all(np.diff(indices) > 0), '64 canonical source IDs')
            check(row['source_days'] == pool_days[indices].tolist(), 'ledger source-day IDs')
            check(np.array_equal(scenario_ghi[d, b], raw_ghi[d][None, None, :] + bank['pool_residuals'][:, indices]), 'unclipped scenario reconstruction')
            distributions = [Counter(mask(path > 600) for path in reference) for reference in scenario_ghi[d, b]]
            raw = mask(raw_ghi[d] > 600)
            baseline = scores(distributions, raw)
            check(row['raw_metrics'] == baseline, 'raw exact expected scores')
            possible, unanimous = 0, (1 << 24) - 1
            for distribution in distributions:
                for truth in distribution:
                    possible |= truth
                    unanimous &= truth
            ambiguous = possible ^ unanimous
            uncertain = [i for i in range(24) if ambiguous & (1 << i)]
            expected_set = {raw}
            for included in product((False, True), repeat=len(uncertain)):
                expected_set.add(unanimous | sum(1 << i for i, yes in zip(uncertain, included) if yes))
            check(row['unanimous_positive'] == [i for i in range(24) if unanimous & (1 << i)] and row['uncertain'] == uncertain, 'reduction metadata')
            check(row['unanimous_negative'] == [i for i in range(24) if not possible & (1 << i)], 'negative reduction metadata')
            check(row['canonical_subsets'] == 2 ** len(uncertain), 'canonical subset count')
            check(len(row['candidates']) == len(expected_set) and {mask(v['decision']) for v in row['candidates']} == expected_set, 'complete candidate enumeration')
            for r, (table, distribution) in enumerate(zip(row['coefficients'], distributions)):
                active = sum(weight for truth, weight in distribution.items() if truth)
                check(table['scenarios'] == 64 and table['positive_scenarios'] == active and table['empty_f1'] == F(64 - active, 64), 'coefficient scenario metadata')
                for i in range(24):
                    bit = 1 << i
                    check(table['probability'][i] == F(sum(weight for truth, weight in distribution.items() if truth & bit), 64), 'exact marginal coefficient')
                    if active:
                        check(table['recall'][i] == sum((weight * F(1, truth.bit_count()) for truth, weight in distribution.items() if truth & bit), F()) / active, 'exact recall coefficient')
                    else:
                        check(table['recall'] is None, 'undefined recall coefficient')
                    for k in range(1, 25):
                        expected = sum((weight * F(2, truth.bit_count() + k) for truth, weight in distribution.items() if truth & bit), F()) / 64
                        check(table['f1'][str(k)][i] == expected, 'exact F1 coefficient')
            feasible = {}
            for candidate in row['candidates']:
                action = mask(candidate['decision'])
                metrics = scores(distributions, action)
                failures = failed(metrics, baseline, action, raw)
                gains = objective(metrics, baseline)
                check(candidate['metrics'] == metrics and candidate['failed_constraints'] == failures, 'candidate exact metrics and guards')
                check(candidate['objectives'] == gains and candidate['positive_calls'] == action.bit_count() and candidate['changed_bits'] == (action ^ raw).bit_count(), 'candidate objective and counts')
                if not failures:
                    feasible[action] = metrics
                candidate_count += 1
            for a, arm in enumerate(('robust', 'pooled')):
                def rank(action):
                    return (-objective(feasible[action], baseline)[arm], (action ^ raw).bit_count(), action.bit_count(), tuple(i for i in range(24) if action & (1 << i)))
                best = min(feasible, key=rank)
                selected = row['arms'][arm]
                check(mask(selected['decision']) == best == mask(calls[d, 1 + 2 * b + a]), 'selected exact ranked optimum')
                check(selected['metrics'] == feasible[best] and selected['objective'] == -rank(best)[0], 'selected exact scores and gain')
                check(selected['objective'] > 0 or best == raw, 'strict objective gain or raw fallback')
    original_rows = csv_rows(ROOT / 'eval' / ('cv_predictions.csv' if stage == 'validation' else 'test_predictions.csv'))
    original = keyed(original_rows, 'time')
    origin_index = {str(t): i for i, t in enumerate(origins)}
    selected_positions = [origin_index[r['time']] for r in original_rows]
    check(len(selected_positions) == hours, 'original hour count')
    expected_targets = [str(targets[i]) for i in selected_positions]
    location = {int(i): (d, h) for d, block in enumerate(positions) for h, i in enumerate(block)}
    w, s = [weather[i] for i in selected_positions], [satellite[i] for i in selected_positions]
    check(all(float(r['actual']) == v for r, v in zip(original_rows, w)), 'original weather identity')
    membership = keyed(csv_rows(ROOT / f'app/experiments/f1-009/result/{stage}-reference-membership.csv'), 'target_time')
    check(set(membership) == set(expected_targets), 'original frozen mask IDs')
    for i, target in enumerate(expected_targets):
        source = membership[target]
        check(float(source['weather_w_m2']) == w[i] and (float(source['satellite_w_m2']) if source['satellite_w_m2'] else None) == s[i] and bool(int(source['satellite_available'])) == (s[i] is not None), 'original frozen mask values')
    methods = {name: [bool(calls[location[i][0], m, location[i][1]]) for i in selected_positions] for m, name in enumerate(METHODS)}
    methods.update(original=[float(r['predicted']) > 600 for r in original_rows], persistence=[float(r['baseline']) > 600 for r in original_rows])
    for experiment, arm, weather_field, selected_field in [('008', 'consensus_two_source', 'weather_actual_w_m2', 'selected_augmented_arm'), ('009', 'joint', 'weather_w_m2', 'selected_arm')]:
        selection = load(ROOT / f'app/experiments/f1-{experiment}/result/validation-selection.json')
        check(selection[selected_field] == arm, 'frozen selected comparator arm')
        policy = selection['policies'][arm]['policy']
        context = keyed(csv_rows(ROOT / f'app/experiments/f1-{experiment}/result/predictions/{stage}-{arm}.csv'), 'target_time')
        check(set(context) == set(expected_targets), 'saved comparator exact hour IDs')
        predictions = []
        for j, target in enumerate(expected_targets):
            row = context[target]
            raw, probability = methods['raw_nwp'][j], float(row['probability'])
            call = raw if policy['kind'] == 'control' else probability > policy['lower' if raw else 'upper']
            check(bool(int(row['predicted_positive'])) == call and bool(int(row['nwp_positive'])) == raw, 'frozen comparator threshold')
            check(float(row[weather_field]) == w[j] and (float(row['satellite_w_m2']) if row['satellite_w_m2'] else None) == s[j], 'saved comparator reference identity')
            predictions.append(call)
        methods['f1_' + experiment + '_selected'] = predictions
    common = [i for i, v in enumerate(s) if v is not None]
    check(len(common) == common_count, 'exact common-hour count')
    metrics = {method: dict(weather_full=measured([v > 600 for v in w], predicted),
        weather_common=measured([w[j] > 600 for j in common], [predicted[j] for j in common]),
        satellite_common=measured([s[j] > 600 for j in common], [predicted[j] for j in common])) for method, predicted in methods.items()}
    check(report['splits'][stage]['metrics'] == metrics, 'all observed counts and exact P/R/F1')
    exported = csv_rows(OUT / stage / 'predictions.csv')
    check(len(exported) == hours, 'per-hour prediction export count')
    for j, row in enumerate(exported):
        check(int(row['source_position']) == selected_positions[j] and row['feature_time'] == str(origins[selected_positions[j]]) and row['target_time'] == expected_targets[j], 'per-hour export IDs')
        check(all(int(row[method]) == int(predicted[j]) for method, predicted in methods.items()), 'per-hour export all decisions')
    selected_set = set(selected_positions)
    exported_membership = csv_rows(OUT / stage / 'evaluation-membership.csv')
    expected_membership = [dict(source_position=str(int(i)), target_time=str(targets[i]), original_period=str(int(i in selected_set)), satellite_available=str(int(satellite[i] is not None))) for i in positions.flat]
    check(exported_membership == expected_membership, 'padded membership retains every endpoint')
    check(report['splits'][stage]['padding_hours'] == days * 24 - hours and report['splits'][stage]['missing_satellite_hours'] == hours - common_count, 'padding and missing rows reported')
    index = {p: j for j, p in enumerate(selected_positions)}
    expected_daily = []
    for d, block in enumerate(positions):
        for subset, reference in (('weather_full', weather), ('weather_common', weather), ('satellite_common', satellite)):
            included = [int(i) for i in block if i in index and (subset == 'weather_full' or satellite[i] is not None)]
            for method, predicted in methods.items():
                expected_daily.append(dict(day=str(targets[block[0]].date()), subset=subset, method=method,
                    **measured([reference[i] > 600 for i in included], [predicted[index[i]] for i in included])))
    check(load(OUT / stage / 'daily-metrics.json') == expected_daily, 'all daily comparator metric distributions')
    expected_corrections = {method: dict(additions=sum(p and not b for p, b in zip(predicted, methods['raw_nwp'])), removals=sum(b and not p for p, b in zip(predicted, methods['raw_nwp'])),
        changed_full_day_counts=sum(int(calls[d, METHODS.index(method)].sum()) != int(calls[d, 0].sum()) for d in range(days)) if method in METHODS else None) for method, predicted in methods.items()}
    check(report['splits'][stage]['corrections'] == expected_corrections, 'all additions removals and changed K counts')
    comparisons[stage] = {method: {control: compare(metrics[method], metrics[control]) for control in ('raw_nwp', 'original', 'persistence', 'f1_008_selected', 'f1_009_selected')} for method in METHODS[1:]}
    check(report['splits'][stage]['comparisons'] == comparisons[stage], 'all exact comparator differences and period gates')
    interpretations[stage] = {method: {control: [name for name, value in result['differences'].items() if value is not None and value < 0] for control, result in controls.items()} for method, controls in comparisons[stage].items()}
expected_gates = {method: dict(raw_control_both_periods=all(comparisons[stage][method]['raw_nwp']['passed'] for stage in STAGES),
    all_six_strict_both_periods=all(comparisons[stage][method]['raw_nwp']['all_six_strict'] for stage in STAGES)) for method in METHODS[1:]}
check(report['gates'] == expected_gates and report['primary_method'] == 'conditional_robust', 'fixed primary and cross-period gates')
for name, digest in pins.items():
    check(sha(ROOT / name) == digest, 'input stable after independent audit ' + name)
print(json.dumps(dict(status='PASS', checks=checks, candidate_records=candidate_count, horizons=299, horizon_bank_records=598,
    input_lock_sha256=sha(EXPERIMENT / 'inputs.json'), planning_freeze_sha256=sha(OUT / 'planning-freeze.json'),
    checker_sha256=sha(Path(__file__)), result_manifest_sha256=sha(OUT / 'outputs.json'),
    gates=expected_gates, regressions=interpretations, elapsed_seconds=time.perf_counter() - start, cpu_seconds=time.process_time() - cpu,
    peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    scope='Every retained historical candidate, exact empirical coefficient, score, safeguard and ranked optimum, all masks, control decisions and observed metrics independently reconstructed. No production helper imported.'), indent=2))
