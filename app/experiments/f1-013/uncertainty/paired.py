"""Paired calendar-block precision, recall and F1 sensitivity."""
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
METHODS = ('conditional_robust', 'raw_nwp', 'original', 'persistence', 'f1_008_selected', 'f1_009_selected')
REFERENCES = ('weather_full', 'satellite_common')
METRICS = ('precision', 'recall', 'f1')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def scores(counts):
    tp, fp, fn = np.moveaxis(counts.astype(float), -1, 0)
    numerator = np.stack((tp, tp, 2 * tp), axis=-1)
    denominator = np.stack((tp + fp, tp + fn, 2 * tp + fp + fn), axis=-1)
    return np.divide(numerator, denominator, out=np.full_like(numerator, np.nan), where=denominator != 0)


def weights(rng, days, block, draws=5000):
    starts = rng.integers(days, size=(draws, (days + block - 1) // block))
    indices = ((starts[..., None] + np.arange(block)) % days).reshape(draws, -1)[:, :days]
    result = np.zeros((draws, days), dtype=np.int64)
    np.add.at(result, (np.arange(draws)[:, None], indices), 1)
    return result


def daily(path, stage):
    with path.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != {'validation': 3566, 'test': 3567}[stage]:
        raise ValueError('Original hour count changed')
    times = [datetime.fromisoformat(row['target_time']) for row in rows]
    if len(set(times)) != len(times) or any(b - a != timedelta(hours=1) for a, b in zip(times, times[1:])):
        raise ValueError('Original target ordering changed')
    first, last = times[0].date(), times[-1].date()
    days = (last - first).days + 1
    counts = np.zeros((days, 2, len(METHODS), 3), dtype=np.int64)
    common = 0
    for stamp, row in zip(times, rows):
        d = (stamp.date() - first).days
        if row['satellite_available'] not in ('0', '1'):
            raise ValueError('Invalid reference mask')
        available = row['satellite_available'] == '1'
        if available != bool(row['satellite_w_m2']):
            raise ValueError('Satellite missingness changed')
        common += available
        for r, key in enumerate(('weather_w_m2', 'satellite_w_m2')):
            if r and not available:
                continue
            value = float(row[key])
            if not np.isfinite(value):
                raise ValueError('Invalid reference')
            truth = value > 600
            for m, name in enumerate(METHODS):
                if row[name] not in ('0', '1'):
                    raise ValueError('Invalid decision')
                predicted = row[name] == '1'
                counts[d, r, m] += (truth and predicted, not truth and predicted, truth and not predicted)
    if common != {'validation': 3419, 'test': 3517}[stage]:
        raise ValueError('Common mask changed')
    return counts, [str(first + timedelta(days=i)) for i in range(days)]


def execute():
    out = HERE / 'result'
    out.mkdir(exist_ok=False)
    start, cpu = time.perf_counter(), time.process_time()
    inputs = [HERE / 'paired.py', HERE / 'PROTOCOL.md', HERE.parent / 'result/planning-freeze.json', HERE.parent / 'result/report.json']
    inputs += [HERE.parent / 'result' / stage / 'predictions.csv' for stage in ('validation', 'test')]
    pins = {str(p.relative_to(HERE.parent)): sha(p) for p in inputs}
    save(out / 'inputs.json', pins)
    receipt = dict(started_at_utc=datetime.now(timezone.utc).isoformat(), command=sys.argv, status='RUNNING')
    save(out / 'execution-start.json', receipt)
    try:
        rng, results = np.random.default_rng(20261004), []
        report = json.loads((HERE.parent / 'result/report.json').read_text())
        for stage in ('validation', 'test'):
            counts, days = daily(HERE.parent / 'result' / stage / 'predictions.csv', stage)
            totals = counts.sum(axis=0)
            for r, reference in enumerate(REFERENCES):
                for m, method in enumerate(METHODS):
                    previous = report['splits'][stage]['metrics'][method][reference]
                    if totals[r, m].tolist() != [previous[k] for k in ('tp', 'fp', 'fn')]:
                        raise AssertionError('Independent confusion-count replay failed')
            observed = scores(totals)
            for block in (1, 7):
                draws = weights(rng, len(days), block)
                np.savez_compressed(out / f'{stage}-block-{block}.npz', weights=draws, days=np.asarray(days), counts=counts)
                sampled = scores(np.einsum('bd,drmk->brmk', draws, counts))
                for r, reference in enumerate(REFERENCES):
                    for m, control in enumerate(METHODS[1:], 1):
                        for metric, name in enumerate(METRICS):
                            delta = sampled[:, r, 0, metric] - sampled[:, r, m, metric]
                            valid = delta[np.isfinite(delta)]
                            point = observed[r, 0, metric] - observed[r, m, metric]
                            results.append(dict(period=stage, reference=reference, block_days=block,
                                control=control, metric=name, difference=float(point) if np.isfinite(point) else None,
                                interval95=np.quantile(valid, [.025, .975], method='linear').tolist() if len(valid) else None,
                                valid_draws=len(valid), undefined_draws=len(delta)-len(valid)))
        if any(sha(HERE.parent / name) != digest for name, digest in pins.items()):
            raise AssertionError('Inputs changed during uncertainty analysis')
        save(out / 'report.json', dict(primary='conditional_robust', draws_per_period_and_block=5000, seed=20261004,
            scope='Exploratory marginal resampling intervals. No fresh holdout or multiple-experiment adjustment. Not an additional admission gate.', results=results))
        receipt.update(status='COMPLETE', exit_code=0)
    except BaseException as error:
        receipt.update(status='FAILED', exit_code=1, error=str(error), error_type=type(error).__name__)
        raise
    finally:
        receipt.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.perf_counter()-start,
            cpu_seconds=time.process_time()-cpu, peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024))
        save(out / 'execution-receipt.json', receipt)
        save(out / 'outputs.json', {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != 'outputs.json'})
    print('COMPLETE', len(results), 'paired intervals')


if __name__ == '__main__':
    execute()
