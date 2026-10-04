"""Four frozen CPU BQN fits, retained distributions and unchanged008 decision gate."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import resource
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import scipy
from scipy.optimize import minimize
import bqn

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OLD=HERE.parent/'f1-008'
spec=importlib.util.spec_from_file_location('decision008',OLD/'run.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
PROTOCOL='b266806d0e2eb83ee8d1bbd1c04982348ee84497dfb6b06ac384aad96393c6ed'
ARMS=('weather','joint')
sha=policy.sha;read=policy.read;save=policy.save;now=policy.now


def distribution_scores(pred,actual):
    residual=actual[:,None]-pred['quantiles']
    pinball=float(np.mean(np.where(residual>=0,bqn.LEVELS*residual,(bqn.LEVELS-1)*residual)))
    difference=np.diff(pred['quantiles'],axis=1)
    return {'hours':len(actual),'mean_pinball_51_w_m2':pinball,'approx_crps_51_w_m2':2*pinball,
            'median_mae_w_m2':float(np.mean(np.abs(pred['median']-actual))),
            'mean_rmse_w_m2':float(np.sqrt(np.mean((pred['mean']-actual)**2))),
            'coverage_90':float(np.mean((actual>=pred['lower'])&(actual<=pred['upper']))),
            'interval_width_90_w_m2':float(np.mean(pred['upper']-pred['lower'])),
            'mean_zero_mass':float(np.mean(pred['zero_mass'])),
            'crossing_count_above_1e_9_w_m2':int(np.sum(difference < -1e-9)),
            'minimum_quantile_step_w_m2':float(np.min(difference))}


def scores(pred,weather,satellite):
    available=np.isfinite(satellite);result={}
    for name,y,mask in [('weather_full',weather,np.ones(len(weather),bool)),('weather_common',weather,available),('satellite_common',satellite,available)]:
        result[name]=distribution_scores({k:v[mask] for k,v in pred.items() if k!='coefficients'},y[mask])
    return result


def point_distribution(point):
    return {'quantiles':np.repeat(point[:,None],51,axis=1),'median':point,'mean':point,'lower':point,'upper':point,
            'zero_mass':(point==0).astype(float),'probability':(point>600).astype(float)}


def main(out):
    if HERE not in out.parents:raise ValueError('Output must be inside experiment')
    if sha(HERE/'PROTOCOL.md')!=PROTOCOL:raise ValueError('Changed protocol')
    pins=json.loads((HERE/'inputs.json').read_text())
    for name,h in pins.items():
        if sha(ROOT/name)!=h:raise ValueError('Changed input: '+name)
    out.mkdir(parents=True,exist_ok=False)
    (out/'models').mkdir();(out/'predictions').mkdir()
    features=read(OLD/'result/features.csv');targets=read(HERE.parent/'f1-006/result/feature-targets.csv')
    ref=read(HERE.parent/'reference-training-001/result/joined-reference.csv')
    if len(features)!=17832 or len(targets)!=len(features) or len(ref)!=len(features) or not features.feature_time.is_unique:raise ValueError('Row count/membership')
    if not features.feature_time.equals(targets.feature_time) or not features.feature_time.equals(ref.feature_time):raise ValueError('Origin order')
    origin=pd.to_datetime(features.feature_time);target=pd.to_datetime(targets.target_time)
    if not (target==origin+pd.Timedelta(hours=24)).all() or not (origin.diff().dropna()==pd.Timedelta(hours=1)).all():raise ValueError('Horizon')
    if not target.dt.tz_localize('Etc/GMT-3').dt.tz_convert('UTC').equals(pd.to_datetime(ref.valid_time_utc,utc=True)):raise ValueError('Clock')
    if not np.array_equal(targets.actual,ref.weather_actual_w_m2):raise ValueError('Weather reference')
    x=features.drop(columns='feature_time').to_numpy(dtype=float)
    if x.shape!=(17832,27) or np.isinf(x).any():raise ValueError('Feature schema')
    nwp=features.nwp_day2_radiation.to_numpy();sat=ref.satellite_w_m2.to_numpy()
    if not np.isfinite(nwp).all() or np.isinf(sat).any() or np.any(sat<0):raise ValueError('Reference/input values')
    old_report=json.loads((OLD/'result/report.json').read_text());old_name=old_report['selected_augmented_arm']
    report={'status':'RUNNING','started_at_utc':now(),'protocol_sha256':PROTOCOL,'code_sha256':sha(Path(__file__)),
            'core_sha256':sha(HERE/'bqn.py'),'inputs_sha256':pins,'versions':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__},
            'feature_names':list(features.columns[1:]),'architecture':{'inputs':27,'hidden':[16],'degree':12,'parameters':len(bqn.initialize()),'seed':17,'l2':bqn.L2},
            'scope':'Post-inspection retrospective CPU adaptation; no installed dependency, product changes or live/calibration claims.',
            'methods':{},'fits':{},'splits':{},'comparator_008':old_name,'selected_arm':None}
    policies={};selected=None
    for stage,file in [('validation','cv_predictions.csv'),('test','test_predictions.csv')]:
        if stage=='test' and sha(out/'validation-selection.json')!=report['selection_sha256']:raise ValueError('Selection changed')
        split=read(ROOT/'eval'/file);names=split.iloc[:,0];positions=pd.Index(features.feature_time).get_indexer(names)
        if np.any(positions<0) or not names.is_unique or len(split)!={'validation':3566,'test':3567}[stage]:raise ValueError('Evaluation membership')
        w=split.actual.to_numpy();s=sat[positions];baseline=nwp[positions]>600
        if not np.array_equal(w,targets.actual.iloc[positions]):raise ValueError('Evaluation labels')
        train=np.flatnonzero(target<pd.Timestamp(names.iloc[0]));old_train=read(HERE.parent/'f1-006/result'/f'{stage}-training-origins.csv')
        if list(features.feature_time.iloc[train])!=list(old_train.feature_time) or list(targets.target_time.iloc[train])!=list(old_train.target_time):raise ValueError('Training purge')
        means,scales=bqn.fit_scaler(x[train]);xt=bqn.transform(x[train],means,scales);xe=bqn.transform(x[positions],means,scales)
        train_weather=targets.actual.iloc[train].to_numpy()/1000;train_sat=sat[train]/1000
        labels=pd.DataFrame({'feature_time':features.feature_time.iloc[train].to_numpy(),'target_time':targets.target_time.iloc[train].to_numpy(),
                             'weather_w_m2':targets.actual.iloc[train].to_numpy(),'satellite_w_m2':sat[train],'satellite_available':np.isfinite(train_sat).astype(int)})
        labels.to_csv(out/f'{stage}-training-rows.csv',index=False)
        save(out/f'{stage}-scaler.json',{'mean':means.tolist(),'scale':scales.tolist(),'missing_train':np.isnan(x[train]).sum(axis=0).tolist(),'missing_evaluation':np.isnan(x[positions]).sum(axis=0).tolist(),'features':report['feature_names']})
        membership=pd.DataFrame({'feature_time':names,'target_time':targets.target_time.iloc[positions].to_numpy(),'weather_w_m2':w,'satellite_w_m2':s,'satellite_available':np.isfinite(s).astype(int)})
        membership.to_csv(out/f'{stage}-reference-membership.csv',index=False)
        previous=read(HERE.parent/'f1-006/result'/f'{stage}-reference-membership.csv')
        if not np.array_equal(s,previous.satellite_w_m2.to_numpy(),equal_nan=True):raise ValueError('Changed satellite evaluation reference')
        report['splits'][stage]={'hours':len(split),'training_hours':len(train),'satellite_common_hours':int(np.isfinite(s).sum()),'satellite_missing_hours':int(np.isnan(s).sum()),'latest_training_target':targets.target_time.iloc[train[-1]],'first_evaluation_origin':names.iloc[0]}
        for name,point in [('original',split.predicted.to_numpy()),('persistence',split.baseline.to_numpy()),('nwp_day2',nwp[positions])]:
            pred=point_distribution(point)
            report['methods'].setdefault(name,{})[stage]={'events':policy.metrics(point>600,w,s,pred['probability']),'distribution':scores(pred,w,s),'distribution_kind':'point mass at supplied forecast'}
        old=read(OLD/'result/predictions'/f'{stage}-{old_name}.csv')
        if not np.array_equal(old.feature_time,names):raise ValueError('008 comparison membership')
        report['methods'].setdefault('f1_008_frozen',{})[stage]={'events':policy.metrics(old.predicted_positive.to_numpy().astype(bool),w,s,old.probability.to_numpy()),'source_method':old_name}
        for arm in ARMS:
            started=time.monotonic();cpu=time.process_time()
            result=minimize(bqn.objective,bqn.initialize(),args=(xt,nwp[train]/1000,train_weather,train_sat,arm=='joint'),method='L-BFGS-B',jac=True,
                            options={'maxiter':200,'maxfun':1000,'maxls':40,'ftol':1e-10,'gtol':1e-6})
            if not np.isfinite(result.x).all() or not np.isfinite(result.fun) or not np.isfinite(result.jac).all():raise ValueError('Nonfinite optimizer result')
            fit={'success':bool(result.success),'status':int(result.status),'message':str(result.message),'iterations':int(result.nit),'function_evaluations':int(result.nfev),'gradient_evaluations':int(result.njev),
                 'objective_internal_units':float(result.fun),'maximum_gradient_absolute':float(np.abs(result.jac).max()),'wall_seconds':time.monotonic()-started,'cpu_seconds':time.process_time()-cpu,
                 'process_peak_rss_bytes':int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=='darwin' else 1024)}
            report['fits'][stage+'-'+arm]=fit
            np.savez_compressed(out/'models'/f'{stage}-{arm}.npz',theta=result.x,mean=means,scale=scales,training_positions=train)
            pred=bqn.predict(result.x,xe,nwp[positions]/1000)
            np.savez_compressed(out/'predictions'/f'{stage}-{arm}-distribution.npz',**pred)
            if stage=='validation':
                policies[arm],grid=policy.select(baseline,pred['probability'],w,s);save(out/f'validation-grid-{arm}.json',grid)
            decision=policy.decide(baseline,pred['probability'],policies[arm]['policy'])
            report['methods'].setdefault(arm,{})[stage]={'policy':policies[arm]['policy'],'events':policy.metrics(decision,w,s,pred['probability']),
                'default_events':policy.metrics(pred['probability']>.5,w,s,pred['probability']),'distribution':scores(pred,w,s),
                'corrections':{'added':int(np.sum(~baseline&decision)),'removed':int(np.sum(baseline&~decision))}}
            frame=membership.copy()
            for key in ('probability','zero_mass','median','mean','lower','upper'):frame[key]=pred[key]
            frame['nwp_positive']=baseline.astype(int);frame['predicted_positive']=decision.astype(int);frame['default_positive']=(pred['probability']>.5).astype(int)
            frame.to_csv(out/'predictions'/f'{stage}-{arm}.csv',index=False)
            print(stage,arm,json.dumps({'fit':fit,'policy':policies[arm]['policy'],'events':{b:report['methods'][arm][stage]['events'][b] for b in policy.BASES}}),flush=True)
        if stage=='validation':
            selected=max(ARMS,key=lambda a:(*policy.rank(policies[a]),a=='weather'))
            save(out/'validation-selection.json',{'selected_arm':selected,'policies':policies,'frozen_at_utc':now(),'protocol_sha256':PROTOCOL,'runner_sha256':report['code_sha256'],'core_sha256':report['core_sha256']})
            report['selected_arm']=selected;report['selection_sha256']=sha(out/'validation-selection.json');print('FROZEN',selected,flush=True)
        save(out/'report.json',report)
    selected_metrics={b:report['methods'][selected]['test']['events'][b] for b in policy.BASES}
    report['test_gate']=policy.joint.test_gate(selected_metrics,{b:report['methods']['nwp_day2']['test']['events'][b] for b in policy.BASES})
    report['comparison_008']=policy.joint.test_gate(selected_metrics,{b:report['methods']['f1_008_frozen']['test']['events'][b] for b in policy.BASES})
    for name,h in pins.items():
        if sha(ROOT/name)!=h:raise ValueError('Input changed during run: '+name)
    report['status']='COMPLETE';report['completed_at_utc']=now();report['recommendation']='Research only; retain established control unless every required metric passes review. No product replacement.'
    report['outputs_sha256']={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='report.json'}
    save(out/'report.json',report);print('COMPLETE',json.dumps(report['test_gate']),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output.resolve())
