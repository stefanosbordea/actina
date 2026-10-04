"""Historical execution is explicit and separate from fixtures/input freezing."""
import os
THREAD_LIMITS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')
for name in THREAD_LIMITS:
    os.environ[name] = '1'

import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import platform
import resource
import signal
import sys
import time
import numpy as np
import scipy
from link import CALL_METHODS, CANDIDATES, CONTROLS, METHODS, compare, forecast_metrics, optimizer, project, summary, water_exact

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = HERE.parent / 'physical-012'
EVENT = HERE.parent / 'f1-013'
STAGES = ('validation', 'test')
DAYS = dict(validation=150, test=149)
ORIGINAL_HOURS = dict(validation=3566, test=3567)
COMMON_HOURS = dict(validation=3419, test=3517)
PRIMARY_DAYS = dict(validation=139, test=144)
CUTOFF = dict(validation='2025-12-04 00:00:00', test='2026-05-02 00:00:00')
OPTIMIZER_SHA = '4931d0c86dcd296b0c43e88a8418766b8ba1491677ba89beb7e7301bdb0a78db'
BUDGET_SECONDS = 1800


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def rows(path):
    with Path(path).open(newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, values):
    with Path(path).open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def verify_hashes(pins):
    for name, expected in pins.items():
        path = (ROOT / name).resolve()
        if ROOT not in path.parents or sha(path) != expected:
            raise ValueError('Changed or invalid pinned source: ' + name)


def freeze_inputs():
    lock = HERE / 'inputs.json'
    if lock.exists():
        raise FileExistsError('Input lock already exists')
    pins = {}
    for directory in (OLD, EVENT):
        inherited = json.loads((directory / 'inputs.json').read_text())
        verify_hashes(inherited)
        for name, digest in inherited.items():
            if name in pins and pins[name] != digest:
                raise ValueError('Conflicting inherited source: ' + name)
            pins[name] = digest
    paths = [HERE / name for name in ('PROTOCOL.md', 'link.py', 'run.py', 'test_link.py')]
    paths += [HERE.parent / 'research-2026-10-04/forecast-water-link.md']
    for directory in (OLD, EVENT):
        paths += [directory / 'inputs.json', directory / 'result/planning-freeze.json']
    for stage in STAGES:
        paths += [OLD / 'result' / stage / name for name in ('plans.npz', 'plan-metadata.csv', 'evaluation-membership.csv', 'daily-outcomes.csv')]
        paths += [EVENT / 'result' / stage / 'calls.npz']
    paths += [ROOT / 'app/experiments/f1-008/result/features.csv', ROOT / 'app/experiments/f1-006/result/feature-targets.csv',
              ROOT / 'app/experiments/reference-training-001/result/joined-reference.csv', ROOT / 'eval/cv_predictions.csv', ROOT / 'eval/test_predictions.csv']
    for path in paths:
        pins[str(path.relative_to(ROOT))] = sha(path)
    if pins['app/experiments/physical-011/optimizer.py'] != OPTIMIZER_SHA:
        raise ValueError('The declared optimizer changed')
    verify_hashes(pins)
    save(lock, dict(frozen_at_utc=now(), files_sha256=dict(sorted(pins.items())),
                   statement='Fixed four-arm interface. Only source identities frozen here. No historical schedules or 013 outcome tables read.'))
    print('INPUTS FROZEN', len(pins), sha(lock), flush=True)


def sources():
    source = rows(ROOT / 'app/experiments/f1-008/result/features.csv')
    origins = [datetime.fromisoformat(v['feature_time']) for v in source]
    targets = [v + timedelta(hours=24) for v in origins]
    forecast = np.asarray([float(v['nwp_day2_radiation']) for v in source])
    if len(source) != 17832 or len(set(origins)) != len(source) or any(b-a != timedelta(hours=1) for a,b in zip(origins, origins[1:])):
        raise ValueError('Source membership or chronology')
    if not np.isfinite(forecast).all() or np.any(forecast < 0):
        raise ValueError('Invalid raw source forecast')
    return origins, targets, forecast


def package(stage, targets, forecast):
    for directory, names in ((OLD, ('plans.npz', 'plan-metadata.csv')), (EVENT, ('calls.npz',))):
        freeze = json.loads((directory / 'result/planning-freeze.json').read_text())['files_sha256']
        for name in names:
            key = f'{stage}/{name}'
            if sha(directory / 'result' / key) != freeze[key]:
                raise ValueError('Source planning-freeze mismatch: ' + key)
    with np.load(OLD / 'result' / stage / 'plans.npz', allow_pickle=False) as data:
        if tuple(data['methods']) != CONTROLS:
            raise ValueError('012 method identity')
        control, positions, raw = data['production'], data['target_positions'], data['raw_forecast_ghi']
    with np.load(EVENT / 'result' / stage / 'calls.npz', allow_pickle=False) as data:
        if tuple(data['methods']) != CALL_METHODS or not np.array_equal(data['target_positions'], positions):
            raise ValueError('013 methods or target identity')
        calls = data['calls']
    n = DAYS[stage]
    if positions.shape != (n,24) or positions.dtype.kind not in 'iu' or positions.min() < 0 or positions.max() >= len(targets) or len(set(positions.flat)) != positions.size:
        raise ValueError('Target positions')
    if raw.dtype != np.float64 or raw.shape != (n,24) or not np.array_equal(raw, forecast[positions]):
        raise ValueError('Raw forecast identity')
    if calls.dtype != np.bool_ or calls.shape != (n,5,24) or not np.array_equal(calls[:,0], raw > 600):
        raise ValueError('013 strict calls or dimensions')
    if control.shape != (n,6,24) or not np.isfinite(control).all():
        raise ValueError('012 control dimensions')
    metadata = rows(OLD / 'result' / stage / 'plan-metadata.csv')
    if len(metadata) != n:
        raise ValueError('Metadata membership')
    cutoff = datetime.fromisoformat(CUTOFF[stage])
    for d, (indices, item) in enumerate(zip(positions, metadata)):
        day = datetime.fromisoformat(item['day'])
        issue = day - timedelta(days=1)
        if day != cutoff + timedelta(days=d+1) or [targets[i] for i in indices] != [day+timedelta(hours=h) for h in range(24)]:
            raise ValueError('Complete ordered horizon identity')
        expected = dict(issue_time=issue, maximum_nwp_nominal_time=issue-timedelta(hours=1), interval_start=day-timedelta(hours=1), interval_end=day+timedelta(hours=23))
        if any(datetime.fromisoformat(item[k]) != v for k,v in expected.items()):
            raise ValueError('Issue or interval metadata')
        if datetime.fromisoformat(item['maximum_selected_source_time']) >= cutoff:
            raise ValueError('Historical source cutoff')
        if datetime.fromisoformat(item['issue_utc']) != issue.replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc):
            raise ValueError('UTC issue identity')
        for q in control[d]:
            optimizer.audit(q)
    return dict(control=control, positions=positions, raw=raw, calls=calls, metadata=metadata)


def plan(stage, item, targets, directory, log):
    n = DAYS[stage]
    production = np.empty((n,len(METHODS),24))
    production[:,:6] = item['control']
    mapped = np.empty((n,4,24))
    reproductions, audits, interface, schedules = [], [], [], []
    for d, metadata in enumerate(item['metadata']):
        raw, raw_q = item['raw'][d], production[d,1]
        reproduced, record = optimizer.solve(optimizer.pv(raw))
        difference = float(np.abs(reproduced-raw_q).max())
        reproductions.append(dict(day=metadata['day'], exactly_equal=bool(np.array_equal(reproduced,raw_q)), maximum_difference_m3=difference))
        log.write(json.dumps(dict(stage=stage, day=metadata['day'], method='raw_point_reproduction', **record), allow_nan=False)+'\n')
        if difference > optimizer.AUDIT_TOL:
            raise AssertionError('Raw-point reproduction failed')
        for c, method in enumerate(CANDIDATES):
            values = project(raw, item['calls'][d,c+1])
            mapped[d,c] = values
            identity = values.tobytes() == raw.tobytes()
            if identity:
                q, record = raw_q.copy(), dict(status='EXACT_RAW_INPUT_IDENTITY', copied_archived_raw=True)
            else:
                q, record = optimizer.solve(optimizer.pv(values))
            production[d,6+c] = q
            log.write(json.dumps(dict(stage=stage, day=metadata['day'], method=method, **record), allow_nan=False)+'\n')
            for h, position in enumerate(item['positions'][d]):
                interface.append(dict(day=metadata['day'], target_time=str(targets[position]), method=method, source_position=int(position), raw_call=bool(raw[h]>600),
                    corrected_call=bool(item['calls'][d,c+1,h]), raw_ghi_hex=float(raw[h]).hex(), mapped_ghi_hex=float(values[h]).hex(),
                    ghi_difference_w_m2=float(values[h]-raw[h]), pv_difference_kw=float(optimizer.pv(values)[h]-optimizer.pv(raw)[h]), exact_raw_input_identity=identity))
        for m, method in enumerate(METHODS):
            q = production[d,m]
            audit = optimizer.audit(q)
            audits.append(dict(day=metadata['day'], method=method, numerical=audit, exact=water_exact(q)))
            stock = 2000 + np.cumsum(q-120)
            for h, position in enumerate(item['positions'][d]):
                schedules.append(dict(day=metadata['day'], method=method, source_position=int(position), target_time=str(targets[position]),
                    interval_start=str(targets[position]-timedelta(hours=1)), issue_time=metadata['issue_time'], production_m3=float(q[h]), demand_m3=120.,
                    inventory_start_m3=float(2000 if h==0 else stock[h-1]), inventory_end_m3=float(stock[h]), tariff_eur_kwh=float(optimizer.PRICE[h])))
        if (d+1)%25 == 0:
            log.flush()
            print('PLANNED', stage, d+1, flush=True)
    np.savez_compressed(directory/'plans.npz', production=production, methods=np.asarray(METHODS), raw_forecast_ghi=item['raw'],
                        mapped_forecast_ghi=mapped, mapped_pv=optimizer.pv(mapped), raw_pv=optimizer.pv(item['raw']),
                        target_positions=item['positions'], calls=item['calls'], call_methods=np.asarray(CALL_METHODS))
    with np.load(directory/'plans.npz', allow_pickle=False) as saved:
        if saved['mapped_forecast_ghi'].tobytes() != mapped.tobytes() or not np.array_equal(saved['mapped_forecast_ghi']>600, item['calls'][:,1:]):
            raise AssertionError('Serialized interface identity')
    write_csv(directory/'raw-reproduction.csv', reproductions)
    write_csv(directory/'interface.csv', interface)
    write_csv(directory/'schedules.csv', schedules)
    write_csv(directory/'plan-metadata.csv', item['metadata'])
    save(directory/'water-audits.json', audits)
    return dict(**item, production=production, mapped=mapped)


def references(origins, targets):
    original = rows(ROOT/'app/experiments/f1-006/result/feature-targets.csv')
    joined = rows(ROOT/'app/experiments/reference-training-001/result/joined-reference.csv')
    if len(original) != len(origins) or len(joined) != len(origins):
        raise ValueError('Reference length')
    weather, satellite = [], []
    for origin, target, a, b in zip(origins, targets, original, joined):
        if any(datetime.fromisoformat(row['target_time']) != target or datetime.fromisoformat(row['feature_time']) != origin for row in (a,b)):
            raise ValueError('Reference source join')
        utc = target.replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc)
        if datetime.fromisoformat(b['valid_time_utc']) != utc or datetime.fromisoformat(b['interval_start_utc']) != utc-timedelta(hours=1):
            raise ValueError('Reference UTC join')
        w = float(a['actual'])
        s = float(b['satellite_w_m2']) if b['satellite_w_m2'] else np.nan
        if w != float(b['weather_actual_w_m2']) or not np.isfinite(w) or w < 0 or np.isinf(s) or s < 0:
            raise ValueError('Reference value identity')
        if b['is_missing'] not in ('0','1') or (b['is_missing']=='1') != bool(np.isnan(s)):
            raise ValueError('Reference missingness')
        weather.append(w)
        satellite.append(s)
    return np.asarray(weather), np.asarray(satellite)


def forecast_diagnostics(stage, item, original_positions, split, weather, satellite):
    lookup = {int(p):(d,h) for d,indices in enumerate(item['positions']) for h,p in enumerate(indices)}
    values = dict(original=np.asarray([float(v['predicted']) for v in split]), persistence=np.asarray([float(v['baseline']) for v in split]),
                  raw_nwp=np.asarray([item['raw'][lookup[i]] for i in original_positions]))
    for c, method in enumerate(CANDIDATES):
        values[method] = np.asarray([item['mapped'][lookup[i][0],c,lookup[i][1]] for i in original_positions])
    common = np.isfinite(satellite[original_positions])
    if len(original_positions) != ORIGINAL_HOURS[stage] or int(common.sum()) != COMMON_HOURS[stage]:
        raise ValueError('Original forecast masks')
    result = {}
    for basis, actual, mask in (('weather_full',weather,np.ones(len(common),dtype=bool)),('weather_common',weather,common),('satellite_common',satellite,common)):
        result[basis] = {method:forecast_metrics(actual[original_positions][mask],forecast[mask]) for method,forecast in values.items()}
    return result


def score(stage, item, origins, weather, satellite, directory):
    split = rows(ROOT/'eval'/('cv_predictions.csv' if stage=='validation' else 'test_predictions.csv'))
    lookup = {str(v):i for i,v in enumerate(origins)}
    original_positions = [lookup[str(datetime.fromisoformat(v['time']))] for v in split]
    if len(set(original_positions)) != ORIGINAL_HOURS[stage] or not np.array_equal(weather[original_positions],np.asarray([float(v['actual']) for v in split])):
        raise ValueError('Original membership or reference identity')
    original_set = set(original_positions)
    exclusions, daily = [], []
    for d, (indices, metadata) in enumerate(zip(item['positions'],item['metadata'])):
        inside = all(int(i) in original_set for i in indices)
        complete = bool(np.isfinite(satellite[indices]).all())
        reasons = ([] if inside else ['partial_original_period'])+([] if complete else ['missing_satellite_endpoint'])
        exclusions.append(dict(day=metadata['day'], primary=inside and complete, weather_sensitivity=inside, original_hours=sum(int(i) in original_set for i in indices),
                               available_satellite_hours=int(np.isfinite(satellite[indices]).sum()), exclusion_reasons='|'.join(reasons)))
        for reference, values in (('weather',weather),('satellite',satellite)):
            if reference=='satellite' and not complete:
                continue
            solar = optimizer.pv(values[indices])
            baseline = optimizer.evaluate(item['production'][d,1],solar)
            for m, method in enumerate(METHODS):
                q = item['production'][d,m]
                evaluated = optimizer.evaluate(q,solar)
                daily.append(dict(day=metadata['day'], method=method, reference=reference, primary=inside and complete, weather_sensitivity=inside and reference=='weather',
                    cost_eur=float(evaluated['cost']), grid_kwh=float(evaluated['grid_energy']), unused_pv_kwh=float(evaluated['unused_pv']),
                    peak_grid_kw=float(np.maximum(optimizer.SEC*q-solar,0).max()), cost_regret_eur=float(evaluated['cost']-baseline['cost']),
                    grid_regret_kwh=float(evaluated['grid_energy']-baseline['grid_energy']), **optimizer.audit(q)))
    archived_mask = rows(OLD/'result'/stage/'evaluation-membership.csv')
    if [{k:str(v) for k,v in row.items()} for row in exclusions] != archived_mask:
        raise AssertionError('Changed physical scoring membership')
    if sum(v['primary'] for v in exclusions) != PRIMARY_DAYS[stage] or sum(v['weather_sensitivity'] for v in exclusions) != 148:
        raise AssertionError('Physical cohort counts')
    old_rows = rows(OLD/'result'/stage/'daily-outcomes.csv')
    archived = {(v['day'],v['method'],v['reference']):v for v in old_rows}
    if len(archived) != len(old_rows):
        raise ValueError('Duplicate archived outcomes')
    replay = []
    for row in daily:
        if row['method'] not in CONTROLS:
            continue
        before = archived.pop((row['day'],row['method'],row['reference']))
        for metric in row:
            if metric in ('day','method','reference','primary','weather_sensitivity'):
                continue
            delta = row[metric]-float(before[metric])
            replay.append(dict(day=row['day'], method=row['method'], reference=row['reference'], metric=metric, difference=delta, exactly_equal=delta==0))
            if abs(delta)>1e-9:
                raise AssertionError('Changed archived control outcome')
    if archived:
        raise AssertionError('Missing archived control outcomes')
    write_csv(directory/'evaluation-membership.csv',exclusions)
    write_csv(directory/'daily-outcomes.csv',daily)
    write_csv(directory/'control-outcome-replay.csv',replay)
    comparisons, aggregates = {}, {}
    for method in METHODS:
        aggregates[method] = {}
        for basis, reference, flag in (('weather_common','weather','primary'),('satellite_common','satellite','primary'),('weather_full_days','weather','weather_sensitivity')):
            subset = [v for v in daily if v['method']==method and v['reference']==reference and v[flag]]
            aggregates[method][basis] = {metric:summary([v[metric] for v in subset]) for metric in ('cost_eur','grid_kwh','unused_pv_kwh','peak_grid_kw')}
    for candidate in CANDIDATES:
        comparisons[candidate] = {}
        for control in CONTROLS[1:]:
            pairs = {}
            for reference in ('weather','satellite'):
                a = [v for v in daily if v['method']==candidate and v['reference']==reference and v['primary']]
                b = [v for v in daily if v['method']==control and v['reference']==reference and v['primary']]
                if [v['day'] for v in a] != [v['day'] for v in b]:
                    raise ValueError('Paired day identity')
                pairs[reference] = {metric:([v[metric] for v in a],[v[metric] for v in b]) for metric in ('cost_eur','grid_kwh')}
            comparisons[candidate][control] = compare(pairs)
    return dict(primary_days=PRIMARY_DAYS[stage], weather_sensitivity_days=148, aggregates=aggregates, comparisons=comparisons,
                forecast_diagnostics=forecast_diagnostics(stage,item,original_positions,split,weather,satellite),
                archived_control_replay=dict(comparisons=len(replay), exactly_equal=sum(v['exactly_equal'] for v in replay), maximum_difference=max(abs(v['difference']) for v in replay)))


def execute(out):
    started, cpu = time.perf_counter(), time.process_time()
    out = out.resolve()
    if HERE not in out.parents:
        raise ValueError('Output must be inside physical-014')
    out.mkdir(exist_ok=False)
    receipt = dict(started_at_utc=now(), command=sys.argv, status='VERIFYING_INPUTS', outcome_scoring_started=False, total_runtime_budget_seconds=BUDGET_SECONDS,
                   versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__), thread_limits={v:os.environ[v] for v in THREAD_LIMITS})
    save(out/'execution-start.json',receipt)
    def timeout(signum, frame):
        raise TimeoutError('Predeclared process budget exhausted')
    previous = signal.signal(signal.SIGALRM,timeout)
    signal.setitimer(signal.ITIMER_REAL,max(0.000001,BUDGET_SECONDS-(time.perf_counter()-started)))
    try:
        pins = json.loads((HERE/'inputs.json').read_text())['files_sha256']
        verify_hashes(pins)
        receipt.update(input_lock_sha256=sha(HERE/'inputs.json'), protocol_sha256=sha(HERE/'PROTOCOL.md'))
        origins, targets, forecast = sources()
        packages = {stage:package(stage,targets,forecast) for stage in STAGES}
        cache = {}
        with (out/'solver-records.jsonl').open('x') as log:
            for stage in STAGES:
                directory = out/stage
                directory.mkdir()
                cache[stage] = plan(stage,packages[stage],targets,directory,log)
        verify_hashes(pins)
        frozen = {str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
        save(out/'planning-freeze.json',dict(frozen_at_utc=now(),files_sha256=frozen,statement='All 299 horizons and 2990 plans retained before scoring references or masks were opened.'))
        print('ALL PLANS FROZEN BEFORE SCORING',flush=True)
        receipt['outcome_scoring_started'] = True
        weather, satellite = references(origins,targets)
        report = dict(status='COMPLETE',primary_method='mapped_conditional_robust',methods=METHODS,planning_freeze_sha256=sha(out/'planning-freeze.json'),
                      reporting_thresholds=dict(cost_eur=1e-5,grid_kwh=1e-5,interpretation='Numerical reporting thresholds only. Not meter or plant resolution. Only the euro action floor belongs to the optimizer. Strict signs and gates remain unchanged.'),
                      scope='Retrospective effect of the frozen binary64 event interface on illustrative solar-to-water scheduling. No new calibration or field claim.',splits={})
        for stage in STAGES:
            report['splits'][stage] = score(stage,cache[stage],origins,weather,satellite,out/stage)
        report['gates'] = {method:dict(physical_upgrade=all(report['splits'][s]['comparisons'][method][c][gate] for s in STAGES for c in CONTROLS[1:] for gate in ('all_axis_pass','risk_only_pass')),
                                      raw_control_both_periods=all(report['splits'][s]['comparisons'][method]['raw_point'][gate] for s in STAGES for gate in ('all_axis_pass','risk_only_pass')))
                           for method in CANDIDATES}
        if any(sha(out/name)!=value for name,value in frozen.items()):
            raise AssertionError('Frozen plan changed')
        verify_hashes(pins)
        save(out/'report.json',report)
        receipt.update(status='COMPLETE',exit_code=0)
    except BaseException as error:
        receipt.update(status='FAILED',exit_code=1,error_type=type(error).__name__,error=str(error))
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)
        receipt.update(finished_at_utc=now(),elapsed_seconds=time.perf_counter()-started,cpu_seconds=time.process_time()-cpu,
                       peak_rss_bytes=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=='darwin' else 1024),peak_rss_convention='macOS bytes, Linux KiB converted to bytes')
        save(out/'execution-receipt.json',receipt)
        save(out/'outputs.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='outputs.json'})
    print(receipt['status'],flush=True)


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze-inputs',action='store_true')
    parser.add_argument('--execute-historical',action='store_true')
    parser.add_argument('--out',type=Path)
    args = parser.parse_args()
    if args.freeze_inputs and not args.execute_historical and args.out is None:
        freeze_inputs()
    elif args.execute_historical and args.out is not None and not args.freeze_inputs:
        execute(args.out)
    else:
        parser.error('Use --freeze-inputs, or --execute-historical --out FRESH_PATH')
