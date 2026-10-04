"""Fixed conditional-residual scenario experiment. No original artifact writes."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import platform
import time
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import Ridge
from geometry import solar_features

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROTOCOL_SHA = 'cebe09579d33da67a648c9516047f173bd2a65d046f5162888a45b2b1215ab60'
ARCHIVE = HERE.parent/'nwp-archive-001/archive.json'
ARCHIVE_SHA = 'bae187f19e9bacf6c00343666feda994bb051d7053b77f0cc53b9f75555378fc'
spec = importlib.util.spec_from_file_location('reference001', HERE.parent/'f1-001/run.py')
reference = importlib.util.module_from_spec(spec); spec.loader.exec_module(reference)
METHODS = ['persistence','original','nwp_day2','median_bias','ridge_bias','global_residual','analogue_raw','analogue_solar']
SCENARIOS = METHODS[5:]
CUTOFFS = [i/100 for i in range(30,71,5)]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value): path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def ratio(m,name):
    tp,fp,fn = m['tp'],m['fp'],m['fn']
    a,b = {'f1':(2*tp,2*tp+fp+fn),'precision':(tp,tp+fp),'recall':(tp,tp+fn)}[name]
    return Fraction(a,b) if b else Fraction(-1)


def rank(m): return tuple(ratio(m,k) for k in ['f1','precision','recall'])


def gate(m,controls):
    return all(ratio(m,k)>=0 and ratio(m,k)>=max(ratio(c,k) for c in controls) for k in ['precision','recall'])


def metrics(actual,point,probability,cutoff,low=None,high=None):
    result=reference.score(actual>600,probability>cutoff)
    if len(actual):
        error=point-actual
        result.update(mae=float(np.mean(abs(error))),rmse=float(np.sqrt(np.mean(error**2))),brier=float(np.mean((probability-(actual>600))**2)),
            interval_coverage_90=float(np.mean((low<=actual)&(actual<=high))) if low is not None else None,
            interval_width_90=float(np.mean(high-low)) if low is not None else None)
    else: result.update(mae=None,rmse=None,brier=None,interval_coverage_90=None,interval_width_90=None)
    return result


def summaries(actual,point,probability,cutoff,daytime,months,low=None,high=None):
    def at(mask):
        return metrics(actual[mask],point[mask],probability[mask],cutoff,low[mask] if low is not None else None,high[mask] if high is not None else None)
    return {'full':at(np.ones(len(actual),dtype=bool)),'daytime':at(daytime),
        'monthly':[{'month':m,**at(months==m)} for m in sorted(set(months))],
        'daytime_monthly':[{'month':m,**at((months==m)&daytime)} for m in sorted(set(months))]}


def nearest(train,query,k=64):
    indices=np.empty((len(query),k),dtype=np.int32);distances=np.empty((len(query),k))
    origins=np.arange(len(train))
    for i,row in enumerate(query):
        squared=np.sum((train-row)**2,axis=1)
        boundary=np.partition(squared,k-1)[k-1]
        eligible=origins[squared<=boundary]
        chosen=eligible[np.lexsort((eligible,squared[eligible]))][:k]
        indices[i]=chosen;distances[i]=squared[chosen]
    return indices,distances


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);out=parser.parse_args().output.resolve()
    if sha(HERE/'PROTOCOL.md')!=PROTOCOL_SHA or sha(ARCHIVE)!=ARCHIVE_SHA: raise ValueError('Frozen protocol/input changed')
    out.mkdir(parents=True,exist_ok=False)
    for name in ['predictions','scenarios','parameters']: (out/name).mkdir()
    source_names=['data/features.csv','data/paphos_weather_data.csv','eval/cv_predictions.csv','eval/test_predictions.csv']
    input_hashes={name:sha(ROOT/name) for name in source_names}
    frame,base,unused,targets,splits=reference.inputs();del unused
    for name,index in [('features',frame.index),*[(k,v.index) for k,v in splits.items()]]:
        if not index.is_unique or not np.all(index[1:]-index[:-1]==pd.Timedelta(hours=1)):raise ValueError('Invalid hourly coverage: '+name)
    hourly=json.loads(ARCHIVE.read_text())['hourly'];epochs=hourly['time']
    if len(epochs)!=len(set(epochs)) or any(b-a!=3600 for a,b in zip(epochs,epochs[1:])):raise ValueError('Invalid archive times')
    lookup={stamp:i for i,stamp in enumerate(epochs)}
    target_epochs=np.array([int(t.tz_localize('Etc/GMT-3').timestamp()) for t in targets])
    if any(int(t) not in lookup for t in target_epochs):raise ValueError('Missing forecast join')
    positions=[lookup[int(t)] for t in target_epochs]
    nwp=np.asarray(hourly['shortwave_radiation_previous_day2'],dtype=float)[positions]
    cloud=np.asarray(hourly['cloud_cover_previous_day2'],dtype=float)[positions]
    if not np.isfinite(base.to_numpy()).all() or not np.isfinite(nwp).all() or np.any(nwp<0) or np.isinf(cloud).any() or np.any((cloud<0)|(cloud>100)):raise ValueError('Invalid original/radiation/cloud input')
    geometry=np.array([solar_features(t.to_pydatetime()) for t in targets])
    scale,coszen,sine,cosine=geometry.T
    if not np.isfinite(geometry).all() or np.any(scale<100) or np.any(scale>1000.000000001):raise ValueError('Invalid geometry')
    joined=pd.DataFrame({'feature_time':frame.index,'target_time':targets,'target_epoch_utc':target_epochs,'nwp_day2_w_m2':nwp,'nwp_cloud':cloud,
        'cloud_missing':np.isnan(cloud).astype(int),'solar_scale':scale,'mean_coszen':coszen,'solar_hour_sin':sine,'solar_hour_cos':cosine})
    joined.to_csv(out/'joined-inputs.csv',index=False)
    report={'experiment':'AktinaBench F1 004','status':'RUNNING','scope':'Retrospective model-derived reference; no verified historical forecast publication, independent measured truth or release recommendation.',
        'protocol_sha256':PROTOCOL_SHA,'code_sha256':sha(Path(__file__)),'geometry_sha256':sha(HERE/'geometry.py'),
        'reference_evaluator_sha256':sha(HERE.parent/'f1-001/run.py'),'archive_sha256':ARCHIVE_SHA,'input_sha256':input_hashes,
        'versions':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__},
        'distance_features':['nwp_over_solar_scale','cloud_imputed','cloud_missing','mean_coszen','solar_hour_sin','solar_hour_cos'],
        'K':64,'splits':{},'methods':{},'outputs_sha256':{}}
    configs={};comparison=[]
    for stage in ['validation','test']:
        started=time.monotonic();split=splits[stage];eval_pos=frame.index.get_indexer(split.index)
        if np.any(eval_pos<0) or not np.array_equal(split.baseline.to_numpy(),base.shortwave_radiation.loc[split.index].to_numpy()):raise ValueError('Evaluation membership or baseline changed')
        if stage=='test':
            if sha(out/'validation-selection.json')!=report['selection_sha256']:raise ValueError('Changed frozen selection')
            print('TEST after frozen validation selection: '+report['recommendation']['method'],flush=True)
        train_pos=np.flatnonzero(targets<split.index[0]);train_origins=frame.index[train_pos]
        if len(train_pos)<64:raise ValueError('Too few eligible training hours')
        pd.DataFrame({'feature_time':train_origins,'target_time':targets[train_pos]}).to_csv(out/f'{stage}-training-origins.csv',index=False)
        cloud_median=float(np.nanmedian(cloud[train_pos]))
        if not np.isfinite(cloud_median):raise ValueError('No training cloud median')
        inputs=np.column_stack([nwp/scale,np.where(np.isnan(cloud),cloud_median,cloud),np.isnan(cloud).astype(float),coszen,sine,cosine])
        mean=inputs[train_pos].mean(axis=0);std=inputs[train_pos].std(axis=0);std[std==0]=1
        train_x=(inputs[train_pos]-mean)/std;eval_x=(inputs[eval_pos]-mean)/std
        residual=frame.target.to_numpy()[train_pos]-nwp[train_pos]
        ridge=Ridge(alpha=1,fit_intercept=True,solver='svd').fit(train_x,residual)
        neighbor,distances=nearest(train_x,eval_x)
        order=np.lexsort((np.arange(len(train_pos)),residual));representatives=order[np.floor((np.arange(64)+.5)*len(train_pos)/64).astype(int)]
        parameters={'cloud_median':cloud_median,'feature_mean':mean.tolist(),'feature_std':std.tolist(),
            'ridge':{'alpha':1,'fit_intercept':True,'solver':'svd','coef':ridge.coef_.tolist(),'intercept':float(ridge.intercept_)},
            'raw_residual_median':float(np.median(residual)),
            'global_source_origins':[str(t) for t in train_origins[representatives]],'global_residuals':residual[representatives].tolist()}
        write(out/'parameters'/f'{stage}.json',parameters)
        neighbor_frame=pd.DataFrame({'feature_time':np.repeat(split.index,64),'rank':np.tile(np.arange(64),len(split)),
            'source_feature_time':train_origins.to_numpy()[neighbor.ravel()],'distance_squared':distances.ravel()})
        neighbor_frame.to_csv(out/f'{stage}-analogue-neighbours.csv.gz',index=False,compression={'method':'gzip','mtime':0})
        q=nwp[eval_pos];s=scale[eval_pos];actual=split.actual.to_numpy();months=(split.index+pd.Timedelta(hours=24)).strftime('%Y-%m');daytime=s>100
        scenario_values={
            'global_residual':np.maximum(0,q[:,None]+residual[representatives][None,:]),
            'analogue_raw':np.maximum(0,q[:,None]+residual[neighbor]),
            'analogue_solar':np.maximum(0,q[:,None]+s[:,None]*residual[neighbor]/scale[train_pos][neighbor])}
        points={'persistence':split.baseline.to_numpy(),'original':split.predicted.to_numpy(),'nwp_day2':q,
            'median_bias':np.maximum(0,q+np.median(residual)),'ridge_bias':np.maximum(0,q+ridge.predict(eval_x))}
        controls=[metrics(actual,points[n],(points[n]>600).astype(float),.5) for n in ['original','persistence','nwp_day2']]
        report['splits'][stage]={'hours':len(split),'daytime_hours':int(daytime.sum()),'origin_start':str(split.index[0]),'origin_end':str(split.index[-1]),
            'train_hours':len(train_pos),'train_start':str(train_origins[0]),'train_end':str(train_origins[-1]),'latest_training_target':str(targets[train_pos][-1]),
            'purged_hours':int(((frame.index<split.index[0])&~(targets<split.index[0])).sum()),'training_excluded':0,
            'training_cloud_missing':int(np.isnan(cloud[train_pos]).sum()),'evaluation_cloud_missing':int(np.isnan(cloud[eval_pos]).sum()),
            'training_origins_sha256':sha(out/f'{stage}-training-origins.csv'),'analogue_neighbours_sha256':sha(out/f'{stage}-analogue-neighbours.csv.gz')}
        for name in METHODS:
            if name in SCENARIOS:
                scenarios=scenario_values[name];point=np.median(scenarios,axis=1);probability=np.mean(scenarios>600,axis=1)
                low,high=np.quantile(scenarios,[.05,.95],axis=1,method='linear')
                table=pd.DataFrame(scenarios,columns=[f'scenario_{i}' for i in range(64)]);table.insert(0,'feature_time',split.index)
                table.to_csv(out/'scenarios'/f'{stage}-{name}.csv.gz',index=False,compression={'method':'gzip','mtime':0})
            else:point=points[name];probability=(point>600).astype(float);low=high=None
            if stage=='validation':
                if name in SCENARIOS:
                    grid=[{'cutoff':c,**metrics(actual,point,probability,c,low,high)} for c in CUTOFFS]
                    for row in grid:row['qualifies']=gate(row,controls)
                    write(out/f'validation-grid-{name}.json',grid)
                    admitted=[g for g in grid if g['qualifies']]
                    best=max(admitted,key=lambda g:(*rank(g),-abs(g['cutoff']-.5),-g['cutoff'])) if admitted else None
                    configs[name]={'probability_cutoff':best['cutoff'] if best else .5,'qualifies':bool(best),'point_cutoff':None}
                else:configs[name]={'probability_cutoff':.5,'qualifies':gate(metrics(actual,point,probability,.5),controls),'point_cutoff':600}
            cfg=configs[name]
            selected=summaries(actual,point,probability,cfg['probability_cutoff'],daytime,months,low,high)
            default=summaries(actual,point,probability,.5,daytime,months,low,high)
            report['methods'].setdefault(name,{})[stage]={'configuration':cfg,'probability_kind':'empirical_scenarios' if name in SCENARIOS else 'deterministic_event','selected':selected,'default':default}
            pd.DataFrame({'feature_time':split.index,'target_time':split.index+pd.Timedelta(hours=24),'actual_w_m2':actual,'point_w_m2':point,
                'probability':probability,'probability_cutoff':cfg['probability_cutoff'],'predicted_positive':(probability>cfg['probability_cutoff']).astype(int),
                'default_positive':(probability>.5).astype(int),'solar_scale':s,'daytime':daytime.astype(int),
                'interval_low_w_m2':low if low is not None else [None]*len(split),'interval_high_w_m2':high if high is not None else [None]*len(split)}).to_csv(out/'predictions'/f'{stage}-{name}.csv',index=False)
            for basis,results in [('selected',selected),('default',default)]:
                for scope in ['full','daytime']:comparison.append({'split':stage,'method':name,'basis':basis,'scope':scope,
                    'probability_cutoff':cfg['probability_cutoff'] if basis=='selected' else .5,'validation_qualifies':cfg['qualifies'],**results[scope]})
            write(out/'report.json',report)
            print(f'{stage} {name} cutoff={cfg["probability_cutoff"]}: '+json.dumps(selected['full']),flush=True)
        report['splits'][stage]['fit_predict_score_seconds']=time.monotonic()-started
        if stage=='validation':
            admitted=[n for n in METHODS if configs[n]['qualifies']]
            chosen=max(admitted,key=lambda n:(*rank(report['methods'][n]['validation']['selected']['full']),
                -abs(configs[n]['probability_cutoff']-.5) if n in SCENARIOS else 0,-METHODS.index(n))) if admitted else 'nwp_day2'
            selection={'method':chosen,'fallback_no_qualifier':not admitted,'configuration':configs[chosen],'all_configurations':configs,
                'validation':{n:report['methods'][n]['validation']['selected']['full'] for n in METHODS},
                'grid_sha256':{p.name:sha(p) for p in sorted(out.glob('validation-grid-*.json'))},'protocol_sha256':PROTOCOL_SHA,
                'code_sha256':report['code_sha256'],'geometry_sha256':report['geometry_sha256']}
            write(out/'validation-selection.json',selection);report['selection_sha256']=sha(out/'validation-selection.json')
            report['recommendation']={k:selection[k] for k in ['method','fallback_no_qualifier','configuration']}
            write(out/'report.json',report);print('VALIDATION selection frozen: '+json.dumps(report['recommendation']),flush=True)
    if input_hashes!={name:sha(ROOT/name) for name in source_names} or sha(ARCHIVE)!=ARCHIVE_SHA:raise ValueError('Input mutation during run')
    pd.DataFrame(comparison).to_csv(out/'comparison.csv',index=False)
    report['outputs_sha256']={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='report.json'}
    report['status']='COMPLETE';write(out/'report.json',report);print('COMPLETE; original inputs unchanged.',flush=True)


if __name__=='__main__':main()
