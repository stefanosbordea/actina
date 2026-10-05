"""Recompute the saved experiment using stdlib only; never fit or change results."""
import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = HERE / 'result-retry1'
DAY, HOUR = timedelta(hours=24), timedelta(hours=1)
METHODS = ['persistence', 'original', 'absolute_l1', 'residual_base', 'residual_history']
MEASURES = ['hours', 'tp', 'fp', 'fn', 'tn', 'precision', 'recall', 'f1', 'mae', 'rmse']


def require(test, message):
    if not test:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def load(path):
    return json.loads(path.read_text())


def metrics(actual, values, cutoff):
    tp = fp = fn = tn = 0
    for actual_value, value in zip(actual, values, strict=True):
        if actual_value > 600:
            if value > cutoff: tp += 1
            else: fn += 1
        elif value > cutoff: fp += 1
        else: tn += 1
    differences = [v - a for a, v in zip(actual, values, strict=True)]
    return dict(hours=len(actual), tp=tp, fp=fp, fn=fn, tn=tn,
        precision=tp / (tp + fp) if tp + fp else None,
        recall=tp / (tp + fn) if tp + fn else None,
        f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        mae=math.fsum(abs(x) for x in differences) / len(actual),
        rmse=math.sqrt(math.fsum(x * x for x in differences) / len(actual)))


def equal(a, b):
    if a is None or b is None: return a is b
    return abs(a - b) <= 1e-9


def compare(a, b, label):
    for key in MEASURES:
        ok = a[key] == b[key] if key in ['hours', 'tp', 'fp', 'fn', 'tn'] else equal(a[key], b[key])
        require(ok, f'{label}: {key}: {a[key]} != {b[key]}')


def ratios(m):
    tp, fp, fn = m['tp'], m['fp'], m['fn']
    return tuple(Fraction(a, b) if b else Fraction(-1) for a, b in
                 [(2 * tp, 2 * tp + fp + fn), (tp, tp + fp), (tp, tp + fn)])


def gate(m, persistence, original):
    _, p, r = ratios(m)
    return p >= 0 and r >= 0 and p >= ratios(persistence)[1] and r >= ratios(original)[2]


def forecast(name, raw, base, alpha):
    if name.startswith('residual_'): return max(0, base + alpha * raw)
    if name == 'absolute_l1': return max(0, raw)
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = load(RUN / 'report.json')
    require(report['status'] == 'COMPLETE', 'Incomplete run')
    identities = {ROOT / name: value for name, value in report['input_sha256'].items()}
    identities.update({HERE / 'PROTOCOL.md': report['protocol_sha256'], HERE / 'run.py': report['code_sha256'],
                       HERE.parent / 'f1-001/run.py': report['reused_evaluator_sha256']})
    identities.update({RUN / name: value for name, value in report['outputs_sha256'].items()})
    for path, expected in identities.items(): require(sha(path) == expected, 'Changed: ' + str(path))
    sources = {name: rows(ROOT / name) for name in report['input_sha256']}
    for name, records in sources.items():
        times = [datetime.fromisoformat(row['time']) for row in records]
        require(len(times) == len(set(times)) and all(b - a == HOUR for a, b in zip(times, times[1:])), name + ' coverage')
    feature_rows = {datetime.fromisoformat(r['time']): r for r in sources['data/features.csv']}
    weather = {datetime.fromisoformat(r['time']): r for r in sources['data/paphos_weather_data.csv']}
    base_fields = ['temperature_2m', 'shortwave_radiation', 'relative_humidity_2m', 'cloud_cover', 'radiation_yesterday', 'hour', 'month']
    complete = []
    for origin, row in feature_rows.items():
        require(float(row['target']) == float(weather[origin + DAY]['shortwave_radiation']), 'Target mismatch')
        require(float(row['shortwave_radiation']) == float(weather[origin]['shortwave_radiation']), 'Origin radiation mismatch')
        available = all(math.isfinite(float(row[field])) for field in base_fields)
        available &= all(origin - lag * HOUR in weather and all(math.isfinite(float(weather[origin - lag * HOUR][field]))
                            for field in ['shortwave_radiation', 'cloud_cover']) for lag in range(25))
        if available: complete.append(origin)
    require(report['features']['base'] == base_fields and len(report['features']['history']) == 25, 'Feature counts')
    reference_parse_residual = {'values': 0, 'maximum_absolute_w_m2': 0.0, 'classification_changes': 0}
    complete = set(complete)
    checks = dict(prediction_files=0, prediction_rows=0, full_scores=0, monthly_scores=0,
                  validation_combinations=0, training_memberships=0, comparison_rows=0)
    independently_scored = {}
    predictions = {}
    for stage, original_name in [('validation', 'cv_predictions.csv'), ('test', 'test_predictions.csv')]:
        original = sources['eval/' + original_name]
        origins = [datetime.fromisoformat(r['time']) for r in original]
        targets = [x + DAY for x in origins]
        actual = [float(r['actual']) for r in original]
        baseline = [float(r['baseline']) for r in original]
        for time, a, b in zip(origins, actual, baseline, strict=True):
            require(time in complete, 'Incomplete evaluation origin')
            require(a == float(feature_rows[time]['target']) and b == float(feature_rows[time]['shortwave_radiation']), 'Split identity')
        expected_train = sorted(t for t in complete if t + DAY < origins[0])
        training = rows(RUN / f'{stage}-training-origins.csv')
        require([datetime.fromisoformat(r['feature_time']) for r in training] == expected_train, 'Training membership')
        require(all(datetime.fromisoformat(r['target_time']) == t + DAY for r, t in zip(training, expected_train, strict=True)), 'Training target identity')
        expected_split = dict(hours=len(original), origin_start=str(origins[0]), origin_end=str(origins[-1]),
            target_start=str(targets[0]), target_end=str(targets[-1]), train_hours=len(expected_train),
            train_start=str(expected_train[0]), train_end=str(expected_train[-1]), latest_training_target=str(expected_train[-1]+DAY),
            warmup_removed=sum(t + DAY < origins[0] and t not in complete for t in feature_rows),
            purged_hours=sum(t < origins[0] and not t + DAY < origins[0] for t in feature_rows),
            training_origins_sha256=sha(RUN / f'{stage}-training-origins.csv'))
        require(report['splits'][stage] == expected_split, 'Training boundary report')
        checks['training_memberships'] += 1
        months = defaultdict(list)
        for i, target in enumerate(targets): months[target.strftime('%Y-%m')].append(i)
        for name in METHODS:
            saved = rows(RUN / 'predictions' / f'{stage}-{name}.csv')
            require(len(saved) == len(original), 'Dropped evaluation rows')
            expected = report['methods'][name][stage]
            cfg = expected['configuration']
            raw, selected, default = [], [], []
            for i, row in enumerate(saved):
                require(datetime.fromisoformat(row['feature_time']) == origins[i] and datetime.fromisoformat(row['target_time']) == targets[i], 'Changed prediction time')
                require(float(row['actual_w_m2']) == actual[i] and float(row['baseline_w_m2']) == baseline[i], 'Changed prediction label/baseline')
                require(float(row['alpha']) == cfg['alpha'] and float(row['cutoff']) == cfg['cutoff'], 'Changed frozen config')
                value = float(row['raw_prediction'])
                if name in ['persistence', 'original']:
                    original_value = float(original[i]['baseline' if name == 'persistence' else 'predicted'])
                    residual = abs(value - original_value)
                    require(equal(value, original_value) and (value > 600) == (original_value > 600), 'Changed original reference')
                    if residual:
                        reference_parse_residual['values'] += 1
                        reference_parse_residual['maximum_absolute_w_m2'] = max(reference_parse_residual['maximum_absolute_w_m2'], residual)
                s = forecast(name, value, baseline[i], cfg['alpha'])
                d = forecast(name, value, baseline[i], 0 if name == 'persistence' else 1)
                require(equal(s, float(row['score'])) and equal(d, float(row['default_score'])), 'Incorrect reconstruction')
                require(int(row['predicted_positive']) == (s > cfg['cutoff']) and int(row['default_positive']) == (d > 600), 'Incorrect threshold result')
                raw.append(value); selected.append(s); default.append(d)
            predictions[stage, name] = dict(actual=actual, baseline=baseline, raw=raw)
            for basis, values, cutoff, monthly_key in [('selected', selected, cfg['cutoff'], 'monthly'), ('default', default, 600, 'default_monthly')]:
                m = metrics(actual, values, cutoff)
                independently_scored[stage, name, basis] = m
                compare(m, expected[basis], f'{stage}/{name}/{basis}')
                require([r['month'] for r in expected[monthly_key]] == list(months), 'Dropped or reordered month')
                for row in expected[monthly_key]:
                    indices = months[row['month']]
                    compare(metrics([actual[i] for i in indices], [values[i] for i in indices], cutoff), row, 'Month')
                    checks['monthly_scores'] += 1
                checks['full_scores'] += 1
            checks['prediction_files'] += 1; checks['prediction_rows'] += len(saved)
    persistence = independently_scored['validation', 'persistence', 'selected']
    original = independently_scored['validation', 'original', 'selected']
    selection = load(RUN / 'validation-selection.json')
    require(sha(RUN / 'validation-selection.json') == report['selection_sha256'], 'Frozen selection identity')
    for name in METHODS:
        cfg = report['methods'][name]['validation']['configuration']
        require(cfg == report['methods'][name]['test']['configuration'] == selection['all_configurations'][name], 'Test retuning')
        compare(independently_scored['validation', name, 'selected'], selection['validation'][name], 'Selection scores')
        if name not in METHODS[2:]:
            require(cfg['qualifies'] == gate(independently_scored['validation', name, 'selected'], persistence, original), 'Reference gate')
            continue
        grid_file = RUN / f'validation-grid-{name}.json'
        require(sha(grid_file) == selection['grid_sha256'][name], 'Changed selection grid')
        grid = load(grid_file)
        combinations = [(a, c) for a in ([0, .25, .5, .75, 1] if name.startswith('residual_') else [1]) for c in range(500,701,10)]
        require([(g['alpha'], g['cutoff']) for g in grid] == combinations, 'Grid coverage')
        data = predictions['validation', name]
        for row in grid:
            values = [forecast(name, r, b, row['alpha']) for r, b in zip(data['raw'], data['baseline'], strict=True)]
            m = metrics(data['actual'], values, row['cutoff'])
            compare(m, row, 'Grid metrics')
            require(row['qualifies'] == gate(m, persistence, original), 'Grid gate')
            checks['validation_combinations'] += 1
        qualifying = [g for g in grid if g['qualifies']]
        best = max(qualifying, key=lambda g: (*ratios(g), -abs(g['cutoff']-600), -g['alpha'], -g['cutoff'])) if qualifying else None
        expected_cfg = {k: best[k] for k in ['alpha','cutoff','qualifies']} if best else dict(alpha=1,cutoff=600,qualifies=False)
        require(cfg == expected_cfg, 'Per-method selection rule')
    order = ['persistence', *METHODS[2:]]
    candidates = [n for n in order if selection['all_configurations'][n]['qualifies']]
    chosen = max(candidates, key=lambda n:(*ratios(independently_scored['validation',n,'selected']),-order.index(n))) if candidates else 'persistence'
    require(selection['method'] == chosen == report['recommendation']['method'], 'Global selection rule')
    require(selection['fallback_no_qualifier'] == (not candidates), 'Fallback status')
    comparison = rows(RUN / 'comparison.csv')
    require(len(comparison) == 20, 'Comparison row coverage')
    seen = set()
    for row in comparison:
        key = row['split'], row['method'], row['basis']
        require(key not in seen and key in independently_scored, 'Repeated/unknown comparison row'); seen.add(key)
        parsed = {k: (None if row[k] == '' else float(row[k])) for k in MEASURES}
        compare(independently_scored[key], parsed, 'Comparison export'); checks['comparison_rows'] += 1
    chosen_test = independently_scored['test',chosen,'selected']
    original_test = independently_scored['test','original','selected']
    baseline_test = independently_scored['test','persistence','selected']
    strict_original = all(a > b for a,b in zip(ratios(chosen_test),ratios(original_test),strict=True))
    noninferior_persistence = all(a >= b for a,b in zip(ratios(chosen_test),ratios(baseline_test),strict=True))
    strict_persistence = any(a > b for a,b in zip(ratios(chosen_test),ratios(baseline_test),strict=True))
    audit = {'status':'PASS','mismatches':[], 'checks':checks, 'result_sha256':sha(RUN/'report.json'),
        'protocol_sha256':report['protocol_sha256'], 'code_sha256':report['code_sha256'], 'checker_sha256':sha(Path(__file__)),
        'input_sha256':report['input_sha256'], 'selected_method':chosen,
        'reference_csv_parser_residual':reference_parse_residual,
        'numeric_check_tolerance_absolute':1e-9,
        'promotion_check': {'criterion_provenance':'Additional parent/user condition after protocol freeze; does not change selection.',
            'selected_full_test':chosen_test, 'original_full_test':original_test, 'persistence_full_test':baseline_test,
            'strictly_exceeds_original_f1_precision_recall':strict_original,
            'noninferior_to_persistence_all_three':noninferior_persistence,
            'strict_gain_over_persistence':strict_persistence,
            'passes_numerical_gate':strict_original and noninferior_persistence and strict_persistence,
            'release_recommendation':False, 'new_independent_evidence':False},
        'initial_failed_attempt':{'stage':'Input cadence validation; no model fitted', 'exit_status':1,
            'cause':'DatetimeIndex stored microseconds, while initial integer check assumed nanoseconds.',
            'fix':'Compare Timedelta values directly; no input, split, model or selection change.',
            'code_sha256':sha(HERE/'attempts/initial-run.py'),'log_sha256':sha(HERE/'attempts/initial-run.log')},
        'successful_run_log_sha256':sha(HERE/'run-retry1.log')}
    if args.output:
        with args.output.open('x') as stream: stream.write(json.dumps(audit,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':audit['status'],'checks':checks,'selected':chosen,'promotion':audit['promotion_check']['passes_numerical_gate']},sort_keys=True))


if __name__ == '__main__':
    main()
