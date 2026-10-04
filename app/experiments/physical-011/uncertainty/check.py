"""Exploratory calendar-block sensitivity of fixed physical schedules."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def statistics(values, weights):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if values.ndim != 1 or weights.ndim != 2 or weights.shape[1] != len(values):
        raise ValueError('Invalid paired dimensions')
    if not np.isfinite(values).all() or not np.isfinite(weights).all() or np.any(weights < 0):
        raise ValueError('Nonfinite values or negative weights')
    count = weights.sum(axis=1)
    if np.any(count <= 0):
        raise ValueError('Empty weighted distribution')
    order = np.argsort(-values, kind='stable')
    ordered = weights[:, order]
    before = np.cumsum(ordered, axis=1) - ordered
    selected_tenths = np.minimum(10 * ordered, np.maximum(count[:, None] - 10 * before, 0.))
    return np.stack((weights @ values / count, (selected_tenths @ values[order]) / count), axis=-1)


def fixtures():
    for values in (np.full(64, -3.), np.arange(64.), np.array([-1., 0., 0., 5.])):
        for weights in (np.ones(len(values), dtype=int), np.arange(len(values)) % 3):
            expanded = np.repeat(values, weights)
            ordered = np.sort(expanded)[::-1]
            whole, remainder = divmod(len(ordered), 10)
            tail = (10 * sum(ordered[:whole]) + remainder * ordered[whole]) / len(ordered)
            actual = statistics(values, weights[None])[0]
            assert np.allclose(actual, [expanded.mean(), tail], rtol=0, atol=1e-12)
    assert np.array_equal(statistics([1., 999., 3.], [[1, 0, 1]]), [[2., 3.]])
    return {'status': 'PASS', 'checks': 'Expanded integer weights, fractional tails, negative losses, ties and omitted days'}


def main():
    checked = fixtures()
    paths = [HERE / 'PROTOCOL.md', Path(__file__).resolve()]
    for split in ('validation', 'test'):
        paths += [EXP / f'result/{split}/{name}' for name in ('evaluation-membership.csv', 'daily-outcomes.csv')]
    identities = {str(p.relative_to(EXP)): sha(p) for p in paths}
    rng = np.random.default_rng(20261004)
    results = []
    for split in ('validation', 'test'):
        membership = pd.read_csv(EXP / f'result/{split}/evaluation-membership.csv')
        daily = pd.read_csv(EXP / f'result/{split}/daily-outcomes.csv', float_precision='round_trip')
        dates = pd.DatetimeIndex(membership.day)
        assert dates.is_unique and np.all(dates[1:] - dates[:-1] == pd.Timedelta(days=1))
        mask = membership.primary.to_numpy()
        names = membership.day[mask].tolist()
        points = {}
        for reference in ('weather', 'satellite'):
            for method in ('raw_point', 'coherent', 'shuffled'):
                rows = daily.loc[daily.primary & (daily.reference == reference) & (daily.method == method)]
                assert rows.day.tolist() == names
                points[reference, method] = rows[['cost_eur', 'grid_kwh']].to_numpy()
        for block in (1, 7):
            origins = rng.integers(len(dates), size=(5000, (len(dates) + block - 1) // block))
            indices = ((origins[..., None] + np.arange(block)) % len(dates)).reshape(5000, -1)[:, :len(dates)]
            weights = np.zeros((5000, len(dates)), dtype=np.int64)
            np.add.at(weights, (np.arange(5000)[:, None], indices), 1)
            assert np.all(weights.sum(axis=1) == len(dates))
            selected = weights[:, mask]
            counts = selected.sum(axis=1)
            empty = counts == 0
            selected = selected[~empty]
            record = dict(split=split, block_days=block, draws=5000, empty_draws=int(empty.sum()),
                          calendar_days=len(dates), primary_days=len(names),
                          minimum_primary_days_in_draw=int(counts.min()), maximum_primary_days_in_draw=int(counts.max()),
                          comparisons=[])
            all_weights = np.vstack((np.ones((1, len(names))), selected))
            for method in ('coherent', 'shuffled'):
                axes, risk, draws = [], [], []
                for reference in ('weather', 'satellite'):
                    candidate = points[reference, method]
                    control = points[reference, 'raw_point']
                    for column, metric in enumerate(('cost_eur', 'grid_kwh')):
                        difference = statistics(candidate[:, column], all_weights) - statistics(control[:, column], all_weights)
                        draws.append(difference[1:])
                        for j, name in enumerate(('mean', 'cvar90')):
                            axes.append(dict(reference=reference, metric=metric, statistic=name, difference=float(difference[0, j]),
                                             percentile_95=np.quantile(difference[1:, j], [.025, .975], method='linear').tolist()))
                    regret = statistics(candidate[:, 0] - control[:, 0], all_weights)[:, 1]
                    risk.append(dict(reference=reference, cvar90_daily_cost_regret=float(regret[0]),
                                     percentile_95=np.quantile(regret[1:], [.025, .975], method='linear').tolist()))
                record['comparisons'].append(dict(method=method, axes=axes, risk=risk,
                    fraction_all_eight_axes_strictly_improved=float(np.mean(np.all(np.column_stack(draws) < 0, axis=1)))))
            results.append(record)
    assert identities == {str(p.relative_to(EXP)): sha(p) for p in paths}
    return dict(status='PASS', fixtures=checked, inputs_sha256=identities, seed=20261004,
                draws_per_period_and_block=5000, comparisons=results,
                scope='Post-result exploratory sensitivity. No selection, multiplicity, seasonal or future-availability correction. Frequencies are not posterior probabilities.')


if __name__ == '__main__':
    result = main()
    with (HERE / 'result.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('inputs_sha256', 'comparisons')}))
