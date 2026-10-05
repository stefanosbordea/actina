"""Independent perfect-information bounds, never an available forecast policy."""
import hashlib
import json
from pathlib import Path
import time
import warnings

import numpy as np
import pandas as pd
from scipy.optimize import linprog, OptimizeWarning

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
ROOT = HERE.parents[3]
PRICE = np.array([.101 if 10 <= h < 17 else .183 if 17 <= h < 23 else .130 for h in range(24)])
TOL = 1e-6


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(solar, objective):
    solar = np.asarray(solar, dtype=float)
    if solar.shape != (24,) or not np.isfinite(solar).all() or np.any((solar < 0) | (solar > 1700)):
        raise ValueError('Invalid illustrative PV trajectory')
    if objective not in ('cost_eur', 'grid_kwh'):
        raise ValueError('Unknown objective')
    cumulative = np.tril(np.ones((24, 24)))
    matrix = np.block([[cumulative, np.zeros((24, 24))],
                       [-cumulative, np.zeros((24, 24))],
                       [3.4 * np.eye(24), -np.eye(24)]])
    rhs = np.r_[2000 + 120 * np.arange(1, 25), 1200 - 120 * np.arange(1, 25), solar]
    weights = PRICE if objective == 'cost_eur' else np.ones(24)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', OptimizeWarning)
        solved = linprog(np.r_[np.zeros(24), weights], A_ub=matrix, b_ub=rhs,
                         A_eq=np.r_[np.ones(24), np.zeros(24)][None], b_eq=[2880.],
                         bounds=[(0., 500.)] * 24 + [(0., None)] * 24,
                         method='highs-ds', options=dict(threads=1,
                         primal_feasibility_tolerance=1e-9, dual_feasibility_tolerance=1e-9))
    if not solved.success:
        raise RuntimeError(solved.message)
    q = solved.x[:24]
    grid = np.maximum(3.4 * q - solar, 0.)
    inventory = np.r_[2000., 2000. + np.cumsum(q - 120.)]
    violations = [0., -q.min(), q.max() - 500., 800. - inventory.min(),
                  inventory.max() - 4000., abs(inventory[-1] - 2000.),
                  abs(q.sum() - 2880.), np.max(abs(grid - solved.x[24:])),
                  abs(float(grid @ weights) - solved.fun)]
    if max(violations) > TOL:
        raise AssertionError(('Invalid lower-bound solution', violations))
    return dict(objective=objective, minimum=float(solved.fun), production=q.tolist(),
                grid=grid.tolist(), inventory=inventory.tolist(),
                maximum_violation=float(max(violations)), status=int(solved.status),
                message=solved.message, iterations=int(solved.nit),
                warnings=[str(w.message) for w in caught])


def fixtures():
    zero = np.zeros(24)
    energy = bounds(zero, 'grid_kwh')
    cost = bounds(zero, 'cost_eur')
    assert abs(energy['minimum'] - 9792.) <= TOL
    assert abs(cost['minimum'] - 9792. * .101) <= TOL
    solar = np.zeros(24)
    solar[10:17] = 1000.
    for objective, expected in [('grid_kwh', 2792.), ('cost_eur', 2792. * .101)]:
        a = bounds(solar, objective)
        b = bounds(solar, objective)
        assert abs(a['minimum'] - expected) <= TOL
        assert a == b
    return dict(status='PASS', zero_pv_energy=energy['minimum'], zero_pv_cost=cost['minimum'],
                checked=['zero PV', 'known midday PV', 'water feasibility', 'deterministic repeated solve'])


def main():
    started = time.perf_counter()
    preflight = fixtures()
    report = json.loads((EXP / 'result/report.json').read_text())
    assert report['status'] == 'COMPLETE'
    source_paths = [HERE / 'PROTOCOL.md', Path(__file__).resolve(),
                    EXP / 'result/report.json', EXP / 'result/planning-freeze.json',
                    ROOT / 'app/experiments/f1-006/result/feature-targets.csv',
                    ROOT / 'app/experiments/reference-training-001/result/joined-reference.csv']
    for split in ('validation', 'test'):
        source_paths += [EXP / f'result/{split}/{name}' for name in
                         ('plans.npz', 'plan-metadata.csv', 'evaluation-membership.csv')]
    identities = {str(p.relative_to(ROOT)): sha(p) for p in source_paths}
    weather = pd.read_csv(source_paths[4], float_precision='round_trip')
    satellite = pd.read_csv(source_paths[5], float_precision='round_trip')
    assert weather.target_time.equals(satellite.target_time)
    assert np.array_equal(weather.actual.to_numpy(), satellite.weather_actual_w_m2.to_numpy())
    values = dict(weather=weather.actual.to_numpy(), satellite=satellite.satellite_w_m2.to_numpy())
    records, plans = [], []
    for split in ('validation', 'test'):
        directory = EXP / 'result' / split
        archive = np.load(directory / 'plans.npz', allow_pickle=False)
        membership = pd.read_csv(directory / 'evaluation-membership.csv')
        metadata = pd.read_csv(directory / 'plan-metadata.csv')
        assert membership.day.equals(metadata.day)
        assert len(membership) == len(archive['production'])
        methods = archive['methods'].tolist()
        for d in np.flatnonzero(membership.primary.to_numpy()):
            positions = archive['target_positions'][d]
            times = pd.DatetimeIndex(weather.target_time.iloc[positions])
            assert len(times) == 24 and times.hour.tolist() == list(range(24))
            assert all(str(t.date()) == membership.day.iloc[d] for t in times)
            for reference in ('weather', 'satellite'):
                ghi = values[reference][positions]
                assert np.isfinite(ghi).all()
                solar = np.minimum(1700., 1.7 * np.maximum(ghi, 0.))
                for objective in ('cost_eur', 'grid_kwh'):
                    solution = bounds(solar, objective)
                    identity = dict(split=split, day=membership.day.iloc[d], reference=reference, objective=objective)
                    plans.append({**identity, **solution})
                    weights = PRICE if objective == 'cost_eur' else np.ones(24)
                    for m, method in enumerate(methods):
                        q = archive['production'][d, m]
                        grid = np.maximum(3.4 * q - solar, 0.)
                        value = float(grid @ weights)
                        gap = value - solution['minimum']
                        if gap < -TOL:
                            raise AssertionError(('Saved plan below lower bound', identity, method, gap))
                        records.append({**identity, 'method': method, 'observed': value,
                                        'perfect_information_bound': solution['minimum'], 'gap': gap})
    frame = pd.DataFrame(records)
    summaries = []
    for keys, rows in frame.groupby(['split', 'reference', 'objective', 'method'], sort=False):
        summaries.append(dict(zip(('split', 'reference', 'objective', 'method'), keys)) |
                         dict(days=len(rows), mean_observed=float(rows.observed.mean()),
                              mean_bound=float(rows.perfect_information_bound.mean()), mean_gap=float(rows.gap.mean()),
                              minimum_gap=float(rows.gap.min()), maximum_gap=float(rows.gap.max())))
    assert identities == {str(p.relative_to(ROOT)): sha(p) for p in source_paths}
    out = HERE / 'result'
    out.mkdir(exist_ok=False)
    frame.to_csv(out / 'daily-gaps.csv', index=False)
    with (out / 'oracle-solutions.jsonl').open('x') as stream:
        for row in plans:
            stream.write(json.dumps(row, allow_nan=False) + '\n')
    result = dict(status='PASS', scope='Post-protocol perfect-information diagnostic, not an operating policy or attainable forecast gain.',
                  inputs_sha256=identities, fixtures=preflight, independent_linear_programs=len(plans),
                  compared_daily_objectives=len(frame), numerical_tolerance=TOL,
                  maximum_solution_violation=max(p['maximum_violation'] for p in plans), summaries=summaries,
                  wall_seconds=time.perf_counter() - started)
    (out / 'report.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    (out / 'outputs.json').write_text(json.dumps({p.name: sha(p) for p in sorted(out.iterdir())}, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('inputs_sha256', 'summaries')}))
    return result


if __name__ == '__main__':
    main()
