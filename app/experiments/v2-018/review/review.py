"""Independent causal-context reconstruction and saved-model replay for 018."""
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '2'
from bisect import bisect_left
from datetime import timedelta, timezone
from fractions import Fraction
import importlib.util
import json
import math
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
ROOT = EXP.parents[2]
PREVIOUS = EXP.parent/'v2-017'
RESULT = EXP/'result'
HELPER = PREVIOUS/'review/review.py'
spec = importlib.util.spec_from_file_location('independent017', HELPER)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
np, pd, lgb = h.np, h.pd, h.lgb
sha, read_json, frame, counts, close, check_metrics = h.sha, h.read_json, h.frame, h.counts, h.close, h.check_metrics
DAY = pd.Timedelta(hours=24)
NAMES = ['past_v2_bias', 'past_v2_mae', 'past_ecmwf_bias', 'past_ecmwf_mae']


def independent_context(origins, history, observed):
    values, coverage = {}, {}
    for name, field in (('v2','v2_prediction'),('ecmwf','ecmwf_prediction')):
        source = history.loc[history[field].notna(),field]
        times = sorted(set(source.index)&set(observed.index))
        residual = [float(source.at[t])-float(observed.at[t,'actual']) for t in times]
        mean, absolute, size, latest = [], [], [], []
        for origin in origins:
            start = bisect_left(times,origin-pd.Timedelta(hours=336))
            stop = bisect_left(times,origin)
            block = residual[start:stop]
            assert all(origin-pd.Timedelta(hours=336) <= t < origin for t in times[start:stop])
            mean.append(math.fsum(block)/len(block)/100 if block else 0)
            absolute.append(math.fsum(map(abs,block))/len(block)/100 if block else 0)
            size.append(len(block))
            latest.append(str(times[stop-1]) if block else '')
        values[f'past_{name}_bias'] = mean
        values[f'past_{name}_mae'] = absolute
        coverage[f'{name}_count'] = size
        coverage[f'{name}_latest_target'] = latest
    return pd.DataFrame(values,index=origins), pd.DataFrame(coverage,index=origins)


def audit():
    lock = read_json(EXP/'lock.json')
    for name, expected in lock['source_sha256'].items():
        assert sha(ROOT/name) == expected, name
    completion = read_json(RESULT/'completion.json')
    assert completion['status'] == 'completed' and completion['error'] is None
    for name, expected in completion['output_sha256'].items():
        assert sha(RESULT/name) == expected, name
    head = read_json(RESULT/'head-freeze.json')
    decision = read_json(RESULT/'decision-freeze.json')
    assert head['lock_sha256'] == sha(EXP/'lock.json')
    assert decision['head_freeze_sha256'] == sha(RESULT/'head-freeze.json')
    for entries in (head['model_sha256'],head['training_context_sha256'],decision['prediction_sha256']):
        for name,expected in entries.items():
            assert sha(RESULT/name) == expected, name
    execution = read_json(EXP/'execution-001.json')
    assert execution['exit_code'] == 0 and execution['log_sha256'] == sha(EXP/'execution-001.log')
    assert lock['frozen_at_utc'] < execution['started_at_utc'] < head['frozen_at_utc'] < decision['frozen_at_utc'] < completion['completed_at_utc']
    log = (EXP/'execution-001.log').read_text()
    assert log.index('HEAD_FREEZE') < log.index('DECISION_FREEZE')
    manifest = read_json(EXP/'inputs/manifest.json')
    upstream = subprocess.check_output(['git','show',f"{manifest['upstream_commit']}:{manifest['upstream_weather_file']}"],cwd=ROOT)
    assert h.h.hashlib.sha256(upstream).hexdigest() == manifest['upstream_weather_sha256']
    for name,expected in manifest['files'].items():
        assert sha(EXP/'inputs'/name) == expected
    train = frame(PREVIOUS/'inputs/train.csv',original_parser=True)
    valid = frame(PREVIOUS/'inputs/validation.csv',original_parser=True)
    assert (len(train),len(valid)) == (10675,3566)
    assert (train.index+DAY).max() < valid.index.min()
    history = frame(EXP/'inputs/history-predictions.csv','target_time',True)
    observed_train = frame(EXP/'inputs/observations-training.csv','target_time',True)
    stream = frame(EXP/'inputs/observations-validation-stream.csv','target_time',True)
    observed = pd.concat([observed_train,stream])
    for data in (history,observed):
        assert data.index.is_unique and data.index.is_monotonic_increasing
    assert observed_train.index.max() < train.index.max() <= stream.index.min()
    assert stream.index.max() < valid.index.max()
    present = history.v2_prediction.notna()
    assert pd.DatetimeIndex(pd.to_datetime(history.loc[present,'v2_source_origin'])).equals(history.index[present]-DAY)
    old_oof = frame(EXP.parent/'v2-016/result/base-oof.csv')
    old_valid = frame(EXP.parent/'v2-016/result/validation-decisions.csv')
    source_prediction = pd.concat([old_oof.base_prediction,old_valid.base_prediction])
    source_prediction.index = source_prediction.index+DAY
    close(history.loc[present,'v2_prediction'], source_prediction.loc[history.index[present]])
    raw = read_json(EXP.parent/'nwp-archive-001/archive.json')['hourly']
    raw_ecmwf = dict(zip(raw['time'],raw['shortwave_radiation_previous_day2']))
    present_ecmwf = history.ecmwf_prediction.notna()
    epochs = [t.to_pydatetime().replace(tzinfo=timezone(timedelta(hours=3))).timestamp() for t in history.index[present_ecmwf]]
    assert np.array_equal(history.loc[present_ecmwf,'ecmwf_prediction'],[raw_ecmwf[t] for t in epochs])
    # Parse only retained pre-final-origin observation rows from the upstream weather table.
    import csv, io
    retained = {}
    for row in csv.DictReader(io.StringIO(upstream.decode())):
        time = pd.Timestamp(row['time'])
        if time in observed.index:
            retained[time] = float(row['shortwave_radiation'])
    assert set(retained) == set(observed.index)
    assert np.array_equal(observed.actual,[retained[t] for t in observed.index])
    contexts, errors, coverage_summary = {}, {}, {}
    for label, data, observations in (('training',train,observed_train),('validation',valid,observed)):
        reconstructed, coverage = independent_context(data.index,history,observations)
        saved = frame(RESULT/f'{label}-context.csv')
        saved_coverage = frame(RESULT/f'{label}-context-coverage.csv')
        assert saved.index.equals(data.index) and list(saved) == NAMES
        errors[label] = close(reconstructed,saved,tolerance=1e-12)
        for field in coverage:
            if field.endswith('_count'):
                assert np.array_equal(coverage[field],saved_coverage[field])
            else:
                assert coverage[field].tolist() == saved_coverage[field].fillna('').tolist()
        # Match exact retained inference values after checking their independent derivation.
        contexts[label] = saved
        coverage_summary[label] = {name:dict(minimum=int(coverage[f'{name}_count'].min()), maximum=int(coverage[f'{name}_count'].max()),
            zero_windows=int((coverage[f'{name}_count']==0).sum()),partial_windows=int((coverage[f'{name}_count']<336).sum())) for name in ('v2','ecmwf')}
    decisions = frame(RESULT/'validation-decisions.csv')
    assert decisions.index.equals(valid.index)
    close(decisions.base_prediction,valid.base_prediction)
    truth_train = train.target.to_numpy()>600
    eligible = train.fold.to_numpy()>=3
    cap = counts(truth_train[eligible],train.ecmwf_day2.to_numpy()[eligible]>600)['fp']
    probabilities, thresholds, replay_errors = {}, {}, {}
    for arm in ('core','expanded'):
        x = h.features(train,True)
        xv = h.features(valid,True)
        if arm == 'expanded':
            x = pd.concat([x,contexts['training']],axis=1)
            xv = pd.concat([xv,contexts['validation']],axis=1)
        forward = frame(RESULT/f'{arm}-forward.csv')
        assert forward.index.equals(train.index) and np.array_equal(forward.truth,truth_train.astype(int))
        assert np.array_equal(forward.forward_probability.notna(),eligible)
        for fold in range(3,7):
            held = train.fold.to_numpy()==fold
            fit = (train.fold.to_numpy()<fold)&(train.index+DAY<train.index[held][0])
            member = frame(RESULT/f'{arm}-fold{fold}-membership.csv')
            assert member.index.equals(train.index)
            assert np.array_equal(member.fit,fit.astype(int)) and np.array_equal(member.held,held.astype(int))
            assert pd.DatetimeIndex(pd.to_datetime(member.target_time)).equals(train.index+DAY)
            assert (train.index[fit]+DAY).max()<train.index[held][0]
            model = lgb.Booster(model_file=str(RESULT/f'{arm}-fold{fold}.txt'))
            assert model.current_iteration()==150 and model.feature_name()==list(x)
            replay_errors[f'{arm}-fold{fold}'] = close(model.predict(x.loc[held],num_threads=2),forward.loc[held,'forward_probability'])
        ledger = pd.read_csv(RESULT/f'{arm}-thresholds.csv',float_precision='round_trip')
        assert ledger.tick.tolist()==list(range(10,191))
        ranked=[]
        for saved in ledger.to_dict('records'):
            tick=saved['tick']
            computed=counts(truth_train[eligible],forward.forward_probability.to_numpy()[eligible]>tick/200)
            check_metrics(computed,saved)
            admitted=computed['f1_exact'] is not None and computed['fp']<=cap
            assert saved['threshold']==tick/200 and saved['raw_ecmwf_fp_cap']==cap and bool(saved['eligible'])==admitted
            if admitted:
                ranked.append((Fraction(computed['f1_exact']),-abs(tick-100),tick))
        assert ranked
        tick=max(ranked)[2]
        assert tick==head['selected_training_thresholds'][arm]['tick']
        thresholds[arm]=tick/200
        model=lgb.Booster(model_file=str(RESULT/f'{arm}-final.txt'))
        assert model.current_iteration()==150 and model.feature_name()==list(xv)
        probabilities[arm]=model.predict(xv,num_threads=2)
        replay_errors[f'{arm}-final']=close(probabilities[arm],decisions[f'{arm}_probability'])
        assert np.array_equal(probabilities[arm]>tick/200,decisions[f'{arm}_call'].astype(bool))
        if arm=='core':
            prior_forward=frame(PREVIOUS/'result/expanded-forward.csv')
            close(forward.loc[eligible,'forward_probability'],prior_forward.loc[eligible,'forward_probability'])
            prior=frame(PREVIOUS/'result/validation-decisions.csv')
            close(probabilities[arm],prior.expanded_probability)
            assert np.array_equal(decisions.core_call,prior.expanded_call)
    supplied=frame(PREVIOUS/'inputs/cv_predictions_v2.csv','time')
    fixed=frame(PREVIOUS/'inputs/fixed008-validation.csv','feature_time')
    assert supplied.index.equals(valid.index) and fixed.index.equals(valid.index)
    assert np.array_equal(supplied.actual,fixed.weather_actual_w_m2)
    actual=supplied.actual.to_numpy()
    truth=actual>600
    points=dict(base_refit=valid.base_prediction.to_numpy(),supplied_v2_600=supplied.predicted.to_numpy(),
        supplied_v2_562=supplied.predicted.to_numpy(),supplied_raw_day1=supplied.forecast.to_numpy(),
        retained_raw_day2=valid.ecmwf_day2.to_numpy(),persistence=supplied.baseline.to_numpy())
    calls={name:values>(562 if name=='supplied_v2_562' else 600) for name,values in points.items()}
    calls['fixed008']=fixed.predicted_positive.to_numpy(dtype=bool)
    calls.update({arm:probabilities[arm]>thresholds[arm] for arm in probabilities})
    summary=read_json(RESULT/'summary.json')
    evaluation=frame(RESULT/'validation-evaluation.csv')
    assert evaluation.index.equals(valid.index) and np.array_equal(evaluation.actual,actual)
    assert pd.DatetimeIndex(pd.to_datetime(evaluation.target_time)).equals(valid.index+DAY)
    measured={}
    for name,call in calls.items():
        measured[name]=counts(truth,call)
        check_metrics(measured[name],summary['metrics'][name])
        assert np.array_equal(call,evaluation[f'call_{name}'].astype(bool))
        if name in points:
            close(points[name],evaluation[f'radiation_{name}'])
            error=(points[name]-actual).tolist()
            check_metrics(dict(mae_w_m2=math.fsum(map(abs,error))/len(error),rmse_w_m2=math.sqrt(math.fsum(e*e for e in error)/len(error)),
                bias_w_m2=math.fsum(error)/len(error)),summary['metrics'][name])
        elif name in probabilities:
            p=probabilities[name]
            clipped=np.clip(p,1e-15,1-1e-15)
            check_metrics(dict(brier=float(np.mean((p-truth)**2)),log_loss=float(-np.mean(np.where(truth,np.log(clipped),np.log1p(-clipped))))),summary['metrics'][name])
    dates=np.array([(t.to_pydatetime()+timedelta(hours=24)).date() for t in valid.index])
    days=sorted(set(dates))
    assert len(days)==150 and all(b-a==timedelta(days=1) for a,b in zip(days,days[1:]))
    draws=np.random.Generator(np.random.PCG64(17017)).integers(0,len(days),size=(2000,len(days)))
    distributions={}
    for name,call in calls.items():
        daily=[counts(truth[dates==day],call[dates==day]) for day in days]
        blocks=np.array([[r['tp'],r['fp'],r['fn']] for r in daily],dtype=np.int64)
        total=blocks[draws].sum(axis=1)
        denominator=2*total[:,0]+total[:,1]+total[:,2]
        distributions[name]=np.divide(2*total[:,0],denominator,out=np.full(2000,np.nan),where=denominator!=0)
    bootstrap=read_json(RESULT/'day-bootstrap.json')
    assert (bootstrap['seed'],bootstrap['replicates'],bootstrap['target_day_blocks'])==(17017,2000,150)
    intervals,comparisons={},{}
    for arm in probabilities:
        comparisons[arm]={}
        for control in ('core','base_refit','supplied_v2_600','supplied_v2_562','fixed008'):
            if arm==control:
                continue
            name=f'{arm}_minus_{control}'
            delta=distributions[arm]-distributions[control]
            endpoints=np.quantile(delta[np.isfinite(delta)],[.025,.975])
            close(endpoints,[bootstrap['comparisons'][name]['lower_025'],bootstrap['comparisons'][name]['upper_975']])
            assert int(np.sum(~np.isfinite(delta)))==bootstrap['comparisons'][name]['undefined_replicates']==0
            intervals[name]=endpoints.tolist()
            comparisons[arm][control]=dict(f1_difference=measured[arm]['f1']-measured[control]['f1'],
                true_positive_difference=measured[arm]['tp']-measured[control]['tp'],false_positive_difference=measured[arm]['fp']-measured[control]['fp'],
                higher_f1_without_more_false_positives=Fraction(measured[arm]['f1_exact'])>Fraction(measured[control]['f1_exact']) and measured[arm]['fp']<=measured[control]['fp'])
        assert summary['comparisons'][arm]['user_gate']==comparisons[arm]['fixed008']['higher_f1_without_more_false_positives']
    for label,key in (('training','train'),('validation','validation')):
        assert coverage_summary[label]==summary['coverage'][key]
    for name,expected in lock['source_sha256'].items():
        assert sha(ROOT/name)==expected
    return dict(status='PASS',source_sha256=sha(Path(__file__)),helper_sha256=sha(HELPER),lock_sha256=sha(EXP/'lock.json'),
        source_hashes_checked=len(lock['source_sha256']),original_run_exit_code=execution['exit_code'],training_hours=len(train),validation_hours=len(valid),
        context_entries_checked=(len(train)+len(valid))*4,maximum_context_error=errors,coverage=coverage_summary,
        intermediate_models_replayed=8,final_models_replayed=2,maximum_replay_errors=replay_errors,
        threshold_rows_checked=362,training_false_positive_cap=cap,thresholds=thresholds,metrics=measured,
        comparisons=comparisons,paired_f1_intervals=intervals,fits_executed=0,test_files_read=False,
        timing='Weights and thresholds frozen before validation observation stream. Each context depends only on targets before its origin. Full scoring follows decision freeze.',
        limits=['Reused exploratory validation, not a fresh holdout.', 'Historical OOF forecast history is reconstructed rather than a logged operational feed.',
                'Archived weather forecast publication times are not independently established.'])


if __name__=='__main__':
    with h.h.threadpool_limits(limits=2):
        report=audit()
    with (HERE/'review.json').open('x') as stream:
        json.dump(report,stream,indent=2,allow_nan=False)
        stream.write('\n')
    print(json.dumps(report,allow_nan=False))
