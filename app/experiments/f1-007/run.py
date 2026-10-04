"""Fixed joint-reference soft labels and paired validation policy; no live claims."""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = ROOT / 'app/experiments/f1-006'
PROTOCOL_SHA = 'f6950483c4bc3864c4a902d9b1e230681011c634d02bd7474c025cec4aa461fc'
spec = importlib.util.spec_from_file_location('experiment006', OLD / 'run.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
CONFIGS = base.CONFIGS
score, fraction = base.score, base.fraction


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
def read(path): return pd.read_csv(path, float_precision='round_trip')
def now(): return datetime.now(timezone.utc).isoformat()


def joint_scores(probability, cutoff, weather, satellite):
    decision = probability > cutoff
    available = np.isfinite(satellite)
    return {'weather_full': score(weather > 600, decision),
            'satellite_common': score(satellite[available] > 600, decision[available])}


def qualifies(candidate, control):
    return all(fraction(candidate[b], k) >= 0 and fraction(candidate[b], k) >= fraction(control[b], k)
               for b in control for k in ('precision', 'recall', 'f1'))


def rank(record):
    values = record['metrics']
    f1 = [fraction(m, 'f1') for m in values.values()]
    return (min(f1), sum(f1, Fraction()) / 2,
            min(fraction(m, 'precision') for m in values.values()),
            min(fraction(m, 'recall') for m in values.values()))


def threshold(probability, weather, satellite, control):
    grid = []
    for cutoff in np.unique(np.r_[0., probability, 1.]):
        metrics = joint_scores(probability, cutoff, weather, satellite)
        grid.append({'cutoff': float(cutoff), 'metrics': metrics, 'qualifies': qualifies(metrics, control)})
    eligible = [r for r in grid if r['qualifies']]
    return max(eligible or grid, key=lambda r: (*rank(r), -abs(r['cutoff'] - .5), r['cutoff'])), grid


def choose(selected, family):
    eligible = [family + '_' + name for name in CONFIGS if selected[family + '_' + name]['qualifies']]
    return max(eligible, key=lambda name: (*rank(selected[name]), -list(CONFIGS).index(name.split('_')[1]))) if eligible else 'nwp_day2'


def test_gate(candidate, control):
    comparisons = []
    for basis in control:
        for metric in ('precision', 'recall', 'f1'):
            a, b = fraction(candidate[basis], metric), fraction(control[basis], metric)
            comparisons.append({'basis': basis, 'metric': metric, 'candidate': candidate[basis][metric],
                                'control': control[basis][metric],
                                'status': 'improved' if a > b else 'equal' if a == b else 'regressed'})
    return {'passes_frozen_gate': qualifies(candidate, control) and any(r['status'] == 'improved' for r in comparisons),
            'all_six_strictly_improved': all(r['status'] == 'improved' for r in comparisons), 'comparisons': comparisons}


def main(out):
    if sha(HERE / 'PROTOCOL.md') != PROTOCOL_SHA: raise ValueError('Changed protocol')
    pins = json.loads((HERE / 'inputs.json').read_text())
    for name, expected in pins.items():
        if sha(ROOT / name) != expected: raise ValueError('Changed input: ' + name)
    out.mkdir(parents=True, exist_ok=False)
    for name in ('models', 'predictions'): (out / name).mkdir()
    features = read(OLD / 'result/features.csv')
    targets = read(OLD / 'result/feature-targets.csv')
    joined = read(ROOT / 'app/experiments/reference-training-001/result/joined-reference.csv')
    original = read(ROOT / 'data/features.csv')
    if len(features) != 17832 or len(targets) != len(features) or len(joined) != len(features): raise ValueError('Changed row count')
    if not features.feature_time.is_unique or not features.feature_time.equals(targets.feature_time) or not features.feature_time.equals(joined.feature_time): raise ValueError('Changed row membership')
    if not features.feature_time.equals(original.iloc[:, 0]) or not np.array_equal(targets.actual, original.target): raise ValueError('Original data mismatch')
    origin = pd.to_datetime(features.feature_time)
    target = pd.to_datetime(targets.target_time)
    if not (target == origin + pd.Timedelta(hours=24)).all() or not (origin.diff().dropna() == pd.Timedelta(hours=1)).all(): raise ValueError('Invalid horizon')
    valid = target.dt.tz_localize('Etc/GMT-3').dt.tz_convert('UTC')
    if not valid.equals(pd.to_datetime(joined.valid_time_utc, utc=True)) or not target.equals(pd.to_datetime(joined.target_time)): raise ValueError('Reference timestamp mismatch')
    if not np.array_equal(targets.actual, joined.weather_actual_w_m2): raise ValueError('Weather reference mismatch')
    satellite_source = read(ROOT / 'app/experiments/satellite-reference-001/result/reference-full.csv')
    satellite_source.index = pd.to_datetime(satellite_source.valid_time_utc, utc=True)
    if not satellite_source.index.is_unique or not valid.isin(satellite_source.index).all(): raise ValueError('Missing or duplicate satellite timestamp')
    satellite = satellite_source.shortwave_radiation_w_m2.reindex(valid).to_numpy()
    if not np.array_equal(satellite, joined.satellite_w_m2.to_numpy(), equal_nan=True): raise ValueError('Changed satellite values')
    if np.isinf(satellite).any() or np.any(satellite < 0) or not np.array_equal(np.isnan(satellite), joined.is_missing.astype(bool)): raise ValueError('Invalid satellite missingness/value')
    x = features.drop(columns='feature_time')
    old_report = json.loads((OLD / 'result/report.json').read_text())
    if list(x.columns) != old_report['features'] or np.isinf(x.to_numpy()).any(): raise ValueError('Changed feature schema')
    report = {'status': 'RUNNING', 'started_at_utc': now(), 'command': [sys.executable, *sys.argv],
              'protocol_sha256': PROTOCOL_SHA, 'code_sha256': sha(Path(__file__)), 'input_sha256': pins,
              'feature_source': 'app/experiments/f1-006/result/features.csv', 'configurations': CONFIGS,
              'versions': {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__, 'lightgbm': lgb.__version__},
              'scope': 'Retrospective post-inspection experiment; reference consensus is not latent truth or physical curtailment. Historical availability is unverified.',
              'label_rule': {'paired_weather_weight': .5, 'paired_satellite_weight': .5, 'missing_satellite_weather_weight': 1, 'row_weight': 1},
              'splits': {}, 'methods': {}, 'reference_sensitivity': {}}
    selected, comparison, selection = {}, [], None
    for stage, filename in (('validation', 'cv_predictions.csv'), ('test', 'test_predictions.csv')):
        if stage == 'test' and sha(out / 'validation-selection.json') != report['selection_sha256']: raise ValueError('Changed selection')
        split = read(ROOT / 'eval' / filename)
        names = split.iloc[:, 0]
        positions = pd.Index(features.feature_time).get_indexer(names)
        if np.any(positions < 0) or not names.is_unique or len(split) != {'validation': 3566, 'test': 3567}[stage]: raise ValueError('Invalid evaluation membership')
        if not np.array_equal(split.actual, targets.actual.iloc[positions]): raise ValueError('Changed evaluation truth')
        train = np.flatnonzero(target < pd.Timestamp(names.iloc[0]))
        old_train = read(OLD / 'result' / f'{stage}-training-origins.csv')
        if list(features.feature_time.iloc[train]) != list(old_train.feature_time) or list(targets.target_time.iloc[train]) != list(old_train.target_time): raise ValueError('Changed purged training membership')
        if not np.array_equal(np.isin(np.arange(len(features)), train), joined[stage + '_training'].astype(bool)): raise ValueError('Training join flag mismatch')
        weather_event = targets.actual.iloc[train].to_numpy() > 600
        sat_values = satellite[train]
        available = np.isfinite(sat_values)
        soft = np.where(available, (weather_event.astype(float) + (sat_values > 600)) / 2, weather_event.astype(float))
        if not np.isin(soft, [0., .5, 1.]).all(): raise ValueError('Invalid soft target')
        labels = pd.DataFrame({'feature_time': features.feature_time.iloc[train].to_numpy(), 'target_time': targets.target_time.iloc[train].to_numpy(),
                               'valid_time_utc': valid.iloc[train].to_numpy(), 'weather_event': weather_event.astype(int),
                               'satellite_event': np.where(available, (sat_values > 600).astype(float), np.nan),
                               'satellite_missing': (~available).astype(int), 'source_count': 1 + available.astype(int), 'soft_target': soft})
        labels.to_csv(out / f'{stage}-training-labels.csv', index=False)
        report['splits'][stage] = {'hours': len(split), 'training_hours': len(train), 'satellite_available': int(available.sum()),
                                  'satellite_missing': int((~available).sum()), 'paired_disagreements': int(np.sum(soft == .5)),
                                  'soft_target_counts': {str(v): int(np.sum(soft == v)) for v in (0., .5, 1.)},
                                  'latest_training_target': str(target.iloc[train[-1]]), 'first_evaluation_origin': names.iloc[0]}
        w, sat = split.actual.to_numpy(), satellite[positions]
        has_sat = np.isfinite(sat)
        membership = pd.DataFrame({'feature_time': names, 'target_time_utc': valid.iloc[positions].to_numpy(),
                                   'weather_actual_w_m2': w, 'satellite_w_m2': sat, 'scored': has_sat.astype(int)})
        membership.to_csv(out / f'{stage}-reference-membership.csv', index=False)
        old_membership = read(OLD / 'result' / f'{stage}-reference-membership.csv')
        if not np.array_equal(sat, old_membership.satellite_w_m2.to_numpy(), equal_nan=True): raise ValueError('Changed evaluation satellite reference')
        report['reference_sensitivity'][stage] = {'original_hours': len(split), 'common_hours': int(has_sat.sum()), 'missing_hours': int((~has_sat).sum()),
                                                'missing_valid_times_utc': [str(v) for v in valid.iloc[positions].to_numpy()[~has_sat]]}
        nwp = read(OLD / 'result/predictions' / f'{stage}-nwp_day2.csv').probability.to_numpy()
        control = joint_scores(nwp, .5, w, sat)
        methods = ['original', 'persistence', 'nwp_day2', *['weather_' + n for n in CONFIGS], *['consensus_' + n for n in CONFIGS]]
        for name in methods:
            prior_cutoff = None
            if name.startswith('consensus_'):
                configuration = CONFIGS[name.split('_')[1]]
                model = lgb.LGBMRegressor(objective='cross_entropy', **configuration, learning_rate=.03, reg_lambda=2,
                                          random_state=17, n_jobs=2, deterministic=True, force_col_wise=True, verbosity=-1)
                model.fit(x.iloc[train], soft)
                probability = model.predict(x.iloc[positions])
                model.booster_.save_model(str(out / 'models' / f'{stage}-{name}.txt'))
                if model.booster_.params['objective'] != 'cross_entropy': raise ValueError('Wrong objective')
            else:
                old_name = name.split('_')[1] if name.startswith('weather_') else name
                old = read(OLD / 'result/predictions' / f'{stage}-{old_name}.csv')
                if not np.array_equal(old.feature_time, names) or not np.array_equal(old.actual_w_m2, w): raise ValueError('Old prediction membership mismatch')
                probability = old.probability.to_numpy()
                if name.startswith('weather_'): prior_cutoff = old_report['methods'][old_name][stage]['cutoff']
            if not np.isfinite(probability).all() or np.any((probability < 0) | (probability > 1)): raise ValueError('Invalid probability')
            if name.startswith(('weather_', 'consensus_')):
                if stage == 'validation':
                    best, grid = threshold(probability, w, sat, control)
                    selected[name] = best
                    save(out / f'validation-grid-{name}.json', grid)
                cutoff = selected[name]['cutoff']
            else: cutoff = .5
            cuts = {'selected': cutoff, 'default_0_5': .5}
            if prior_cutoff is not None: cuts['previous_006'] = prior_cutoff
            report['methods'].setdefault(name, {})[stage] = {'cutoff': cutoff, 'modes': {}}
            pred = pd.DataFrame({'feature_time': names, 'target_time': targets.target_time.iloc[positions].to_numpy(), 'valid_time_utc': valid.iloc[positions].to_numpy(),
                                 'weather_actual_w_m2': w, 'satellite_w_m2': sat, 'probability': probability, 'cutoff': cutoff,
                                 'predicted_positive': (probability > cutoff).astype(int), 'default_positive': (probability > .5).astype(int)})
            if prior_cutoff is not None:
                pred['previous_006_cutoff'] = prior_cutoff
                pred['previous_006_positive'] = (probability > prior_cutoff).astype(int)
            pred.to_csv(out / 'predictions' / f'{stage}-{name}.csv', index=False)
            for mode, cut in cuts.items():
                group = {}
                for basis, reference, mask in (('weather_full', w, np.ones(len(w), dtype=bool)), ('weather_common', w, has_sat), ('satellite_common', sat, has_sat)):
                    m = score(reference[mask] > 600, probability[mask] > cut, probability[mask])
                    group[basis] = m
                    comparison.append({'split': stage, 'method': name, 'mode': mode, 'basis': basis, 'cutoff': cut, **m})
                report['methods'][name][stage]['modes'][mode] = group
            print(stage, name, json.dumps(report['methods'][name][stage]['modes']['selected']), flush=True)
        if stage == 'validation':
            selection = {'families': {f: choose(selected, f) for f in ('weather', 'consensus')}, 'all_thresholds': selected,
                         'fixed_control': control, 'frozen_at_utc': now(), 'protocol_sha256': PROTOCOL_SHA,
                         'code_sha256': report['code_sha256'], 'input_manifest_sha256': sha(HERE / 'inputs.json'),
                         'recommendation': 'Retain NWP unless the frozen test gate also passes; no live recommendation.'}
            save(out / 'validation-selection.json', selection)
            report['selection_sha256'] = sha(out / 'validation-selection.json')
            report['selected_families'] = selection['families']
            print('FROZEN', json.dumps(selection['families']), flush=True)
        save(out / 'report.json', report)
    report['test_gates'] = {}
    for family, name in selection['families'].items():
        candidate = report['methods'][name]['test']['modes']['selected']
        candidate = {b: candidate[b] for b in ('weather_full', 'satellite_common')}
        report['test_gates'][family] = {'selected_method': name, **test_gate(candidate, control)}
    report['recommendation'] = 'Retain established control; retrospective research does not authorize a model or dispatch replacement.'
    pd.DataFrame(comparison).to_csv(out / 'comparison.csv', index=False)
    for name, expected in pins.items():
        if sha(ROOT / name) != expected: raise ValueError('Input changed during execution: ' + name)
    report['status'] = 'COMPLETE'; report['completed_at_utc'] = now()
    report['outputs_sha256'] = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'report.json'}
    save(out / 'report.json', report)
    print('COMPLETE', json.dumps(report['test_gates']), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args().output.resolve())
