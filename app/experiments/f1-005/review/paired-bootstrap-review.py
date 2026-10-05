"""Check saved paired-day inputs and point estimates; do not rerun resampling."""
import csv
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
NAMES = ('mae', 'rmse', 'precision', 'recall', 'f1')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def metrics(data, name, reference):
    truth = [float(row[reference]) > 600 for row in data]
    decision = [int(row[name + '_positive']) for row in data]
    errors = [float(row[name + '_point_w_m2']) - float(row[reference]) for row in data]
    tp = sum(t and p for t, p in zip(truth, decision))
    fp = sum(not t and p for t, p in zip(truth, decision))
    fn = sum(t and not p for t, p in zip(truth, decision))
    assert tp + fp > 0 and tp + fn > 0
    return {'mae': math.fsum(map(abs, errors)) / len(data),
            'rmse': math.sqrt(math.fsum(e * e for e in errors) / len(data)),
            'precision': tp / (tp + fp), 'recall': tp / (tp + fn),
            'f1': 2 * tp / (2 * tp + fp + fn)}


def main():
    saved = json.loads((HERE / 'paired-bootstrap.json').read_text())
    assert saved['status'] == 'COMPLETE'
    assert saved['seed'] == 20261004 and saved['resamples'] == 20000
    assert saved['direction'] == 'guarded minus original'
    assert saved['code_sha256'] == sha(HERE / 'paired_bootstrap.py')
    source = {name: rows(BASE / 'result' / name) for name in saved['inputs']}
    assert set(source) == {'validation-rows.csv', 'test-rows.csv'}
    for name, expected in saved['inputs'].items():
        assert sha(BASE / 'result' / name) == expected
    prior = {(r['split'], r['basis'], r['method']): r
             for r in rows(BASE / 'result' / 'metrics.csv')}
    expected_groups = {(s, r) for s in ('validation', 'test') for r in
                       ('weather_reference_w_m2', 'satellite_reference_w_m2')}
    assert len(saved['comparisons']) == len(expected_groups)
    assert {(r['split'], r['reference']) for r in saved['comparisons']} == expected_groups
    checked = []
    maximum_error = 0.0
    for group in saved['comparisons']:
        split, reference = group['split'], group['reference']
        all_rows = source[split + '-rows.csv']
        assert len({r['target_time'] for r in all_rows}) == len(all_rows)
        target_times = [datetime.fromisoformat(r['target_time']) for r in all_rows]
        assert all(b - a == timedelta(hours=1) for a, b in zip(target_times, target_times[1:]))
        data = [r for r in all_rows if r[reference] != '']
        days = Counter(datetime.fromisoformat(r['target_time']).date().isoformat() for r in data)
        assert group['hours'] == len(data) and group['unscored_hours'] == len(all_rows) - len(data)
        assert group['day_blocks'] == len(days)
        assert set(group['metrics']) == set(NAMES)
        basis = 'weather_full' if reference == 'weather_reference_w_m2' else 'satellite_common'
        direct = {name: metrics(data, name, reference) for name in ('original', 'guarded')}
        for metric, interval in group['metrics'].items():
            difference = direct['guarded'][metric] - direct['original'][metric]
            error = abs(difference - interval['difference'])
            maximum_error = max(maximum_error, error)
            assert error < 1e-10
            for method in direct:
                assert abs(direct[method][metric] - float(prior[split, basis, method][metric])) < 1e-10
            lo, hi = interval['percentile_95']
            assert math.isfinite(lo) and math.isfinite(hi) and lo <= hi
            assert interval['defined_resamples'] + interval['undefined_resamples'] == 20000
            assert interval['undefined_resamples'] == 0
        checked.append({'split': split, 'reference': reference, 'hours': len(data),
                        'day_blocks': len(days), 'partial_day_blocks': sum(n < 24 for n in days.values()),
                        'point_differences': {m: direct['guarded'][m] - direct['original'][m] for m in NAMES}})
    return {'status': 'PASS', 'scope': 'Independent saved-input, membership and point-estimate recomputation plus static statistical-method review. The 20,000 random draws and percentile endpoints were not rerun.',
            'checks': {'groups': 4, 'point_differences': 20, 'individual_metric_matches_to_005': 40,
                       'maximum_point_difference_abs_error': maximum_error},
            'method_review': ['A common multinomial day-count vector multiplies both forecasts, preserving paired target-day clusters.',
                              'Absolute error, squared error and confusion counts are pooled before computing metrics; variable-sized partial days are not incorrectly averaged as daily scores.',
                              'Day blocks use the original fixed UTC+03 target calendar, not UTC dates; satellite groups condition on available-reference hours and omit entirely missing days.',
                              'Strict >600 event labels, TP/(TP+FP), TP/(TP+FN), 2TP/(2TP+FP+FN), and guarded-minus-original direction are correct.',
                              'np.quantile uses the default linear percentile rule. Nonfinite differences are excluded per metric and their counts reported; all saved groups report zero undefined draws.'],
            'comparisons': checked, 'findings': [],
            'interpretation': ['Weather test F1 gain is 1.866 percentage points, interval [0.924, 2.957]; satellite common-hour gain is 2.138 points, interval [1.148, 3.266].',
                               'Both test precision intervals cross zero. Satellite validation recall also crosses zero; no all-metric confidence claim is supported.',
                               'These are marginal post-inspection intervals without multiplicity or inter-day dependence protection. They do not establish independent, causal, live or general superiority.',
                               'Original is the supplied original forecast; the guarded method uses additional archived weather inputs. This comparison does not isolate model architecture or preserve scheduler dispatch.'],
            'sha256': {name: sha(HERE / name) for name in ('paired_bootstrap.py', 'paired-bootstrap.json', 'paired-bootstrap-review.py')},
            'source_sha256': saved['inputs']}


if __name__ == '__main__':
    result = main()
    with (HERE / 'paired-bootstrap-review.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'checks': result['checks']}))
