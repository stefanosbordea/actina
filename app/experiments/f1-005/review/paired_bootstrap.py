"""Exploratory paired-day intervals against the original forecast; no selection."""
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
NAMES = ('mae', 'rmse', 'precision', 'recall', 'f1')


def metrics(totals):
    n, absolute, squared, tp, fp, fn = totals.T
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.stack((absolute / n, np.sqrt(squared / n), tp / (tp + fp),
                         tp / (tp + fn), 2 * tp / (2 * tp + fp + fn)), axis=-1)


def run():
    output = HERE / 'paired-bootstrap.json'
    if output.exists():
        raise FileExistsError('Preserve the existing bootstrap result')
    result = {'scope': 'Post-inspection exploratory paired-day percentile intervals; '
              'original forecast versus guarded correction only. Marginal 95% intervals, '
              'no multiplicity correction. Whole target-calendar days sampled with replacement; '
              'does not preserve multi-day weather dependence or establish live superiority.',
              'seed': 20261004, 'resamples': 20000, 'direction': 'guarded minus original',
              'command': [sys.executable, *sys.argv],
              'numpy_version': np.__version__,
              'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'inputs': {}, 'comparisons': []}
    for split in ('validation', 'test'):
        path = HERE.parent / 'result' / f'{split}-rows.csv'
        result['inputs'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        with path.open() as stream:
            rows = list(csv.DictReader(stream))
        for reference in ('weather_reference_w_m2', 'satellite_reference_w_m2'):
            retained = [r for r in rows if r[reference] != '']
            days = sorted({r['target_time'][:10] for r in retained})
            index = {day: i for i, day in enumerate(days)}
            blocks = np.zeros((2, len(days), 6), dtype=np.float64)
            for r in retained:
                actual = float(r[reference])
                for m, name in enumerate(('original', 'guarded')):
                    positive = int(r[name + '_positive'])
                    error = float(r[name + '_point_w_m2']) - actual
                    event = actual > 600
                    blocks[m, index[r['target_time'][:10]]] += (
                        1, abs(error), error * error, positive and event,
                        positive and not event, not positive and event)
            rng = np.random.default_rng(result['seed'])
            samples = rng.multinomial(len(days), np.full(len(days), 1 / len(days)),
                                      size=result['resamples'])
            differences = metrics(samples @ blocks[1]) - metrics(samples @ blocks[0])
            observed = metrics(blocks[1].sum(axis=0, keepdims=True))[0] - metrics(
                blocks[0].sum(axis=0, keepdims=True))[0]
            record = {'split': split, 'reference': reference, 'hours': len(retained),
                      'unscored_hours': len(rows) - len(retained), 'day_blocks': len(days),
                      'metrics': {}}
            for j, name in enumerate(NAMES):
                finite = differences[np.isfinite(differences[:, j]), j]
                record['metrics'][name] = {
                    'difference': float(observed[j]),
                    'percentile_95': np.quantile(finite, [.025, .975]).tolist(),
                    'defined_resamples': len(finite),
                    'undefined_resamples': result['resamples'] - len(finite)}
            result['comparisons'].append(record)
    for name, expected in result['inputs'].items():
        if hashlib.sha256((HERE.parent / 'result' / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Input changed during bootstrap')
    result['status'] = 'COMPLETE'
    with output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(result['comparisons'], indent=2))


if __name__ == '__main__':
    run()
