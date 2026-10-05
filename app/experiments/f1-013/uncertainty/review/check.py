"""Independent paired calendar-resampling reconstruction, no production imports."""
import csv
from datetime import datetime, timedelta
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import time
import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
OUT = SOURCE / 'result'
checks = 0
started = time.perf_counter()
METHODS = ('conditional_robust', 'raw_nwp', 'original', 'persistence', 'f1_008_selected', 'f1_009_selected')
REFERENCES = ('weather_full', 'satellite_common')
METRICS = ('precision', 'recall', 'f1')


def check(condition, label):
    global checks
    checks += 1
    if not condition:
        raise AssertionError(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ratios(cells):
    result = np.full(cells.shape[:-1] + (3,), np.nan)
    for index in np.ndindex(cells.shape[:-1]):
        tp, fp, fn = map(int, cells[index])
        for metric, (numerator, denominator) in enumerate(((tp, tp + fp), (tp, tp + fn), (2 * tp, 2 * tp + fp + fn))):
            if denominator:
                result[index + (metric,)] = float(Fraction(numerator, denominator))
    return result


def percentile(values, probability):
    values = sorted(float(v) for v in values if np.isfinite(v))
    if not values:
        return None
    at = (len(values) - 1) * probability
    lo, fraction = int(at), at - int(at)
    return values[lo] if lo == len(values) - 1 else values[lo] + fraction * (values[lo + 1] - values[lo])


pins = json.loads((OUT / 'inputs.json').read_text())
for name, digest in pins.items():
    check(sha(SOURCE.parent / name) == digest, 'input hash ' + name)
for name, digest in json.loads((OUT / 'outputs.json').read_text()).items():
    check(sha(OUT / name) == digest, 'output hash ' + name)
report = json.loads((OUT / 'report.json').read_text())
items = {(r['period'], r['block_days'], r['reference'], r['control'], r['metric']): r for r in report['results']}
check(len(items) == len(report['results']) == 120, 'all 120 unique intervals')
rng = np.random.default_rng(20261004)
maximum_interval_error, undefined, raw_zero = 0.0, 0, 0
for stage, rows_expected, days_expected, common_expected in (('validation', 3566, 150, 3419), ('test', 3567, 149, 3517)):
    with (SOURCE.parent / 'result' / stage / 'predictions.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    timestamps = [datetime.fromisoformat(r['target_time']) for r in rows]
    check(len(rows) == rows_expected and len(set(timestamps)) == rows_expected, 'original row IDs')
    check(all(b - a == timedelta(hours=1) for a, b in zip(timestamps, timestamps[1:])), 'hourly target order')
    first, last = timestamps[0].date(), timestamps[-1].date()
    days = [str(first + timedelta(days=d)) for d in range((last - first).days + 1)]
    check(len(days) == days_expected, 'uncompressed full calendar')
    counts = np.zeros((len(days), 2, len(METHODS), 3), dtype=np.int64)
    common = 0
    for row, stamp in zip(rows, timestamps):
        d = (stamp.date() - first).days
        available = row['satellite_w_m2'] != ''
        check(int(row['satellite_available']) == int(available), 'exact missing mask')
        common += available
        for r, name in enumerate(('weather_w_m2', 'satellite_w_m2')):
            if r and not available:
                continue
            truth = float(row[name]) > 600
            for m, method in enumerate(METHODS):
                prediction = bool(int(row[method]))
                if truth and prediction:
                    counts[d, r, m, 0] += 1
                elif prediction:
                    counts[d, r, m, 1] += 1
                elif truth:
                    counts[d, r, m, 2] += 1
    check(common == common_expected, 'common reference membership count')
    observed = ratios(counts.sum(axis=0))
    for block in (1, 7):
        with np.load(OUT / f'{stage}-block-{block}.npz', allow_pickle=False) as data:
            stored_weights, stored_days, stored_counts = data['weights'], data['days'], data['counts']
        check(stored_days.tolist() == days and np.array_equal(stored_counts, counts), 'saved calendar and all daily confusion counts')
        starts = rng.integers(len(days), size=(5000, (len(days) + block - 1) // block))
        weights = np.zeros_like(stored_weights)
        for draw, sequence in enumerate(starts):
            sampled_days = [(int(begin) + offset) % len(days) for begin in sequence for offset in range(block)][:len(days)]
            weights[draw] = np.bincount(sampled_days, minlength=len(days))
        check(np.array_equal(weights, stored_weights) and np.all(weights.sum(axis=1) == len(days)), 'all paired circular block draws')
        totals = (weights @ counts.reshape(len(days), -1)).reshape(5000, 2, len(METHODS), 3)
        sampled = ratios(totals)
        for r, reference in enumerate(REFERENCES):
            for m, control in enumerate(METHODS[1:], 1):
                for metric, metric_name in enumerate(METRICS):
                    row = items[stage, block, reference, control, metric_name]
                    delta = sampled[:, r, 0, metric] - sampled[:, r, m, metric]
                    good = np.isfinite(delta)
                    check(row['valid_draws'] == int(good.sum()) and row['undefined_draws'] == int((~good).sum()), 'undefined draws counted')
                    undefined += row['undefined_draws']
                    point = observed[r, 0, metric] - observed[r, m, metric]
                    check(row['difference'] == point, 'pooled observed ratio difference')
                    interval = [percentile(delta, q) for q in (0.025, 0.975)]
                    error = max(abs(a - b) for a, b in zip(interval, row['interval95']))
                    maximum_interval_error = max(maximum_interval_error, error)
                    check(error <= 2e-16, 'independent sorted percentile interval')
                    if control == 'raw_nwp':
                        check(np.all(delta == 0) and point == 0 and row['interval95'] == [0, 0], 'exact zero versus raw')
                        raw_zero += 1
check(undefined == 0 and raw_zero == 24, 'retained undefined and zero summaries')
receipt = json.loads((OUT / 'execution-receipt.json').read_text())
check(receipt['exit_code'] == 0 and receipt['status'] == 'COMPLETE', 'successful actual uncertainty run')
print(json.dumps(dict(status='PASS', checks=checks, interval_rows=120, paired_draws=20000, undefined_draws=undefined,
    exact_zero_raw_intervals=raw_zero, maximum_percentile_difference=maximum_interval_error,
    elapsed_seconds=time.perf_counter()-started, source_sha256=sha(SOURCE / 'paired.py'), checker_sha256=sha(Path(__file__)),
    input_lock_sha256=sha(OUT / 'inputs.json'), result_manifest_sha256=sha(OUT / 'outputs.json'),
    scope='All daily counts, calendar IDs, saved draw weights, exact pooled ratios and intervals independently reconstructed without production helpers.'), indent=2))
