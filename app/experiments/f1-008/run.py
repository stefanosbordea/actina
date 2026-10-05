"""Frozen two-forecast ablation with separate event correction thresholds."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys

sys.dont_write_bytecode = True

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('joint007', HERE.parent / 'f1-007/run.py')
joint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(joint)
score, fraction = joint.score, joint.fraction
ARMS = ('weather_ecmwf', 'consensus_ecmwf', 'weather_two_source', 'consensus_two_source')
BASES = ('weather_full', 'satellite_common')


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return pd.read_csv(path, float_precision='round_trip')
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
def now(): return datetime.now(timezone.utc).isoformat()


def decide(baseline, probability, policy):
    if policy['kind'] == 'control': return baseline.copy()
    return (baseline & (probability > policy['lower'])) | (~baseline & (probability > policy['upper']))


def metrics(decision, weather, satellite, probability=None):
    available = np.isfinite(satellite)
    return {'weather_full': score(weather > 600, decision, probability),
            'weather_common': score(weather[available] > 600, decision[available], probability[available] if probability is not None else None),
            'satellite_common': score(satellite[available] > 600, decision[available], probability[available] if probability is not None else None)}


def rank(record):
    return (*joint.rank({'metrics': {b: record['metrics'][b] for b in BASES}}), -record['changed'])


def select(baseline, probability, weather, satellite):
    control = metrics(baseline, weather, satellite)
    restricted = {b: control[b] for b in BASES}
    grid = []
    for lower in range(11):
        for upper in range(10, 21):
            policy = {'kind': 'correction', 'lower': lower / 20, 'upper': upper / 20}
            decision = decide(baseline, probability, policy)
            m = metrics(decision, weather, satellite)
            check = joint.test_gate({b: m[b] for b in BASES}, restricted)
            grid.append({'policy': policy, 'metrics': m, 'changed': int(np.sum(decision != baseline)),
                         'qualifies': joint.qualifies({b: m[b] for b in BASES}, restricted),
                         'strict_gain': check['passes_frozen_gate']})
    eligible = [r for r in grid if r['strict_gain']]
    if not eligible:
        return {'policy': {'kind': 'control'}, 'metrics': control, 'changed': 0, 'qualifies': True, 'strict_gain': False}, grid
    return max(eligible, key=lambda r: (*rank(r), r['policy']['upper'], -r['policy']['lower'])), grid


def main(out):
    pins = json.loads((HERE / 'inputs.json').read_text())
    for name, expected in pins.items():
        if sha(ROOT / name) != expected: raise ValueError('Changed pinned input: ' + name)
    if HERE not in out.parents: raise ValueError('Output must be inside this experiment')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'models').mkdir(); (out / 'predictions').mkdir()
    features = read(HERE.parent / 'f1-006/result/features.csv')
    targets = read(HERE.parent / 'f1-006/result/feature-targets.csv')
    reference = read(HERE.parent / 'reference-training-001/result/joined-reference.csv')
    gfs = read(HERE.parent / 'nwp-alternative-001/result/radiation-only.csv')
    if len(features) != 17832 or any(len(v) != len(features) for v in (targets, reference, gfs)): raise ValueError('Row count')
    for other in (targets, reference, gfs):
        if not features.feature_time.equals(other.feature_time): raise ValueError('Origin membership')
    if not features.feature_time.is_unique or not targets.target_time.equals(gfs.target_time): raise ValueError('Duplicate/time mismatch')
    origin = pd.to_datetime(features.feature_time)
    target = pd.to_datetime(targets.target_time)
    epoch = target.dt.tz_localize('Etc/GMT-3').map(lambda t: int(t.timestamp())).to_numpy()
    if not (target == origin + pd.Timedelta(hours=24)).all() or not (origin.diff().dropna() == pd.Timedelta(hours=1)).all(): raise ValueError('Horizon')
    if not np.array_equal(epoch, targets.target_epoch_utc) or not np.array_equal(epoch, gfs.target_epoch_utc): raise ValueError('UTC mapping')
    if not np.array_equal(targets.actual, reference.weather_actual_w_m2): raise ValueError('Reference mismatch')
    raw = json.loads((HERE.parent / 'nwp-alternative-001/result/response.json').read_text())['hourly']
    lookup = dict(zip(raw['time'], raw['shortwave_radiation_previous_day2']))
    radiation = gfs.gfs_day2_radiation_w_m2.to_numpy()
    if not np.array_equal(radiation, [lookup[int(t)] for t in epoch]) or not np.isfinite(radiation).all() or np.any(radiation < 0): raise ValueError('Raw GFS mismatch')
    x = features.drop(columns='feature_time').copy()
    if len(x.columns) != 24: raise ValueError('Changed base feature schema')
    x['gfs_day2_radiation'] = radiation
    x['gfs_minus_ecmwf'] = radiation - x.nwp_day2_radiation
    x['gfs_ecmwf_absolute_difference'] = abs(x.gfs_minus_ecmwf)
    if np.isinf(x.to_numpy()).any(): raise ValueError('Infinite feature')
    pd.concat([features[['feature_time']], x], axis=1).to_csv(out / 'features.csv', index=False)
    report = {'status': 'RUNNING', 'started_at_utc': now(), 'command': [sys.executable, *sys.argv],
              'code_sha256': sha(Path(__file__)), 'protocol_sha256': sha(HERE / 'PROTOCOL.md'), 'inputs_sha256': pins,
              'features': list(x.columns), 'scope': 'Exploratory historical comparison; already-inspected test; operational availability unverified.',
              'versions': {'python': platform.python_version(), 'lightgbm': lgb.__version__, 'numpy': np.__version__, 'pandas': pd.__version__},
              'configuration': joint.CONFIGS['larger'], 'splits': {}, 'methods': {}, 'irradiance_baselines': {}}
    policies = {}; selected = None
    for stage, filename in (('validation', 'cv_predictions.csv'), ('test', 'test_predictions.csv')):
        if stage == 'test' and sha(out / 'validation-selection.json') != report['selection_sha256']: raise ValueError('Selection changed')
        split = read(ROOT / 'eval' / filename)
        names = split.iloc[:, 0]
        positions = pd.Index(features.feature_time).get_indexer(names)
        if (positions < 0).any() or not names.is_unique or len(names) != {'validation': 3566, 'test': 3567}[stage]: raise ValueError('Split membership')
        if not np.array_equal(targets.actual.iloc[positions], split.actual): raise ValueError('Split truth')
        train = np.flatnonzero(target < pd.Timestamp(names.iloc[0]))
        labels = read(HERE.parent / f'f1-007/result/{stage}-training-labels.csv')
        if not np.array_equal(features.feature_time.iloc[train], labels.feature_time): raise ValueError('Training membership')
        weather_event = targets.actual.iloc[train].to_numpy() > 600
        sat_train = reference.satellite_w_m2.iloc[train].to_numpy()
        soft = np.where(np.isfinite(sat_train), (weather_event.astype(float) + (sat_train > 600)) / 2, weather_event.astype(float))
        if not np.array_equal(soft, labels.soft_target) or not np.array_equal(weather_event, labels.weather_event.astype(bool)): raise ValueError('Soft target')
        labels.to_csv(out / f'{stage}-training-labels.csv', index=False)
        weather = split.actual.to_numpy()
        satellite = reference.satellite_w_m2.iloc[positions].to_numpy()
        member = read(HERE.parent / f'f1-007/result/{stage}-reference-membership.csv')
        if not np.array_equal(satellite, member.satellite_w_m2, equal_nan=True): raise ValueError('Satellite membership')
        member.to_csv(out / f'{stage}-reference-membership.csv', index=False)
        nwp = x.nwp_day2_radiation.iloc[positions].to_numpy()
        baseline = nwp > 600
        report['splits'][stage] = {'hours': len(split), 'training_hours': len(train), 'satellite_hours': int(np.isfinite(satellite).sum()),
                                  'latest_training_target': str(target.iloc[train[-1]]), 'first_origin': names.iloc[0]}
        for name, values in (('ecmwf', nwp), ('gfs', radiation[positions]), ('arithmetic_mean', (nwp + radiation[positions]) / 2)):
            m = metrics(values > 600, weather, satellite)
            for basis, actual, mask in (('weather_full', weather, np.ones(len(weather), dtype=bool)), ('weather_common', weather, np.isfinite(satellite)), ('satellite_common', satellite, np.isfinite(satellite))):
                error = values[mask] - actual[mask]
                m[basis].update(mae=float(np.mean(abs(error))), rmse=float(np.sqrt(np.mean(error ** 2))))
            report['irradiance_baselines'].setdefault(name, {})[stage] = m
        for name in ('original', 'persistence', 'nwp_day2'):
            old = read(HERE.parent / f'f1-006/result/predictions/{stage}-{name}.csv')
            if not np.array_equal(old.feature_time, names): raise ValueError('Control order')
            p = old.probability.to_numpy()
            report['methods'].setdefault(name, {})[stage] = {'metrics': metrics(p > .5, weather, satellite)}
        for arm in ARMS:
            weather_only = arm.startswith('weather_')
            if arm.endswith('_two_source'):
                args = dict(**joint.CONFIGS['larger'], learning_rate=.03, reg_lambda=2, random_state=17, n_jobs=2,
                            deterministic=True, force_col_wise=True, verbosity=-1)
                model = lgb.LGBMClassifier(objective='binary', **args) if weather_only else lgb.LGBMRegressor(objective='cross_entropy', **args)
                model.fit(x.iloc[train], weather_event.astype(int) if weather_only else soft)
                p = model.predict_proba(x.iloc[positions])[:, 1] if weather_only else model.predict(x.iloc[positions])
                model.booster_.save_model(str(out / 'models' / f'{stage}-{arm}.txt'))
            else:
                old_path = f'f1-006/result/predictions/{stage}-larger.csv' if weather_only else f'f1-007/result/predictions/{stage}-consensus_larger.csv'
                old = read(HERE.parent / old_path)
                if not np.array_equal(old.feature_time, names): raise ValueError('Matched arm order')
                p = old.probability.to_numpy()
            if not np.isfinite(p).all() or np.any((p < 0) | (p > 1)): raise ValueError('Probability')
            if stage == 'validation':
                policies[arm], grid = select(baseline, p, weather, satellite)
                save(out / f'validation-grid-{arm}.json', grid)
            policy = policies[arm]['policy']
            decision = decide(baseline, p, policy)
            m = metrics(decision, weather, satellite, p)
            correction = {'added': int(np.sum(~baseline & decision)), 'removed': int(np.sum(baseline & ~decision)), 'changed': int(np.sum(decision != baseline))}
            transitions = {}
            for basis, actual, mask in (('weather_full', weather, np.ones(len(weather), dtype=bool)), ('weather_common', weather, np.isfinite(satellite)), ('satellite_common', satellite, np.isfinite(satellite))):
                positive = actual > 600
                added, removed = ~baseline & decision & mask, baseline & ~decision & mask
                transitions[basis] = {'misses_corrected': int(np.sum(added & positive)), 'false_alarms_added': int(np.sum(added & ~positive)),
                                      'false_alarms_removed': int(np.sum(removed & ~positive)), 'misses_added': int(np.sum(removed & positive))}
            report['methods'].setdefault(arm, {})[stage] = {'policy': policy, 'metrics': m, 'corrections': correction,
                                                         'transitions': transitions,
                                                         'default_0_5': metrics(p > .5, weather, satellite, p)}
            pd.DataFrame({'feature_time': names, 'target_time': targets.target_time.iloc[positions].to_numpy(), 'weather_actual_w_m2': weather,
                          'satellite_w_m2': satellite, 'probability': p, 'nwp_positive': baseline.astype(int),
                          'predicted_positive': decision.astype(int), 'default_positive': (p > .5).astype(int)}).to_csv(out / 'predictions' / f'{stage}-{arm}.csv', index=False)
            print(stage, arm, json.dumps({b: m[b] for b in BASES}), flush=True)
        if stage == 'validation':
            selected = max(('weather_two_source', 'consensus_two_source'), key=lambda a: (*rank(policies[a]), a == 'weather_two_source'))
            save(out / 'validation-selection.json', {'selected_augmented_arm': selected, 'policies': policies, 'frozen_at_utc': now(),
                                                    'protocol_sha256': report['protocol_sha256'], 'code_sha256': report['code_sha256']})
            report['selection_sha256'] = sha(out / 'validation-selection.json')
            report['selected_augmented_arm'] = selected
            print('FROZEN', selected, flush=True)
        save(out / 'report.json', report)
    candidate = {b: report['methods'][selected]['test']['metrics'][b] for b in BASES}
    control = {b: report['methods']['nwp_day2']['test']['metrics'][b] for b in BASES}
    paired_name = selected.replace('two_source', 'ecmwf')
    paired = {b: report['methods'][paired_name]['test']['metrics'][b] for b in BASES}
    report['test_gate'] = joint.test_gate(candidate, control)
    report['matched_ablation'] = {'method': paired_name, **joint.test_gate(candidate, paired)}
    report['recommendation'] = 'Research only; retain established product control pending independent review. No live or novelty claim.'
    for name, expected in pins.items():
        if sha(ROOT / name) != expected: raise ValueError('Input changed during execution: ' + name)
    report['status'] = 'COMPLETE'; report['completed_at_utc'] = now()
    report['outputs_sha256'] = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'report.json'}
    save(out / 'report.json', report)
    print('COMPLETE', json.dumps(report['test_gate']), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    main(parser.parse_args().output.resolve())
