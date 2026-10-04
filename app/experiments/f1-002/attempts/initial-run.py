"""Fixed retrospective feature comparison; leaves original inputs unchanged."""
import argparse
import hashlib
import importlib.util
import json
import platform
import time
from fractions import Fraction
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROTOCOL_SHA = '4d11bf8aca8c9797a9ae8d40d11a612db6354105d91576123f9830b5382b586f'
PREVIOUS = HERE.parent / 'f1-001/run.py'
spec = importlib.util.spec_from_file_location('f1_001', PREVIOUS)
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
METHODS = ['persistence', 'original', 'absolute_l1', 'residual_base', 'residual_history']
FITTED = METHODS[2:]
ALPHAS = [0, .25, .5, .75, 1]
CUTOFFS = list(range(500, 701, 10))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def ratio(metrics, name):
    tp, fp, fn = (metrics[key] for key in ['tp', 'fp', 'fn'])
    numerator, denominator = {'precision': (tp, tp + fp), 'recall': (tp, tp + fn),
                              'f1': (2 * tp, 2 * tp + fp + fn)}[name]
    return Fraction(numerator, denominator) if denominator else Fraction(-1)


def rank(metrics):
    return tuple(ratio(metrics, key) for key in ['f1', 'precision', 'recall'])


def qualifies(metrics, persistence, original):
    p, r = ratio(metrics, 'precision'), ratio(metrics, 'recall')
    return p >= 0 and r >= 0 and p >= ratio(persistence, 'precision') and r >= ratio(original, 'recall')


def forecasts(name, raw, baseline, alpha):
    if name.startswith('residual_'):
        return np.maximum(0, baseline + alpha * raw)
    return np.maximum(0, raw) if name == 'absolute_l1' else raw


def metrics(actual, values, cutoff):
    result = previous.score(actual > 600, values > cutoff)
    errors = values - actual
    return {**result, 'mae': float(np.mean(np.abs(errors))), 'rmse': float(np.sqrt(np.mean(errors ** 2)))}


def month_metrics(actual, values, cutoff, times):
    months = times.strftime('%Y-%m')
    return [{'month': month, **metrics(actual[months == month], values[months == month], cutoff)}
            for month in sorted(set(months))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output.resolve()
    if sha(HERE / 'PROTOCOL.md') != PROTOCOL_SHA:
        raise ValueError('Protocol changed')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'predictions').mkdir(); (out / 'models').mkdir()
    sources = ['data/features.csv', 'data/paphos_weather_data.csv', 'eval/cv_predictions.csv', 'eval/test_predictions.csv']
    input_hashes = {name: sha(ROOT / name) for name in sources}
    frame, base, unused_history, targets, splits = previous.inputs()
    del unused_history
    weather = pd.read_csv(ROOT / sources[1], index_col=0, parse_dates=True)
    for label, index in [('features', frame.index), ('weather', weather.index),
                         *[(name, split.index) for name, split in splits.items()]]:
        if not index.is_unique or not np.all(np.diff(index.asi8) == pd.Timedelta(hours=1).value):
            raise ValueError(label + ' is not complete unique hourly data')
    if list(base.columns) != ['temperature_2m', 'shortwave_radiation', 'relative_humidity_2m',
                              'cloud_cover', 'radiation_yesterday', 'hour', 'month']:
        raise ValueError('Original seven predictors changed')
    extra = {}
    for field in ['shortwave_radiation', 'cloud_cover']:
        for lag in [1, 3, 6, 12]:
            extra[f'{field}_lag{lag}'] = weather[field].shift(lag).reindex(frame.index)
        for hours in [6, 24]:
            extra[f'{field}_mean{hours}'] = weather[field].rolling(hours, min_periods=hours).mean().reindex(frame.index)
        extra[f'{field}_change24'] = (weather[field] - weather[field].shift(24)).reindex(frame.index)
    for name, phase in [('target_hour', targets.hour / 24), ('target_season', (targets.dayofyear - 1) / 365.25)]:
        extra[name + '_sin'] = np.sin(2 * np.pi * phase)
        extra[name + '_cos'] = np.cos(2 * np.pi * phase)
    history = pd.concat([base, pd.DataFrame(extra, index=frame.index)], axis=1)
    complete = np.isfinite(history.to_numpy()).all(axis=1)
    if history.shape[1] != 25:
        raise ValueError('Unexpected feature count')
    report = {'experiment': 'AktinaBench F1 002', 'status': 'RUNNING',
        'scope': 'Retrospective already-inspected test; no independent future holdout or plant-benefit claim.',
        'protocol_sha256': PROTOCOL_SHA, 'code_sha256': sha(Path(__file__)),
        'reused_evaluator_sha256': sha(PREVIOUS), 'input_sha256': input_hashes,
        'versions': {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__, 'lightgbm': lgb.__version__},
        'features': {'base': list(base.columns), 'history': list(history.columns)},
        'settings': {'objective': 'regression_l1', 'n_estimators': 300, 'learning_rate': .05,
                     'num_leaves': 15, 'min_child_samples': 40, 'random_state': 17, 'n_jobs': 2},
        'splits': {}, 'methods': {}, 'outputs_sha256': {}}
    configurations = {}
    comparison = []
    for stage in ['validation', 'test']:
        split = splits[stage]
        if not np.isfinite(history.loc[split.index].to_numpy()).all():
            raise ValueError('Missing evaluation features; membership cannot change')
        if not np.array_equal(split.baseline.to_numpy(), base.shortwave_radiation.loc[split.index].to_numpy()):
            raise ValueError('Original persistence differs from origin radiation')
        mask = (targets < split.index[0]) & complete
        train = frame.index[mask]
        if not len(train) or not (train < split.index[0]).all():
            raise ValueError('Invalid training boundary')
        train_path = out / f'{stage}-training-origins.csv'
        pd.DataFrame({'feature_time': train, 'target_time': targets[mask]}).to_csv(train_path, index=False)
        actual = split.actual.to_numpy()
        baseline = split.baseline.to_numpy()
        target_times = split.index + pd.Timedelta(hours=24)
        references = {name: metrics(actual, split[column].to_numpy(), 600)
                      for name, column in [('persistence', 'baseline'), ('original', 'predicted')]}
        report['splits'][stage] = {'hours': len(split), 'origin_start': str(split.index[0]), 'origin_end': str(split.index[-1]),
            'target_start': str(target_times[0]), 'target_end': str(target_times[-1]),
            'train_hours': len(train), 'train_start': str(train[0]), 'train_end': str(train[-1]),
            'latest_training_target': str(targets[mask][-1]),
            'warmup_removed': int(((targets < split.index[0]) & ~complete).sum()),
            'purged_hours': int(((frame.index < split.index[0]) & ~(targets < split.index[0])).sum()),
            'training_origins_sha256': sha(train_path)}
        if stage == 'test':
            if sha(out / 'validation-selection.json') != report['selection_sha256']:
                raise ValueError('Frozen validation selection changed')
            print('TEST begins after frozen selection: ' + report['recommendation']['method'], flush=True)
        for name in METHODS:
            started = time.monotonic()
            if name in FITTED:
                x = history if name == 'residual_history' else base
                y = frame.target - base.shortwave_radiation if name.startswith('residual_') else frame.target
                estimator = lgb.LGBMRegressor(**report['settings'], verbosity=-1, deterministic=True, force_col_wise=True)
                estimator.fit(x.loc[train], y.loc[train])
                raw = estimator.predict(x.loc[split.index])
                estimator.booster_.save_model(str(out / 'models' / f'{stage}-{name}.txt'))
            else:
                raw = split['baseline' if name == 'persistence' else 'predicted'].to_numpy()
            if not np.isfinite(raw).all():
                raise ValueError('Nonfinite predictions: ' + name)
            default_alpha = 0 if name == 'persistence' else 1
            default_values = forecasts(name, raw, baseline, default_alpha)
            default = metrics(actual, default_values, 600)
            if stage == 'validation':
                grid = []
                if name in FITTED:
                    for alpha in ALPHAS if name.startswith('residual_') else [1]:
                        values = forecasts(name, raw, baseline, alpha)
                        for cutoff in CUTOFFS:
                            m = metrics(actual, values, cutoff)
                            grid.append({'alpha': alpha, 'cutoff': cutoff, 'qualifies': qualifies(m, references['persistence'], references['original']), **m})
                    admitted = [g for g in grid if g['qualifies']]
                    best = max(admitted, key=lambda g: (*rank(g), -abs(g['cutoff'] - 600), -g['alpha'], -g['cutoff'])) if admitted else None
                    configurations[name] = ({key: best[key] for key in ['alpha', 'cutoff', 'qualifies']} if best else
                        {'alpha': default_alpha, 'cutoff': 600, 'qualifies': False})
                    write(out / f'validation-grid-{name}.json', grid)
                else:
                    configurations[name] = {'alpha': default_alpha, 'cutoff': 600,
                        'qualifies': qualifies(default, references['persistence'], references['original'])}
            config = configurations[name]
            values = forecasts(name, raw, baseline, config['alpha'])
            selected = metrics(actual, values, config['cutoff'])
            result = {'configuration': config, 'selected': selected, 'default': default,
                'monthly': month_metrics(actual, values, config['cutoff'], target_times),
                'default_monthly': month_metrics(actual, default_values, 600, target_times),
                'fit_and_score_seconds': time.monotonic() - started}
            report['methods'].setdefault(name, {})[stage] = result
            prediction_path = out / 'predictions' / f'{stage}-{name}.csv'
            pd.DataFrame({'feature_time': split.index, 'target_time': target_times,
                'actual_w_m2': actual, 'baseline_w_m2': baseline, 'raw_prediction': raw,
                'alpha': config['alpha'], 'cutoff': config['cutoff'], 'score': values,
                'predicted_positive': (values > config['cutoff']).astype(int),
                'default_score': default_values, 'default_positive': (default_values > 600).astype(int)
                }).to_csv(prediction_path, index=False)
            for basis, m in [('selected', selected), ('default', default)]:
                comparison.append({'split': stage, 'method': name, 'basis': basis,
                    'alpha': config['alpha'] if basis == 'selected' else default_alpha,
                    'cutoff': config['cutoff'] if basis == 'selected' else 600,
                    'validation_qualifies': config['qualifies'], **m})
            write(out / 'report.json', report)
            print(f'{stage} {name} alpha={config["alpha"]} cutoff={config["cutoff"]}: ' + json.dumps(selected), flush=True)
        if stage == 'validation':
            order = ['persistence', *FITTED]
            admitted = [name for name in order if configurations[name]['qualifies']]
            chosen = max(admitted, key=lambda name: (*rank(report['methods'][name]['validation']['selected']), -order.index(name))) if admitted else 'persistence'
            selection = {'method': chosen, 'fallback_no_qualifier': not admitted,
                'configuration': configurations[chosen], 'all_configurations': configurations,
                'validation': {name: report['methods'][name]['validation']['selected'] for name in METHODS},
                'grid_sha256': {name: sha(out / f'validation-grid-{name}.json') for name in FITTED},
                'protocol_sha256': PROTOCOL_SHA, 'code_sha256': report['code_sha256']}
            write(out / 'validation-selection.json', selection)
            report['recommendation'] = {key: selection[key] for key in ['method', 'fallback_no_qualifier', 'configuration']}
            report['selection_sha256'] = sha(out / 'validation-selection.json')
            write(out / 'report.json', report)
            print('VALIDATION selection frozen: ' + json.dumps(report['recommendation']), flush=True)
    if {name: sha(ROOT / name) for name in sources} != input_hashes:
        raise ValueError('An original input changed during the run')
    pd.DataFrame(comparison).to_csv(out / 'comparison.csv', index=False)
    report['outputs_sha256'] = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*'))
                               if p.is_file() and p.name != 'report.json'}
    report['status'] = 'COMPLETE'
    write(out / 'report.json', report)
    print('COMPLETE; original inputs unchanged.', flush=True)


if __name__ == '__main__':
    main()
