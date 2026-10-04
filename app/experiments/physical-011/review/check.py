"""Independent source, water and economic replay. No production helper or solver import."""
import csv
from datetime import datetime,timedelta,timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import zipfile
sys.dont_write_bytecode=True
import numpy as np
HERE=Path(__file__).resolve().parent
EXP=HERE.parent
ROOT=EXP.parents[2]
OUT=EXP/'result'
checks=0
started=time.perf_counter()

def check(ok,label):
    global checks
    checks+=1
    if not ok:raise AssertionError(label)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def csvread(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def dt(x):return datetime.fromisoformat(x)
def number(x):return float(x) if x else math.nan
def flag(x):return x in ('True','1',True,1)
def load(p):return json.loads(p.read_text())
def equal(a,b,label,tol=0):
    aa,bb=np.asarray(a,dtype=float),np.asarray(b,dtype=float)
    check(aa.shape==bb.shape and np.allclose(aa,bb,rtol=0,atol=tol,equal_nan=True),label)
def tail(values):
    values=sorted((float(v) for v in values),reverse=True)
    check(bool(values) and all(math.isfinite(v) for v in values),'valid tail')
    mass=Fraction(len(values),10)
    remaining=mass
    total=0.
    for v in values:
        weight=min(remaining,Fraction(1))
        total+=float(weight)*v
        remaining-=weight
        if not remaining:break
    return total/float(mass)
def stats(values):
    values=np.asarray(values,dtype=float)
    return dict(mean=float(values.mean()),cvar90=tail(values),maximum=float(values.max()),minimum=float(values.min()))
def compare_stats(a,b,label):
    for k,v in a.items():check(abs(v-b[k])<=1e-8,label+'/'+k)

prices=np.array([.101 if 10<=h<17 else .183 if 17<=h<23 else .130 for h in range(24)])
methods=['tariff_context','raw_point','coherent','shuffled']
references=['weather','satellite']
fixtures=load(HERE/'analytical-fixtures.json')
for case in fixtures['cvar90']:
    values=case.get('losses',range(64))
    expected=float(Fraction(case['expected_fraction'])) if 'expected_fraction' in case else case['expected']
    check(abs(tail(values)-expected)<1e-12,'hand CVaR '+case['id'])
# Finite-scenario CVaR counterexample uses a water-feasible constant plan.
check(tail([816,0])==816 and tail([408,408])==408,'dependent daily tail')
check(sum([816,0])/2==sum([408,408])/2==408,'same mean')

pins=load(EXP/'inputs.json');outputs=load(OUT/'outputs.json');report=load(OUT/'report.json')
identity={ROOT/p:h for p,h in pins.items()}|{OUT/p:h for p,h in outputs.items()}
for p,h in identity.items():check(sha(p)==h,'initial hash '+str(p))
check(report['input_sha256']==pins and report['protocol_sha256']==sha(EXP/'PROTOCOL.md'),'protocol identity')
planning=load(OUT/'planning-freeze.json')
for p,h in planning['files_sha256'].items():check(sha(OUT/p)==h,'planning freeze '+p)
check(report['planning_freeze_sha256']==sha(OUT/'planning-freeze.json'),'planning receipt identity')
check(dt(report['started_at_utc'])<dt(planning['all_plans_created_at_utc'])<dt(report['completed_at_utc']),'planning before report completion')
source=csvread(ROOT/'app/experiments/f1-008/result/features.csv')
targets=csvread(ROOT/'app/experiments/f1-006/result/feature-targets.csv')
reference=csvread(ROOT/'app/experiments/reference-training-001/result/joined-reference.csv')
check(len(source)==len(targets)==len(reference)==17832,'all source hours')
nwp=np.array([number(r['nwp_day2_radiation']) for r in source])
weather=np.array([number(r['actual']) for r in targets]);satellite=np.array([number(r['satellite_w_m2']) for r in reference])
times=[dt(r['target_time']) for r in targets]
origins={r['feature_time']:i for i,r in enumerate(source)}
days={}
for i,(s,t,r) in enumerate(zip(source,targets,reference)):
    check(s['feature_time']==t['feature_time']==r['feature_time'],'origin join')
    check(dt(t['target_time'])==dt(r['target_time'])==dt(s['feature_time'])+timedelta(hours=24),'target join')
    check(dt(r['valid_time_utc'])==times[i].replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc),'fixed UTC+03')
    check(number(r['weather_actual_w_m2'])==weather[i] and flag(r['is_missing'])==math.isnan(satellite[i]),'references')
    days.setdefault(times[i].date().isoformat(),[]).append(i)
check(all(len(v)==24 and [times[i].hour for i in v]==list(range(24)) for v in days.values()),'complete source days')
solver={}
with (OUT/'solver-records.jsonl').open() as f:
    for line in f:
        record=json.loads(line);key=(record['stage'],record['day'],record['method'])
        check(key not in solver,'unique solver record');solver[key]=record
water_records=[];summaries={};total_scenario_values=0;max_scenario_cost_error=0.;max_water_residual=Fraction(0);exact_nonzero_water_plans=0
for stage,splitfile in [('validation','cv_predictions.csv'),('test','test_predictions.csv')]:
    directory=OUT/stage
    original=csvread(ROOT/'eval'/splitfile);membership={origins[r[next(iter(r))]] for r in original}
    selected_days=sorted({times[i].date().isoformat() for i in membership})
    cutoff=dt(selected_days[0])-timedelta(days=1)
    bank=np.load(directory/'bank.npz',allow_pickle=False)
    eligible=[];expected_bank_records=[]
    for day,indices in days.items():
        before=all(times[i]<cutoff for i in indices);known=all(math.isfinite(satellite[i]) for i in indices)
        if before and known:eligible.append(day)
        expected_bank_records.append((day,before,known))
    chosen=eligible[-64:];check(len(chosen)==64,'64 paired days')
    positions=np.array([days[d] for d in chosen],dtype=int)
    equal(bank['source_positions'],positions,'bank membership')
    # Read only NPY header. Never deserialize the retained object timestamp array.
    with zipfile.ZipFile(directory/'bank.npz') as archive:
        with archive.open('source_target_time.npy') as member:
            version=np.lib.format.read_magic(member)
            shape,fortran,dtype=np.lib.format.read_array_header_1_0(member) if version==(1,0) else np.lib.format.read_array_header_2_0(member)
    check(shape==(64,24) and dtype.hasobject,'retained timestamp serialization issue identified')
    # Authoritative chronology is independently reconstructed from numeric positions and pinned CSV.
    check(all(times[int(i)]<cutoff for i in positions.flat),'all bank timestamps reconstructed without pickle')
    equal(bank['weather'],weather[positions],'bank weather');equal(bank['satellite'],satellite[positions],'bank satellite');equal(bank['nwp'],nwp[positions],'bank NWP')
    residual=np.array([weather[positions]-nwp[positions],satellite[positions]-nwp[positions]])
    equal(bank['residuals'],residual,'whole residual paths')
    records=csvread(directory/'bank-membership.csv');check(len(records)==len(days),'bank candidate ledger')
    for row,(day,before,known) in zip(records,expected_bank_records):
        check(row['day']==day and flag(row['strictly_before_cutoff'])==before and flag(row['satellite_complete'])==known and flag(row['selected'])==(day in chosen),'bank flags')
    permutation=bank['permutations']
    rng=np.random.default_rng(20261004);expected_permutation=np.array([rng.permutation(64) for _ in range(24)])
    equal(permutation,expected_permutation,'frozen independent per-hour permutations')
    changed=np.empty_like(residual)
    for r in range(2):
        for h in range(24):changed[r,:,h]=residual[r,permutation[h],h]
    equal(np.sort(changed,axis=1),np.sort(residual,axis=1),'residual marginal identity')
    plans=np.load(directory/'plans.npz',allow_pickle=False);replay=np.load(directory/'scenario-replay.npz',allow_pickle=False)
    q=plans['production'];check(q.shape==(len(selected_days),4,24),'plan shape');check(plans['methods'].tolist()==methods,'method order')
    expected_positions=np.array([days[d] for d in selected_days]);equal(plans['target_positions'],expected_positions,'all touched days planned')
    equal(plans['raw_forecast_ghi'],nwp[expected_positions],'raw issued forecast')
    scenarios=np.empty((len(selected_days),2,2,64,24))
    for j,indices in enumerate(expected_positions):
        scenarios[j,0]=nwp[indices][None,None,:]+residual
        scenarios[j,1]=nwp[indices][None,None,:]+changed
    equal(replay['unclipped_ghi'],scenarios,'all unclipped scenarios')
    total_scenario_values+=scenarios.size
    pv=np.minimum(1700.,np.maximum(0.,scenarios)*1.7)
    equal(np.sort(pv[:,0],axis=2),np.sort(pv[:,1],axis=2),'clipped hourly marginal identity')
    costs=np.empty((len(selected_days),2,4,2,64));energies=np.empty_like(costs);unused=np.empty_like(costs)
    for d,day in enumerate(selected_days):
        for m,method in enumerate(methods):
            power=3.4*q[d,m]
            grid=np.maximum(power[None,None,None,:]-pv[d],0.)
            costs[d,:,m]=np.sum(grid*prices,axis=-1)
            energies[d,:,m]=np.sum(grid,axis=-1)
            unused[d,:,m]=np.sum(np.maximum(pv[d]-power,0.),axis=-1)
            equal(energies[d,:,m],float(np.sum(power))-np.sum(pv[d],axis=-1)+unused[d,:,m],'scenario energy identity',1e-8)
            equal(energies[d,:,m],9792-np.sum(pv[d],axis=-1)+unused[d,:,m],'ideal-energy identity within water tolerance',4e-6)
            stocks=[Fraction(2000)]
            for v in q[d,m]:stocks.append(stocks[-1]+Fraction.from_float(float(v))-120)
            errors=[max(Fraction(0),-min(map(lambda v:Fraction.from_float(float(v)),q[d,m]))),
                    max(Fraction(0),max(map(lambda v:Fraction.from_float(float(v)),q[d,m]))-500),
                    max(Fraction(0),800-min(stocks)),max(Fraction(0),max(stocks)-4000),abs(stocks[-1]-2000)]
            error=max(errors);max_water_residual=max(max_water_residual,error);exact_nonzero_water_plans+=bool(error)
            check(error<=Fraction.from_float(1e-6),'numerical water tolerance')
            water_records.append(dict(stage=stage,day=day,method=method,exact_final_m3=str(stocks[-1]),exact_minimum_m3=str(min(stocks)),exact_maximum_m3=str(max(stocks)),maximum_exact_violation_m3=str(error),within_declared_tolerance=True))
            record=solver[(stage,day,method)]
            check(abs(record['water']['water_m3']-sum(float(v) for v in q[d,m]))<1e-8,'logged water')
            if method!='tariff_context':
                check(all(s['success'] and s['status']==0 for s in record['solves']),'successful solver stages')
                if method=='raw_point':
                    raw_pv=np.minimum(1700.,1.7*np.maximum(0.,nwp[expected_positions[d]]))
                    objective=float(np.sum(np.maximum(power-raw_pv,0)*prices));anchor=np.full(24,120.)
                else:
                    family=m-2
                    losses=costs[d,family,m]-costs[d,family,1]
                    objective=max(tail(losses[r]) for r in range(2));anchor=q[d,1]
                check(abs(objective-record['final_direct_objective'])<1e-8,'scenario-specific baseline objective')
                if record['anchor_returned']:
                    check(not record['primary_cap_applies'] and objective-record['primary_optimum']<=1e-5+1e-9,'declared action-floor fallback gap')
                else:
                    check(record['primary_cap_applies'] and objective<=record['primary_cap']+1e-6,'primary cap')
                check(abs(record['primary_optimum']-record['primary_direct_audit'])<=1e-6,'logged primary audit')
                check(abs(record['L1_distance']-np.sum(abs(q[d,m]-anchor)))<1e-8,'L1 distance')
                if record['anchor_returned']:equal(q[d,m],anchor,'exact anchor returned')
    equal(replay['cost_eur'],costs,'scenario cost all plans',1e-8);equal(replay['grid_kwh'],energies,'scenario grid all plans',1e-8);equal(replay['unused_pv_kwh'],unused,'scenario unused PV',1e-8)
    max_scenario_cost_error=max(max_scenario_cost_error,float(np.max(abs(replay['cost_eur']-costs))))
    equal(costs[:,0].mean(axis=-1),costs[:,1].mean(axis=-1),'expected-cost marginal invariance',1e-9)
    equal(energies[:,0].mean(axis=-1),energies[:,1].mean(axis=-1),'expected-energy marginal invariance',1e-8)
    check(np.all(costs[:,:,1]-costs[:,:,1]==0),'baseline own-scenario regret zero')
    metadata=csvread(directory/'plan-metadata.csv');check(len(metadata)==len(selected_days),'metadata coverage')
    for row,day in zip(metadata,selected_days):
        d=dt(day);issue=d-timedelta(days=1)
        check(row['day']==day and dt(row['issue_time'])==issue,'common issuance')
        check(dt(row['issue_utc'])==issue.replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc),'issue UTC')
        check(dt(row['interval_start'])==d-timedelta(hours=1) and dt(row['interval_end'])==d+timedelta(hours=23),'preceding-hour physical horizon')
        check(dt(row['maximum_bank_source_time'])==times[positions[-1,-1]]<cutoff<=issue,'strict bank availability')
        check(dt(row['maximum_nwp_nominal_time'])==d-timedelta(hours=25)<issue,'nominal NWP availability')
    schedule=csvread(directory/'schedules.csv');check(len(schedule)==len(selected_days)*4*24,'all hourly plans')
    for n,row in enumerate(schedule):
        d,m,h=n//96,(n//24)%4,n%24;endpoint=times[expected_positions[d,h]]
        check(row['day']==selected_days[d] and row['method']==methods[m] and dt(row['endpoint_time'])==endpoint and dt(row['interval_start'])==endpoint-timedelta(hours=1),'schedule identity')
        check(float(row['production_m3'])==q[d,m,h] and float(row['demand_m3'])==120 and float(row['tariff_eur_kwh'])==prices[h],'schedule units')
        check(abs(float(row['inventory_end_m3'])-(2000+math.fsum(float(v)-120 for v in q[d,m,:h+1])))<1e-8,'schedule stock')
    mask=csvread(directory/'evaluation-membership.csv');daily=csvread(directory/'daily-outcomes.csv')
    day_lookup={d:i for i,d in enumerate(selected_days)};primary_days=[];weather_days=[]
    for row,day in zip(mask,selected_days):
        indices=days[day];inside=all(i in membership for i in indices);known=all(math.isfinite(satellite[i]) for i in indices)
        if inside:weather_days.append(day)
        if inside and known:primary_days.append(day)
        reasons=[]
        if not inside:reasons.append('partial_original_period')
        if not known:reasons.append('missing_satellite_endpoint')
        check(row['day']==day and flag(row['primary'])==(inside and known) and flag(row['weather_sensitivity'])==inside,'whole day score masks')
        check(int(row['original_hours'])==sum(i in membership for i in indices) and int(row['available_satellite_hours'])==sum(math.isfinite(satellite[i]) for i in indices) and row['exclusion_reasons']=='|'.join(reasons),'excluded days retained')
    check(len({(r['day'],r['method'],r['reference']) for r in daily})==len(daily),'daily rows unique')
    for row in daily:
        d=day_lookup[row['day']];m=methods.index(row['method']);indices=expected_positions[d]
        truth=weather[indices] if row['reference']=='weather' else satellite[indices]
        check(np.isfinite(truth).all(),'no invented missing outcome')
        solar=np.minimum(1700.,1.7*np.maximum(truth,0.));power=3.4*q[d,m];grid=np.maximum(power-solar,0.);basegrid=np.maximum(3.4*q[d,1]-solar,0.)
        values=dict(cost_eur=math.fsum(float(a*b) for a,b in zip(grid,prices)),grid_kwh=math.fsum(grid),unused_pv_kwh=math.fsum(np.maximum(solar-power,0.)),peak_grid_kw=float(grid.max()),cost_regret_eur=math.fsum(float(a*b) for a,b in zip(grid,prices))-math.fsum(float(a*b) for a,b in zip(basegrid,prices)),grid_regret_kwh=math.fsum(grid)-math.fsum(basegrid))
        for k,v in values.items():check(abs(float(row[k])-v)<1e-8,'realized ledger '+k)
        check(abs(values['grid_kwh']-(math.fsum(power)-math.fsum(solar)+values['unused_pv_kwh']))<1e-8,'realized exact allocation identity')
        check(abs(values['grid_kwh']-(9792-math.fsum(solar)+values['unused_pv_kwh']))<4e-6,'realized ideal-energy identity within water tolerance')
        check(flag(row['primary'])==(row['day'] in primary_days) and flag(row['weather_sensitivity'])==(row['day'] in weather_days and row['reference']=='weather'),'daily masks')
    expected_daily=sum(4*(1+int(np.isfinite(satellite[indices]).all())) for indices in expected_positions)
    check(len(daily)==expected_daily,'every available full horizon outcome retained')
    for subset in ('primary','weather_sensitivity'):
        groups={}
        for row in daily:
            if flag(row[subset]):groups.setdefault(row['method']+'/'+row['reference'],[]).append(row)
        expected=report['outcomes'][stage][subset];check(set(groups)==set(expected),'all aggregate groups')
        for key,rows in groups.items():
            item=expected[key]
            for field in ('cost_eur','grid_kwh','unused_pv_kwh','peak_grid_kw','cost_regret_eur','grid_regret_kwh'):
                compare_stats(stats([float(r[field]) for r in rows]),item[field],'aggregate '+key+'/'+field)
            regret=[float(r['cost_regret_eur']) for r in rows]
            check(item['days']==len(rows) and item['worse_days']==sum(v>0 for v in regret) and item['better_days']==sum(v<0 for v in regret) and item['equal_days']==sum(v==0 for v in regret),'every day count')
    # Gate magnitudes reconstructed independently. Preserve stated binary64 signs.
    for method in ('coherent','shuffled','tariff_context'):
        gate=report['gates'][stage][method];risk=[];axes=[]
        for reference_name in references:
            a=[r for r in daily if flag(r['primary']) and r['method']==method and r['reference']==reference_name]
            b=[r for r in daily if flag(r['primary']) and r['method']=='raw_point' and r['reference']==reference_name]
            check([r['day'] for r in a]==[r['day'] for r in b]==primary_days,'paired gate cohorts')
            losses=[float(x['cost_eur'])-float(y['cost_eur']) for x,y in zip(a,b)]
            v=tail(losses);saved=next(r for r in gate['risk'] if r['reference']==reference_name)
            check(abs(v-saved['cvar90_daily_regret'])<1e-8,'risk gate magnitude')
            check(saved['nonregressing']==(saved['cvar90_daily_regret']<=0) and saved['strict_gain']==(saved['cvar90_daily_regret']<0),'literal risk signs')
            risk.append(saved)
            for field in ('cost_eur','grid_kwh'):
                sa=stats([float(r[field]) for r in a]);sb=stats([float(r[field]) for r in b])
                for statistic in ('mean','cvar90'):
                    saved=next(r for r in gate['axes'] if r['reference']==reference_name and r['metric']==field and r['statistic']==statistic)
                    check(abs(saved['difference']-(sa[statistic]-sb[statistic]))<1e-8,'axis magnitude')
                    check(saved['nonregressing']==(saved['difference']<=0) and saved['strict_gain']==(saved['difference']<0) and saved['below_resolution']==(abs(saved['difference'])<1e-5),'literal axis signs')
                    axes.append(saved)
            for field in ('cost_eur','grid_kwh'):
                coherent=[r for r in daily if flag(r['primary']) and r['method']=='coherent' and r['reference']==reference_name]
                shuffled=[r for r in daily if flag(r['primary']) and r['method']=='shuffled' and r['reference']==reference_name]
                compare_stats(stats([float(x[field])-float(y[field]) for x,y in zip(coherent,shuffled)]),report['coherent_minus_shuffled'][stage][reference_name][field],'coherent minus shuffled')
        check(gate['risk_only_pass']==(all(r['nonregressing'] for r in risk) and any(r['strict_gain'] for r in risk)),'risk gate')
        check(gate['all_axis_pass']==(all(r['nonregressing'] for r in axes) and any(r['strict_gain'] for r in axes)),'eight-axis gate')
    check(report['splits'][stage]['primary_days']==len(primary_days) and report['splits'][stage]['weather_sensitivity_days']==len(weather_days),'reported cohorts')
    changed_plans=np.max(abs(q[:,2]-q[:,3]),axis=1)
    summaries[stage]=dict(planned_days=len(selected_days),primary_days=len(primary_days),weather_sensitivity_days=len(weather_days),scenario_values=scenarios.size,daily_outcomes=len(daily),coherent_vs_shuffled_different_above_1e_6_m3=int(np.sum(changed_plans>1e-6)),gates={m:{k:report['gates'][stage][m][k] for k in ('risk_only_pass','all_axis_pass')} for m in ('coherent','shuffled')})
for method in ('coherent','shuffled'):
    check(report['experiment_all_axis_gate'][method]==all(report['gates'][s][method]['all_axis_pass'] for s in ('validation','test')),'whole experiment gate')
for p,h in identity.items():check(sha(p)==h,'final hash '+str(p))
with (HERE/'water-exact.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=water_records[0]);writer.writeheader();writer.writerows(water_records)
result=dict(status='PASS',checks=checks,all_source_endpoints=len(source),reconstructed_scenario_values=total_scenario_values,water_plans=len(water_records),maximum_scenario_cost_error_eur=max_scenario_cost_error,maximum_exact_water_violation_m3_fraction=str(max_water_residual),maximum_exact_water_violation_m3=float(max_water_residual),plans_with_exact_nonzero_residual=exact_nonzero_water_plans,immutable_files=len(identity),splits=summaries,
    limits=['Retained bank NPZ timestamp member has object dtype and was not unpickled. All bank times reconstructed from numerical positions and pinned target CSV.','No fitting or solver replay. Recomputed issued data, actions and outcome arithmetic, not independent proof of LP global optimality.','Exact binary64 water residuals retained alongside the frozen1e-6 m³ tolerance. Tiny representation residuals are not plant failures.','Gate magnitudes independently checked within1e-8. Literal binary64 signs verified from saved values. Differences below declared reporting resolution remain flagged.','Illustrative constant-efficiency plant with unlimited grid backup. No curtailment, physical operating authorization or field-savings inference.','Already-inspected references and test are retrospective. Nominal timestamps do not authenticate historical publication availability.'],
    code_sha256=sha(Path(__file__)),fixtures_sha256=sha(HERE/'analytical-fixtures.json'),protocol_sha256=sha(EXP/'PROTOCOL.md'),report_sha256=sha(OUT/'report.json'),completed_at_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-started)
(HERE/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps(result,allow_nan=False))
