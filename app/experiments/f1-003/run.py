"""Archived day2 forecast experiment, governed by the amended frozen protocol."""
import argparse
import hashlib
import importlib.util
import json
import platform
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROTOCOL_SHA = 'a31cd52672ebbe36c221c822fb8d085bee86e11d972e5fbb8457229938af76c7'
ARCHIVE = HERE.parent / 'nwp-archive-001/archive.json'
ARCHIVE_SHA = 'bae187f19e9bacf6c00343666feda994bb051d7053b77f0cc53b9f75555378fc'
PREVIOUS = HERE.parent / 'f1-002/run.py'
spec = importlib.util.spec_from_file_location('f1_002', PREVIOUS)
previous = importlib.util.module_from_spec(spec); spec.loader.exec_module(previous)
sha, write = previous.sha, previous.write
CONTRACT = json.loads((HERE / 'selection-contract.json').read_text())
METHODS = CONTRACT['method_order']
FITTED = ['classifier_base', 'classifier_nwp', 'residual_nwp']


def qualifies(m, persistence, original):
    for field in ['precision', 'recall']:
        value = previous.ratio(m, field)
        if value < 0 or value < max(previous.ratio(persistence, field), previous.ratio(original, field)):
            return False
    return True


def values(name, raw, nwp, alpha):
    return np.maximum(0, nwp + alpha * raw) if name == 'residual_nwp' else raw


def metrics(actual, predicted, cutoff, probability):
    if probability:
        return {**previous.previous.score(actual > 600, predicted > cutoff), 'mae': None, 'rmse': None}
    return previous.metrics(actual, predicted, cutoff)


def ranking(record, natural):
    return (*previous.rank(record), -abs(record['cutoff'] - natural), -record['alpha'], -record['cutoff'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output.resolve()
    if sha(HERE / 'PROTOCOL.md') != PROTOCOL_SHA or sha(ARCHIVE) != ARCHIVE_SHA:
        raise ValueError('Frozen input or protocol changed')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'models').mkdir(); (out / 'predictions').mkdir()
    names = ['data/features.csv','data/paphos_weather_data.csv','eval/cv_predictions.csv','eval/test_predictions.csv']
    source_hashes = {name: sha(ROOT / name) for name in names}
    frame, base, unused, targets, splits = previous.previous.inputs(); del unused
    if list(base.columns) != ['temperature_2m','shortwave_radiation','relative_humidity_2m','cloud_cover','radiation_yesterday','hour','month']:
        raise ValueError('Original features changed')
    for name, index in [('features', frame.index), *[(k,v.index) for k,v in splits.items()]]:
        if not index.is_unique or not np.all(index[1:] - index[:-1] == pd.Timedelta(hours=1)):
            raise ValueError('Invalid hourly membership: ' + name)
    hourly = json.loads(ARCHIVE.read_text())['hourly']
    epochs = hourly['time']
    if len(epochs) != len(set(epochs)) or any(b-a != 3600 for a,b in zip(epochs,epochs[1:])):
        raise ValueError('Archive timestamps duplicate or incomplete')
    lookup = {stamp: i for i, stamp in enumerate(epochs)}
    target_epochs = np.array([int(t.tz_localize('Etc/GMT-3').timestamp()) for t in targets])
    if any(int(t) not in lookup for t in target_epochs):
        raise ValueError('Missing valid-hour join')
    indices = [lookup[int(t)] for t in target_epochs]
    radiation = np.asarray(hourly['shortwave_radiation_previous_day2'], dtype=float)[indices]
    cloud = np.asarray(hourly['cloud_cover_previous_day2'], dtype=float)[indices]
    if np.any(~np.isfinite(radiation)) or np.any(radiation < 0) or np.isinf(cloud).any() or np.any((cloud < 0) | (cloud > 100)):
        raise ValueError('Invalid required radiation or nonmissing cloud input')
    augmented = base.copy()
    augmented['nwp_day2_radiation'] = radiation
    augmented['nwp_day2_cloud'] = cloud
    for label, phase in [('target_hour', targets.hour/24), ('target_season', (targets.dayofyear-1)/365.25)]:
        augmented[label+'_sin'] = np.sin(2*np.pi*phase); augmented[label+'_cos'] = np.cos(2*np.pi*phase)
    augmented['nwp_day2_cloud_missing'] = np.isnan(cloud).astype(int)
    if augmented.shape[1] != 14:
        raise ValueError('Unexpected augmented feature count')
    complete = np.isfinite(base.to_numpy()).all(axis=1) & np.isfinite(radiation)
    joined = augmented.copy(); joined.insert(0,'target_epoch_utc',target_epochs); joined.insert(0,'target_time',targets)
    joined.index.name='feature_time'; joined.to_csv(out/'joined-features.csv')
    report = {'experiment':'AktinaBench F1 003','status':'RUNNING',
        'scope':'Retrospective already-inspected test; archive publication availability unproven; no release recommendation.',
        'protocol_sha256':PROTOCOL_SHA, 'original_protocol_sha256':sha(HERE/'PROTOCOL-original.md'),
        'amendment_sha256':sha(HERE/'protocol-amendment.json'),'selection_contract_sha256':sha(HERE/'selection-contract.json'),
        'code_sha256':sha(Path(__file__)),'reused_evaluator_sha256':sha(PREVIOUS),
        'original_evaluator_sha256':sha(HERE.parent/'f1-001/run.py'),'archive_sha256':ARCHIVE_SHA,
        'input_sha256':source_hashes,
        'versions':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'lightgbm':lgb.__version__},
        'features':{'base':list(base.columns),'augmented':list(augmented.columns)},
        'settings':{'n_estimators':300,'learning_rate':.05,'num_leaves':15,'min_child_samples':40,'random_state':17,'n_jobs':2},
        'splits':{},'methods':{},'outputs_sha256':{}}
    join_audit = {'clock':'Original naive target labels interpreted with fixed UTC+03; no DST conversion.',
        'feature_origins':len(frame),'unique_matched_target_epochs':len(set(target_epochs)),
        'day2_radiation_missing':int(np.isnan(radiation).sum()),'day2_cloud_missing':int(np.isnan(cloud).sum()),
        'target_start':str(targets[0]),'target_end':str(targets[-1]),'archive_sha256':ARCHIVE_SHA,
        'joined_features_sha256':sha(out/'joined-features.csv'),'splits':{}}
    configurations = {}; comparison = []
    for stage in ['validation','test']:
        split = splits[stage]; positions = frame.index.get_indexer(split.index)
        if np.any(positions < 0) or not complete[positions].all():
            raise ValueError('Incomplete evaluation original/radiation input')
        if not np.array_equal(split.baseline.to_numpy(),base.shortwave_radiation.loc[split.index].to_numpy()):
            raise ValueError('Persistence alignment changed')
        train_mask = (targets < split.index[0]) & complete
        train = frame.index[train_mask]
        pd.DataFrame({'feature_time':train,'target_time':targets[train_mask]}).to_csv(out/f'{stage}-training-origins.csv',index=False)
        actual = split.actual.to_numpy(); nwp = radiation[positions]
        target_times = split.index + pd.Timedelta(hours=24)
        references = {name:metrics(actual,split[column].to_numpy(),600,False) for name,column in [('persistence','baseline'),('original','predicted')]}
        report['splits'][stage] = {'hours':len(split),'origin_start':str(split.index[0]),'origin_end':str(split.index[-1]),
            'target_start':str(target_times[0]),'target_end':str(target_times[-1]),'train_hours':len(train),
            'train_start':str(train[0]),'train_end':str(train[-1]),'latest_training_target':str(targets[train_mask][-1]),
            'training_excluded':int(((targets < split.index[0]) & ~complete).sum()),
            'purged_hours':int(((frame.index < split.index[0]) & ~(targets < split.index[0])).sum()),
            'evaluation_cloud_missing':int(np.isnan(cloud[positions]).sum()),'training_cloud_missing':int(np.isnan(cloud[train_mask]).sum()),
            'training_origins_sha256':sha(out/f'{stage}-training-origins.csv')}
        join_audit['splits'][stage] = {k:report['splits'][stage][k] for k in ['hours','evaluation_cloud_missing','training_cloud_missing','training_excluded']}
        if stage == 'test':
            if sha(out/'validation-selection.json') != report['selection_sha256']: raise ValueError('Changed selection')
            print('TEST after frozen validation selection: '+report['recommendation']['method'],flush=True)
        for name in METHODS:
            started=time.monotonic(); probability=name.startswith('classifier_'); natural=.5 if probability else 600
            if name in FITTED:
                x=base if name=='classifier_base' else augmented
                estimator=(lgb.LGBMClassifier(**report['settings'],verbosity=-1,deterministic=True,force_col_wise=True) if probability else
                    lgb.LGBMRegressor(**report['settings'],objective='regression_l1',verbosity=-1,deterministic=True,force_col_wise=True))
                y=frame.target > 600 if probability else frame.target-radiation
                estimator.fit(x.loc[train],y.loc[train])
                raw=estimator.predict_proba(x.loc[split.index])[:,1] if probability else estimator.predict(x.loc[split.index])
                estimator.booster_.save_model(str(out/'models'/f'{stage}-{name}.txt'))
            elif name in ['persistence','original']: raw=split['baseline' if name=='persistence' else 'predicted'].to_numpy()
            else: raw=nwp
            if not np.isfinite(raw).all(): raise ValueError('Nonfinite predictions')
            default_values=values(name,raw,nwp,1); default=metrics(actual,default_values,natural,probability)
            if stage=='validation':
                if name in ['persistence','original','nwp_day2']:
                    configurations[name]={'alpha':1,'cutoff':natural,'qualifies':qualifies(default,references['persistence'],references['original'])}
                else:
                    grid=[]
                    for alpha in [0,.25,.5,.75,1] if name=='residual_nwp' else [1]:
                        for cutoff in [i/100 for i in range(5,96)] if probability else range(450,751,10):
                            m=metrics(actual,values(name,raw,nwp,alpha),cutoff,probability)
                            grid.append({'alpha':alpha,'cutoff':cutoff,'qualifies':qualifies(m,references['persistence'],references['original']),**m})
                    write(out/f'validation-grid-{name}.json',grid)
                    admitted=[g for g in grid if g['qualifies']]
                    best=max(admitted,key=lambda g:ranking(g,natural)) if admitted else None
                    configurations[name]={k:best[k] for k in ['alpha','cutoff','qualifies']} if best else {'alpha':1,'cutoff':natural,'qualifies':False}
            cfg=configurations[name]; predicted=values(name,raw,nwp,cfg['alpha']); selected=metrics(actual,predicted,cfg['cutoff'],probability)
            months=target_times.strftime('%Y-%m'); result={'configuration':cfg,'score_unit':'probability' if probability else 'W/m2','selected':selected,'default':default,'fit_and_score_seconds':time.monotonic()-started}
            for key,vals,cutoff in [('monthly',predicted,cfg['cutoff']),('default_monthly',default_values,natural)]:
                result[key]=[{'month':m,**metrics(actual[months==m],vals[months==m],cutoff,probability)} for m in sorted(set(months))]
            report['methods'].setdefault(name,{})[stage]=result
            pd.DataFrame({'feature_time':split.index,'target_time':target_times,'target_epoch_utc':target_epochs[positions],
                'actual_w_m2':actual,'baseline_w_m2':split.baseline.to_numpy(),'nwp_day2_w_m2':nwp,'cloud_missing':np.isnan(cloud[positions]).astype(int),
                'raw_prediction':raw,'alpha':cfg['alpha'],'cutoff':cfg['cutoff'],'score':predicted,'predicted_positive':(predicted>cfg['cutoff']).astype(int),
                'default_score':default_values,'default_positive':(default_values>natural).astype(int)}).to_csv(out/'predictions'/f'{stage}-{name}.csv',index=False)
            for basis,m in [('selected',selected),('default',default)]:
                comparison.append({'split':stage,'method':name,'basis':basis,'alpha':cfg['alpha'] if basis=='selected' else 1,
                    'cutoff':cfg['cutoff'] if basis=='selected' else natural,'validation_qualifies':cfg['qualifies'],**m})
            write(out/'report.json',report)
            print(f'{stage} {name} alpha={cfg["alpha"]} cutoff={cfg["cutoff"]}: '+json.dumps(selected),flush=True)
        if stage=='validation':
            admitted=[n for n in METHODS if configurations[n]['qualifies']]
            def key(n):
                cfg=configurations[n]; return (*ranking({**report['methods'][n]['validation']['selected'],**cfg},.5 if n.startswith('classifier_') else 600),-METHODS.index(n))
            chosen=max(admitted,key=key) if admitted else 'persistence'
            selection={'method':chosen,'fallback_no_qualifier':not admitted,'configuration':configurations[chosen],'all_configurations':configurations,
                'validation':{n:report['methods'][n]['validation']['selected'] for n in METHODS},
                'grid_sha256':{p.name:sha(p) for p in sorted(out.glob('validation-grid-*.json'))},
                'protocol_sha256':PROTOCOL_SHA,'code_sha256':report['code_sha256'],'selection_contract_sha256':report['selection_contract_sha256']}
            write(out/'validation-selection.json',selection); report['selection_sha256']=sha(out/'validation-selection.json')
            report['recommendation']={k:selection[k] for k in ['method','fallback_no_qualifier','configuration']}
            write(out/'report.json',report); print('VALIDATION selection frozen: '+json.dumps(report['recommendation']),flush=True)
    if source_hashes != {name:sha(ROOT/name) for name in names} or sha(ARCHIVE)!=ARCHIVE_SHA:
        raise ValueError('Inputs changed during run')
    pd.DataFrame(comparison).to_csv(out/'comparison.csv',index=False); write(out/'join-audit.json',join_audit)
    report['outputs_sha256']={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='report.json'}
    report['status']='COMPLETE'; write(out/'report.json',report); print('COMPLETE; original inputs unchanged.',flush=True)


if __name__=='__main__': main()
