"""Independent expanded-sample audit of fixed calendar-block sensitivity."""
import csv
from fractions import Fraction
from datetime import datetime,timedelta,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
sys.dont_write_bytecode=True
import numpy as np
HERE=Path(__file__).resolve().parent
UNC=HERE.parent
EXP=UNC.parent
start=time.perf_counter();checks=0
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def check(ok,label):
    global checks
    checks+=1
    if not ok:raise AssertionError(label)
def rows(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def flag(v):return v in ('True','1',True)
report=json.loads((UNC/'result.json').read_text())
identity={EXP/p:h for p,h in report['inputs_sha256'].items()}
identity[UNC/'result.json']=sha(UNC/'result.json')
for p,h in identity.items():check(sha(p)==h,'initial identity')
spec=importlib.util.spec_from_file_location('reviewed_tail',UNC/'check.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
# Independent exact-rational expanded integer-weight fixtures.
fixture_rng=np.random.default_rng(918)
maximum_fixture_error=0.
for size in (1,2,3,9,10,11,64,139,144):
    for trial in range(30):
        values=fixture_rng.integers(-100,101,size=size)/8
        weights=fixture_rng.integers(0,5,size=size)
        if not weights.any():weights[0]=1
        expanded=sorted([Fraction.from_float(float(v)) for v,n in zip(values,weights) for _ in range(int(n))],reverse=True)
        mass=Fraction(len(expanded),10);remaining=mass;total=Fraction(0)
        for v in expanded:
            w=min(Fraction(1),remaining);total+=w*v;remaining-=w
            if not remaining:break
        expected=np.array([float(sum(expanded)/len(expanded)),float(total/mass)])
        actual=module.statistics(values,weights[None])[0]
        err=float(np.max(abs(expected-actual)));maximum_fixture_error=max(maximum_fixture_error,err)
        check(err<1e-12,'rational weighted fixture')

# Every bootstrap realization is expanded by calendar indices, not grouped weights.
def expanded_stats(values,indices,mask):
    valid=mask[indices];count=valid.sum(axis=1)
    check(np.all(count>0),'nonempty draws')
    sampled=values[indices]
    mean=np.where(valid,sampled,0.).sum(axis=1)/count
    ordered=np.sort(np.where(valid,sampled,-np.inf),axis=1)[:,::-1]
    whole,remainder=np.divmod(count,10)
    prefix=np.cumsum(ordered,axis=1)
    full=np.where(whole>0,prefix[np.arange(len(count)),np.maximum(whole-1,0)],0.)
    tail=(10*full+remainder*ordered[np.arange(len(count)),whole])/count
    return np.column_stack((mean,tail))

def point_stats(values):
    values=np.sort(np.asarray(values,dtype=float))[::-1];whole,remainder=divmod(len(values),10)
    return np.array([float(values.mean()),float((10*sum(values[:whole])+remainder*values[whole])/len(values))])
rng=np.random.default_rng(20261004);max_metric_error=0.;frequency_differences=[];records=[]
for split in ('validation','test'):
    member=rows(EXP/f'result/{split}/evaluation-membership.csv');daily=rows(EXP/f'result/{split}/daily-outcomes.csv')
    dates=[datetime.fromisoformat(r['day']) for r in member];mask=np.array([flag(r['primary']) for r in member]);calendar={r['day']:i for i,r in enumerate(member)}
    check(all(b-a==timedelta(days=1) for a,b in zip(dates,dates[1:])),'actual contiguous calendar')
    arrays={}
    for reference in ('weather','satellite'):
        for method in ('raw_point','coherent','shuffled'):
            values=np.zeros((len(dates),2));selected=[r for r in daily if flag(r['primary']) and r['reference']==reference and r['method']==method]
            check([r['day'] for r in selected]==[r['day'] for r in member if flag(r['primary'])],'same primary order')
            for r in selected:values[calendar[r['day']]]=[float(r['cost_eur']),float(r['grid_kwh'])]
            arrays[reference,method]=values
    for block in (1,7):
        origins=rng.integers(len(dates),size=(5000,(len(dates)+block-1)//block))
        indices=np.concatenate([((origins[:,j,None]+np.arange(block))%len(dates)) for j in range(origins.shape[1])],axis=1)[:,:len(dates)]
        counts=mask[indices].sum(axis=1);empty=counts==0;indices=indices[~empty]
        record=next(r for r in report['comparisons'] if r['split']==split and r['block_days']==block)
        check(record['empty_draws']==int(empty.sum()) and record['minimum_primary_days_in_draw']==int(counts.min()) and record['maximum_primary_days_in_draw']==int(counts.max()),'calendar weights and missing days')
        check(record['draws']==5000 and record['calendar_days']==len(dates) and record['primary_days']==int(mask.sum()),'draw cohort dimensions')
        for method in ('coherent','shuffled'):
            saved=next(r for r in record['comparisons'] if r['method']==method);differences=[]
            for reference in ('weather','satellite'):
                candidate=arrays[reference,method];control=arrays[reference,'raw_point']
                for col,metric in enumerate(('cost_eur','grid_kwh')):
                    draws=expanded_stats(candidate[:,col],indices,mask)-expanded_stats(control[:,col],indices,mask)
                    point=point_stats(candidate[mask,col])-point_stats(control[mask,col]);differences.append(draws)
                    for j,statistic in enumerate(('mean','cvar90')):
                        item=next(a for a in saved['axes'] if a['reference']==reference and a['metric']==metric and a['statistic']==statistic)
                        interval=np.quantile(draws[:,j],[.025,.975],method='linear')
                        err=max(abs(float(point[j])-item['difference']),float(np.max(abs(interval-item['percentile_95']))));max_metric_error=max(max_metric_error,err)
                        check(err<1e-8,'expanded paired interval')
                regret=candidate[:,0]-control[:,0]
                draws=expanded_stats(regret,indices,mask)[:,1];point=point_stats(regret[mask])[1]
                item=next(a for a in saved['risk'] if a['reference']==reference)
                err=max(abs(float(point)-item['cvar90_daily_cost_regret']),float(np.max(abs(np.quantile(draws,[.025,.975],method='linear')-item['percentile_95']))));max_metric_error=max(max_metric_error,err)
                check(err<1e-8,'regret CVaR distinct from tail difference')
            fraction=float(np.mean(np.all(np.column_stack(differences)<0,axis=1)))
            difference=fraction-saved['fraction_all_eight_axes_strictly_improved']
            if difference:frequency_differences.append(dict(split=split,block_days=block,method=method,expanded_fraction=fraction,saved_fraction=saved['fraction_all_eight_axes_strictly_improved'],difference=difference))
        records.append(dict(split=split,block_days=block,draws=5000,empty_draws=int(empty.sum()),primary_count_range=[int(counts.min()),int(counts.max())]))
for p,h in identity.items():check(sha(p)==h,'final identity')
result=dict(status='PASS' if not frequency_differences else 'METRICS_PASS_FREQUENCY_DIFFERENCE',checks=checks,rational_weighted_fixtures=270,maximum_fixture_error=maximum_fixture_error,expanded_calendar_draws=20000,paired_comparisons=8,maximum_point_or_interval_error=max_metric_error,strict_all_axis_frequency_differences=frequency_differences,calendar_groups=records,immutable_files=len(identity),
    interpretation='Marginal percentile intervals and strict-improvement frequencies are exploratory sensitivity results. Shared calendar resamples retain excluded dates before masking. They neither correct prior selection nor authenticate future availability or physical field benefits.',
    source_report_sha256=sha(UNC/'result.json'),code_sha256=sha(Path(__file__)),completed_at_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-start)
(HERE/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps(result,allow_nan=False))
