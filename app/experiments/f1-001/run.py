"""Frozen F1 comparison. Run from any directory; original model files stay intact."""
import argparse
import hashlib
import json
import platform
import time
import warnings
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import sklearn
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[3]
METHODS = ['persistence', 'calibrated_persistence', 'purged_regression', 'direct_classifier', 'history_classifier', 'deep_classifier']
THRESHOLDS = np.linspace(.05, .95, 91)
SEED = 17


def score(actual, positive):
    truth = np.asarray(actual, dtype=bool)
    predicted = np.asarray(positive, dtype=bool)
    tp = int(np.sum(truth & predicted)); fp = int(np.sum(~truth & predicted))
    fn = int(np.sum(truth & ~predicted)); tn = int(np.sum(~truth & ~predicted))
    return {'hours': len(truth), 'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
            'precision': tp / (tp + fp) if tp + fp else None,
            'recall': tp / (tp + fn) if tp + fn else None,
            'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None}


def rank(metrics):
    return tuple(metrics[key] if metrics[key] is not None else -1 for key in ('f1', 'precision', 'recall'))


def select_cutoff(truth, prediction, cutoffs, centre):
    records = [{'cutoff': float(c), **score(truth, prediction > c)} for c in cutoffs]
    best = max(records, key=lambda r: (*rank(r), -abs(r['cutoff'] - centre)))
    return best['cutoff'], records


def inputs():
    frame = pd.read_csv(ROOT / 'data/features.csv', index_col=0, parse_dates=True)
    weather = pd.read_csv(ROOT / 'data/paphos_weather_data.csv', index_col=0, parse_dates=True)
    if not frame.index.is_unique or not weather.index.is_unique:
        raise ValueError('Repeated timestamps')
    target_time = frame.index + pd.Timedelta(hours=24)
    if not np.allclose(frame.target, weather.shortwave_radiation.reindex(target_time), atol=1e-9, rtol=0):
        raise ValueError('Targets are not aligned to the following day')
    base = frame.drop(columns='target').astype(float)
    history = base.copy()
    lagged = {}
    for field in ['temperature_2m', 'shortwave_radiation', 'relative_humidity_2m', 'cloud_cover']:
        for lag in range(1, 24):
            lagged[f'{field}_lag{lag}'] = weather[field].shift(lag).reindex(frame.index).to_numpy()
    history = pd.concat([history, pd.DataFrame(lagged, index=frame.index)], axis=1)
    for name, phase in [('hour', target_time.hour / 24), ('season', (target_time.dayofyear - 1) / 365.25)]:
        history[name + '_sin'] = np.sin(2 * np.pi * phase)
        history[name + '_cos'] = np.cos(2 * np.pi * phase)
    if not np.isfinite(history.to_numpy()).all():
        raise ValueError('History is incomplete; do not move split boundaries to compensate')
    splits = {name: pd.read_csv(ROOT / f'eval/{filename}', index_col=0, parse_dates=True)
              for name, filename in [('validation', 'cv_predictions.csv'), ('test', 'test_predictions.csv')]}
    for split in splits.values():
        if not np.allclose(frame.target.reindex(split.index), split.actual, atol=1e-9, rtol=0):
            raise ValueError('Original split labels do not match feature targets')
    return frame, base, history, target_time, splits


def model(name):
    if name == 'purged_regression':
        return lgb.LGBMRegressor(n_estimators=148, learning_rate=.05, verbosity=-1, random_state=SEED, n_jobs=2)
    if name in ('direct_classifier', 'history_classifier'):
        return lgb.LGBMClassifier(n_estimators=300, learning_rate=.05, num_leaves=15,
                                  min_child_samples=40, random_state=SEED, n_jobs=2, verbosity=-1)
    if name == 'deep_classifier':
        return make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(64, 32, 16),
            solver='adam', learning_rate_init=.001, alpha=.001, batch_size=128,
            max_iter=200, early_stopping=False, random_state=SEED))
    return None


def predict(estimator, name, x):
    if estimator is None:
        return x.shortwave_radiation.to_numpy()
    if name == 'purged_regression':
        return estimator.predict(x)
    return estimator.predict_proba(x)[:, 1]


def grouped_scores(truth, predictions, timestamps):
    months = timestamps.strftime('%Y-%m')
    return [{'month': month, **score(truth[months == month], predictions[months == month])} for month in sorted(set(months))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / 'models').mkdir(); (out / 'predictions').mkdir()
    frame, base, history, targets, splits = inputs()
    report = {
        'experiment': 'ActinaBench F1 001', 'status': 'RUNNING',
        'scope': 'Retrospective comparison on the already-inspected original test; no claim of independent generalization.',
        'truth': 'actual radiation > 600 W/m²', 'prediction_rule': 'score > selected cutoff',
        'versions': {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__,
                     'sklearn': sklearn.__version__, 'lightgbm': lgb.__version__},
        'input_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                         ['data/features.csv','data/paphos_weather_data.csv','eval/cv_predictions.csv','eval/test_predictions.csv']},
        'protocol_sha256': hashlib.sha256(Path(__file__).with_name('PROTOCOL.md').read_bytes()).hexdigest(),
        'evaluator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'features': {'base': list(base.columns), 'history': list(history.columns)},
        'splits': {}, 'methods': {},
    }
    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    save()
    selected = {}
    for stage in ['validation', 'test']:
        split = splits[stage]
        fit_mask = (frame.index < split.index[0]) & (targets < split.index[0])
        train_indices = frame.index[fit_mask]
        truth = split.actual.to_numpy() > 600
        target_dates = split.index + pd.Timedelta(hours=24)
        report['splits'][stage] = {
            'evaluation_origins_start': str(split.index[0]), 'evaluation_origins_end': str(split.index[-1]),
            'target_start': str(target_dates[0]), 'target_end': str(target_dates[-1]),
            'train_hours': int(fit_mask.sum()), 'evaluation_hours': len(split),
            'purged_hours': int((frame.index < split.index[0]).sum() - fit_mask.sum()),
            'latest_training_target': str(targets[fit_mask][-1]),
            'retained_original_model': score(truth, split.predicted.to_numpy() > 600),
        }
        if stage == 'test':
            report['selected_on_validation'] = max(METHODS, key=lambda name: rank(report['methods'][name]['validation']['selected']))
            save()
            print('Selected before test: ' + report['selected_on_validation'], flush=True)
        for name in METHODS:
            print(stage + ': ' + name, flush=True)
            started = time.monotonic()
            x = history if name in ('history_classifier', 'deep_classifier') else base
            estimator = model(name)
            training_y = frame.target.loc[train_indices] if name == 'purged_regression' else frame.target.loc[train_indices] > 600
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                if estimator is not None:
                    estimator.fit(x.loc[train_indices], training_y)
                values = predict(estimator, name, x.loc[split.index])
            if not np.isfinite(values).all(): raise ValueError(name + ' produced nonfinite predictions')
            thresholds = None
            if stage == 'validation':
                if name == 'calibrated_persistence':
                    cutoff, thresholds = select_cutoff(truth, values, np.arange(450, 751, 10), 600)
                elif name.endswith('classifier'):
                    cutoff, thresholds = select_cutoff(truth, values, THRESHOLDS, .5)
                else:
                    cutoff = 600.0
                selected[name] = cutoff
            else:
                cutoff = selected[name]
            positive = values > cutoff
            result = {'cutoff': cutoff, 'selected': score(truth, positive),
                      'default': score(truth, values > (.5 if name.endswith('classifier') else 600)),
                      'monthly': grouped_scores(truth, positive, target_dates),
                      'seconds': time.monotonic() - started,
                      'warnings': sorted(set(str(w.message) for w in caught))}
            if thresholds is not None: result['validation_thresholds'] = thresholds
            report['methods'].setdefault(name, {})[stage] = result
            pd.DataFrame({'feature_time': split.index, 'target_time': target_dates,
                'actual_w_m2': split.actual.to_numpy(), 'actual_positive': truth.astype(int),
                'score': values, 'cutoff': cutoff, 'predicted_positive': positive.astype(int)}).to_csv(out / 'predictions' / f'{stage}-{name}.csv', index=False)
            if stage == 'test' and estimator is not None:
                joblib.dump(estimator, out / 'models' / (name + '.joblib'))
            save()
            print('  ' + json.dumps(result['selected']) + f'; cutoff {cutoff:.3f}; {result["seconds"]:.1f}s', flush=True)
    report['status'] = 'COMPLETE'
    save()
    print('Completed ' + str(out), flush=True)


if __name__ == '__main__':
    main()
