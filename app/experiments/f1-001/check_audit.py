"""Independently verify the retained audit with stdlib; never train or write files."""
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = HERE / 'result-retry1'
HOUR = timedelta(hours=1)
DAY = timedelta(hours=24)
METRICS = ('hours', 'tp', 'fp', 'fn', 'tn', 'precision', 'recall', 'f1')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(truth, positive):
    counts = {(True, True): 0, (False, True): 0, (True, False): 0, (False, False): 0}
    for pair in zip(truth, positive, strict=True):
        counts[pair] += 1
    tp, fp, fn, tn = (counts[key] for key in [(True, True), (False, True), (True, False), (False, False)])
    return dict(hours=len(truth), tp=tp, fp=fp, fn=fn, tn=tn,
        precision=tp / (tp + fp) if tp + fp else None,
        recall=tp / (tp + fn) if tp + fn else None,
        f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None)


def compare(actual, expected, context):
    for key in METRICS:
        a, b = actual[key], expected[key]
        same = a == b if a is None or b is None or key not in ('precision', 'recall', 'f1') else abs(a - b) <= 1e-14
        require(same, f'{context}: {key}: {a} != {b}')


def ranked(record):
    return tuple(record[key] if record[key] is not None else -1 for key in ('f1', 'precision', 'recall'))


def main():
    audit = json.loads((HERE / 'independent-audit.json').read_text())
    report = json.loads((RUN / 'report.json').read_text())
    require(audit['status'] == 'PASS' and audit['mismatches'] == [], 'Audit does not report a clean pass')
    require(report['status'] == 'COMPLETE', 'Run incomplete')
    identities = {ROOT / path: sha for path, sha in audit['input_sha256'].items()}
    identities.update({HERE / path: sha for path, sha in audit['prediction_sha256'].items()})
    identities.update({RUN / 'report.json': audit['reported_result_sha256'],
        HERE / 'PROTOCOL.md': audit['protocol_sha256'], HERE / 'run.py': audit['evaluator_sha256'],
        HERE / audit['initial_failed_attempt']['log']: audit['initial_failed_attempt']['log_sha256']})
    for path, sha in identities.items():
        require(digest(path) == sha, f'Identity changed: {path.relative_to(ROOT)}')
    for key in ('input_sha256', 'protocol_sha256', 'evaluator_sha256'):
        require(report[key] == audit[key], f'Run/audit identity mismatch: {key}')
    source = {path: rows(ROOT / path) for path in audit['input_sha256']}
    for path, records in source.items():
        times = [datetime.fromisoformat(row['time']) for row in records]
        coverage = dict(rows=len(records), hourly_increasing=all(b - a == HOUR for a, b in zip(times, times[1:])),
                        unique=len(times) == len(set(times)))
        require(coverage == audit['input_coverage'][path], f'Coverage mismatch: {path}')
        require(coverage['hourly_increasing'] and coverage['unique'], f'Invalid hourly source: {path}')
    features = {datetime.fromisoformat(r['time']): r for r in source['data/features.csv']}
    weather = {datetime.fromisoformat(r['time']): r for r in source['data/paphos_weather_data.csv']}
    for origin, row in features.items():
        require(Decimal(row['target']) == Decimal(weather[origin + DAY]['shortwave_radiation']), f'Target mismatch: {origin}')
    checks = dict(prediction_files=0, prediction_rows=0, selected_scores=0, default_scores=0,
                  monthly_scores=0, threshold_scores=0, original_reference_scores=0, input_hashes=len(source))
    scores = {}
    for stage, filename in [('validation', 'cv_predictions.csv'), ('test', 'test_predictions.csv')]:
        original = source['eval/' + filename]
        origins = [datetime.fromisoformat(row['time']) for row in original]
        targets = [time + DAY for time in origins]
        truth = [Decimal(row['actual']) > 600 for row in original]
        train = [time for time in features if time + DAY < origins[0]]
        purged = sum(time < origins[0] for time in features) - len(train)
        split = dict(train_hours=len(train), evaluation_hours=len(original), purged_hours=purged,
                     latest_training_target=str(train[-1] + DAY))
        require(split == audit['split_verification'][stage], f'Purge mismatch: {stage}')
        expected = report['splits'][stage]
        for key, value in {**split, 'evaluation_origins_start': str(origins[0]), 'evaluation_origins_end': str(origins[-1]),
                           'target_start': str(targets[0]), 'target_end': str(targets[-1])}.items():
            require(value == expected[key], f'Split mismatch: {stage}/{key}')
        groups = defaultdict(list)
        for i, (origin, target, row) in enumerate(zip(origins, targets, original, strict=True)):
            require(Decimal(row['actual']) == Decimal(features[origin]['target']), f'Original label: {stage}/{i}')
            require(Decimal(row['baseline']) == Decimal(features[origin]['shortwave_radiation']), f'Original baseline: {stage}/{i}')
            groups[target.strftime('%Y-%m')].append(i)
        reference = score(truth, [Decimal(row['predicted']) > 600 for row in original])
        compare(reference, expected['retained_original_model'], f'Original report/{stage}')
        compare(reference, audit['original_model_reference'][stage]['overall'], f'Original audit/{stage}')
        checks['original_reference_scores'] += 1
        reference_months = audit['original_model_reference'][stage]['monthly']
        require([r['month'] for r in reference_months] == sorted(groups), f'Original months missing: {stage}')
        for month in reference_months:
            indices = groups[month['month']]
            compare(score([truth[i] for i in indices], [Decimal(original[i]['predicted']) > 600 for i in indices]), month, f'Original {stage}/{month["month"]}')
        scores[stage] = {}
        for method, summary in report['methods'].items():
            records = rows(RUN / 'predictions' / f'{stage}-{method}.csv')
            require(len(records) == len(original), f'Length: {stage}/{method}')
            values = [Decimal(row['score']) for row in records]
            cutoff = Decimal(str(summary[stage]['cutoff']))
            require(cutoff == Decimal(str(summary['validation']['cutoff'])), f'Test cutoff changed: {method}')
            require(all(v.is_finite() for v in values), f'Nonfinite score: {stage}/{method}')
            positive = [value > cutoff for value in values]
            for i, row in enumerate(records):
                require(datetime.fromisoformat(row['feature_time']) == origins[i] and datetime.fromisoformat(row['target_time']) == targets[i], f'Membership: {stage}/{method}/{i}')
                require(Decimal(row['actual_w_m2']) == Decimal(original[i]['actual']) and int(row['actual_positive']) == truth[i], f'Label: {stage}/{method}/{i}')
                require(Decimal(row['cutoff']) == cutoff and int(row['predicted_positive']) == positive[i], f'Decision: {stage}/{method}/{i}')
                if method in ('persistence', 'calibrated_persistence'):
                    require(values[i] == Decimal(original[i]['baseline']), f'Persistence changed: {stage}/{i}')
            result = score(truth, positive)
            compare(result, summary[stage]['selected'], f'Selected {stage}/{method}')
            compare(result, audit['recomputed_results'][stage][method], f'Audit {stage}/{method}')
            require(float(cutoff) == audit['recomputed_results'][stage][method]['cutoff'], f'Audit cutoff: {stage}/{method}')
            scores[stage][method] = result
            default = Decimal('.5') if method.endswith('classifier') else Decimal(600)
            compare(score(truth, [value > default for value in values]), summary[stage]['default'], f'Default {stage}/{method}')
            monthly = summary[stage]['monthly']
            require([m['month'] for m in monthly] == sorted(groups), f'Months missing: {stage}/{method}')
            for month in monthly:
                indices = groups[month['month']]
                compare(score([truth[i] for i in indices], [positive[i] for i in indices]), month, f'Month {stage}/{method}/{month["month"]}')
            thresholds = summary[stage].get('validation_thresholds', [])
            if stage == 'validation' and (method == 'calibrated_persistence' or method.endswith('classifier')):
                grid = list(range(450, 751, 10)) if method == 'calibrated_persistence' else [.05 + .90 * i / 90 for i in range(91)]
                require(len(thresholds) == len(grid) and all(abs(r['cutoff'] - g) < 1e-14 for r, g in zip(thresholds, grid)), f'Threshold grid: {method}')
                for threshold in thresholds:
                    compare(score(truth, [value > Decimal(str(threshold['cutoff'])) for value in values]), threshold, f'Threshold {method}/{threshold["cutoff"]}')
                centre = 600 if method == 'calibrated_persistence' else .5
                best = max(thresholds, key=lambda r: (*ranked(r), -abs(r['cutoff'] - centre)))
                require(Decimal(str(best['cutoff'])) == cutoff, f'Cutoff selection: {method}')
            else:
                require(not thresholds, f'Unexpected threshold sweep: {stage}/{method}')
            for key, increment in [('prediction_files', 1), ('prediction_rows', len(records)), ('selected_scores', 1),
                ('default_scores', 1), ('monthly_scores', len(monthly)), ('threshold_scores', len(thresholds))]:
                checks[key] += increment
    winner = max(scores['validation'], key=lambda method: ranked(scores['validation'][method]))
    require(winner == report['selected_on_validation'] == audit['selected_on_validation'], 'Winner mismatch')
    baseline = scores['test']['persistence']
    wins = [method for method, result in scores['test'].items() if all(result[k] > baseline[k] for k in ('f1', 'precision', 'recall'))]
    require(wins == audit['methods_strictly_improving_all_three_test_metrics_over_persistence'], 'All-metrics conclusion mismatch')
    require(checks == audit['checks'], 'Audit check counts differ')
    print(json.dumps({'status': 'PASS', 'mismatches': [], 'checks': checks, 'selected_on_validation': winner}, indent=2))


if __name__ == '__main__':
    main()
