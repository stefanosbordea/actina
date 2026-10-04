"""Forecast-conditioned historical paths with an unchanged physical optimizer."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import resource
import sys
import time
import numpy as np
import pandas as pd
import scipy
from retrieval import descriptor, distances, choose, eligible_pool

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = HERE.parent / 'physical-011'
sys.path.insert(0, str(OLD))
from optimizer import pv, cvar, evaluate, solve, audit, shuffled, PRICE, SEC, AUDIT_TOL
spec = importlib.util.spec_from_file_location('physical011_runner', OLD / 'run.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
METHODS = ('tariff_context', 'raw_point', 'recency_coherent', 'recency_shuffled', 'conditional_coherent', 'conditional_shuffled')
REFERENCES = ('weather', 'satellite')
BANKS = ('recency', 'conditional')
FAMILIES = ('coherent', 'shuffled')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def now():
    return datetime.now(timezone.utc).isoformat()


def compare(frame, method, control):
    paired = frame.loc[frame.method.isin((method, control))].copy()
    paired.loc[paired.method == control, 'method'] = 'raw_point'
    return old.gates(paired, method)


def aggregates(frame):
    result = {}
    for subset in ('primary', 'weather_sensitivity'):
        result[subset] = {}
        for (method, reference), rows in frame.loc[frame[subset]].groupby(['method', 'reference'], sort=False):
            item = {metric: old.summary(rows[metric]) for metric in ('cost_eur', 'grid_kwh', 'unused_pv_kwh', 'peak_grid_kw', 'cost_regret_eur', 'grid_regret_kwh')}
            regret = rows.cost_regret_eur.to_numpy()
            item.update(days=len(rows), worse_days=int(np.sum(regret > 0)), better_days=int(np.sum(regret < 0)), equal_days=int(np.sum(regret == 0)),
                cost_regret_below_reporting_resolution_days=int(np.sum(abs(regret) < 1.e-5)))
            result[subset][method + '/' + reference] = item
    return result


def main(out):
    started, cpu = time.perf_counter(), time.process_time()
    pins = json.loads((HERE / 'inputs.json').read_text())
    for name, digest in pins.items():
        if sha(ROOT / name) != digest:
            raise ValueError('Changed frozen input: ' + name)
    if HERE not in out.parents:
        raise ValueError('Output outside experiment')
    out.mkdir(exist_ok=False)
    data = old.read(ROOT / 'app/experiments/f1-008/result/features.csv')
    target_file = old.read(ROOT / 'app/experiments/f1-006/result/feature-targets.csv')
    ref = old.read(ROOT / 'app/experiments/reference-training-001/result/joined-reference.csv')
    if len(data) != 17832 or not data.feature_time.is_unique or any(not data.feature_time.equals(v.feature_time) for v in (target_file, ref)):
        raise ValueError('Source membership')
    origin = pd.DatetimeIndex(data.feature_time)
    target = pd.DatetimeIndex(target_file.target_time)
    if not np.all(target == origin + pd.Timedelta(hours=24)) or not np.all(target[1:] - target[:-1] == pd.Timedelta(hours=1)):
        raise ValueError('Source chronology')
    if not np.array_equal(target, pd.DatetimeIndex(ref.target_time)) or not np.array_equal(target_file.actual, ref.weather_actual_w_m2):
        raise ValueError('Reference join')
    if not np.array_equal(target.tz_localize('Etc/GMT-3').tz_convert('UTC'), pd.DatetimeIndex(ref.valid_time_utc)):
        raise ValueError('UTC join')
    nwp, weather, satellite = data.nwp_day2_radiation.to_numpy(), target_file.actual.to_numpy(), ref.satellite_w_m2.to_numpy()
    if not np.isfinite(nwp).all() or not np.isfinite(weather).all() or np.isinf(satellite).any() or np.any(nwp < 0) or np.any(weather < 0) or np.any(satellite < 0):
        raise ValueError('Source values')
    if not np.array_equal(np.isnan(satellite), ref.is_missing.astype(bool)):
        raise ValueError('Satellite missingness')
    report = dict(status='PLANNING', started_at_utc=now(), protocol_sha256=sha(HERE/'PROTOCOL.md'), input_lock_sha256=sha(HERE/'inputs.json'), input_sha256=pins,
        versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, pandas=pd.__version__),
        methods=METHODS, banks=BANKS, families=FAMILIES, references=REFERENCES, splits={}, gates={}, matched_gates={}, outcomes={}, comparisons={},
        scope='Retrospective conditioning experiment proposed after inspected 011 outcomes. Illustrative PV and water physics. No live, field or novelty claim.', solver_threads=1)
    cache = {}
    with (out/'solver-records.jsonl').open('x') as log:
        for stage, filename in (('validation', 'cv_predictions.csv'), ('test', 'test_predictions.csv')):
            split = old.read(ROOT/'eval'/filename)
            names = split.iloc[:, 0]
            original_positions = pd.Index(data.feature_time).get_indexer(names)
            if np.any(original_positions < 0) or not names.is_unique or len(names) != {'validation': 3566, 'test': 3567}[stage] or not np.array_equal(weather[original_positions], split.actual):
                raise ValueError('Original split identity')
            days = sorted(set(target[original_positions].normalize()))
            cutoff = days[0] - pd.Timedelta(days=1)
            if str(cutoff) != {'validation': '2025-12-04 00:00:00', 'test': '2026-05-02 00:00:00'}[stage]:
                raise ValueError('Changed historical cutoff')
            pool_days, pool_positions, ledger = eligible_pool(target, nwp, weather, satellite, cutoff)
            pool_nwp = nwp[pool_positions]
            pool_descriptor = np.stack([descriptor(v) for v in pool_nwp])
            pool_residual = np.stack((weather[pool_positions]-pool_nwp, satellite[pool_positions]-pool_nwp))
            recency = np.arange(len(pool_days)-64, len(pool_days))
            directory = out/stage
            directory.mkdir()
            pd.DataFrame(ledger).to_csv(directory/'pool-membership.csv', index=False)
            with np.load(OLD/'result'/stage/'bank.npz', allow_pickle=False) as bank:
                permutations = bank['permutations']
                if not np.array_equal(pool_positions[recency], bank['source_positions']) or not np.array_equal(pool_residual[:, recency], bank['residuals']):
                    raise AssertionError('Recency bank identity')
            archived = np.load(OLD/'result'/stage/'plans.npz', allow_pickle=False)
            archived_scenarios = np.load(OLD/'result'/stage/'scenario-replay.npz', allow_pickle=False)
            if list(archived['methods']) != ['tariff_context', 'raw_point', 'coherent', 'shuffled'] or len(archived['production']) != len(days):
                raise ValueError('Archived plan identity')
            archived_production = archived['production']
            archived_positions = archived['target_positions']
            archived_forecast = archived['raw_forecast_ghi']
            archived_ghi = archived_scenarios['unclipped_ghi']
            plans = np.empty((len(days), 6, 24))
            scenarios = np.empty((len(days), 2, 2, 2, 64, 24))
            replay_cost = np.empty((len(days), 2, 2, 6, 2, 64))
            replay_grid, replay_unused = np.empty_like(replay_cost), np.empty_like(replay_cost)
            distance_matrix = np.empty((len(days), len(pool_days)))
            selected_matrix = np.empty((len(days), 64), dtype=int)
            target_descriptor = np.empty((len(days), 24))
            day_positions, metadata, retrieval_ledger, reproductions = [], [], [], []
            for d, day in enumerate(days):
                indices = np.flatnonzero(target.normalize() == day)
                if len(indices) != 24 or list(target[indices].hour) != list(range(24)):
                    raise ValueError('Incomplete planning day')
                if not np.array_equal(indices, archived_positions[d]) or not np.array_equal(nwp[indices], archived_forecast[d]):
                    raise ValueError('Archived forecast identity')
                issue = day-pd.Timedelta(days=1)
                if np.any(target[indices]-pd.Timedelta(hours=48) >= issue) or np.any(target[pool_positions.reshape(-1)] >= cutoff) or cutoff > issue:
                    raise ValueError('Source chronology violation')
                day_positions.append(indices)
                forecast = nwp[indices]
                target_descriptor[d] = descriptor(forecast)
                distance_matrix[d] = distances(pool_descriptor, target_descriptor[d])
                selected, rank = choose(pool_days, distance_matrix[d])
                selected_matrix[d] = selected
                selected_set = set(selected)
                canonical = {int(p): i for i, p in enumerate(selected)}
                for p, source_day in enumerate(pool_days):
                    retrieval_ledger.append(dict(day=str(day.date()), source_day=source_day, distance_m3=float(distance_matrix[d, p]), rank=int(rank[p]),
                        selected=p in selected_set, canonical_scenario_index=canonical.get(p), source_last_endpoint=str(target[pool_positions[p, -1]])))
                plans[d, :2] = archived_production[d, :2]
                q0 = plans[d, 1]
                for m in range(2):
                    audit(plans[d, m])
                for b, selection in enumerate((recency, selected)):
                    residual = pool_residual[:, selection]
                    permuted = shuffled(residual, permutations)
                    if not np.array_equal(np.sort(residual, axis=1), np.sort(permuted, axis=1)):
                        raise AssertionError('Changed residual marginal')
                    scenarios[d, b, 0] = forecast[None, None, :] + residual
                    scenarios[d, b, 1] = forecast[None, None, :] + permuted
                    if not np.array_equal(np.sort(scenarios[d, b, 0], axis=1), np.sort(scenarios[d, b, 1], axis=1)):
                        raise AssertionError('Changed scenario marginal')
                    if b == 0 and not np.array_equal(scenarios[d, b], archived_ghi[d]):
                        raise AssertionError('Recency scenario identity')
                    for f in range(2):
                        m = 2+2*b+f
                        q, record = solve(pv(scenarios[d, b, f]), q0)
                        plans[d, m] = q
                        record.update(stage=stage, day=str(day.date()), method=METHODS[m])
                        log.write(json.dumps(record, allow_nan=False)+'\n')
                        if b == 0:
                            difference = float(np.max(abs(q-archived_production[d, 2+f])))
                            reproductions.append(dict(day=str(day.date()), method=METHODS[m], maximum_difference_m3=difference,
                                exactly_equal=bool(np.array_equal(q, archived_production[d, 2+f]))))
                            if difference > AUDIT_TOL:
                                raise AssertionError('Archived recency schedule reproduction failed')
                for b in range(2):
                    for f in range(2):
                        solar = pv(scenarios[d, b, f])
                        for m in range(6):
                            values = evaluate(plans[d, m], solar)
                            replay_cost[d, b, f, m] = values['cost']
                            replay_grid[d, b, f, m] = values['grid_energy']
                            replay_unused[d, b, f, m] = values['unused_pv']
                    if not np.allclose(replay_cost[d, b, 0].mean(axis=-1), replay_cost[d, b, 1].mean(axis=-1), rtol=0, atol=1.e-9):
                        raise AssertionError('Expected-cost shuffle invariance')
                ages = (issue-target[pool_positions[selected, -1]]).total_seconds().to_numpy()/3600
                totals = pool_descriptor[:, -1]
                metadata.append(dict(day=str(day.date()), issue_time=str(issue), issue_utc=issue.tz_localize('Etc/GMT-3').tz_convert('UTC').isoformat(),
                    interval_start=str(day-pd.Timedelta(hours=1)), interval_end=str(day+pd.Timedelta(hours=23)),
                    maximum_selected_source_time=str(target[pool_positions[selected].reshape(-1)].max()), maximum_nwp_nominal_time=str(day-pd.Timedelta(hours=25)),
                    distance_64_m3=float(np.max(distance_matrix[d, selected])), minimum_selected_age_hours=float(ages.min()), maximum_selected_age_hours=float(ages.max()),
                    target_potential_water_m3=float(target_descriptor[d, -1]), pool_minimum_potential_water_m3=float(totals.min()), pool_maximum_potential_water_m3=float(totals.max()),
                    target_total_outside_pool=bool(target_descriptor[d, -1] < totals.min() or target_descriptor[d, -1] > totals.max()),
                    conditional_recency_overlap_days=int(np.intersect1d(selected, recency).size)))
                if (d+1) % 10 == 0:
                    print('PLANNED', stage, d+1, 'of', len(days), flush=True)
            log.flush()
            np.savez_compressed(directory/'bank.npz', pool_source_positions=pool_positions, pool_source_target_time=np.asarray(target[pool_positions.reshape(-1)].astype(str), dtype='U19').reshape(-1, 24),
                pool_source_days=np.asarray(pool_days, dtype='U10'), pool_nwp=pool_nwp, pool_weather=weather[pool_positions], pool_satellite=satellite[pool_positions],
                pool_residuals=pool_residual, pool_descriptor=pool_descriptor, recency_pool_indices=recency, conditional_pool_indices=selected_matrix,
                distance_m3=distance_matrix, target_descriptor=target_descriptor, permutations=permutations)
            np.savez_compressed(directory/'plans.npz', production=plans, raw_forecast_ghi=nwp[np.stack(day_positions)], target_positions=np.stack(day_positions), methods=np.asarray(METHODS))
            np.savez_compressed(directory/'scenario-replay.npz', unclipped_ghi=scenarios, cost_eur=replay_cost, grid_kwh=replay_grid, unused_pv_kwh=replay_unused)
            pd.DataFrame(metadata).to_csv(directory/'plan-metadata.csv', index=False)
            pd.DataFrame(retrieval_ledger).to_csv(directory/'retrieval.csv', index=False)
            pd.DataFrame(reproductions).to_csv(directory/'recency-reproduction.csv', index=False)
            schedules = []
            for d, indices in enumerate(day_positions):
                for m, method in enumerate(METHODS):
                    q = plans[d, m]
                    stock = 2000+np.cumsum(q-120)
                    for h in range(24):
                        schedules.append(dict(day=str(days[d].date()), method=method, endpoint_time=str(target[indices[h]]), interval_start=str(target[indices[h]]-pd.Timedelta(hours=1)),
                            production_m3=float(q[h]), demand_m3=120., inventory_start_m3=float(2000 if h == 0 else stock[h-1]), inventory_end_m3=float(stock[h]), tariff_eur_kwh=float(PRICE[h])))
            pd.DataFrame(schedules).to_csv(directory/'schedules.csv', index=False)
            report['splits'][stage] = dict(planned_days=len(days), planned_hours=24*len(days), original_hours=len(original_positions), eligible_pool_days=len(pool_days),
                bank_cutoff=str(cutoff), pool_first_day=pool_days[0], pool_last_day=pool_days[-1],
                recency_reproduction=dict(count=len(reproductions), exactly_equal=sum(v['exactly_equal'] for v in reproductions), maximum_difference_m3=max(v['maximum_difference_m3'] for v in reproductions)),
                support=dict(outside_pool_total_supply_horizons=sum(v['target_total_outside_pool'] for v in metadata), maximum_distance_64_m3=max(v['distance_64_m3'] for v in metadata)))
            cache[stage] = days, day_positions, original_positions, plans
            archived.close()
            archived_scenarios.close()
    plan_files = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    save(out/'planning-freeze.json', dict(all_plans_created_at_utc=now(), files_sha256=plan_files,
        statement='All 299 horizons and 1794 schedules exist before evaluation masks and realized outcome scoring. Recency controls were reproduced.'))
    print('ALL PLANS FROZEN BEFORE SCORING', flush=True)
    report['planning_freeze_sha256'] = sha(out/'planning-freeze.json')
    for stage, (days, day_positions, original_positions, plans) in cache.items():
        membership = set(original_positions)
        exclusions, daily = [], []
        for d, indices in enumerate(day_positions):
            inside = all(i in membership for i in indices)
            sat_complete = bool(np.isfinite(satellite[indices]).all())
            primary = inside and sat_complete
            reasons = ([] if inside else ['partial_original_period']) + ([] if sat_complete else ['missing_satellite_endpoint'])
            exclusions.append(dict(day=str(days[d].date()), primary=primary, weather_sensitivity=inside, original_hours=sum(i in membership for i in indices),
                available_satellite_hours=int(np.isfinite(satellite[indices]).sum()), exclusion_reasons='|'.join(reasons)))
            for reference in REFERENCES:
                if reference == 'satellite' and not sat_complete:
                    continue
                solar = pv(weather[indices] if reference == 'weather' else satellite[indices])
                baseline = evaluate(plans[d, 1], solar)
                for m, method in enumerate(METHODS):
                    q = plans[d, m]
                    values = evaluate(q, solar)
                    daily.append(dict(day=str(days[d].date()), method=method, reference=reference, primary=primary, weather_sensitivity=inside and reference == 'weather',
                        cost_eur=float(values['cost']), grid_kwh=float(values['grid_energy']), unused_pv_kwh=float(values['unused_pv']), peak_grid_kw=float(np.maximum(SEC*q-solar, 0).max()),
                        cost_regret_eur=float(values['cost']-baseline['cost']), grid_regret_kwh=float(values['grid_energy']-baseline['grid_energy']), **audit(q)))
        mask = pd.DataFrame(exclusions)
        old_mask = old.read(OLD/'result'/stage/'evaluation-membership.csv').fillna({'exclusion_reasons': ''})
        if list(mask.columns) != list(old_mask.columns) or any(not np.array_equal(mask[column], old_mask[column]) for column in mask):
            raise AssertionError('Changed 011 evaluation membership')
        mask.to_csv(out/stage/'evaluation-membership.csv', index=False)
        frame = pd.DataFrame(daily)
        frame.to_csv(out/stage/'daily-outcomes.csv', index=False)
        report['splits'][stage].update(primary_days=int(mask.primary.sum()), weather_sensitivity_days=int(mask.weather_sensitivity.sum()))
        report['outcomes'][stage] = aggregates(frame)
        report['gates'][stage] = {method: old.gates(frame, method) for method in METHODS[2:]}
        report['matched_gates'][stage] = {method: compare(frame, method, control) for method, control in
            (('conditional_coherent', 'recency_coherent'), ('conditional_shuffled', 'recency_shuffled'))}
        report['comparisons'][stage] = {}
        for a, b in (('conditional_coherent', 'recency_coherent'), ('conditional_shuffled', 'recency_shuffled'), ('conditional_coherent', 'conditional_shuffled'), ('recency_coherent', 'recency_shuffled')):
            pair = {}
            for reference in REFERENCES:
                left = frame.loc[frame.primary & (frame.reference == reference) & (frame.method == a)]
                right = frame.loc[frame.primary & (frame.reference == reference) & (frame.method == b)]
                if not np.array_equal(left.day, right.day):
                    raise AssertionError('Comparison alignment')
                pair[reference] = {metric: old.summary(left[metric].to_numpy()-right[metric].to_numpy()) for metric in ('cost_eur', 'grid_kwh')}
            report['comparisons'][stage][a+'_minus_'+b] = pair
    if any(sha(out/name) != digest for name, digest in plan_files.items()) or any(sha(ROOT/name) != digest for name, digest in pins.items()):
        raise AssertionError('Frozen source or plan changed')
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report.update(status='COMPLETE', completed_at_utc=now(), wall_seconds=time.perf_counter()-started, cpu_seconds=time.process_time()-cpu,
        peak_rss_bytes=int(rss if sys.platform == 'darwin' else rss*1024),
        experiment_gate={m: dict(risk_both_periods=all(report['gates'][s][m]['risk_only_pass'] for s in ('validation', 'test')),
            all_axis_both_periods=all(report['gates'][s][m]['all_axis_pass'] for s in ('validation', 'test')),
            overall_no_tradeoff=all(report['gates'][s][m]['risk_only_pass'] and report['gates'][s][m]['all_axis_pass'] for s in ('validation', 'test'))) for m in METHODS[4:]})
    save(out/'report.json', report)
    save(out/'outputs.json', {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'outputs.json'})
    print('COMPLETE', json.dumps(report['experiment_gate']), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=HERE/'result')
    main(parser.parse_args().out.resolve())
