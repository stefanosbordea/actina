"""Replay all saved 019 logistic coefficients and exact event evaluations."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name]='2'
from datetime import timedelta
from fractions import Fraction
import importlib.util
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
EXP=HERE.parent
ROOT=EXP.parents[2]
SOURCE=EXP.parent/'v2-017'
CONTEXT=EXP.parent/'v2-018'
RESULT=EXP/'result'
HELPER=SOURCE/'review/review.py'
spec=importlib.util.spec_from_file_location('independent017',HELPER)
h=importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
np,pd=h.np,h.pd
sha,read_json,frame,counts,close,check_metrics=h.sha,h.read_json,h.frame,h.counts,h.close,h.check_metrics
DAY=pd.Timedelta(hours=24)
CONTEXT_NAMES=['past_v2_bias','past_v2_mae','past_ecmwf_bias','past_ecmwf_mae']


def probability(model,x):
    assert model['features']==list(x) and model['classes']==[False,True]
    p=model['parameters']
    assert p['C']==1 and p['solver']=='lbfgs' and p['tol']==1e-8 and p['max_iter']==1000 and p['class_weight'] is None
    assert 0<model['iterations']<1000
    linear=x.to_numpy()@np.asarray(model['coefficients'])+model['intercept']
    return np.array([1/(1+math.exp(-z)) if z>=0 else math.exp(z)/(1+math.exp(z)) for z in linear])


def audit():
    lock=read_json(EXP/'lock.json')
    for name,expected in lock['source_sha256'].items():
        assert sha(ROOT/name)==expected,name
    completion=read_json(RESULT/'completion.json')
    assert completion['status']=='completed' and completion['error'] is None
    for name,expected in completion['output_sha256'].items():
        assert sha(RESULT/name)==expected,name
    head=read_json(RESULT/'head-freeze.json')
    decision=read_json(RESULT/'decision-freeze.json')
    assert head['lock_sha256']==sha(EXP/'lock.json') and decision['head_freeze_sha256']==sha(RESULT/'head-freeze.json')
    for name,expected in head['models_sha256'].items():
        assert sha(RESULT/name)==expected,name
    assert sha(RESULT/'validation-decisions.csv')==decision['validation_decisions_sha256']
    assert sha(CONTEXT/'result/validation-context.csv')==decision['context_sha256']
    execution=read_json(EXP/'execution-001.json')
    assert execution['exit_code']==0 and sha(EXP/'execution-001.log')==execution['log_sha256']
    assert lock['frozen_at_utc']<execution['started_at_utc']<head['frozen_at_utc']<decision['frozen_at_utc']<completion['completed_at_utc']
    log=(EXP/'execution-001.log').read_text()
    assert log.index('HEAD_FREEZE')<log.index('DECISION_FREEZE')
    assert 'ConvergenceWarning' not in log
    prior_review=read_json(CONTEXT/'review/review.json')
    prior_prefix=read_json(CONTEXT/'review/prefix-mutation.json')
    assert prior_review['status']==prior_prefix['status']=='PASS'
    assert prior_review['lock_sha256']==sha(CONTEXT/'lock.json')
    old_completion=read_json(CONTEXT/'result/completion.json')
    for name in ('training-context.csv','validation-context.csv','training-context-coverage.csv','validation-context-coverage.csv'):
        assert sha(CONTEXT/'result'/name)==old_completion['output_sha256'][name]
    train=frame(SOURCE/'inputs/train.csv',original_parser=True)
    valid=frame(SOURCE/'inputs/validation.csv',original_parser=True)
    tc=frame(CONTEXT/'result/training-context.csv',original_parser=True)
    vc=frame(CONTEXT/'result/validation-context.csv',original_parser=True)
    assert tc.index.equals(train.index) and vc.index.equals(valid.index) and list(tc)==list(vc)==CONTEXT_NAMES
    assert (len(train),len(valid))==(10675,3566) and (train.index+DAY).max()<valid.index.min()
    truth_train=train.target.to_numpy()>600
    eligible=train.fold.to_numpy()>=3
    cap=counts(truth_train[eligible],train.ecmwf_day2.to_numpy()[eligible]>600)['fp']
    decisions=frame(RESULT/'validation-decisions.csv')
    assert decisions.index.equals(valid.index)
    close(decisions.base_prediction,valid.base_prediction)
    probabilities,thresholds,replay_errors,iterations={},{},{},{}
    fits={(row['arm'],row['fold']):row for row in head['fits']}
    for arm in ('core','expanded'):
        x=h.features(train,True)
        xv=h.features(valid,True)
        if arm=='expanded':
            x=pd.concat([x,tc],axis=1)
            xv=pd.concat([xv,vc],axis=1)
        forward=frame(RESULT/f'{arm}-forward.csv')
        assert forward.index.equals(train.index) and np.array_equal(forward.truth,truth_train.astype(int))
        assert np.array_equal(forward.fold,train.fold) and np.array_equal(forward.forward_probability.notna(),eligible)
        for fold in range(3,7):
            held=train.fold.to_numpy()==fold
            fit=(train.fold.to_numpy()<fold)&(train.index+DAY<train.index[held][0])
            member=frame(RESULT/f'{arm}-fold{fold}-membership.csv')
            assert member.index.equals(train.index)
            assert np.array_equal(member.fit,fit.astype(int)) and np.array_equal(member.held,held.astype(int))
            assert pd.DatetimeIndex(pd.to_datetime(member.target_time)).equals(train.index+DAY)
            assert (train.index[fit]+DAY).max()<train.index[held][0]
            info=fits[(arm,fold)]
            assert info['fit_rows']==int(fit.sum()) and info['held_rows']==int(held.sum())
            assert info['fit_target_last']==str((train.index[fit]+DAY).max()) and info['held_origin_first']==str(train.index[held][0])
            label=f'{arm}-fold{fold}'
            model=read_json(RESULT/f'{label}.json')
            replay_errors[label]=close(probability(model,x.loc[held]),forward.loc[held,'forward_probability'])
            iterations[label]=model['iterations']
        ledger=pd.read_csv(RESULT/f'{arm}-thresholds.csv',float_precision='round_trip')
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
        assert head['selected_training_thresholds'][arm]['tick']==tick
        check_metrics(counts(truth_train[eligible],forward.forward_probability.to_numpy()[eligible]>tick/200),head['selected_training_thresholds'][arm])
        thresholds[arm]=tick/200
        model=read_json(RESULT/f'{arm}-final.json')
        probabilities[arm]=probability(model,xv)
        iterations[f'{arm}-final']=model['iterations']
        replay_errors[f'{arm}-final']=close(probabilities[arm],decisions[f'{arm}_probability'])
        assert np.array_equal(probabilities[arm]>tick/200,decisions[f'{arm}_call'].astype(bool))
    supplied=frame(SOURCE/'inputs/cv_predictions_v2.csv','time')
    original=frame(SOURCE/'inputs/original-validation.csv','time')
    fixed=frame(SOURCE/'inputs/fixed008-validation.csv','feature_time')
    for data in (supplied,original,fixed):
        assert data.index.equals(valid.index)
    assert np.array_equal(supplied.actual,original.actual) and np.array_equal(supplied.baseline,original.baseline)
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
    metrics={}
    for name,call in calls.items():
        metrics[name]=counts(truth,call)
        check_metrics(metrics[name],summary['metrics'][name])
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
            comparisons[arm][control]=dict(f1_difference=metrics[arm]['f1']-metrics[control]['f1'],
                true_positive_difference=metrics[arm]['tp']-metrics[control]['tp'],false_positive_difference=metrics[arm]['fp']-metrics[control]['fp'],
                higher_f1_without_more_false_positives=Fraction(metrics[arm]['f1_exact'])>Fraction(metrics[control]['f1_exact']) and metrics[arm]['fp']<=metrics[control]['fp'])
        assert summary['comparisons'][arm]['user_gate']==comparisons[arm]['fixed008']['higher_f1_without_more_false_positives']
    for name,expected in lock['source_sha256'].items():
        assert sha(ROOT/name)==expected
    return dict(status='PASS',source_sha256=sha(Path(__file__)),helper_sha256=sha(HELPER),lock_sha256=sha(EXP/'lock.json'),
        source_hashes_checked=len(lock['source_sha256']),prior_context_audit_sha256=sha(CONTEXT/'review/review.json'),
        prior_actual_prefix_proof_sha256=sha(CONTEXT/'review/prefix-mutation.json'),original_run_exit_code=execution['exit_code'],
        training_hours=len(train),validation_hours=len(valid),intermediate_models_replayed=8,final_models_replayed=2,
        maximum_replay_errors=replay_errors,iterations=iterations,threshold_rows_checked=362,training_false_positive_cap=cap,
        thresholds=thresholds,metrics=metrics,comparisons=comparisons,paired_f1_intervals=intervals,
        fits_executed=0,test_files_read=False,limits=['Reused exploratory validation, not a fresh holdout.',
            'Unchanged context from018 was already independently reconstructed and tested against actual future-observation mutations.',
            'Reported paired intervals do not correct repeated validation use.'])


if __name__=='__main__':
    with h.h.threadpool_limits(limits=2):
        report=audit()
    with (HERE/'review.json').open('x') as stream:
        json.dump(report,stream,indent=2,allow_nan=False)
        stream.write('\n')
    print(json.dumps(report,allow_nan=False))
