"""Independent reconstruction. Imports saved Booster API, never experiment runners."""
import bisect
import csv
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys
import time
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
ROOT = EXP.parents[2]
OUT = EXP / 'result'
checks = 0
start = time.perf_counter()

def check(value, message):
    global checks
    checks += 1
    if not value: raise AssertionError(message)

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    with p.open(newline='') as f: return list(csv.DictReader(f))
def dt(v): return datetime.fromisoformat(v) if v else None
def num(v): return float(v) if v not in ('', None) else math.nan
def boolean(v): return v in ('True', '1', 1, True)
def same(a, b, label, tolerance=0):
    a, b = num(a), num(b)
    check((math.isnan(a) and math.isnan(b)) or abs(a-b) <= tolerance, label)
def metric(y, p, probability=None):
    tp=sum(a and b for a,b in zip(y,p)); fp=sum(not a and b for a,b in zip(y,p))
    fn=sum(a and not b for a,b in zip(y,p)); tn=len(y)-tp-fp-fn
    return dict(hours=len(y),tp=tp,fp=fp,fn=fn,tn=tn,
        precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,
        f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
        brier=math.fsum((v-int(a))**2 for v,a in zip(probability,y))/len(y) if probability is not None else None)
def metrics(rows, p, probability=None):
    common=[i for i,r in enumerate(rows) if math.isfinite(num(r['satellite_w_m2']))]
    def one(indices, field):
        return metric([num(rows[i][field])>600 for i in indices],[p[i] for i in indices],
                      [probability[i] for i in indices] if probability is not None else None)
    return dict(weather_full=one(range(len(rows)),'weather_actual_w_m2'),
        weather_common=one(common,'weather_actual_w_m2'),satellite_common=one(common,'satellite_w_m2'))
def compare(actual, expected, label):
    for basis, values in actual.items():
        for k,v in values.items():
            e=expected[basis][k]
            check((v is None and e is None) or (v is not None and e is not None and abs(v-e)<=1e-13), label+'/'+basis+'/'+k)
def frac(m,k):
    n,d={'precision':(m['tp'],m['tp']+m['fp']),'recall':(m['tp'],m['tp']+m['fn']),
         'f1':(2*m['tp'],2*m['tp']+m['fp']+m['fn'])}[k]
    return Fraction(n,d) if d else None

def gate(a,b):
    pairs=[(frac(a[s],k),frac(b[s],k)) for s in ('weather_full','satellite_common') for k in ('precision','recall','f1')]
    return (all(x is not None and y is not None and x>=y for x,y in pairs) and any(x>y for x,y in pairs if x is not None and y is not None),
            all(x is not None and y is not None and x>y for x,y in pairs))
def rank(c):
    v=c['metrics']; pairs=[v[s] for s in ('weather_full','satellite_common')]
    fs=[frac(m,'f1') for m in pairs]
    return min(fs),sum(fs)/2,min(frac(m,'precision') for m in pairs),min(frac(m,'recall') for m in pairs),-c['full_day_swaps'],c['policy']['margin']

pins=json.loads((EXP/'inputs.json').read_text())
outputs=json.loads((OUT/'outputs.json').read_text())
identities={ROOT/p:h for p,h in pins.items()} | {OUT/p:h for p,h in outputs.items()}
for p,h in identities.items(): check(sha(p)==h,'initial hash '+str(p))
report=json.loads((OUT/'report.json').read_text())
check(report['input_sha256']==pins,'report inputs')
features=read(OUT/'features.csv'); old=read(ROOT/'app/experiments/f1-008/result/features.csv')
meta=read(OUT/'source-timestamps.csv'); targets=read(ROOT/'app/experiments/f1-006/result/feature-targets.csv')
ref=read(ROOT/'app/experiments/reference-training-001/result/joined-reference.csv')
weather={dt(r['time']):r for r in read(ROOT/'data/paphos_weather_data.csv')}
check(len(features)==len(old)==len(meta)==len(targets)==len(ref)==17832,'source count')
times=[dt(r['target_time']) for r in targets]
check(len(set(times))==len(times) and all(b-a==timedelta(hours=1) for a,b in zip(times,times[1:])),'unique hourly chronology')
residuals=[num(r['actual'])-num(f['nwp_day2_radiation']) for r,f in zip(targets,old)]
index={r['feature_time']:i for i,r in enumerate(features)}
history={}
for i,(f,o,m,t,r) in enumerate(zip(features,old,meta,targets,ref)):
    target=times[i]; issue=target.replace(hour=0)-timedelta(days=1); state=issue-timedelta(hours=1); lag=issue-timedelta(hours=24)
    check(dt(f['feature_time'])==dt(o['feature_time'])==dt(t['feature_time'])==target-timedelta(days=1),'origin')
    check(target==dt(r['target_time']) and target.replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc)==dt(r['valid_time_utc']),'reference clock')
    same(t['actual'],r['weather_actual_w_m2'],'weather reference');same(t['actual'],weather[target]['shortwave_radiation'],'raw truth')
    if issue not in history:
        last=bisect.bisect_left(times,issue); h={}
        for window in (24,168):
            first=bisect.bisect_left(times,issue-timedelta(hours=window)); values=residuals[first:last]
            h[f'issue_residual_count_{window}']=len(values)
            h[f'issue_residual_mean_{window}']=math.fsum(values)/len(values) if values else math.nan
        at=bisect.bisect_left(times,lag)
        h['issue_residual_lag24']=residuals[at] if at<len(times) and times[at]==lag else math.nan
        history[issue]=(h,times[last-1] if last else None)
    h,latest=history[issue]
    expected={k:v for k,v in o.items() if k not in ('feature_time','temperature_2m','shortwave_radiation','relative_humidity_2m','cloud_cover','radiation_yesterday','hour','month','residual_mean_24','residual_count_24','residual_mean_168','residual_count_168','residual_lag24')}
    expected.update({'issue_'+k:weather[state][k] for k in ('temperature_2m','shortwave_radiation','relative_humidity_2m','cloud_cover')})
    expected.update(issue_radiation_lag24=weather[lag]['shortwave_radiation'],lead_hours=(target-issue).total_seconds()/3600,issue_month=issue.month,**h)
    check(set(expected)==set(f)-{'feature_time'},'27 names')
    for k,v in expected.items(): same(f[k],v,'feature '+k,1e-9 if 'residual_mean' in k else 0)
    expected_times=dict(feature_time=target-timedelta(days=1),target_time=target,issue_time=issue,weather_source_time=state,lag24_source_time=lag,latest_residual_source_time=latest,nwp_nominal_time=target-timedelta(hours=48),maximum_source_time=state)
    for k,v in expected_times.items(): check(dt(m[k])==v,'metadata '+k)
    check(max(v for k,v in expected_times.items() if k.endswith('source_time') and v is not None)<issue,'all observation sources strictly before issue')
    check(expected_times['nwp_nominal_time']<issue,'nominal NWP before issue')

import pandas as pd
import lightgbm as lgb
matrix=pd.read_csv(OUT/'features.csv',float_precision='round_trip').drop(columns='feature_time')
selection=json.loads((OUT/'validation-selection.json').read_text())
check(selection['validation_prediction_sha256']==sha(OUT/'predictions/validation-full.csv'),'selection prediction identity')
check(dt(report['started_at_utc'])<dt(selection['frozen_at_utc'])<dt(report['completed_at_utc']),'selection execution order')
summary={}; maximum_replay_error=0; total_pairs=0; metric_records=0
for stage,filename in [('validation','cv_predictions.csv'),('test','test_predictions.csv')]:
    original=read(ROOT/'eval'/filename); origins=[r[next(iter(r))] for r in original]
    scored_indices=[index[v] for v in origins]; days={times[i].date() for i in scored_indices}
    full_indices=[i for i,t in enumerate(times) if t.date() in days]
    pred=read(OUT/f'predictions/{stage}-full.csv')
    check([r['feature_time'] for r in pred]==[features[i]['feature_time'] for i in full_indices],'full day membership')
    check(len(pred)==24*len(days),'full day count')
    scored=[]; baseline=[]
    for j,(p,i) in enumerate(zip(pred,full_indices)):
        check(boolean(p['original_score_mask'])==(i in scored_indices),'original mask')
        check(boolean(p['satellite_score_mask'])==((i in scored_indices) and math.isfinite(num(ref[i]['satellite_w_m2']))),'satellite mask')
        for k in meta[i]: check(dt(p[k])==dt(meta[i][k]),'prediction source')
        same(p['weather_actual_w_m2'],targets[i]['actual'],'prediction weather');same(p['satellite_w_m2'],ref[i]['satellite_w_m2'],'prediction SAT')
        same(p['nwp_day2_w_m2'],features[i]['nwp_day2_radiation'],'prediction NWP')
        baseline.append(num(p['nwp_day2_w_m2'])>600)
        check(boolean(p['nwp_positive'])==baseline[-1],'strict raw cutoff')
        if boolean(p['original_score_mask']): scored.append(j)
    check([pred[j]['feature_time'] for j in scored]==origins,'all original hours order')
    for o,j in zip(original,scored): same(o['actual'],pred[j]['weather_actual_w_m2'],'original actual')
    cutoff=min(dt(p['issue_time']) for p in pred); train_indices=[i for i,t in enumerate(times) if t<cutoff]
    train=read(OUT/f'{stage}-training.csv')
    check([r['feature_time'] for r in train]==[features[i]['feature_time'] for i in train_indices],'purged training exact')
    sat_train=0
    for row,i in zip(train,train_indices):
        for k,v in meta[i].items(): check(dt(row[k])==dt(v),'training source')
        same(row['weather_actual_w_m2'],targets[i]['actual'],'training weather'); same(row['satellite_w_m2'],ref[i]['satellite_w_m2'],'training satellite')
        known=math.isfinite(num(row['satellite_w_m2'])); sat_train+=known
        check(boolean(row['weather_event'])==(num(targets[i]['actual'])>600),'weather label')
        check((not known and row['satellite_event']=='') or (known and num(row['satellite_event'])==int(num(ref[i]['satellite_w_m2'])>600)),'SAT label')
        check(boolean(row['satellite_training'])==known and row['satellite_exclusion']==('' if known else 'missing_reference'),'missing training ledger')
    check(report['splits'][stage]['weather_training_rows']==len(train) and report['splits'][stage]['satellite_training_rows']==sat_train,'reported train count')
    scored_rows=[pred[j] for j in scored]; control=metrics(scored_rows,[baseline[j] for j in scored])
    compare(control,report['methods']['nwp_day2'][stage]['metrics'],'control');metric_records+=3
    probabilities={}
    for head in ('weather','satellite'):
        booster=lgb.Booster(model_file=str(OUT/f'models/{stage}-{head}.txt'))
        check(booster.feature_name()==list(matrix.columns),'saved feature order')
        values=booster.predict(matrix.iloc[full_indices],num_threads=2)
        probabilities[head]=[num(p['probability_'+head]) for p in pred]
        err=max(abs(float(a)-b) for a,b in zip(values,probabilities[head]));maximum_replay_error=max(maximum_replay_error,err)
        check(err==0,'Booster exact replay')
        pm=[probabilities[head][j] for j in scored]
        compare(metrics(scored_rows,[v>.5 for v in pm],pm),report['raw_head_scores'][head][stage],'head metrics');metric_records+=3
    for name in ('original','persistence','008_context'):
        path=ROOT/('app/experiments/f1-008/result/predictions/'+stage+'-consensus_two_source.csv' if name=='008_context' else 'app/experiments/f1-006/result/predictions/'+stage+'-'+name+'.csv')
        saved=read(path);check([r['feature_time'] for r in saved]==origins,'context membership')
        decisions=[boolean(r['predicted_positive']) if name=='008_context' else num(r['probability'])>.5 for r in saved]
        compare(metrics(scored_rows,decisions),report['methods'][name][stage]['metrics'],'context metric');metric_records+=3
    arms={}
    for arm in ('min','mean'):
        ledger=read(OUT/f'pairs/{stage}-{arm}.csv'); bykey={(r['target_day'],float(r['margin'])):r for r in ledger}
        check(len(ledger)==len(bykey)==len(days)*6,'pair ledger unique coverage')
        candidates=json.loads((OUT/f'{stage}-grid-{arm}.json').read_text());check([c['policy']['margin'] for c in candidates]==[0,.05,.1,.2,.3,.5],'fixed margin grid')
        rebuilt=[]
        for candidate in candidates:
            margin=candidate['policy']['margin']; decisions=baseline.copy(); swaps=0
            for first in range(0,len(pred),24):
                end=first+24; b=baseline[first:end]; pw=probabilities['weather'][first:end]; ps=probabilities['satellite'][first:end]
                options=[]
                for a in range(24):
                    if b[a]: continue
                    for r in range(24):
                        if not b[r]: continue
                        dw=pw[a]-pw[r]; ds=ps[a]-ps[r]
                        score=min(dw,ds) if arm=='min' else (dw+ds)/2
                        options.append((score,-a,-r,dw,ds))
                pair=max(options,key=lambda z:z[:3]) if options else None
                acted=pair is not None and pair[0]>margin
                day=dt(pred[first]['target_time']).date().isoformat(); row=bykey[(day,margin)]
                check(row['arm']==arm and dt(row['issue_time'])==dt(pred[first]['issue_time']),'pair issue')
                check(boolean(row['acted'])==acted,'strict margin action')
                if pair:
                    score,na,nr,dw,ds=pair; a,r=-na,-nr
                    for k,v in [('add',a),('remove',r),('weather_difference',dw),('satellite_difference',ds),('score',score)]: same(row[k],v,'best pair '+k)
                    for prefix,pos in [('add',first+a),('remove',first+r)]:
                        check(dt(row[prefix+'_target'])==dt(pred[pos]['target_time']),'pair target')
                        for mask in ('original','satellite'): check(boolean(row[prefix+'_'+mask+'_mask'])==boolean(pred[pos][mask+'_score_mask']),'post hoc pair masks')
                    if acted: decisions[first+a]=True;decisions[first+r]=False;swaps+=1
                else: check(row['add']==row['remove']==row['score']=='','no pair')
                check(sum(decisions[first:end])==sum(b)==int(row['positive_count_before'])==int(row['positive_count_after']),'full-day preserved count')
                total_pairs+=1
            col=f'{arm}_margin_{margin:g}_positive'
            check([boolean(p[col]) for p in pred]==decisions,'all policy decisions')
            scores=metrics(scored_rows,[decisions[j] for j in scored]); compare(scores,candidate['metrics'],'grid metric');metric_records+=3
            check(candidate['full_day_swaps']==swaps,'full swaps')
            added=sum(decisions[j] and not baseline[j] for j in scored); removed=sum(baseline[j] and not decisions[j] for j in scored)
            check(candidate['original_added']==added and candidate['original_removed']==removed,'masked count')
            passed,strict=gate(scores,control)
            check(candidate['gate']['passes_frozen_gate']==passed and candidate['gate']['all_six_strictly_improved']==strict,'exact six gate')
            rebuilt.append(dict(policy=candidate['policy'],metrics=scores,full_day_swaps=swaps,passes=passed))
        if stage=='validation':
            eligible=[c for c in rebuilt if c['passes']]
            choice=max(eligible,key=rank)['policy'] if eligible else {'kind':'control'}
            check(choice==selection['policies'][arm],'CV choice independent')
        choice=selection['policies'][arm]
        selected=baseline if choice['kind']=='control' else [boolean(p[f'{arm}_margin_{choice["margin"]:g}_positive']) for p in pred]
        check([boolean(p[arm+'_selected_positive']) for p in pred]==selected,'frozen selected policy')
        compare(metrics(scored_rows,[selected[j] for j in scored]),report['methods'][arm][stage]['metrics'],'selected metrics');metric_records+=3
        arms[arm]=dict(policy=choice,margin_swaps=[c['full_day_swaps'] for c in rebuilt])
    summary[stage]=dict(original_hours=len(scored),full_hours=len(pred),complete_days=len(days),weather_training=len(train),satellite_training=sat_train,arms=arms)

# Reconstruct the separate validation-only hindsight budget, never select by it.
validation=read(OUT/'predictions/validation-full.csv'); budget={}
for key,field in [('weather_complete_days','weather_actual_w_m2'),('satellite_complete_available_days','satellite_w_m2')]:
    values=dict(complete_days=0,hours=0,positive_calls=0,positive_truth=0,tp=0,fp=0,fn=0,days_with_both_false_alarm_and_miss=0,maximum_tp_with_one_perfect_pair_per_day=0,maximum_tp_with_arbitrary_count_preserving_reordering=0,unavoidable_fn_from_daily_count_budget=0)
    for i in range(0,len(validation),24):
        day=validation[i:i+24]
        if any(not math.isfinite(num(r[field])) for r in day): continue
        y=[num(r[field])>600 for r in day]; b=[boolean(r['nwp_positive']) for r in day]; m=metric(y,b)
        values['complete_days']+=1;values['hours']+=24;values['positive_calls']+=sum(b);values['positive_truth']+=sum(y)
        for k in ('tp','fp','fn'): values[k]+=m[k]
        correctable=int(m['fp']>0 and m['fn']>0)
        values['days_with_both_false_alarm_and_miss']+=correctable
        values['maximum_tp_with_one_perfect_pair_per_day']+=m['tp']+correctable
        values['maximum_tp_with_arbitrary_count_preserving_reordering']+=min(sum(y),sum(b))
        values['unavoidable_fn_from_daily_count_budget']+=max(0,sum(y)-sum(b))
    budget[key]=values
check(budget==json.loads((EXP/'validation-budget-diagnostic.json').read_text())['references'],'validation count ceiling')
for p,h in identities.items(): check(sha(p)==h,'final hash '+str(p))
result=dict(status='PASS',checks=checks,source_rows=len(features),feature_values=len(features)*27,head_replay_rows=sum(v['full_hours']*2 for v in summary.values()),maximum_probability_replay_error=maximum_replay_error,pair_margin_ledger_rows=total_pairs,metric_records=metric_records,inputs_and_outputs_unchanged=len(identities),splits=summary,validation_count_budget=budget,
    limits=['No training or network. Saved Boosters replayed, fitting implementation not independently replicated.','Common-issue chronology is nominal timestamp evidence, not provider publication-time proof.','Historical references are estimates. Previously inspected test is retrospective.','No-swap selected for both arms. Full-day call count is not water service.'],
    code_sha256=sha(Path(__file__)),protocol_sha256=sha(EXP/'PROTOCOL.md'),report_sha256=sha(OUT/'report.json'),completed_at_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-start)
(HERE/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps(result,allow_nan=False))
