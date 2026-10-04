"""Paired day-block sensitivity of frozen decisions, without fitting."""
import csv
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
NAMES = ('precision', 'recall', 'f1')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def scores(counts):
    tp, fp, fn = np.moveaxis(counts, -1, 0)
    denominator = np.stack((tp + fp, tp + fn, 2 * tp + fp + fn), axis=-1)
    numerator = np.stack((tp, tp, 2 * tp), axis=-1)
    return np.divide(numerator, denominator, out=np.full_like(numerator, np.nan, dtype=float), where=denominator > 0)


def main():
    paths = [EXP / 'result/predictions/test-joint.csv',
             EXP.parent / 'f1-008/result/predictions/test-consensus_two_source.csv',
             HERE / 'uncertainty-protocol.md', Path(__file__)]
    identities = {str(p.relative_to(EXP.parent)): sha(p) for p in paths}
    new, old = map(read, paths[:2])
    assert len(new) == len(old) == 3567
    dates = [datetime.fromisoformat(r['target_time']) for r in new]
    assert all(b-a == timedelta(hours=1) for a, b in zip(dates, dates[1:]))
    days = list(dict.fromkeys(t.date() for t in dates))
    assert all(b-a == timedelta(days=1) for a, b in zip(days, days[1:]))
    index = {day: i for i, day in enumerate(days)}
    counts = np.zeros((len(days), 2, 3, 3), dtype=np.int64)
    hours = np.zeros((len(days), 2), dtype=np.int64)
    for a, b, target in zip(new, old, dates):
        for key in ('feature_time', 'target_time', 'satellite_w_m2', 'nwp_positive'):
            assert a[key] == b[key], (key, a['target_time'])
        assert float(a['weather_w_m2']) == float(b['weather_actual_w_m2'])
        decisions = [int(a['predicted_positive']), int(a['nwp_positive']), int(b['predicted_positive'])]
        assert set(decisions) <= {0, 1}
        d = index[target.date()]
        for reference, field in enumerate(('weather_w_m2', 'satellite_w_m2')):
            if not a[field]:
                assert reference == 1
                continue
            value = float(a[field])
            assert np.isfinite(value) and value >= 0
            truth = value > 600
            hours[d, reference] += 1
            for method, decision in enumerate(decisions):
                counts[d, reference, method] += (int(truth and decision), int(not truth and decision), int(truth and not decision))
    assert hours.sum(axis=0).tolist() == [3567, 3517]
    assert counts.sum(axis=0)[:, :2].tolist() == [[[994, 15, 16], [993, 15, 17]], [[951, 42, 24], [950, 42, 25]]]
    point = scores(counts.sum(axis=0))
    rng = np.random.default_rng(20261004)
    comparisons = []
    for length in (1, 7):
        differences = []
        for start in range(0, 20000, 250):
            size = min(250, 20000-start)
            origins = rng.integers(len(days), size=(size, (len(days)+length-1)//length))
            sampled = ((origins[..., None] + np.arange(length)) % len(days)).reshape(size, -1)[:, :len(days)]
            weights = np.zeros((size, len(days)), dtype=np.int64)
            np.add.at(weights, (np.arange(size)[:, None], sampled), 1)
            assert np.all(weights.sum(axis=1) == len(days))
            pooled = np.einsum('bd,drmk->brmk', weights, counts)
            value = scores(pooled)
            differences.append(value[:, :, :1, :] - value[:, :, 1:, :])
        differences = np.concatenate(differences)
        for control, name in enumerate(('raw_nwp', 'frozen_008')):
            comparison = {'block_days': length, 'control': name, 'references': {}}
            difference = differences[:, :, control, :]
            comparison['fraction_all_six_strictly_positive_draws'] = float(np.mean(np.all(difference > 0, axis=(1, 2))))
            for reference, label in enumerate(('weather_full', 'satellite_common')):
                comparison['references'][label] = {}
                for metric, label_metric in enumerate(NAMES):
                    values = difference[:, reference, metric]
                    finite = np.isfinite(values)
                    comparison['references'][label][label_metric] = {
                        'difference': float(point[reference, 0, metric]-point[reference, control+1, metric]),
                        'percentile_95': np.quantile(values[finite], [.025, .975], method='linear').tolist(),
                        'defined_resamples': int(finite.sum()), 'undefined_resamples': int((~finite).sum())}
            comparisons.append(comparison)
    assert identities == {str(p.relative_to(EXP.parent)): sha(p) for p in paths}
    return {'status': 'COMPLETE', 'seed': 20261004, 'resamples_per_block_length': 20000,
            'direction': 'frozen_009_joint minus control', 'target_clock': 'fixed UTC+03',
            'days': len(days), 'hours': hours.sum(axis=0).tolist(),
            'day_counts': [{'day': str(day), 'hours_weather_satellite': h.tolist(),
                            'counts_reference_method_tp_fp_fn': c.tolist()} for day, h, c in zip(days, hours, counts)],
            'references_order': ['weather_full', 'satellite_common'],
            'methods_order': ['frozen_009_joint', 'raw_nwp', 'frozen_008'],
            'inputs_sha256': identities, 'comparisons': comparisons,
            'interpretation': 'Exploratory paired sensitivity only. No adjustment for repeated test inspection, model selection, multiplicity or longer seasonal dependence. Resampling fractions are not posterior probabilities.'}


if __name__ == '__main__':
    result = main()
    with (HERE / 'uncertainty-result.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'day_counts'}, indent=2))
