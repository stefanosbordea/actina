"""Resolve strict bootstrap comparisons with exact binary64 integer sums."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent.parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
start = time.perf_counter()
report = json.loads((HERE.parent / 'result.json').read_text())
identity = {EXP / p: h for p, h in report['inputs_sha256'].items()}
identity[HERE.parent / 'result.json'] = sha(HERE.parent / 'result.json')
assert all(sha(p) == h for p, h in identity.items())


def rows(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def numerators(values, weights, denominator):
    integers = np.array([n * (denominator // d) for n, d in
                         (float(v).as_integer_ratio() for v in values)], dtype=object)
    order = np.argsort(-values, kind='stable')
    ordered = weights[:, order]
    before = np.cumsum(ordered, axis=1) - ordered
    tenths = np.minimum(10 * ordered, np.maximum(weights.sum(axis=1)[:, None] - 10 * before, 0))
    return np.column_stack((weights @ integers, tenths @ integers[order]))


def floating(values, weights):
    count = weights.sum(axis=1)
    order = np.argsort(-values, kind='stable')
    ordered = weights[:, order]
    before = np.cumsum(ordered, axis=1) - ordered
    tenths = np.minimum(10 * ordered, np.maximum(count[:, None] - 10 * before, 0))
    return np.column_stack((weights @ values / count, tenths @ values[order] / count))


rng = np.random.default_rng(20261004)
records = []
for split in ('validation', 'test'):
    members = rows(EXP / f'result/{split}/evaluation-membership.csv')
    daily = rows(EXP / f'result/{split}/daily-outcomes.csv')
    mask = np.array([r['primary'] == 'True' for r in members])
    names = [r['day'] for r in members if r['primary'] == 'True']
    values = {}
    for ref in ('weather', 'satellite'):
        for method in ('raw_point', 'coherent', 'shuffled'):
            selected = [r for r in daily if r['primary'] == 'True' and r['reference'] == ref and r['method'] == method]
            assert [r['day'] for r in selected] == names
            values[ref, method] = np.array([[float(r['cost_eur']), float(r['grid_kwh'])] for r in selected])
    for block in (1, 7):
        origins = rng.integers(len(members), size=(5000, (len(members) + block - 1) // block))
        indices = ((origins[..., None] + np.arange(block)) % len(members)).reshape(5000, -1)[:, :len(members)]
        weights = np.zeros((5000, len(members)), dtype=np.int64)
        np.add.at(weights, (np.arange(5000)[:, None], indices), 1)
        weights = weights[:, mask]
        assert (weights.sum(axis=1) > 0).all()
        for method in ('coherent', 'shuffled'):
            exact, binary = [], []
            labels = []
            for ref in ('weather', 'satellite'):
                for col, metric in enumerate(('cost_eur', 'grid_kwh')):
                    a, b = values[ref, method][:, col], values[ref, 'raw_point'][:, col]
                    denominator = max(float(v).as_integer_ratio()[1] for v in np.r_[a, b])
                    exact.append(numerators(a, weights, denominator) - numerators(b, weights, denominator))
                    binary.append(floating(a, weights) - floating(b, weights))
                    labels.extend((f'{ref}/{metric}/mean', f'{ref}/{metric}/cvar90'))
            exact, binary = np.column_stack(exact), np.column_stack(binary)
            ewin, fwin = np.all(exact < 0, axis=1), np.all(binary < 0, axis=1)
            different = np.flatnonzero(ewin != fwin)
            changed_axes = (exact < 0) != (binary < 0)
            saved_group = next(r for r in report['comparisons'] if r['split'] == split and r['block_days'] == block)
            saved = next(r for r in saved_group['comparisons'] if r['method'] == method)['fraction_all_eight_axes_strictly_improved']
            records.append(dict(split=split, block_days=block, method=method,
                exact_fraction=float(ewin.mean()), grouped_float_fraction=float(fwin.mean()), saved_fraction=saved,
                differing_draws=different.tolist(), changed_axis_comparisons=int(changed_axes.sum()),
                largest_absolute_float_difference_at_sign_disagreement=float(np.max(np.abs(binary[changed_axes]))) if changed_axes.any() else 0.,
                affected_examples=[dict(draw=int(i), exact_all_improved=bool(ewin[i]),
                    axes=[dict(axis=labels[j], exact_numerator=str(exact[i, j]), floating_difference=float(binary[i, j]))
                          for j in np.flatnonzero(changed_axes[i])]) for i in different[:10]]))
assert all(sha(p) == h for p, h in identity.items())
result = dict(status='EXACT_STRICT_COUNTS_RECONSTRUCTED', comparisons=records,
    scope='Exact signs for binary64 input values using integer sums and fractional tail tenths. Source reports preserved. Tiny strict comparisons are not operational gains.',
    source_report_sha256=sha(HERE.parent / 'result.json'), code_sha256=sha(Path(__file__)),
    completed_at_utc=datetime.now(timezone.utc).isoformat(), wall_seconds=time.perf_counter() - start)
(HERE / 'frequency-result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
print(json.dumps(result, allow_nan=False))
