"""Independent008 audit: saved-model prediction only; never fit or import the runner."""
import csv
from datetime import datetime,timedelta,timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import lightgbm as lgb
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
EXP=HERE.parent
ROOT=EXP.parents[2]
OUT=EXP/'result'
ARMS=['weather_ecmwf','consensus_ecmwf','weather_two_source','consensus_two_source']
BASES=['weather_full','satellite_common']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def rows(p):
    with p.open() as f:return list(csv.DictReader(f))
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def num(v):return None if v=='' else float(v)
def ratio(m,k):
    a,b={'precision':(m['tp'],m['tp']+m['fp']),'recall':(m['tp'],m['tp']+m['fn']),'f1':(2*m['tp'],2*m['tp']+m['fp']+m['fn'])}[k]
    return Fraction(a,b) if b else Fraction(-1)
def qualifies(a,b):return all(ratio(a[s],k)>=0 and ratio(a[s],k)>=ratio(b[s],k) for s in BASES for k in ('precision','recall','f1'))
def improves(a,b):return qualifies(a,b) and any(ratio(a[s],k)>ratio(b[s],k) for s in BASES for k in ('precision','recall','f1'))
def rank(r):
    m=r['metrics'];f=[ratio(m[s],'f1') for s in BASES]
    return min(f),sum(f,Fraction())/2,min(ratio(m[s],'precision') for s in BASES),min(ratio(m[s],'recall') for s in BASES),-r['changed']
def decide(b,p,policy):return b if policy['kind']=='control' else (b and p>policy['lower']) or (not b and p>policy['upper'])
def count(truth,pred):
    pairs=list(zip(truth,pred));tp=sum(a and b for a,b in pairs);fp=sum(not a and b for a,b in pairs);fn=sum(a and not b for a,b in pairs);tn=sum(not a and not b for a,b in pairs)
    return dict(hours=len(pairs),tp=tp,fp=fp,fn=fn,tn=tn)
def verify(m,record):
    for k in ('hours','tp','fp','fn','tn'):assert m[k]==record[k],(k,m,record)
    for k in ('precision','recall','f1'):
        f=ratio(m,k);assert record[k] is None if f<0 else abs(float(f)-record[k])<=1e-15

def check():
    report=load(OUT/'report.json');report_sha=sha(OUT/'report.json');selection=load(OUT/'validation-selection.json')
    assert report['status']=='COMPLETE' and sha(EXP/'run.py')==report['code_sha256'] and sha(EXP/'PROTOCOL.md')==report['protocol_sha256']
    assert sha(OUT/'validation-selection.json')==report['selection_sha256']
    for name,digest in report['inputs_sha256'].items():assert sha(ROOT/name)==digest,name
    for name,digest in report['outputs_sha256'].items():assert sha(OUT/name)==digest,name
    old=EXP.parent/'f1-006/result';source=rows(old/'features.csv');target=rows(old/'feature-targets.csv');current=rows(OUT/'features.csv')
    assert len(source)==len(target)==len(current)==17832
    assert list(current[0])[1:]==report['features'] and len(report['features'])==27
    raw=load(EXP.parent/'nwp-alternative-001/result/response.json');hours=raw['hourly'];ts=hours['time']
    assert len(ts)==len(set(ts)) and all(b-a==3600 for a,b in zip(ts,ts[1:]))
    nwp_lookup=dict(zip(ts,hours['shortwave_radiation_previous_day2']))
    satellite={datetime.fromisoformat(r['valid_time_utc']):num(r['shortwave_radiation_w_m2']) for r in rows(EXP.parent/'satellite-reference-001/result/reference-full.csv')}
    by_origin={r['feature_time']:i for i,r in enumerate(source)};assert len(by_origin)==len(source)
    base_fields=list(source[0])[1:];satellite_values=[];epochs=[]
    for a,t,b in zip(source,target,current):
        assert a['feature_time']==t['feature_time']==b['feature_time']
        origin=datetime.fromisoformat(a['feature_time']);valid=datetime.fromisoformat(t['target_time'])
        assert valid==origin+timedelta(hours=24)
        epoch=int(valid.replace(tzinfo=timezone(timedelta(hours=3))).timestamp());assert epoch==int(t['target_epoch_utc'])
        epochs.append(epoch);satellite_values.append(satellite[datetime.fromtimestamp(epoch,timezone.utc)])
        for name in base_fields:assert num(a[name])==num(b[name]),(a['feature_time'],name)
        gfs=nwp_lookup[epoch];ecmwf=float(a['nwp_day2_radiation'])
        assert gfs is not None and math.isfinite(gfs) and gfs>=0
        assert float(b['gfs_day2_radiation'])==gfs and float(b['gfs_minus_ecmwf'])==gfs-ecmwf and float(b['gfs_ecmwf_absolute_difference'])==abs(gfs-ecmwf)
    all_pred={};best_policies={};metric_records=0;labels_checked=0;grid_pairs=0;replays=[];transitions={};saved_selected={};missing={}
    features=pd.read_csv(OUT/'features.csv',float_precision='round_trip');x=features.drop(columns='feature_time')
    for stage,file in [('validation','cv_predictions.csv'),('test','test_predictions.csv')]:
        split=rows(ROOT/'eval'/file);time_key=next(iter(split[0]));names=[r[time_key] for r in split]
        assert len(names)=={'validation':3566,'test':3567}[stage] and len(set(names))==len(names)
        indices=[by_origin[n] for n in names];weather=[float(r['actual']) for r in split];sat=[satellite_values[i] for i in indices]
        nwp=[float(source[i]['nwp_day2_radiation']) for i in indices];baseline=[v>600 for v in nwp];gfs=[nwp_lookup[epochs[i]] for i in indices]
        masks={'weather_full':list(range(len(indices))),'weather_common':[i for i,v in enumerate(sat) if v is not None]};masks['satellite_common']=masks['weather_common']
        missing[stage]=len(indices)-len(masks['weather_common'])
        truths={basis:[(sat[i] if basis=='satellite_common' else weather[i])>600 for i in mask] for basis,mask in masks.items()}
        def stats(decisions,expected,probability=None):
            nonlocal metric_records
            result={}
            for basis,mask in masks.items():
                m=count(truths[basis],[decisions[i] for i in mask]);verify(m,expected[basis]);metric_records+=1;result[basis]=m
                if probability is not None:
                    brier=math.fsum((probability[i]-truth)**2 for i,truth in zip(mask,truths[basis]))/len(mask)
                    assert abs(brier-expected[basis]['brier'])<=1e-14
            return result
        control_counts={basis:count(truths[basis],[baseline[i] for i in mask]) for basis,mask in masks.items()}
        train=[i for i,r in enumerate(target) if datetime.fromisoformat(r['target_time'])<datetime.fromisoformat(names[0])]
        labels=rows(OUT/f'{stage}-training-labels.csv');assert len(labels)==len(train)==report['splits'][stage]['training_hours']
        old_train=rows(old/f'{stage}-training-origins.csv');assert [r['feature_time'] for r in old_train]==[source[i]['feature_time'] for i in train]
        for r,i in zip(labels,train):
            assert r['feature_time']==source[i]['feature_time'] and r['target_time']==target[i]['target_time']
            w=float(target[i]['actual'])>600;s=satellite_values[i];soft=float(w) if s is None else (int(w)+int(s>600))/2
            assert float(r['soft_target'])==soft and int(r['weather_event'])==w
            assert int(r['satellite_missing'])==(s is None) and int(r['source_count'])==1+int(s is not None)
            assert (r['satellite_event']=='' if s is None else float(r['satellite_event'])==int(s>600))
            labels_checked+=1
        member=rows(OUT/f'{stage}-reference-membership.csv');assert len(member)==len(names)
        for r,i,w,s in zip(member,indices,weather,sat):
            assert r['feature_time']==source[i]['feature_time'] and float(r['weather_actual_w_m2'])==w and num(r['satellite_w_m2'])==s
            assert datetime.fromisoformat(r['target_time_utc'])==datetime.fromtimestamp(epochs[i],timezone.utc) and int(r['scored'])==(s is not None)
        for method in ['original','persistence','nwp_day2']:
            old_preds=rows(old/'predictions'/f'{stage}-{method}.csv');assert [r['feature_time'] for r in old_preds]==names
            p=[float(r['probability']) for r in old_preds]
            expected_positive=[float(s['predicted' if method=='original' else 'baseline'])>600 for s in split] if method!='nwp_day2' else baseline
            assert [v>.5 for v in p]==expected_positive
            stats(expected_positive,report['methods'][method][stage]['metrics'])
        for arm in ARMS:
            pred=rows(OUT/'predictions'/f'{stage}-{arm}.csv');assert len(pred)==len(names)
            all_pred[stage,arm]=pred;p=[float(r['probability']) for r in pred]
            for r,i,w,s,b in zip(pred,indices,weather,sat,baseline):
                assert r['feature_time']==source[i]['feature_time'] and r['target_time']==target[i]['target_time']
                assert float(r['weather_actual_w_m2'])==w and num(r['satellite_w_m2'])==s and int(r['nwp_positive'])==b
            if arm.endswith('two_source'):
                model_path=OUT/'models'/f'{stage}-{arm}.txt';model=lgb.Booster(model_file=str(model_path))
                assert model.feature_name()==list(x.columns)
                replay=model.predict(x.iloc[indices],num_threads=2,validate_features=True)
                assert np.array_equal(replay,np.array(p)),(stage,arm,float(np.max(abs(replay-p))))
                replays.append({'stage':stage,'arm':arm,'rows':len(p),'maximum_probability_error':0,'model_sha256':sha(model_path),'objective':model.params['objective'],'trees':model.num_trees()})
            else:
                prior=old/'predictions'/f'{stage}-larger.csv' if arm=='weather_ecmwf' else EXP.parent/'f1-007/result/predictions'/f'{stage}-consensus_larger.csv'
                prior_rows=rows(prior);assert [r['feature_time'] for r in prior_rows]==names and p==[float(r['probability']) for r in prior_rows]
            if stage=='validation':
                grid=load(OUT/f'validation-grid-{arm}.json');assert len(grid)==121
                assert [(r['policy']['lower'],r['policy']['upper']) for r in grid]==[(lo/20,hi/20) for lo in range(11) for hi in range(10,21)]
                for r in grid:
                    d=[decide(b,v,r['policy']) for b,v in zip(baseline,p)];m=stats(d,r['metrics']);changed=sum(a!=b for a,b in zip(d,baseline))
                    assert r['changed']==changed and r['qualifies']==qualifies(m,control_counts) and r['strict_gain']==improves(m,control_counts)
                    grid_pairs+=1
                eligible=[r for r in grid if r['strict_gain']]
                best=max(eligible,key=lambda r:(*rank(r),r['policy']['upper'],-r['policy']['lower'])) if eligible else {'policy':{'kind':'control'},'metrics':control_counts,'changed':0,'qualifies':True,'strict_gain':False}
                assert best['policy']==selection['policies'][arm]['policy'] and best['changed']==selection['policies'][arm]['changed']
                assert best['strict_gain']==selection['policies'][arm]['strict_gain'];best_policies[arm]=best
            policy=selection['policies'][arm]['policy'];assert policy==report['methods'][arm][stage]['policy']
            d=[decide(b,v,policy) for b,v in zip(baseline,p)];default=[v>.5 for v in p]
            assert d==[r['predicted_positive']=='1' for r in pred] and default==[r['default_positive']=='1' for r in pred]
            m=stats(d,report['methods'][arm][stage]['metrics'],p);stats(default,report['methods'][arm][stage]['default_0_5'],p)
            corrections={'added':sum(not b and v for b,v in zip(baseline,d)),'removed':sum(b and not v for b,v in zip(baseline,d)),'changed':sum(b!=v for b,v in zip(baseline,d))}
            assert corrections==report['methods'][arm][stage]['corrections'];transitions[stage+'-'+arm]=corrections;saved_selected[stage,arm]=m
        for method,values in [('ecmwf',nwp),('gfs',gfs),('arithmetic_mean',[(a+b)/2 for a,b in zip(nwp,gfs)])]:
            expected=report['irradiance_baselines'][method][stage];stats([v>600 for v in values],expected)
            for basis,mask in masks.items():
                errors=[values[i]-(sat[i] if basis=='satellite_common' else weather[i]) for i in mask]
                assert abs(math.fsum(abs(v) for v in errors)/len(errors)-expected[basis]['mae'])<=1e-10
                assert abs(math.sqrt(math.fsum(v*v for v in errors)/len(errors))-expected[basis]['rmse'])<=1e-10
    chosen=max(['weather_two_source','consensus_two_source'],key=lambda arm:(*rank(best_policies[arm]),arm=='weather_two_source'))
    assert chosen==selection['selected_augmented_arm']==report['selected_augmented_arm']
    for key,control_name in [('test_gate','nwp_day2'),('matched_ablation',chosen.replace('two_source','ecmwf'))]:
        candidate=saved_selected['test',chosen];control=report['methods'][control_name]['test']['metrics'];record=report[key]
        assert record['passes_frozen_gate']==improves(candidate,control)
        assert record['all_six_strictly_improved']==all(ratio(candidate[b],k)>ratio(control[b],k) for b in BASES for k in ('precision','recall','f1'))
        expected=[(b,k,'improved' if ratio(candidate[b],k)>ratio(control[b],k) else 'equal' if ratio(candidate[b],k)==ratio(control[b],k) else 'regressed') for b in BASES for k in ('precision','recall','f1')]
        assert [(r['basis'],r['metric'],r['status']) for r in record['comparisons']]==expected
    for name,digest in report['inputs_sha256'].items():assert sha(ROOT/name)==digest,name
    for name,digest in report['outputs_sha256'].items():assert sha(OUT/name)==digest,name
    assert sha(OUT/'report.json')==report_sha
    return {'status':'PASS','report_sha256':report_sha,'checker_sha256':sha(Path(__file__)),'inputs_unchanged':True,'outputs_unchanged':True,
        'joined_feature_rows':len(current),'features':len(report['features']),'training_labels_checked':labels_checked,'prediction_rows_checked':sum(len(p) for p in all_pred.values()),
        'grid_pairs_checked':grid_pairs,'metric_records_checked':metric_records,'saved_model_replays':replays,'reused_probability_arms_checked':4,'satellite_missing':missing,
        'selected_arm':chosen,'test_gate_passed':report['test_gate']['passes_frozen_gate'],'test_comparisons':report['test_gate']['comparisons'],'transitions':transitions,
        'tolerances':{'identities_timestamps_labels_decisions_probabilities':0,'reported_metric_float_absolute':1e-15,'brier_absolute':1e-14,'point_error_aggregation_absolute':1e-10},
        'no_fitting_performed':True,'source_and_history_scope':'Reconstructs008 additions and reuses pinned006 base feature bytes;006 strict-past history independently verified previously.'}

if __name__=='__main__':
    try:
        result=check();save(HERE/'result.json',result);print(json.dumps(result,indent=2))
    except Exception as error:
        save(HERE/'failure.json',{'status':'FAIL','error':repr(error),'checker_sha256':sha(Path(__file__))});raise
