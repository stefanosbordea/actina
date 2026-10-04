"""Independent saved-probability/reference/count audit; no model fit or inference."""
import csv
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent; EXP=HERE.parent; ROOT=EXP.parents[2]; OUT=EXP/'result'
METHODS=['original','persistence','nwp_day2','small','medium','larger']
checks=0


def require(condition,label):
    global checks
    checks+=1
    if not condition: raise AssertionError(label)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with path.open(newline='') as stream:return list(csv.DictReader(stream))


def score(values):
    tp=sum(truth and call for truth,call,p in values);fp=sum(not truth and call for truth,call,p in values)
    fn=sum(truth and not call for truth,call,p in values);tn=len(values)-tp-fp-fn
    return {'hours':len(values),'tp':tp,'fp':fp,'fn':fn,'tn':tn,
        'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,
        'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
        'brier':math.fsum((p-int(truth))**2 for truth,call,p in values)/len(values) if values else None}


def compare(actual,expected,label):
    require(set(actual)==set(expected),label+' fields')
    for key,value in expected.items():
        if value is None:require(actual[key] is None,label+'.'+key)
        elif isinstance(value,int):require(actual[key]==value,label+'.'+key)
        else:require(math.isclose(actual[key],value,abs_tol=1e-12,rel_tol=1e-12),label+'.'+key)


report=json.loads((OUT/'report.json').read_text());selection=json.loads((OUT/'validation-selection.json').read_text())
pins=json.loads((EXP/'inputs.json').read_text());frozen_report_sha=sha(OUT/'report.json')
require(report['status']=='COMPLETE','completed source run')
require(sha(EXP/'PROTOCOL.md')==report['protocol_sha256'],'protocol hash')
require(sha(EXP/'run.py')==report['code_sha256'],'runner hash')
require(sha(OUT/'validation-selection.json')==report['selection_sha256'],'selection hash')
require(sha(EXP/'inputs.json')==selection['input_manifest_sha256'],'input lock hash')
for path,value in pins.items():require(sha(ROOT/path)==value==report['input_sha256'][path],'input hash '+path)
for path,value in report['outputs_sha256'].items():require(sha(OUT/path)==value,'output hash '+path)
source_sat=rows(ROOT/'app/experiments/satellite-reference-001/result/reference-full.csv')
sat={datetime.fromisoformat(r['valid_time_utc']):None if r['shortwave_radiation_w_m2']=='' else float(r['shortwave_radiation_w_m2']) for r in source_sat}
require(len(sat)==len(source_sat),'unique satellite epochs')
for r in source_sat:require(int(r['is_missing'])==(sat[datetime.fromisoformat(r['valid_time_utc'])] is None),'satellite missing flag')
archive=json.loads((ROOT/'app/experiments/nwp-archive-001/archive.json').read_text())['hourly']
nwp=dict(zip(archive['time'],archive['shortwave_radiation_previous_day2']))
comparison=rows(OUT/'comparison.csv');require(len(comparison)==36,'all36 comparisons retained')
require(len({(r['split'],r['method'],r['basis']) for r in comparison})==36,'unique comparison groups')
summary={};coverage={};predicted_rows=0;threshold_equalities={};default_rows=0
for stage,file,n in [('validation','cv_predictions.csv',3566),('test','test_predictions.csv',3567)]:
    original=rows(ROOT/'eval'/file);keys=[r['time'] for r in original]
    require(len(keys)==n and len(set(keys))==n,'original membership')
    member=rows(OUT/f'{stage}-reference-membership.csv');require([r['feature_time'] for r in member]==keys,'reference membership')
    values=[];missing=[]
    for source,m in zip(original,member):
        origin=datetime.fromisoformat(source['time']);target=origin+timedelta(hours=24)
        valid=target.replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc)
        require(valid in sat,'exact UTC satellite key exists')
        satellite=sat[valid];weather=float(source['actual'])
        require(datetime.fromisoformat(m['target_time_utc'])==valid,'membership UTC time')
        require(float(m['weather_actual_w_m2'])==weather,'membership weather value')
        require((None if m['satellite_w_m2']=='' else float(m['satellite_w_m2']))==satellite,'membership satellite value')
        require(int(m['scored'])==(satellite is not None),'null satellite retained unscored')
        if satellite is None:missing.append(valid.isoformat())
        values.append((target,valid,weather,satellite))
    coverage[stage]={'original_hours':n,'common_hours':n-len(missing),'missing_hours':len(missing),'missing_valid_times_utc':missing}
    require(report['reference_sensitivity'][stage]==coverage[stage],'reported complete missingness')
    for method in METHODS:
        records=rows(OUT/'predictions'/f'{stage}-{method}.csv')
        require([r['feature_time'] for r in records]==keys,'all forecast keys')
        cutoff=selection['all_thresholds'][method]['cutoff'] if method in selection['all_thresholds'] else .5
        require(report['methods'][method][stage]['cutoff']==cutoff,'frozen validation cutoff')
        groups={'weather_full':[],'weather_common':[],'satellite_common':[]};defaults=[];ties=0
        for source,r,(target,valid,weather,satellite) in zip(original,records,values):
            require(datetime.fromisoformat(r['target_time'])==target and int(r['target_epoch_utc'])==int(valid.timestamp()),'prediction target/epoch')
            require(float(r['actual_w_m2'])==weather,'prediction reference unchanged')
            probability=float(r['probability']);saved_cutoff=float(r['cutoff'])
            require(math.isfinite(probability) and 0<=probability<=1 and saved_cutoff==cutoff,'probability/cutoff')
            event=probability>cutoff;default=probability>.5
            require(int(r['predicted_positive'])==event and int(r['default_positive'])==default,'exact strict cutoff')
            if probability==cutoff:ties+=1;require(not event,'threshold equality negative')
            if method in ['original','persistence','nwp_day2']:
                value=float(source['predicted']) if method=='original' else float(source['baseline']) if method=='persistence' else nwp[int(valid.timestamp())]
                require(probability==int(value>600),'unaltered source control')
            groups['weather_full'].append((weather>600,event,probability));defaults.append((weather>600,default,probability))
            if satellite is not None:
                groups['weather_common'].append((weather>600,event,probability));groups['satellite_common'].append((satellite>600,event,probability))
            predicted_rows+=1
        threshold_equalities[stage+'_'+method]=ties
        compare(report['methods'][method][stage]['metrics'],score(groups['weather_full']),'report full '+stage+method)
        compare(report['methods'][method][stage]['default_0_5'],score(defaults),'report default '+stage+method);default_rows+=1
        for basis,group in groups.items():
            actual=next(r for r in comparison if (r['split'],r['method'],r['basis'])==(stage,method,basis))
            require(float(actual['cutoff'])==cutoff,'comparison frozen cutoff')
            parsed={k:None if actual[k]=='' else int(actual[k]) if k in ['hours','tp','tn','fp','fn'] else float(actual[k]) for k in score(group)}
            expected=score(group);compare(parsed,expected,'comparison '+stage+method+basis)
            summary.setdefault(stage+'_'+basis,{})[method]=expected
chosen=selection['selected_method'];require(chosen==report['selected_method'],'same selected method')
m=summary['test_weather_full'][chosen];control=summary['test_weather_full']['nwp_day2']
def exact(m,key):
    a,b={'precision':(m['tp'],m['tp']+m['fp']),'recall':(m['tp'],m['tp']+m['fn']),'f1':(2*m['tp'],2*m['tp']+m['fp']+m['fn'])}[key]
    return Fraction(a,b) if b else Fraction(-1)
gate=chosen!='nwp_day2' and all(exact(m,k)>=exact(control,k)>=0 for k in ['precision','recall','f1']) and any(exact(m,k)>exact(control,k) for k in ['precision','recall','f1'])
require(gate==report['test_gate_passed'],'reported retrospective test gate')
require(all(sha(ROOT/path)==value for path,value in pins.items()),'immutable input bytes after audit')
require(sha(OUT/'report.json')==frozen_report_sha,'result report unchanged')
result={'status':'PASS','checks':checks,'saved_prediction_rows_verified':predicted_rows,'comparison_rows_verified':36,'default_metric_rows_verified':default_rows,
    'coverage':coverage,'exact_cutoff_equalities':threshold_equalities,'selected_method':chosen,'threshold':selection['all_thresholds'][chosen]['cutoff'],
    'retrospective_weather_test_gate_passed':gate,'metrics':summary,'protocol_sha256':report['protocol_sha256'],'source_report_sha256':frozen_report_sha,
    'checker_sha256':sha(Path(__file__)),'source_inputs_unchanged':True,'count_and_decision_comparison':'exact; Brier/P/R/F1 absolute and relative tolerance1e-12',
    'scope':'Independent reference joins, source controls, saved probabilities/cutoffs, all full/common/default metrics and hashes. No model fitting or probability-model replay; chronology and threshold-grid selection reviewed separately by storage_requirements_core.',
    'limitations':['Already-inspected test and archive-derived streaming residual context; no verified issuance/publication availability.','Historical weather-reference gate is not a release or universal-improvement test.','Satellite-test selected classifier loses to NWP in precision, recall and F1.','No new irradiance point estimate, plant feasibility, curtailment recovery or measured savings established.']}
(HERE/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:result[k] for k in ['status','checks','saved_prediction_rows_verified','comparison_rows_verified','default_metric_rows_verified','selected_method','threshold']}))
