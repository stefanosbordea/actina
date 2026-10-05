"""Exact event decisions from immutable 012 paths, followed by delayed scoring."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import resource
import signal
import sys
import time
THREAD_LIMITS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')
for variable in THREAD_LIMITS:
    os.environ[variable] = '2'
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREVIOUS = ROOT / 'app/experiments/physical-012'
STAGES = ('validation', 'test')
BANKS = ('recency', 'conditional')
METHODS = ('raw_nwp', 'recency_robust', 'recency_pooled', 'conditional_robust', 'conditional_pooled')
HOURS = {'validation': 3566, 'test': 3567}
COMMON = {'validation': 3419, 'test': 3517}
DAYS = {'validation': 150, 'test': 149}
POOL_DAYS = {'validation': 444, 'test': 584}
CUTOFF = {'validation': datetime(2025, 12, 4), 'test': datetime(2026, 5, 2)}
BUDGET_SECONDS = 1800


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    if isinstance(value, Fraction):
        return {'numerator': value.numerator, 'denominator': value.denominator, 'value': float(value)}
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def dump(value):
    return json.dumps(value, default=encoded, allow_nan=False, separators=(',', ':'))


def save(path, value):
    Path(path).write_text(json.dumps(value, default=encoded, indent=2, allow_nan=False) + '\n')


def dt(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is not None:
        raise ValueError('Expected fixed UTC+03 naive source clock')
    return result


def rows(path):
    with Path(path).open(newline='') as source:
        return list(csv.DictReader(source))


def unique_map(records, key):
    result = {}
    for row in records:
        identity = dt(row[key])
        if identity in result:
            raise ValueError('Duplicate target identity')
        result[identity] = row
    return result


def number(value, optional=False):
    if optional and value == '':
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Nonfinite source value')
    return result


def bit(value):
    if value not in ('0', '1'):
        raise ValueError('Invalid binary source value')
    return value == '1'


def input_paths():
    files = [HERE / name for name in ('PROTOCOL.md', 'run.py', 'decision.py', 'test_decision.py', 'test_runner.py')]
    files += [PREVIOUS / name for name in ('PROTOCOL.md', 'inputs.json', 'result/planning-freeze.json', 'result/outputs.json')]
    files += [ROOT / name for name in ('app/experiments/f1-008/result/features.csv',
        'app/experiments/f1-006/result/feature-targets.csv',
        'app/experiments/reference-training-001/result/joined-reference.csv',
        'app/experiments/f1-008/result/validation-selection.json',
        'app/experiments/f1-009/result/validation-selection.json',
        'eval/cv_predictions.csv', 'eval/test_predictions.csv',
        'app/experiments/research-2026-10-04/variable-count-event-review.md',
        'app/experiments/research-2026-10-04/variable-count-event-sources.json',
        'app/experiments/research-2026-10-04/variable-count-event-protocol.md')]
    for stage in STAGES:
        files += [PREVIOUS / f'result/{stage}/{name}' for name in ('bank.npz', 'plans.npz', 'scenario-replay.npz', 'plan-metadata.csv')]
        files += [ROOT / f'app/experiments/f1-008/result/predictions/{stage}-consensus_two_source.csv',
            ROOT / f'app/experiments/f1-009/result/predictions/{stage}-joint.csv',
            ROOT / f'app/experiments/f1-009/result/{stage}-reference-membership.csv']
    return files


def freeze_inputs():
    destination = HERE / 'inputs.json'
    if destination.exists():
        raise FileExistsError(destination)
    pins = {str(path.relative_to(ROOT)): sha(path) for path in input_paths()}
    save(destination, pins)
    print('INPUTS_FROZEN', len(pins), sha(destination))


def verify_inputs():
    pins = json.loads((HERE / 'inputs.json').read_text())
    if set(pins) != {str(path.relative_to(ROOT)) for path in input_paths()}:
        raise ValueError('Unexpected pinned input set')
    for name, digest in pins.items():
        if sha(ROOT / name) != digest:
            raise ValueError('Changed frozen input: ' + name)
    previous = json.loads((PREVIOUS / 'inputs.json').read_text())
    for name in set(previous) & set(pins):
        if pins[name] != previous[name]:
            raise ValueError('Changed 012 pinned source: ' + name)
    return pins


def features():
    records = rows(ROOT / 'app/experiments/f1-008/result/features.csv')
    origins = [dt(row['feature_time']) for row in records]
    targets = [origin + timedelta(hours=24) for origin in origins]
    forecast = np.asarray([number(row['nwp_day2_radiation']) for row in records])
    if len(origins) != 17832 or len(set(origins)) != len(origins):
        raise ValueError('Original source membership')
    if any(b - a != timedelta(hours=1) for a, b in zip(targets, targets[1:])):
        raise ValueError('Original source chronology')
    if np.any(forecast < 0):
        raise ValueError('Invalid raw forecast')
    return origins, targets, forecast


def forecast_package(stage, targets, forecast):
    """Read forecast/history artifacts only, never evaluation references or masks."""
    freeze = json.loads((PREVIOUS / 'result/planning-freeze.json').read_text())['files_sha256']
    outputs = json.loads((PREVIOUS / 'result/outputs.json').read_text())
    for name in ('bank.npz', 'plans.npz', 'scenario-replay.npz', 'plan-metadata.csv'):
        key = f'{stage}/{name}'
        actual = sha(PREVIOUS / 'result' / key)
        if freeze[key] != actual or outputs[key] != actual:
            raise ValueError('012 pre-scoring identity: ' + key)
    directory = PREVIOUS / 'result' / stage
    with np.load(directory / 'plans.npz', allow_pickle=False) as source:
        positions = source['target_positions']
        raw = source['raw_forecast_ghi']
    with np.load(directory / 'scenario-replay.npz', allow_pickle=False) as source:
        all_scenarios = source['unclipped_ghi']
    if positions.shape != (DAYS[stage], 24) or positions.dtype.kind not in 'iu':
        raise ValueError('Target position dimensions')
    if positions.min() < 0 or positions.max() >= len(targets) or len(set(positions.flat)) != positions.size:
        raise ValueError('Invalid or duplicate positions')
    if raw.shape != positions.shape or not np.array_equal(raw, forecast[positions]):
        raise ValueError('Raw forecast identity')
    if all_scenarios.shape != (DAYS[stage], 2, 2, 2, 64, 24) or not np.isfinite(all_scenarios).all():
        raise ValueError('Scenario dimensions or values')
    scenarios = all_scenarios[:, :, 0].copy()
    del all_scenarios
    metadata = rows(directory / 'plan-metadata.csv')
    with np.load(directory / 'bank.npz', allow_pickle=False) as source:
        pool_positions = source['pool_source_positions']
        pool_times = source['pool_source_target_time']
        pool_days = source['pool_source_days']
        pool_nwp = source['pool_nwp']
        residuals = source['pool_residuals']
        recency = source['recency_pool_indices']
        conditional = source['conditional_pool_indices']
    if pool_positions.ndim != 2 or pool_positions.shape[1] != 24 or pool_positions.dtype.kind not in 'iu':
        raise ValueError('Historical position dimensions')
    n = len(pool_positions)
    if n != POOL_DAYS[stage] or pool_times.shape != (n, 24) or pool_days.shape != (n,) or pool_times.dtype.kind != 'U' or pool_days.dtype.kind != 'U':
        raise ValueError('Historical pool identity')
    if pool_positions.min() < 0 or pool_positions.max() >= len(targets) or len(set(pool_positions.flat)) != pool_positions.size:
        raise ValueError('Historical positions')
    expected_times = np.asarray([str(targets[i]) for i in pool_positions.flat], dtype='U19').reshape(n, 24)
    if not np.array_equal(pool_times, expected_times) or any(dt(t) >= CUTOFF[stage] for t in pool_times.flat):
        raise ValueError('Historical cutoff or timestamps')
    for i, stamp in enumerate(pool_days):
        day = dt(str(stamp))
        if day.hour != 0 or [dt(t) for t in pool_times[i]] != [day + timedelta(hours=h) for h in range(24)]:
            raise ValueError('Historical complete-day identity')
        if i and stamp <= pool_days[i - 1]:
            raise ValueError('Historical day order')
    if pool_nwp.shape != (n, 24) or not np.array_equal(pool_nwp, forecast[pool_positions]):
        raise ValueError('Historical NWP identity')
    if residuals.shape != (2, n, 24) or not np.isfinite(residuals).all():
        raise ValueError('Historical paired residuals')
    if not np.array_equal(recency, np.arange(n - 64, n)) or conditional.shape != (DAYS[stage], 64):
        raise ValueError('Retained selection dimensions')
    if len(metadata) != DAYS[stage] or len(set(pool_days)) != n:
        raise ValueError('Historical day metadata')
    selected_days = []
    for d, indices in enumerate(positions):
        times = [targets[i] for i in indices]
        day = times[0]
        if day.hour != 0 or times != [day + timedelta(hours=h) for h in range(24)]:
            raise ValueError('Incomplete forecast horizon')
        if d and day != targets[positions[d - 1, 0]] + timedelta(days=1):
            raise ValueError('Nonconsecutive forecast days')
        issue = day - timedelta(days=1)
        if issue < CUTOFF[stage] or (d == 0 and issue != CUTOFF[stage]):
            raise ValueError('Forecast cutoff')
        meta = metadata[d]
        if meta['day'] != day.date().isoformat() or dt(meta['issue_time']) != issue:
            raise ValueError('Issue metadata')
        if dt(meta['maximum_nwp_nominal_time']) != issue - timedelta(hours=1):
            raise ValueError('Nominal NWP clock')
        issue_utc = issue.replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc)
        if datetime.fromisoformat(meta['issue_utc']) != issue_utc or dt(meta['interval_start']) != day - timedelta(hours=1) or dt(meta['interval_end']) != day + timedelta(hours=23):
            raise ValueError('Issue UTC or interval endpoints')
        selected = []
        for b, choice in enumerate((recency, conditional[d])):
            if choice.dtype.kind not in 'iu' or np.any(choice < 0) or np.any(choice >= n) or len(set(choice)) != 64 or np.any(np.diff(choice) <= 0):
                raise ValueError('Canonical selected days')
            expected = raw[d][None, None, :] + residuals[:, choice]
            if not np.array_equal(expected, scenarios[d, b]):
                raise ValueError('Retained scenario reconstruction')
            selected.append(pool_days[choice].tolist())
        if dt(meta['maximum_selected_source_time']) != max(dt(t) for t in pool_times[conditional[d]].flat):
            raise ValueError('Selected source availability clock')
        selected_days.append(selected)
    return dict(positions=positions, raw=raw, scenarios=scenarios, metadata=metadata, selected_days=selected_days)


def complexity(package):
    result = {}
    for b, bank in enumerate(BANKS):
        counts, extra_raw = [], 0
        for d, scenario in enumerate(package['scenarios'][:, b]):
            events = scenario > 600
            ones, zeroes = events.all(axis=(0, 1)), ~events.any(axis=(0, 1))
            uncertain = ~(ones | zeroes)
            counts.append(int(uncertain.sum()))
            raw = package['raw'][d] > 600
            extra_raw += int(np.any(~raw & ones) or np.any(raw & zeroes))
        result[bank] = dict(uncertain_hours=counts, max_uncertain_hours=max(counts), canonical_subsets=sum(2 ** count for count in counts), extra_noncanonical_raw_candidates=extra_raw)
    return result


def direct_expected(events, action):
    answer = []
    k = sum(bool(v) for v in action)
    for reference in events:
        counts = [int(row.sum()) for row in reference]
        tps = [int(np.sum(row & action)) for row in reference]
        nonempty = sum(s > 0 for s in counts)
        answer.append(dict(precision=sum((Fraction(tp, k) for tp in tps), Fraction()) / len(tps) if k else None,
            recall=sum((Fraction(tp, s) for tp, s in zip(tps, counts) if s), Fraction()) / nonempty if nonempty else None,
            f1=sum((Fraction(2 * tp, s + k) if s + k else Fraction(1) for tp, s in zip(tps, counts)), Fraction()) / len(tps)))
    return answer


def event_metrics(truth, predicted):
    if len(truth) != len(predicted):
        raise ValueError('Metric row mismatch')
    tp = sum(bool(t) and bool(p) for t, p in zip(truth, predicted))
    fp = sum(not bool(t) and bool(p) for t, p in zip(truth, predicted))
    fn = sum(bool(t) and not bool(p) for t, p in zip(truth, predicted))
    return dict(hours=len(truth), tp=tp, fp=fp, fn=fn, tn=len(truth) - tp - fp - fn,
        positive_calls=tp + fp, precision=Fraction(tp, tp + fp) if tp + fp else None,
        recall=Fraction(tp, tp + fn) if tp + fn else None,
        f1=Fraction(2 * tp, 2 * tp + fp + fn) if 2 * tp + fp + fn else None)


def comparison(candidate, control):
    differences, assessable = {}, True
    for ref in ('weather_full', 'satellite_common'):
        for name in ('precision', 'recall', 'f1'):
            a, b = candidate[ref][name], control[ref][name]
            assessable &= a is not None and b is not None
            differences[ref + '/' + name] = None if a is None or b is None else a - b
    valid = [v for v in differences.values() if v is not None]
    return dict(assessable=assessable, nonregression=assessable and all(v >= 0 for v in valid),
        strict_gain=assessable and any(v > 0 for v in valid), all_six_strict=assessable and all(v > 0 for v in valid),
        passed=assessable and all(v >= 0 for v in valid) and any(v > 0 for v in valid), differences=differences)


def write_csv(path, records):
    if not records:
        raise ValueError('Empty CSV output')
    with Path(path).open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def references(origins, targets):
    observed = rows(ROOT / 'app/experiments/f1-006/result/feature-targets.csv')
    joined = rows(ROOT / 'app/experiments/reference-training-001/result/joined-reference.csv')
    if len(observed) != len(targets) or len(joined) != len(targets):
        raise ValueError('Reference row membership')
    weather, satellite = [], []
    for i, (a, b) in enumerate(zip(observed, joined)):
        if any(dt(r['feature_time']) != origins[i] or dt(r['target_time']) != targets[i] for r in (a, b)):
            raise ValueError('Reference time join')
        valid = targets[i].replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc)
        if datetime.fromisoformat(b['valid_time_utc']) != valid or datetime.fromisoformat(b['interval_start_utc']) != valid - timedelta(hours=1):
            raise ValueError('Reference UTC alignment')
        w, s = number(a['actual']), number(b['satellite_w_m2'], True)
        if w != number(b['weather_actual_w_m2']) or bit(b['is_missing']) != (s is None) or w < 0 or (s is not None and s < 0):
            raise ValueError('Reference value or missingness')
        weather.append(w)
        satellite.append(s)
    return weather, satellite


def context_decisions(stage, expected, nwp, weather, satellite):
    selected008 = json.loads((ROOT / 'app/experiments/f1-008/result/validation-selection.json').read_text())
    selected009 = json.loads((ROOT / 'app/experiments/f1-009/result/validation-selection.json').read_text())
    if selected008['selected_augmented_arm'] != 'consensus_two_source' or selected009['selected_arm'] != 'joint':
        raise ValueError('Changed selected context arm')
    answer = {}
    for experiment, arm, field, selection in (('008', 'consensus_two_source', 'weather_actual_w_m2', selected008), ('009', 'joint', 'weather_w_m2', selected009)):
        source = unique_map(rows(ROOT / f'app/experiments/f1-{experiment}/result/predictions/{stage}-{arm}.csv'), 'target_time')
        if set(source) != set(expected):
            raise ValueError('Context target membership')
        policy = selection['policies'][arm]['policy']
        prediction = []
        for j, target in enumerate(expected):
            row = source[target]
            p = number(row['probability'])
            if not 0 <= p <= 1 or number(row[field]) != weather[j] or number(row['satellite_w_m2'], True) != satellite[j]:
                raise ValueError('Context reference identity')
            if dt(row['feature_time']) + timedelta(hours=24) != target or bit(row['nwp_positive']) != nwp[j]:
                raise ValueError('Context issue or raw event identity')
            call = nwp[j] if policy['kind'] == 'control' else ((nwp[j] and p > policy['lower']) or (not nwp[j] and p > policy['upper']))
            if bit(row['predicted_positive']) != call:
                raise ValueError('Context frozen cutoff mismatch')
            prediction.append(call)
        answer['f1_' + experiment + '_selected'] = prediction
    return answer


def score_stage(stage, origins, targets, forecast, package, calls, weather, satellite, out):
    filename = 'cv_predictions.csv' if stage == 'validation' else 'test_predictions.csv'
    source = rows(ROOT / 'eval' / filename)
    original = unique_map(source, 'time')
    origin_index = {value: i for i, value in enumerate(origins)}
    if len(original) != HOURS[stage] or any(origin not in origin_index for origin in original) or list(original) != sorted(original):
        raise ValueError('Original evaluation membership')
    selected_positions = [origin_index[dt(row['time'])] for row in source]
    planned = {int(position): (d, h) for d, day in enumerate(package['positions']) for h, position in enumerate(day)}
    if any(i not in planned for i in selected_positions):
        raise ValueError('Unplanned original target')
    expected = [targets[i] for i in selected_positions]
    w, s = [weather[i] for i in selected_positions], [satellite[i] for i in selected_positions]
    nwp = [bool(forecast[i] > 600) for i in selected_positions]
    if any(number(row['actual']) != value for row, value in zip(source, w)):
        raise ValueError('Original reference equality')
    member = unique_map(rows(ROOT / f'app/experiments/f1-009/result/{stage}-reference-membership.csv'), 'target_time')
    if set(member) != set(expected):
        raise ValueError('Frozen reference mask membership')
    for j, target in enumerate(expected):
        row = member[target]
        if dt(row['feature_time']) + timedelta(hours=24) != target:
            raise ValueError('Frozen reference feature time')
        if number(row['weather_w_m2']) != w[j] or number(row['satellite_w_m2'], True) != s[j] or bit(row['satellite_available']) != (s[j] is not None):
            raise ValueError('Frozen reference mask values')
    common = [j for j, value in enumerate(s) if value is not None]
    if len(common) != COMMON[stage]:
        raise ValueError('Reference common-hour count')
    methods = {name: [bool(calls[planned[i][0], m, planned[i][1]]) for i in selected_positions] for m, name in enumerate(METHODS)}
    if methods['raw_nwp'] != nwp:
        raise ValueError('Planned raw calls differ')
    methods.update(original=[number(row['predicted']) > 600 for row in source], persistence=[number(row['baseline']) > 600 for row in source])
    methods.update(context_decisions(stage, expected, nwp, w, s))
    metrics = {}
    for method, predicted in methods.items():
        metrics[method] = dict(weather_full=event_metrics([v > 600 for v in w], predicted),
            weather_common=event_metrics([w[j] > 600 for j in common], [predicted[j] for j in common]),
            satellite_common=event_metrics([s[j] > 600 for j in common], [predicted[j] for j in common]))
    predictions = []
    for j, i in enumerate(selected_positions):
        item = dict(source_position=i, feature_time=str(origins[i]), target_time=str(targets[i]),
            weather_w_m2=w[j], satellite_w_m2=s[j], satellite_available=int(s[j] is not None))
        item.update({method: int(predicted[j]) for method, predicted in methods.items()})
        predictions.append(item)
    write_csv(out / stage / 'predictions.csv', predictions)
    selected_set = set(selected_positions)
    membership, daily = [], []
    for d, indices in enumerate(package['positions']):
        for h, i in enumerate(indices):
            membership.append(dict(source_position=int(i), target_time=str(targets[i]), original_period=int(i in selected_set), satellite_available=int(satellite[i] is not None)))
        for subset, reference in (('weather_full', weather), ('weather_common', weather), ('satellite_common', satellite)):
            mask = [h for h, i in enumerate(indices) if i in selected_set and (subset == 'weather_full' or satellite[i] is not None)]
            period_index = {position: j for j, position in enumerate(selected_positions)}
            for method, predicted in methods.items():
                counts = event_metrics([reference[indices[h]] > 600 for h in mask], [predicted[period_index[int(indices[h])]] for h in mask])
                daily.append(dict(day=package['metadata'][d]['day'], subset=subset, method=method, **counts))
    write_csv(out / stage / 'evaluation-membership.csv', membership)
    save(out / stage / 'daily-metrics.json', daily)
    corrections = {name: dict(additions=sum(p and not b for p, b in zip(predicted, nwp)), removals=sum(b and not p for p, b in zip(predicted, nwp)),
        changed_full_day_counts=sum(int(calls[d, METHODS.index(name)].sum()) != int(calls[d, 0].sum()) for d in range(len(calls))) if name in METHODS else None) for name, predicted in methods.items()}
    comparisons = {method: {control: comparison(metrics[method], metrics[control]) for control in ('raw_nwp', 'original', 'persistence', 'f1_008_selected', 'f1_009_selected')} for method in METHODS[1:]}
    return dict(hours=len(expected), common_hours=len(common), missing_satellite_hours=len(expected) - len(common), planned_hours=int(package['positions'].size), padding_hours=int(package['positions'].size) - len(expected), metrics=metrics, corrections=corrections, comparisons=comparisons)


def gz_lines(path):
    return io.TextIOWrapper(gzip.GzipFile(filename=str(path), mode='xb', mtime=0), encoding='utf-8')


def execute(out, complexity_only=False):
    start, cpu = time.perf_counter(), time.process_time()
    deadline = time.monotonic() + BUDGET_SECONDS
    out = Path(out).resolve()
    if HERE not in out.parents:
        raise ValueError('Output must be inside experiment')
    out.mkdir(exist_ok=False)
    receipt = dict(started_at_utc=now(), command=sys.argv, status='VERIFYING_INPUTS', outcome_scoring_started=False,
        mode='complexity_only' if complexity_only else 'experiment', total_runtime_budget_seconds=BUDGET_SECONDS, thread_limits={v: os.environ[v] for v in THREAD_LIMITS}, versions=dict(python=platform.python_version(), numpy=np.__version__))
    save(out / 'execution-start.json', receipt)
    phase = out / 'events.jsonl'
    def event(name, **fields):
        with phase.open('a') as stream:
            stream.write(dump(dict(at_utc=now(), event=name, **fields)) + '\n')
    event('START', outcome_scoring_started=False)
    def timeout(signum, frame):
        raise TimeoutError('Predeclared total runtime budget exhausted')
    previous_handler = signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, max(0.000001, deadline - time.monotonic()))
    try:
        pins = verify_inputs()
        receipt.update(protocol_sha256=sha(HERE / 'PROTOCOL.md'), input_lock_sha256=sha(HERE / 'inputs.json'), input_sha256=pins)
        origins, targets, forecast = features()
        packages, decisions, diagnostic = {}, {}, {}
        for stage in STAGES:
            if time.perf_counter() - start > BUDGET_SECONDS:
                raise TimeoutError('Predeclared runtime budget exhausted before scoring')
            package = forecast_package(stage, targets, forecast)
            packages[stage] = package
            diagnostic[stage] = complexity(package)
        diagnostic['total_canonical_subsets'] = sum(diagnostic[s][b]['canonical_subsets'] for s in STAGES for b in BANKS)
        diagnostic['total_extra_noncanonical_raw_candidates'] = sum(diagnostic[s][b]['extra_noncanonical_raw_candidates'] for s in STAGES for b in BANKS)
        diagnostic['scope'] = 'Saved scenario event-label complexity only. No realized references, candidate actions or scores.'
        save(out / 'complexity.json', diagnostic)
        event('FORECAST_INPUTS_VERIFIED', canonical_subsets=diagnostic['total_canonical_subsets'])
        if complexity_only:
            receipt['status'] = 'COMPLETE_COMPLEXITY_ONLY'
        else:
            from decision import solve
            for stage in STAGES:
                package = packages[stage]
                directory = out / stage
                directory.mkdir()
                calls = np.empty((DAYS[stage], len(METHODS), 24), dtype=bool)
                with gz_lines(directory / 'decisions.jsonl.gz') as records:
                    for d, day in enumerate(package['metadata']):
                        if time.perf_counter() - start > BUDGET_SECONDS:
                            raise TimeoutError('Predeclared runtime budget exhausted before scoring')
                        raw = package['raw'][d] > 600
                        calls[d, 0] = raw
                        for b, bank in enumerate(BANKS):
                            events = package['scenarios'][d, b] > 600
                            result = solve(events, raw, deadline=deadline)
                            if result['raw_metrics'] != direct_expected(events, raw):
                                raise AssertionError('Direct raw-score verification')
                            for a, arm in enumerate(('robust', 'pooled')):
                                selected = result['arms'][arm]
                                action = np.asarray(selected['decision'], dtype=bool)
                                if action.shape != (24,) or selected['metrics'] != direct_expected(events, action):
                                    raise AssertionError('Direct selected-score verification')
                                for current, baseline in zip(direct_expected(events, action), result['raw_metrics']):
                                    if any(baseline[name] is not None and (current[name] is None or current[name] < baseline[name]) for name in ('precision', 'recall', 'f1')):
                                        raise AssertionError('Direct selected safeguard verification')
                                if not action.any() and raw.any():
                                    raise AssertionError('Prohibited zero-call action')
                                calls[d, 1 + 2 * b + a] = action
                            records.write(dump(dict(stage=stage, day=day['day'], bank=bank,
                                issue_time=day['issue_time'], source_days=package['selected_days'][d][b], **result)) + '\n')
                        if (d + 1) % 25 == 0:
                            records.flush()
                            event('DECISION_PROGRESS', stage=stage, horizons=d + 1, outcome_scoring_started=False)
                            print('PLANNED', stage, d + 1, flush=True)
                np.savez_compressed(directory / 'calls.npz', calls=calls, methods=np.asarray(METHODS), target_positions=package['positions'])
                write_csv(directory / 'calls.csv', [dict(day=package['metadata'][d]['day'], target_time=str(targets[i]), source_position=int(i),
                    **{name: int(calls[d, m, h]) for m, name in enumerate(METHODS)}) for d, day in enumerate(package['positions']) for h, i in enumerate(day)])
                decisions[stage] = calls
            verify_inputs()
            planned = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name not in ('events.jsonl', 'execution-start.json')}
            save(out / 'planning-freeze.json', dict(frozen_at_utc=now(), files_sha256=planned, statement='Both periods and all four fixed arms complete before loading evaluation references, masks or context predictions.'))
            event('ALL_DECISIONS_FROZEN', planning_freeze_sha256=sha(out / 'planning-freeze.json'), outcome_scoring_started=False)
            receipt['outcome_scoring_started'] = True
            event('SCORING_REFERENCES_OPENED', outcome_scoring_started=True)
            weather, satellite = references(origins, targets)
            report = dict(status='COMPLETE', scope='Retrospective event decisions on previously inspected estimated references. No model fit, live evidence, physical dispatch or novelty claim.',
                methods=METHODS, protocol_sha256=receipt['protocol_sha256'], input_lock_sha256=receipt['input_lock_sha256'], splits={})
            for stage in STAGES:
                report['splits'][stage] = score_stage(stage, origins, targets, forecast, packages[stage], decisions[stage], weather, satellite, out)
            report['gates'] = {method: dict(raw_control_both_periods=all(report['splits'][s]['comparisons'][method]['raw_nwp']['passed'] for s in STAGES),
                all_six_strict_both_periods=all(report['splits'][s]['comparisons'][method]['raw_nwp']['all_six_strict'] for s in STAGES)) for method in METHODS[1:]}
            report['primary_method'] = 'conditional_robust'
            report['context_information_limit'] = 'Original, persistence, 008 and 009 use later rolling issuance information. They are same-hour context benchmarks, not matched issue-time controls.'
            save(out / 'report.json', report)
            receipt['status'] = 'COMPLETE'
        verify_inputs()
        receipt['exit_code'] = 0
        event('COMPLETE', outcome_scoring_started=receipt['outcome_scoring_started'])
    except BaseException as error:
        receipt.update(status='FAILED', exit_code=1, error_type=type(error).__name__, error=str(error))
        event('FAILED', error_type=type(error).__name__, error=str(error), outcome_scoring_started=receipt['outcome_scoring_started'])
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        receipt.update(finished_at_utc=now(), elapsed_seconds=time.perf_counter() - start, cpu_seconds=time.process_time() - cpu,
            peak_rss_bytes=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * (1 if sys.platform == 'darwin' else 1024), peak_rss_convention='macOS bytes, Linux KiB converted to bytes')
        save(out / 'execution-receipt.json', receipt)
        save(out / 'outputs.json', {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'outputs.json'})
    print(receipt['status'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path)
    parser.add_argument('--complexity', action='store_true')
    parser.add_argument('--freeze-inputs', action='store_true')
    args = parser.parse_args()
    if args.freeze_inputs:
        if args.out or args.complexity:
            parser.error('Input freeze is a separate action')
        freeze_inputs()
    else:
        if args.out is None:
            parser.error('--out is required')
        execute(args.out, args.complexity)
