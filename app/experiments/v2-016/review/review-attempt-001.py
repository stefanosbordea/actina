"""Independent saved-model replay and validation audit. No fitting or test data."""
import os
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[name] = '2'
import argparse
from datetime import timedelta
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
RESULT = EXP / 'result'
FEATURES = ['temperature_2m', 'shortwave_radiation', 'relative_humidity_2m', 'cloud_cover',
            'nwp_radiation', 'nwp_cloud', 'radiation_yesterday', 'hour', 'month']
HEAD = ['base_margin', 'nwp_minus_base', 'nwp_cloud', 'margin_cloud', 'hour_sin', 'hour_cos', 'month_sin', 'month_cos']
DAY = pd.Timedelta(hours=24)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def frame(path, index='origin', original_parser=False):
    return pd.read_csv(path, index_col=index, parse_dates=[index],
                       float_precision=None if original_parser else 'round_trip')


def counts(truth, call):
    pairs = list(zip(truth, call))
    tp = sum(bool(a) and bool(p) for a, p in pairs)
    fp = sum(not bool(a) and bool(p) for a, p in pairs)
    fn = sum(bool(a) and not bool(p) for a, p in pairs)
    tn = len(pairs) - tp - fp - fn
    ratio = lambda n, d: None if not d else n / d
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, precision=ratio(tp, tp+fp), recall=ratio(tp, tp+fn),
                f1=ratio(2*tp, 2*tp+fp+fn), f1_exact=None if not 2*tp+fp+fn else str(Fraction(2*tp, 2*tp+fp+fn)))


def close(first, second, tolerance=1e-10):
    error = float(np.max(np.abs(np.asarray(first) - np.asarray(second))))
    assert math.isfinite(error) and error <= tolerance, error
    return error


def check_metrics(computed, saved):
    for key, value in computed.items():
        if isinstance(value, float):
            close(value, saved[key])
        else:
            assert value == saved[key], (key, value, saved[key])


def audit():
    lock = read_json(EXP / 'lock.json')
    for name, expected in lock['sha256'].items():
        assert sha(EXP / name) == expected, name
    completion = read_json(RESULT / 'completion.json')
    assert completion['status'] == 'completed' and completion['error'] is None
    for name, expected in completion['output_sha256'].items():
        assert sha(RESULT / name) == expected, name
    freeze = read_json(RESULT / 'policy-freeze.json')
    assert freeze['lock_sha256'] == sha(EXP / 'lock.json')
    for name, expected in freeze['frozen_prediction_files_sha256'].items():
        assert sha(RESULT / name) == expected, name
    execution = read_json(EXP / 'execution-001.json')
    assert execution['exit_code'] == 0
    assert execution['started_at_utc'] < freeze['frozen_at_utc'] < completion['completed_at_utc']
    assert sha(EXP / 'execution-001.log') == execution['log_sha256']

    # Match the fitter's input parser. Saved numeric outputs use round-trip parsing.
    train = frame(EXP / 'inputs/train.csv', 'time', True)
    valid = frame(EXP / 'inputs/validation-features.csv', 'time', True)
    assert list(train) == FEATURES + ['target'] and list(valid) == FEATURES
    assert (len(train), len(valid)) == (16444, 3566)
    for data in (train, valid):
        assert data.index.is_unique and data.index.is_monotonic_increasing
        assert all(b-a == DAY for a,b in zip(data.index, data.index[1:]))
    assert train.index[-1] + DAY < valid.index[0]
    oof = frame(RESULT / 'base-oof.csv')
    assert len(oof) == 12499 and oof.index.is_unique
    close(oof[FEATURES + ['target']], train.loc[oof.index, FEATURES + ['target']])
    replay_errors = {}
    folds = []
    for info in freeze['base_fits'] + [freeze['final_base']]:
        label = info['label']
        membership = frame(RESULT / f'{label}-training-membership.csv')
        expected = train.index if label == 'final' else train.index[train.index + DAY < pd.Timestamp(info['held_origin_first'])]
        assert membership.index.equals(expected)
        assert pd.DatetimeIndex(pd.to_datetime(membership.target_time)).equals(expected + DAY)
        stop = expected >= expected[-1] - pd.Timedelta(days=28) + pd.Timedelta(hours=1)
        fit = expected + DAY < expected[stop][0]
        assert np.array_equal(membership.inner_fit, fit.astype(int))
        assert np.array_equal(membership.inner_stop, stop.astype(int))
        assert int(stop.sum()) == 672 and int((~fit & ~stop).sum()) == 24
        assert expected[fit][-1] + DAY < expected[stop][0]
        model = lgb.Booster(model_file=str(RESULT / f'{label}-base.txt'))
        inner = lgb.Booster(model_file=str(RESULT / f'{label}-inner.txt'))
        assert model.feature_name() == FEATURES and inner.feature_name() == FEATURES
        assert model.current_iteration() == inner.current_iteration() == info['selected_trees']
        if label != 'final':
            number = int(label[4:])
            held = oof.loc[oof.fold == number]
            assert len(held) == info['held_rows']
            assert str(held.index[0]) == info['held_origin_first'] and str(held.index[-1]) == info['held_origin_last']
            prediction = np.maximum(model.predict(train.loc[held.index, FEATURES], num_threads=2), 0)
            replay_errors[label] = close(prediction, held.base_prediction)
            folds.append(dict(fold=number, train_rows=len(expected), held_rows=len(held), trees=info['selected_trees']))
        else:
            base = np.maximum(model.predict(valid[FEATURES], num_threads=2), 0)
    decisions = frame(RESULT / 'validation-decisions.csv')
    assert decisions.index.equals(valid.index)
    replay_errors['final_base'] = close(base, decisions.base_prediction)

    margin = (base - 600) / 100
    cloud = valid.nwp_cloud.to_numpy() / 100
    hour = valid.hour.to_numpy() * (2 * np.pi / 24)
    month = (valid.month.to_numpy() - 1) * (2 * np.pi / 12)
    x = np.column_stack([margin, (valid.nwp_radiation.to_numpy()-base)/100, cloud, margin*cloud,
                         np.sin(hour), np.cos(hour), np.sin(month), np.cos(month)])
    logistic = read_json(RESULT / 'logistic-model.json')
    assert logistic['features'] == HEAD and logistic['classes'] == [False, True]
    z = x @ np.asarray(logistic['coefficients']) + logistic['intercept']
    probability = {'logistic': np.array([1/(1+math.exp(-v)) if v >= 0 else math.exp(v)/(1+math.exp(v)) for v in z])}
    boosted = lgb.Booster(model_file=str(RESULT / 'boosted-head.txt'))
    assert boosted.feature_name() == HEAD
    probability['boosted'] = boosted.predict(x, num_threads=2)
    thresholds = {}
    for arm in ('logistic', 'boosted'):
        replay_errors[arm] = close(probability[arm], decisions[f'{arm}_probability'])
        forward = frame(RESULT / f'{arm}-forward.csv')
        assert forward.index.equals(oof.index)
        assert np.array_equal(forward.truth.to_numpy(), (oof.target > 600).astype(int))
        assert forward.forward_probability.notna().equals(oof.fold >= 3)
        for fold in range(3, 7):
            member = frame(RESULT / f'{arm}-fold{fold}-membership.csv')
            assert member.index.equals(oof.index)
            held = oof.fold == fold
            fit = (oof.fold < fold) & (oof.index + DAY < oof.index[held][0])
            assert np.array_equal(member.fit, fit.astype(int)) and np.array_equal(member.held, held.astype(int))
            assert (oof.index[fit] + DAY).max() < oof.index[held][0]
        usable = forward.loc[forward.forward_probability.notna()]
        ledger = pd.read_csv(RESULT / f'{arm}-training-thresholds.csv', float_precision='round_trip')
        assert len(ledger) == 181 and ledger.tick.tolist() == list(range(10,191))
        exact_rows = []
        for saved in ledger.to_dict('records'):
            tick = saved['tick']
            computed = counts(usable.truth.to_numpy(), usable.forward_probability.to_numpy() > tick/200)
            check_metrics(computed, saved)
            exact_rows.append((Fraction(computed['f1_exact']), -abs(tick-100), tick))
        selected = max(exact_rows)[2]
        assert selected == freeze['selected_training_thresholds'][arm]['tick']
        thresholds[arm] = selected/200
        assert np.array_equal(probability[arm] > selected/200, decisions[f'{arm}_call'].astype(bool))

    supplied = frame(EXP / 'inputs/cv_predictions_v2.csv', 'time')
    original = frame(EXP / 'inputs/original-validation.csv', 'time')
    fixed = frame(EXP / 'inputs/fixed008-validation.csv', 'feature_time')
    day2 = frame(EXP / 'inputs/retained-day2-validation.csv', 'feature_time')
    for table in (supplied, original, fixed, day2):
        assert table.index.equals(valid.index)
    assert np.array_equal(supplied.actual, original.actual)
    assert np.array_equal(supplied.baseline, original.baseline)
    assert np.array_equal(supplied.actual, fixed.weather_actual_w_m2)
    assert pd.DatetimeIndex(pd.to_datetime(fixed.target_time)).equals(valid.index + DAY)
    close(valid.nwp_radiation, supplied.forecast)
    actual = supplied.actual.to_numpy()
    truth = actual > 600
    points = dict(base_refit=base, supplied_v2_600=supplied.predicted.to_numpy(), supplied_v2_562=supplied.predicted.to_numpy(),
                  supplied_raw_day1=supplied.forecast.to_numpy(), retained_raw_day2=day2.nwp_day2_radiation.to_numpy(), persistence=supplied.baseline.to_numpy())
    calls = {name: values > (562 if name == 'supplied_v2_562' else 600) for name,values in points.items()}
    calls['fixed008'] = fixed.predicted_positive.to_numpy(dtype=bool)
    calls.update({arm: probability[arm] > thresholds[arm] for arm in probability})
    summary = read_json(RESULT / 'summary.json')
    evaluated = frame(RESULT / 'validation-evaluation.csv')
    assert evaluated.index.equals(valid.index)
    measured = {}
    for name, call in calls.items():
        measured[name] = counts(truth, call)
        check_metrics(measured[name], summary['metrics'][name])
        assert np.array_equal(call, evaluated[f'call_{name}'].astype(bool))
        if name in points:
            errors = (points[name]-actual).tolist()
            regression = dict(mae_w_m2=math.fsum(map(abs, errors))/len(errors), rmse_w_m2=math.sqrt(math.fsum(e*e for e in errors)/len(errors)), bias_w_m2=math.fsum(errors)/len(errors))
            check_metrics(regression, summary['metrics'][name])
        if name in probability:
            p = probability[name]
            clipped = np.clip(p, 1e-15, 1-1e-15)
            check_metrics(dict(brier=float(np.mean((p-truth)**2)), log_loss=float(-np.mean(np.where(truth, np.log(clipped), np.log1p(-clipped))))), summary['metrics'][name])

    dates = np.array([(t.to_pydatetime()+timedelta(hours=24)).date() for t in valid.index])
    unique = sorted(set(dates))
    assert len(unique) == 150 and all(b-a == timedelta(days=1) for a,b in zip(unique,unique[1:]))
    samples = np.random.Generator(np.random.PCG64(16016)).integers(0, len(unique), size=(2000,len(unique)))
    distributions = {}
    for name, call in calls.items():
        daily = [counts(truth[dates==day], call[dates==day]) for day in unique]
        array = np.array([[row['tp'],row['fp'],row['fn']] for row in daily], dtype=np.int64)
        totals = np.sum(array[samples], axis=1)
        denominator = 2*totals[:,0]+totals[:,1]+totals[:,2]
        distributions[name] = np.divide(2*totals[:,0], denominator, out=np.full(2000,np.nan), where=denominator!=0)
    retained = read_json(RESULT / 'day-bootstrap.json')
    intervals = {}
    target = {}
    for arm in probability:
        target[arm] = {}
        for control in ('base_refit','supplied_v2_600','supplied_v2_562','fixed008'):
            delta = distributions[arm]-distributions[control]
            endpoints = np.quantile(delta[np.isfinite(delta)], [.025,.975])
            name = f'{arm}_minus_{control}'
            close(endpoints, [retained['comparisons'][name]['lower_025'],retained['comparisons'][name]['upper_975']])
            assert int(np.sum(~np.isfinite(delta))) == retained['comparisons'][name]['undefined_replicates'] == 0
            intervals[name] = endpoints.tolist()
            target[arm][control] = dict(f1_difference=measured[arm]['f1']-measured[control]['f1'],
                false_positive_difference=measured[arm]['fp']-measured[control]['fp'],
                true_positive_difference=measured[arm]['tp']-measured[control]['tp'],
                higher_f1_without_more_false_positives=Fraction(measured[arm]['f1_exact'])>Fraction(measured[control]['f1_exact']) and measured[arm]['fp']<=measured[control]['fp'])
    assert all(value == sha(EXP/name) for name,value in lock['sha256'].items())
    return dict(status='PASS', source_sha256=sha(Path(__file__)), lock_sha256=sha(EXP/'lock.json'),
        original_run_exit_code=execution['exit_code'], validation_rows=3566, base_oof_rows=12499,
        base_models_replayed=7, correction_models_replayed=2, threshold_rows_checked=362,
        base_folds=folds, maximum_replay_errors=replay_errors, thresholds=thresholds,
        metrics=measured, comparisons=target, paired_f1_intervals=intervals,
        source_and_output_hashes_verified=True, fits_executed=0, test_files_read=False,
        limits=['Intermediate forward head models were not saved, so their scores were checked against retained memberships and threshold ledgers rather than replayed.',
                'The final base and both final heads were independently replayed from saved parameters.',
                'All intervals include zero. They do not correct repeated validation use or establish a meaningful improvement.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    with threadpool_limits(limits=2):
        report = audit()
    output = HERE / 'review.json'
    if args.check:
        assert report == read_json(output)
    else:
        with output.open('x') as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write('\n')
    print(json.dumps({key:report[key] for key in ('status','validation_rows','base_oof_rows','maximum_replay_errors','comparisons')}, indent=2))
