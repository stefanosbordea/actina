"""Independent v2-017 saved-model and source audit. No fitting or test scoring."""
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '2'
import calendar
from datetime import timedelta, timezone
from fractions import Fraction
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
ROOT = EXP.parents[2]
RESULT = EXP / 'result'
OLD = EXP.parent / 'v2-016'
HELPER = OLD / 'review/review.py'
spec = importlib.util.spec_from_file_location('independent016', HELPER)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
np, pd, lgb = h.np, h.pd, h.lgb
sha, read_json, frame, counts, close, check_metrics = h.sha, h.read_json, h.frame, h.counts, h.close, h.check_metrics
DAY = pd.Timedelta(hours=24)
CORE = ['v2_margin', 'day1_minus_v2', 'day1_cloud', 'v2_solar_ratio',
        'target_hour_sin', 'target_hour_cos', 'target_season_sin', 'target_season_cos']
EXTRA = ['ecmwf_minus_v2', 'gfs_minus_v2', 'forecast_disagreement']


def features(data, expanded=False):
    base = data.base_prediction.to_numpy()
    fields = [(base-600)/100, (data.nwp_radiation.to_numpy()-base)/100,
              data.nwp_cloud.to_numpy()/100, base/data.solar_scale.to_numpy()]
    fields.extend(data[name].to_numpy() for name in CORE[4:])
    if expanded:
        fields.extend([(data.ecmwf_day2.to_numpy()-base)/100, (data.gfs_day2.to_numpy()-base)/100,
                       np.abs(data.gfs_day2.to_numpy()-data.ecmwf_day2.to_numpy())/100])
    result = pd.DataFrame(np.column_stack(fields), index=data.index, columns=CORE+(EXTRA if expanded else []))
    assert np.isfinite(result.to_numpy()).all()
    return result


def solar_scale(target):
    samples = []
    latitude = math.radians(34.7744)
    for minute in (5, 15, 25, 35, 45, 55):
        local = target - timedelta(hours=1) + timedelta(minutes=minute)
        hour = local.hour + local.minute/60 + local.second/3600
        gamma = 2*math.pi/(366 if calendar.isleap(local.year) else 365)*(local.timetuple().tm_yday-1+(hour-12)/24)
        equation = 229.18*(.000075+.001868*math.cos(gamma)-.032077*math.sin(gamma)-.014615*math.cos(2*gamma)-.040849*math.sin(2*gamma))
        declination = .006918-.399912*math.cos(gamma)+.070257*math.sin(gamma)-.006758*math.cos(2*gamma)+.000907*math.sin(2*gamma)-.002697*math.cos(3*gamma)+.00148*math.sin(3*gamma)
        angle = math.radians((hour*60+equation+4*32.4229-180)/4-180)
        samples.append(max(0, math.sin(latitude)*math.sin(declination)+math.cos(latitude)*math.cos(declination)*math.cos(angle)))
    return max(100, 1000*math.fsum(samples)/6)


def audit():
    lock = read_json(EXP/'lock.json')
    for name, expected in lock['source_sha256'].items():
        assert sha(ROOT/name) == expected, name
    completion = read_json(RESULT/'completion.json')
    assert completion['status'] == 'completed' and completion['error'] is None
    for name, expected in completion['output_sha256'].items():
        assert sha(RESULT/name) == expected, name
    freeze = read_json(RESULT/'policy-freeze.json')
    assert freeze['lock_sha256'] == sha(EXP/'lock.json')
    for name, expected in freeze['frozen_files_sha256'].items():
        assert sha(RESULT/name) == expected, name
    execution = read_json(EXP/'execution-001.json')
    assert execution['exit_code'] == 0 and sha(EXP/'execution-001.log') == execution['log_sha256']
    assert lock['frozen_at_utc'] < execution['started_at_utc'] < freeze['frozen_at_utc'] < completion['completed_at_utc']

    train = frame(EXP/'inputs/train.csv', original_parser=True)
    valid = frame(EXP/'inputs/validation.csv', original_parser=True)
    source_train = frame(EXP/'inputs/train.csv')
    source_valid = frame(EXP/'inputs/validation.csv')
    oof = frame(OLD/'result/base-oof.csv')
    old_valid = frame(OLD/'inputs/validation-features.csv', 'time')
    old_decisions = frame(OLD/'result/validation-decisions.csv')
    original_features = frame(EXP.parent/'f1-008/result/features.csv', 'feature_time')
    gfs = frame(EXP.parent/'nwp-alternative-001/result/radiation-only.csv', 'feature_time')
    common = oof.index.intersection(original_features.index).intersection(gfs.index).sort_values()
    excluded = frame(EXP/'inputs/excluded-oof-origins.csv')
    assert train.index.equals(common) and len(train) == 10675
    assert excluded.index.equals(oof.index.difference(common).sort_values()) and len(excluded) == 1824
    assert valid.index.equals(old_valid.index) and len(valid) == 3566
    assert (train.index+DAY).max() < valid.index.min()
    archives = []
    for path in (EXP.parent/'nwp-archive-001/archive.json', EXP.parent/'nwp-alternative-001/result/response.json'):
        raw = read_json(path)['hourly']
        assert len(raw['time']) == len(set(raw['time']))
        archives.append(dict(zip(raw['time'], raw['shortwave_radiation_previous_day2'])))
    source_errors = {}
    for label, data, prior in (('train', source_train, oof), ('validation', source_valid, old_valid)):
        assert data.index.is_unique and data.index.is_monotonic_increasing
        assert pd.DatetimeIndex(pd.to_datetime(data.target_time)).equals(data.index+DAY)
        epochs = [(origin.to_pydatetime()+timedelta(hours=24)).replace(tzinfo=timezone(timedelta(hours=3))).timestamp() for origin in data.index]
        assert np.array_equal(data.target_epoch_utc, epochs)
        assert np.array_equal(data.ecmwf_day2, [archives[0][epoch] for epoch in epochs])
        assert np.array_equal(data.gfs_day2, [archives[1][epoch] for epoch in epochs])
        assert np.array_equal(data.ecmwf_day2, original_features.loc[data.index, 'nwp_day2_radiation'])
        assert np.array_equal(data.gfs_day2, gfs.loc[data.index, 'gfs_day2_radiation_w_m2'])
        close(data[CORE[4:]], original_features.loc[data.index, CORE[4:]])
        for field in ('temperature_2m', 'shortwave_radiation', 'relative_humidity_2m', 'cloud_cover'):
            assert np.array_equal(prior.loc[data.index, field], original_features.loc[data.index, field])
        assert np.array_equal(data.nwp_radiation, prior.loc[data.index, 'nwp_radiation'])
        assert np.array_equal(data.nwp_cloud, prior.loc[data.index, 'nwp_cloud'])
        base = prior.loc[data.index, 'base_prediction'] if label == 'train' else old_decisions.base_prediction
        assert np.array_equal(data.base_prediction, base)
        source_errors[label] = close(data.solar_scale, [solar_scale(t.to_pydatetime()+timedelta(hours=24)) for t in data.index])
    assert np.array_equal(source_train.target, oof.loc[train.index, 'target'])
    assert np.array_equal(source_train.fold, oof.loc[train.index, 'fold'])
    assert 'target' not in valid and 'fold' not in valid

    decisions = frame(RESULT/'validation-decisions.csv')
    assert decisions.index.equals(valid.index)
    close(decisions.base_prediction, valid.base_prediction)
    truth_train = train.target.to_numpy() > 600
    eligible_rows = train.fold.to_numpy() >= 3
    cap = counts(truth_train[eligible_rows], train.ecmwf_day2.to_numpy()[eligible_rows] > 600)['fp']
    replay_errors, probabilities, thresholds = {}, {}, {}
    fits = {(row['arm'], row['fold']):row for row in freeze['fits']}
    for arm in ('core', 'expanded'):
        x = features(train, arm == 'expanded')
        xv = features(valid, arm == 'expanded')
        assert list(x) == freeze['feature_names'][arm]
        forward = frame(RESULT/f'{arm}-forward.csv')
        assert forward.index.equals(train.index)
        assert np.array_equal(forward.truth, truth_train.astype(int)) and np.array_equal(forward.fold, train.fold)
        assert np.array_equal(forward.forward_probability.notna(), eligible_rows)
        for fold in range(3,7):
            held = train.fold.to_numpy() == fold
            first = train.index[held][0]
            fit = (train.fold.to_numpy() < fold) & (train.index+DAY < first)
            assert (train.index[fit]+DAY).max() < first
            membership = frame(RESULT/f'{arm}-fold{fold}-membership.csv')
            assert membership.index.equals(train.index)
            assert np.array_equal(membership.fit, fit.astype(int)) and np.array_equal(membership.held, held.astype(int))
            assert pd.DatetimeIndex(pd.to_datetime(membership.target_time)).equals(train.index+DAY)
            info = fits[(arm,fold)]
            assert info['fit_rows'] == int(fit.sum()) and info['held_rows'] == int(held.sum())
            assert info['held_origin_first'] == str(first) and info['fit_target_last'] == str((train.index[fit]+DAY).max())
            model = lgb.Booster(model_file=str(RESULT/f'{arm}-fold{fold}.txt'))
            assert model.feature_name() == list(x) and model.current_iteration() == 150
            replay_errors[f'{arm}-fold{fold}'] = close(model.predict(x.loc[held], num_threads=2), forward.loc[held, 'forward_probability'])
        ledger = pd.read_csv(RESULT/f'{arm}-thresholds.csv', float_precision='round_trip')
        assert ledger.tick.tolist() == list(range(10,191))
        ranked = []
        for saved in ledger.to_dict('records'):
            tick = saved['tick']
            measured = counts(truth_train[eligible_rows], forward.forward_probability.to_numpy()[eligible_rows] > tick/200)
            check_metrics(measured, saved)
            assert saved['threshold'] == tick/200 and saved['raw_ecmwf_fp_cap'] == cap
            admitted = measured['f1_exact'] is not None and measured['fp'] <= cap
            assert bool(saved['eligible']) == admitted
            if admitted:
                ranked.append((Fraction(measured['f1_exact']), -abs(tick-100), tick))
        tick = max(ranked)[2]
        chosen = freeze['selected_training_thresholds'][arm]
        assert chosen['tick'] == tick
        check_metrics(counts(truth_train[eligible_rows], forward.forward_probability.to_numpy()[eligible_rows] > tick/200), chosen)
        thresholds[arm] = tick/200
        model = lgb.Booster(model_file=str(RESULT/f'{arm}-final.txt'))
        assert model.feature_name() == list(xv) and model.current_iteration() == 150
        probabilities[arm] = model.predict(xv, num_threads=2)
        replay_errors[f'{arm}-final'] = close(probabilities[arm], decisions[f'{arm}_probability'])
        assert np.array_equal(probabilities[arm] > tick/200, decisions[f'{arm}_call'].astype(bool))

    supplied = frame(EXP/'inputs/cv_predictions_v2.csv', 'time')
    original = frame(EXP/'inputs/original-validation.csv', 'time')
    fixed = frame(EXP/'inputs/fixed008-validation.csv', 'feature_time')
    for data in (supplied, original, fixed):
        assert data.index.equals(valid.index)
    assert np.array_equal(supplied.actual, original.actual) and np.array_equal(supplied.baseline, original.baseline)
    assert np.array_equal(supplied.actual, fixed.weather_actual_w_m2)
    assert pd.DatetimeIndex(pd.to_datetime(fixed.target_time)).equals(valid.index+DAY)
    actual = supplied.actual.to_numpy()
    truth = actual > 600
    points = dict(base_refit=valid.base_prediction.to_numpy(), supplied_v2_600=supplied.predicted.to_numpy(),
                  supplied_v2_562=supplied.predicted.to_numpy(), supplied_raw_day1=supplied.forecast.to_numpy(),
                  retained_raw_day2=valid.ecmwf_day2.to_numpy(), persistence=supplied.baseline.to_numpy())
    calls = {name:values > (562 if name == 'supplied_v2_562' else 600) for name,values in points.items()}
    calls['fixed008'] = fixed.predicted_positive.to_numpy(dtype=bool)
    calls.update({arm:probabilities[arm] > thresholds[arm] for arm in probabilities})
    evaluated = frame(RESULT/'validation-evaluation.csv')
    assert evaluated.index.equals(valid.index) and np.array_equal(evaluated.actual, actual)
    assert pd.DatetimeIndex(pd.to_datetime(evaluated.target_time)).equals(valid.index+DAY)
    summary = read_json(RESULT/'summary.json')
    metrics = {}
    for name, call in calls.items():
        metrics[name] = counts(truth, call)
        check_metrics(metrics[name], summary['metrics'][name])
        assert np.array_equal(call, evaluated[f'call_{name}'].astype(bool))
        if name in points:
            close(evaluated[f'radiation_{name}'], points[name])
            errors = (points[name]-actual).tolist()
            check_metrics(dict(mae_w_m2=math.fsum(map(abs,errors))/len(errors),
                rmse_w_m2=math.sqrt(math.fsum(e*e for e in errors)/len(errors)), bias_w_m2=math.fsum(errors)/len(errors)), summary['metrics'][name])
        elif name in probabilities:
            p = probabilities[name]
            clipped = np.clip(p, 1e-15, 1-1e-15)
            check_metrics(dict(brier=float(np.mean((p-truth)**2)), log_loss=float(-np.mean(np.where(truth,np.log(clipped),np.log1p(-clipped))))), summary['metrics'][name])
    dates = np.array([(t.to_pydatetime()+timedelta(hours=24)).date() for t in valid.index])
    days = sorted(set(dates))
    assert len(days) == 150 and all(b-a == timedelta(days=1) for a,b in zip(days,days[1:]))
    draws = np.random.Generator(np.random.PCG64(17017)).integers(0,len(days),size=(2000,len(days)))
    distributions = {}
    for name, call in calls.items():
        daily = [counts(truth[dates==day],call[dates==day]) for day in days]
        blocks = np.array([[r['tp'],r['fp'],r['fn']] for r in daily],dtype=np.int64)
        total = blocks[draws].sum(axis=1)
        denominator = 2*total[:,0]+total[:,1]+total[:,2]
        distributions[name] = np.divide(2*total[:,0],denominator,out=np.full(2000,np.nan),where=denominator!=0)
    bootstrap = read_json(RESULT/'day-bootstrap.json')
    assert (bootstrap['seed'], bootstrap['replicates'], bootstrap['target_day_blocks']) == (17017,2000,150)
    intervals, comparisons = {}, {}
    for arm in probabilities:
        comparisons[arm] = {}
        for control in ('core','base_refit','supplied_v2_600','supplied_v2_562','fixed008'):
            if arm == control:
                continue
            name = f'{arm}_minus_{control}'
            delta = distributions[arm]-distributions[control]
            endpoints = np.quantile(delta[np.isfinite(delta)],[.025,.975])
            saved = bootstrap['comparisons'][name]
            close(endpoints,[saved['lower_025'],saved['upper_975']])
            assert int(np.sum(~np.isfinite(delta))) == saved['undefined_replicates'] == 0
            intervals[name] = endpoints.tolist()
            comparisons[arm][control] = dict(f1_difference=metrics[arm]['f1']-metrics[control]['f1'],
                true_positive_difference=metrics[arm]['tp']-metrics[control]['tp'],
                false_positive_difference=metrics[arm]['fp']-metrics[control]['fp'],
                higher_f1_without_more_false_positives=Fraction(metrics[arm]['f1_exact'])>Fraction(metrics[control]['f1_exact']) and metrics[arm]['fp']<=metrics[control]['fp'])
        assert summary['comparisons'][arm]['user_gate'] == comparisons[arm]['fixed008']['higher_f1_without_more_false_positives']
    for name, expected in lock['source_sha256'].items():
        assert sha(ROOT/name) == expected
    return dict(status='PASS', source_sha256=sha(Path(__file__)), helper_sha256=sha(HELPER), lock_sha256=sha(EXP/'lock.json'),
        source_hashes_checked=len(lock['source_sha256']), original_run_exit_code=execution['exit_code'], validation_hours=len(valid),
        matched_training_hours=len(train), excluded_training_hours=len(excluded), training_threshold_hours=int(eligible_rows.sum()),
        intermediate_models_replayed=8, final_models_replayed=2, maximum_replay_errors=replay_errors,
        maximum_solar_reconstruction_errors=source_errors, threshold_rows_checked=362, training_false_positive_cap=cap,
        thresholds=thresholds, metrics=metrics, comparisons=comparisons, paired_f1_intervals=intervals,
        fits_executed=0, test_files_read=False,
        limits=['Additional forecasts improve the matched head, but its paired interval includes zero.',
                'Expanded versus fixed-threshold v2 has a positive descriptive paired interval, without correction for repeated validation use.',
                'Expanded remains below 008 F1 with five more false alarms. Both requested gates fail.',
                'Training false-positive limits do not guarantee validation false-positive limits.'])


if __name__ == '__main__':
    with h.threadpool_limits(limits=2):
        report = audit()
    with (HERE/'review.json').open('x') as stream:
        json.dump(report,stream,indent=2,allow_nan=False)
        stream.write('\n')
    print(json.dumps(report,allow_nan=False))
