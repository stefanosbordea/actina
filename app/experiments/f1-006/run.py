"""Frozen NWP event classification; writes only this experiment's new result directory."""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import time

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROTOCOL_SHA = 'd764be04235af9dd860867a3374bf2651d8cca6cc736e2d4e94242ee3a5c7446'
CONFIGS = {'small':dict(n_estimators=200,num_leaves=5,max_depth=3,min_child_samples=80),
           'medium':dict(n_estimators=300,num_leaves=9,max_depth=4,min_child_samples=60),
           'larger':dict(n_estimators=300,num_leaves=15,max_depth=4,min_child_samples=40)}


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, obj): path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def now(): return datetime.now(timezone.utc).isoformat()
def csv(path, **kwargs): return pd.read_csv(path,float_precision='round_trip',**kwargs)


def score(truth, positive, probability=None):
    tp=int(np.sum(truth & positive));fp=int(np.sum(~truth & positive))
    fn=int(np.sum(truth & ~positive));tn=int(np.sum(~truth & ~positive))
    return dict(hours=len(truth),tp=tp,fp=fp,fn=fn,tn=tn,
        precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,
        f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
        brier=float(np.mean((probability-truth)**2)) if probability is not None else None)


def fraction(m,key):
    a,b={'precision':(m['tp'],m['tp']+m['fp']),'recall':(m['tp'],m['tp']+m['fn']),
         'f1':(2*m['tp'],2*m['tp']+m['fp']+m['fn'])}[key]
    return Fraction(a,b) if b else Fraction(-1)


def qualifies(m,control):
    return all(fraction(m,k)>=0 and fraction(m,k)>=fraction(control,k) for k in ('precision','recall','f1'))


def rank(m): return tuple(fraction(m,k) for k in ('f1','precision','recall'))


def threshold(probability,truth,control):
    records=[]
    for cutoff in np.unique(np.r_[0.,probability,1.]):
        row={'cutoff':float(cutoff),**score(truth,probability>cutoff)}
        row['qualifies']=qualifies(row,control);records.append(row)
    eligible=[r for r in records if r['qualifies']]
    best=max(eligible or records,key=lambda r:(*rank(r),-abs(r['cutoff']-.5),r['cutoff']))
    return best,records


def main(out):
    if sha(HERE/'PROTOCOL.md')!=PROTOCOL_SHA:raise ValueError('Changed frozen protocol')
    pins=json.loads((HERE/'inputs.json').read_text())
    for name,expected in pins.items():
        if sha(ROOT/name)!=expected:raise ValueError('Changed pinned input: '+name)
    out.mkdir(parents=True,exist_ok=False)
    for name in ('models','predictions'):(out/name).mkdir()
    frame=csv(ROOT/'data/features.csv',index_col=0,parse_dates=True)
    weather=csv(ROOT/'data/paphos_weather_data.csv',index_col=0,parse_dates=True)
    targets=frame.index+pd.Timedelta(hours=24)
    if not frame.index.is_unique or not weather.index.is_unique or not np.all(frame.index[1:]-frame.index[:-1]==pd.Timedelta(hours=1)):raise ValueError('Invalid original hourly membership')
    if not np.array_equal(frame.target.to_numpy(),weather.shortwave_radiation.reindex(targets).to_numpy()):raise ValueError('Original target shift changed')
    joined003=csv(ROOT/'app/experiments/f1-003/result/joined-features.csv',index_col='feature_time',parse_dates=['feature_time','target_time'])
    joined004=csv(ROOT/'app/experiments/f1-004/result/joined-inputs.csv',index_col='feature_time',parse_dates=['feature_time','target_time'])
    epochs=np.array([int(t.tz_localize('Etc/GMT-3').timestamp()) for t in targets])
    for joined in (joined003,joined004):
        if not joined.index.equals(frame.index) or not np.array_equal(joined.target_time,targets) or not np.array_equal(joined.target_epoch_utc,epochs):raise ValueError('Changed join membership/time mapping')
    x=joined003.drop(columns=['target_time','target_epoch_utc']).copy()
    if x.shape[1]!=14:raise ValueError('Unexpected003 feature columns')
    base=frame.drop(columns='target')
    if not np.allclose(x[base.columns],base,rtol=0,atol=1e-12):raise ValueError('Changed original feature values')
    x[base.columns]=base
    spec=importlib.util.spec_from_file_location('solar004',ROOT/'app/experiments/f1-004/geometry.py')
    geometry=importlib.util.module_from_spec(spec);spec.loader.exec_module(geometry)
    calculated=np.array([geometry.solar_features(t.to_pydatetime()) for t in targets])
    geo_names=['solar_scale','mean_coszen','solar_hour_sin','solar_hour_cos']
    if not np.allclose(calculated,joined004[geo_names],rtol=0,atol=1e-10):raise ValueError('Geometry reconstruction failed')
    x[geo_names]=calculated
    nwp=joined004.nwp_day2_w_m2.to_numpy()
    archive=json.loads((ROOT/'app/experiments/nwp-archive-001/archive.json').read_text())['hourly']
    times=archive['time']
    if len(times)!=len(set(times)) or any(b-a!=3600 for a,b in zip(times,times[1:])):raise ValueError('Invalid raw archive timestamps')
    lookup=dict(zip(times,archive['shortwave_radiation_previous_day2']))
    if not np.array_equal(nwp,np.array([lookup[int(t)] for t in epochs])) or not np.array_equal(nwp,x.nwp_day2_radiation):raise ValueError('NWP join values changed')
    x['nwp_over_solar_scale']=nwp/calculated[:,0]
    residual=pd.Series(frame.target.to_numpy()-nwp,index=targets)
    full_index=pd.date_range(frame.index[0]-pd.Timedelta(hours=168),frame.index[-1],freq='h')
    prior=residual.reindex(full_index).shift(1)
    for window in (24,168):
        rolling=prior.rolling(window,min_periods=1)
        x[f'residual_mean_{window}']=rolling.mean().reindex(frame.index)
        x[f'residual_count_{window}']=rolling.count().reindex(frame.index)
    x['residual_lag24']=residual.reindex(frame.index-pd.Timedelta(hours=24)).to_numpy()
    if np.isinf(x.to_numpy()).any() or not np.isfinite(base.to_numpy()).all() or not np.isfinite(nwp).all():raise ValueError('Invalid feature values')
    x.index.name='feature_time';x.to_csv(out/'features.csv')
    pd.DataFrame({'feature_time':frame.index,'target_time':targets,'target_epoch_utc':epochs,'actual':frame.target}).to_csv(out/'feature-targets.csv',index=False)
    report={'status':'RUNNING','started_at_utc':now(),'protocol_sha256':PROTOCOL_SHA,'code_sha256':sha(Path(__file__)),
        'input_sha256':pins,'configurations':CONFIGS,'features':list(x.columns),
        'versions':dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,lightgbm=lgb.__version__),
        'scope':'Retrospective already-inspected test. Historical publication and operational availability of archived inputs unverified. No live or ground-sensor claim.',
        'join_comparison_tolerances':{'original_feature_abs':1e-12,'geometry_abs':1e-10,'timestamps_and_nwp':0},
        'splits':{},'methods':{},'reference_sensitivity':{}}
    splits={name:csv(ROOT/f'eval/{filename}',index_col=0,parse_dates=True) for name,filename in [('validation','cv_predictions.csv'),('test','test_predictions.csv')]}
    selected={};vectors={};comparison=[]
    for stage,split in splits.items():
        started=time.monotonic();positions=frame.index.get_indexer(split.index)
        if np.any(positions<0) or not split.index.is_unique or not np.all(split.index[1:]-split.index[:-1]==pd.Timedelta(hours=1)):raise ValueError('Invalid evaluation membership')
        if not np.array_equal(split.actual,frame.target.iloc[positions]) or not np.array_equal(split.baseline,base.shortwave_radiation.iloc[positions]):raise ValueError('Evaluation reference/baseline mismatch')
        if len(split)!={'validation':3566,'test':3567}[stage]:raise ValueError('Changed evaluation denominator')
        train=np.flatnonzero(targets<split.index[0])
        pd.DataFrame({'feature_time':frame.index[train],'target_time':targets[train]}).to_csv(out/f'{stage}-training-origins.csv',index=False)
        truth=split.actual.to_numpy()>600
        control=score(truth,nwp[positions]>600)
        report['splits'][stage]={'hours':len(split),'training_hours':len(train),'latest_training_target':str(targets[train[-1]]),'first_evaluation_origin':str(split.index[0]),'purged_hours':int(((frame.index<split.index[0])&~(targets<split.index[0])).sum()),'missing_features':{c:int(x.iloc[positions][c].isna().sum()) for c in x.columns if x.iloc[positions][c].isna().any()}}
        if stage=='test':
            if sha(out/'validation-selection.json')!=report['selection_sha256']:raise ValueError('Frozen selection changed')
            print('TEST after frozen selection: '+report['selected_method'],flush=True)
        vectors[stage]={}
        for name in ['original','persistence','nwp_day2',*CONFIGS]:
            if name in CONFIGS:
                model=lgb.LGBMClassifier(**CONFIGS[name],learning_rate=.03,reg_lambda=2,random_state=17,n_jobs=2,deterministic=True,force_col_wise=True,verbosity=-1)
                model.fit(x.iloc[train],frame.target.iloc[train]>600)
                prob=model.predict_proba(x.iloc[positions])[:,1]
                model.booster_.save_model(str(out/'models'/f'{stage}-{name}.txt'))
                if not np.isfinite(prob).all() or np.any((prob<0)|(prob>1)):raise ValueError('Invalid fitted probabilities')
                if stage=='validation':
                    best,grid=threshold(prob,truth,control);selected[name]=best
                    save(out/f'validation-grid-{name}.json',grid)
                cutoff=selected[name]['cutoff']
            else:
                value=split.predicted.to_numpy() if name=='original' else split.baseline.to_numpy() if name=='persistence' else nwp[positions]
                prob=(value>600).astype(float);cutoff=.5
            positive=prob>cutoff
            m=score(truth,positive,prob);default=score(truth,prob>.5,prob)
            report['methods'].setdefault(name,{})[stage]={'cutoff':cutoff,'metrics':m,'default_0_5':default}
            vectors[stage][name]=(prob,positive)
            pd.DataFrame({'feature_time':split.index,'target_time':targets[positions],'target_epoch_utc':epochs[positions],'actual_w_m2':split.actual,'probability':prob,'cutoff':cutoff,'predicted_positive':positive.astype(int),'default_positive':(prob>.5).astype(int)}).to_csv(out/'predictions'/f'{stage}-{name}.csv',index=False)
            comparison.append({'split':stage,'method':name,'basis':'weather_full','cutoff':cutoff,**m})
            print(stage+' '+name+' '+json.dumps(m),flush=True)
        report['splits'][stage]['fit_score_seconds']=time.monotonic()-started
        if stage=='validation':
            eligible=[name for name in CONFIGS if selected[name]['qualifies']]
            chosen=max(eligible,key=lambda n:(*rank(selected[n]),-list(CONFIGS).index(n))) if eligible else 'nwp_day2'
            selection={'selected_method':chosen,'fallback_no_learned_qualifier':not eligible,'all_thresholds':selected,'fixed_control':control,'frozen_at_utc':now(),'protocol_sha256':PROTOCOL_SHA,'code_sha256':report['code_sha256'],'input_manifest_sha256':sha(HERE/'inputs.json')}
            save(out/'validation-selection.json',selection);report['selection_sha256']=sha(out/'validation-selection.json');report['selected_method']=chosen
            print('FROZEN selection '+chosen,flush=True)
        save(out/'report.json',report)
    satellite=csv(ROOT/'app/experiments/satellite-reference-001/result/reference-full.csv')
    sat_times=pd.to_datetime(satellite.valid_time_utc,utc=True)
    if not sat_times.is_unique or not np.all(sat_times[1:].to_numpy()-sat_times[:-1].to_numpy()==np.timedelta64(1,'h')):raise ValueError('Invalid satellite membership')
    sat=pd.Series(satellite.shortwave_radiation_w_m2.to_numpy(),index=sat_times)
    for stage,split in splits.items():
        valid=(split.index+pd.Timedelta(hours=24)).tz_localize('Etc/GMT-3').tz_convert('UTC')
        if not valid.isin(sat.index).all():raise ValueError('Missing satellite timestamp')
        truth=sat.reindex(valid).to_numpy();available=np.isfinite(truth)
        if np.isinf(truth).any() or np.any(truth<0):raise ValueError('Invalid satellite reference')
        report['reference_sensitivity'][stage]={'original_hours':len(split),'common_hours':int(available.sum()),'missing_hours':int((~available).sum()),'missing_valid_times_utc':[t.isoformat() for t in valid[~available]]}
        pd.DataFrame({'feature_time':split.index,'target_time_utc':valid,'weather_actual_w_m2':split.actual,'satellite_w_m2':truth,'scored':available.astype(int)}).to_csv(out/f'{stage}-reference-membership.csv',index=False)
        for name,(prob,positive) in vectors[stage].items():
            for basis,reference in [('weather_common',split.actual.to_numpy()),('satellite_common',truth)]:
                comparison.append({'split':stage,'method':name,'basis':basis,'cutoff':report['methods'][name][stage]['cutoff'],**score(reference[available]>600,positive[available],prob[available])})
    chosen=report['selected_method'];m=report['methods'][chosen]['test']['metrics'];control=report['methods']['nwp_day2']['test']['metrics']
    report['test_gate_passed']=chosen!='nwp_day2' and qualifies(m,control) and any(fraction(m,k)>fraction(control,k) for k in ('precision','recall','f1'))
    report['recommendation']='No learned replacement' if not report['test_gate_passed'] else 'Retrospective candidate only; no deployment recommendation'
    pd.DataFrame(comparison).to_csv(out/'comparison.csv',index=False)
    for name,expected in pins.items():
        if sha(ROOT/name)!=expected:raise ValueError('Input changed during execution: '+name)
    report['status']='COMPLETE';report['completed_at_utc']=now();report['outputs_sha256']={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='report.json'}
    save(out/'report.json',report);print('COMPLETE '+report['recommendation'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output.resolve())
