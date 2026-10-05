"""Stdlib-only independent join, membership, metric and selection checks."""
import argparse
import importlib.util
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RUN=HERE/'result'
spec=importlib.util.spec_from_file_location('audit002',HERE.parent/'f1-002/check_audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
load,rows,sha,require,equal=audit.load,audit.rows,audit.sha,audit.require,audit.equal
DAY,HOUR=timedelta(hours=24),timedelta(hours=1)
FIXED=timezone(timedelta(hours=3))


def metrics(actual,predicted,cutoff,probability):
    result=audit.metrics(actual,predicted,cutoff)
    if probability: result.update(mae=None,rmse=None)
    return result


def gate(m,persistence,original):
    return all(value>=0 and value>=max(p,o) for value,p,o in
               zip(audit.ratios(m)[1:],audit.ratios(persistence)[1:],audit.ratios(original)[1:],strict=True))


def value(name,raw,nwp,alpha):
    return max(0,nwp+alpha*raw) if name=='residual_nwp' else raw


def ranking(row,natural):
    return (*audit.ratios(row),-abs(row['cutoff']-natural),-row['alpha'],-row['cutoff'])


def promotion(m,original,persistence):
    a,b,c=audit.ratios(m),audit.ratios(original),audit.ratios(persistence)
    return all(x>y for x,y in zip(a,b,strict=True)) and all(x>=y for x,y in zip(a,c,strict=True)) and any(x>y for x,y in zip(a,c,strict=True))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args()
    report=load(RUN/'report.json');require(report['status']=='COMPLETE','Incomplete run')
    contract=load(HERE/'selection-contract.json');methods=contract['method_order']
    archive_path=HERE.parent/'nwp-archive-001/archive.json'
    identities={ROOT/p:h for p,h in report['input_sha256'].items()}
    identities.update({HERE/'PROTOCOL.md':report['protocol_sha256'],HERE/'PROTOCOL-original.md':report['original_protocol_sha256'],
        HERE/'protocol-amendment.json':report['amendment_sha256'],HERE/'selection-contract.json':report['selection_contract_sha256'],
        HERE/'run.py':report['code_sha256'],HERE.parent/'f1-002/run.py':report['reused_evaluator_sha256'],
        HERE.parent/'f1-001/run.py':report['original_evaluator_sha256'],archive_path:report['archive_sha256']})
    identities.update({RUN/p:h for p,h in report['outputs_sha256'].items()})
    for p,h in identities.items():require(sha(p)==h,'Changed identity: '+str(p))
    original_sources={name:rows(ROOT/name) for name in report['input_sha256']}
    for name,records in original_sources.items():
        times=[datetime.fromisoformat(r['time']) for r in records]
        require(len(times)==len(set(times)) and all(b-a==HOUR for a,b in zip(times,times[1:])),name+' coverage')
    features={datetime.fromisoformat(r['time']):r for r in original_sources['data/features.csv']}
    weather={datetime.fromisoformat(r['time']):r for r in original_sources['data/paphos_weather_data.csv']}
    raw=load(archive_path)['hourly'];epochs=raw['time']
    require(len(epochs)==len(set(epochs)) and all(b-a==3600 for a,b in zip(epochs,epochs[1:])),'Archive UTC coverage')
    by_epoch={stamp:(rad,cloud) for stamp,rad,cloud in zip(epochs,raw['shortwave_radiation_previous_day2'],raw['cloud_cover_previous_day2'],strict=True)}
    base_fields=['temperature_2m','shortwave_radiation','relative_humidity_2m','cloud_cover','radiation_yesterday','hour','month']
    require(report['features']['base']==base_fields and len(report['features']['augmented'])==14,'Feature scope')
    joined=rows(RUN/'joined-features.csv');require(len(joined)==len(features),'Join lost origins')
    joined_by_origin={};missing=0
    for saved,(origin,original) in zip(joined,features.items(),strict=True):
        target=origin+DAY;epoch=int(target.replace(tzinfo=FIXED).timestamp())
        require(datetime.fromisoformat(saved['feature_time'])==origin and datetime.fromisoformat(saved['target_time'])==target,'Joined time identity')
        require(int(saved['target_epoch_utc'])==epoch and epoch in by_epoch,'Fixed-offset archive join')
        rad,cloud=by_epoch[epoch];require(rad is not None and math.isfinite(rad) and rad>=0,'Missing radiation')
        require(float(original['target'])==float(weather[target]['shortwave_radiation']),'Target label changed')
        for field in base_fields:require(equal(float(saved[field]),float(original[field])),'Changed original feature')
        require(float(saved['nwp_day2_radiation'])==rad,'Joined radiation changed')
        require(int(saved['nwp_day2_cloud_missing'])==(cloud is None),'Missing indicator changed')
        if cloud is None:require(saved['nwp_day2_cloud']=='','Cloud was filled');missing+=1
        else:require(math.isfinite(cloud) and 0<=cloud<=100 and float(saved['nwp_day2_cloud'])==cloud,'Cloud changed')
        for label,phase in [('target_hour',target.hour/24),('target_season',(target.timetuple().tm_yday-1)/365.25)]:
            for trig,fn in [('sin',math.sin),('cos',math.cos)]:
                require(equal(float(saved[label+'_'+trig]),fn(2*math.pi*phase)),'Calendar feature changed')
        joined_by_origin[origin]=(epoch,rad,cloud)
    require(missing==129,'Unexpected archive missing count')
    checks=dict(joined_feature_rows=len(joined),prediction_files=0,prediction_rows=0,full_scores=0,monthly_scores=0,validation_combinations=0,training_memberships=0,comparison_rows=0)
    residual=dict(values=0,maximum_absolute_w_m2=0.0,classification_changes=0)
    scored={};predictions={};split_audit={}
    for stage,filename in [('validation','cv_predictions.csv'),('test','test_predictions.csv')]:
        originals=original_sources['eval/'+filename];origins=[datetime.fromisoformat(r['time']) for r in originals];targets=[t+DAY for t in origins]
        actual=[float(r['actual']) for r in originals];baseline=[float(r['baseline']) for r in originals]
        nwp=[joined_by_origin[t][1] for t in origins]
        for t,a,b in zip(origins,actual,baseline,strict=True):require(a==float(features[t]['target']) and b==float(features[t]['shortwave_radiation']),'Evaluation labels changed')
        train=[t for t in features if t+DAY<origins[0]]
        saved_train=rows(RUN/f'{stage}-training-origins.csv')
        require([datetime.fromisoformat(r['feature_time']) for r in saved_train]==train,'Training memberships differ')
        require(all(datetime.fromisoformat(r['target_time'])==t+DAY for r,t in zip(saved_train,train,strict=True)),'Training target times differ')
        expected=dict(hours=len(origins),origin_start=str(origins[0]),origin_end=str(origins[-1]),target_start=str(targets[0]),target_end=str(targets[-1]),
            train_hours=len(train),train_start=str(train[0]),train_end=str(train[-1]),latest_training_target=str(train[-1]+DAY),training_excluded=0,
            purged_hours=sum(t<origins[0] and not t+DAY<origins[0] for t in features),
            evaluation_cloud_missing=sum(joined_by_origin[t][2] is None for t in origins),training_cloud_missing=sum(joined_by_origin[t][2] is None for t in train),
            training_origins_sha256=sha(RUN/f'{stage}-training-origins.csv'))
        require(report['splits'][stage]==expected,'Split report differs');checks['training_memberships']+=1
        split_audit[stage]={k:expected[k] for k in ['hours','evaluation_cloud_missing','training_cloud_missing','training_excluded']}
        months=defaultdict(list)
        for i,t in enumerate(targets):months[t.strftime('%Y-%m')].append(i)
        for name in methods:
            saved=rows(RUN/'predictions'/f'{stage}-{name}.csv');require(len(saved)==len(origins),'Prediction rows lost')
            result=report['methods'][name][stage];cfg=result['configuration'];probability=name.startswith('classifier_');natural=.5 if probability else 600
            require(result['score_unit']==('probability' if probability else 'W/m2'),'Score unit error')
            raw_values=[];selected=[];default=[]
            for i,row in enumerate(saved):
                require(datetime.fromisoformat(row['feature_time'])==origins[i] and datetime.fromisoformat(row['target_time'])==targets[i],'Prediction timestamps differ')
                require(int(row['target_epoch_utc'])==joined_by_origin[origins[i]][0],'Prediction UTC join differs')
                require(float(row['actual_w_m2'])==actual[i] and float(row['baseline_w_m2'])==baseline[i] and float(row['nwp_day2_w_m2'])==nwp[i],'Prediction inputs differ')
                require(int(row['cloud_missing'])==(joined_by_origin[origins[i]][2] is None),'Prediction missingness differs')
                raw_value=float(row['raw_prediction']);require(math.isfinite(raw_value),'Nonfinite prediction')
                if probability:require(0<=raw_value<=1,'Invalid probability')
                if name in ['persistence','original']:
                    reference=float(originals[i]['baseline' if name=='persistence' else 'predicted']);difference=abs(raw_value-reference)
                    require(equal(raw_value,reference) and (raw_value>600)==(reference>600),'Original reference changed')
                    if difference:residual['values']+=1;residual['maximum_absolute_w_m2']=max(residual['maximum_absolute_w_m2'],difference)
                if name in ['nwp_day2','nwp_calibrated']:require(raw_value==nwp[i],'Direct NWP reference changed')
                require(float(row['alpha'])==cfg['alpha'] and float(row['cutoff'])==cfg['cutoff'],'Prediction config differs')
                s=value(name,raw_value,nwp[i],cfg['alpha']);d=value(name,raw_value,nwp[i],1)
                require(equal(s,float(row['score'])) and equal(d,float(row['default_score'])),'Score reconstruction differs')
                require(int(row['predicted_positive'])==(s>cfg['cutoff']) and int(row['default_positive'])==(d>natural),'Strict threshold differs')
                raw_values.append(raw_value);selected.append(s);default.append(d)
            predictions[stage,name]=dict(actual=actual,nwp=nwp,raw=raw_values)
            for basis,vals,cutoff,monthly in [('selected',selected,cfg['cutoff'],'monthly'),('default',default,natural,'default_monthly')]:
                m=metrics(actual,vals,cutoff,probability);audit.compare(m,result[basis],'Full score');scored[stage,name,basis]=m;checks['full_scores']+=1
                require([r['month'] for r in result[monthly]]==list(months),'Month missing or reordered')
                for row in result[monthly]:
                    indices=months[row['month']];audit.compare(metrics([actual[i] for i in indices],[vals[i] for i in indices],cutoff,probability),row,'Monthly score');checks['monthly_scores']+=1
            checks['prediction_files']+=1;checks['prediction_rows']+=len(saved)
    selection=load(RUN/'validation-selection.json');require(sha(RUN/'validation-selection.json')==report['selection_sha256'],'Selection identity differs')
    persistence,original=scored['validation','persistence','selected'],scored['validation','original','selected']
    for name in methods:
        cfg=report['methods'][name]['validation']['configuration'];require(cfg==report['methods'][name]['test']['configuration']==selection['all_configurations'][name],'Test retuning')
        audit.compare(scored['validation',name,'selected'],selection['validation'][name],'Frozen selection score')
        natural=.5 if name.startswith('classifier_') else 600
        if name in ['persistence','original','nwp_day2']:
            require(cfg==dict(alpha=1,cutoff=600,qualifies=gate(scored['validation',name,'selected'],persistence,original)),'Fixed reference gate');continue
        grid_path=RUN/f'validation-grid-{name}.json';require(sha(grid_path)==selection['grid_sha256'][grid_path.name],'Grid identity differs');grid=load(grid_path)
        cutoffs=[i/100 for i in range(5,96)] if name.startswith('classifier_') else list(range(450,751,10))
        combinations=[(a,c) for a in ([0,.25,.5,.75,1] if name=='residual_nwp' else [1]) for c in cutoffs]
        require([(g['alpha'],g['cutoff']) for g in grid]==combinations,'Grid coverage differs');data=predictions['validation',name]
        for row in grid:
            vals=[value(name,r,n,row['alpha']) for r,n in zip(data['raw'],data['nwp'],strict=True)]
            m=metrics(data['actual'],vals,row['cutoff'],name.startswith('classifier_'));audit.compare(m,row,'Grid score')
            require(row['qualifies']==gate(m,persistence,original),'Grid gate differs');checks['validation_combinations']+=1
        qualifying=[g for g in grid if g['qualifies']];best=max(qualifying,key=lambda g:ranking(g,natural)) if qualifying else None
        require(cfg==({k:best[k] for k in ['alpha','cutoff','qualifies']} if best else dict(alpha=1,cutoff=natural,qualifies=False)),'Per-method selection differs')
    qualifying=[n for n in methods if selection['all_configurations'][n]['qualifies']]
    chosen=max(qualifying,key=lambda n:(*ranking({**scored['validation',n,'selected'],**selection['all_configurations'][n]},.5 if n.startswith('classifier_') else 600),-methods.index(n))) if qualifying else 'persistence'
    require(chosen==selection['method']==report['recommendation']['method'] and selection['fallback_no_qualifier']==(not qualifying),'Global selection differs')
    comparison=rows(RUN/'comparison.csv');require(len(comparison)==28,'Comparison coverage differs');seen=set()
    for row in comparison:
        key=row['split'],row['method'],row['basis'];require(key not in seen and key in scored,'Comparison repeated/unknown');seen.add(key)
        audit.compare(scored[key],{k:None if row[k]=='' else float(row[k]) for k in audit.MEASURES},'Comparison score');checks['comparison_rows']+=1
    join_audit=load(RUN/'join-audit.json');require(join_audit['splits']==split_audit and join_audit['day2_cloud_missing']==missing and join_audit['day2_radiation_missing']==0,'Join audit differs')
    numerical={n:promotion(scored['test',n,'selected'],scored['test','original','selected'],scored['test','persistence','selected']) for n in methods}
    result={'status':'PASS','mismatches':[],'checks':checks,'report_sha256':sha(RUN/'report.json'),
        'protocol_sha256':report['protocol_sha256'],'code_sha256':report['code_sha256'],'checker_sha256':sha(Path(__file__)),
        'reused_checker_sha256':sha(HERE.parent/'f1-002/check_audit.py'),'archive_sha256':report['archive_sha256'],
        'input_sha256':report['input_sha256'],'run_log_sha256':sha(HERE/'run.log'),'split_missingness':split_audit,
        'reference_csv_parser_residual':residual,'numeric_check_tolerance_absolute':1e-9,
        'selected_method':chosen,'selected_passes_numerical_promotion':numerical[chosen],
        'all_methods_numerical_gate':numerical,'release_recommendation':False,'independent_future_evidence':False,
        'interpretation':'Per-method numerical passes do not change the frozen validation winner or establish live archive availability.'}
    if args.output:
        with args.output.open('x') as stream:stream.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':result['status'],'checks':checks,'selected':chosen,'selected_numerical_promotion':numerical[chosen],'all_methods_gate':numerical},sort_keys=True))


if __name__=='__main__':main()
