"""Reconstruct gaps and independently solve explicit-inventory perfect-information LPs."""
import csv
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import time
import warnings
import numpy as np
from scipy.optimize import linprog,OptimizeWarning
HERE=Path(__file__).resolve().parent
HEAD=HERE.parent
EXP=HEAD.parent
ROOT=EXP.parents[2]
OUT=HEAD/'result'
checks=0
start=time.perf_counter()
def check(ok,label):
    global checks
    checks+=1
    if not ok:raise AssertionError(label)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def rows(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def dt(s):return datetime.fromisoformat(s)
def num(v):return float(v) if v else math.nan
prices=np.array([.101 if 10<=h<17 else .183 if 17<=h<23 else .130 for h in range(24)])
report=load(OUT/'report.json');outputs=load(OUT/'outputs.json')
identities={ROOT/p:h for p,h in report['inputs_sha256'].items()}|{OUT/p:h for p,h in outputs.items()}
for p,h in identities.items():check(sha(p)==h,'initial input identity '+str(p))
weather=rows(ROOT/'app/experiments/f1-006/result/feature-targets.csv')
satellite=rows(ROOT/'app/experiments/reference-training-001/result/joined-reference.csv')
check(len(weather)==len(satellite)==17832,'source count')
for w,s in zip(weather,satellite):
    check(w['feature_time']==s['feature_time'] and dt(w['target_time'])==dt(s['target_time']) and num(w['actual'])==num(s['weather_actual_w_m2']),'reference identity')
origin={r['feature_time']:i for i,r in enumerate(weather)}
source_days={}
for i,r in enumerate(weather):source_days.setdefault(dt(r['target_time']).date().isoformat(),[]).append(i)
inputs={};expected_keys=set();plans={};primary={}
for split,filename in [('validation','cv_predictions.csv'),('test','test_predictions.csv')]:
    sample=rows(ROOT/'eval'/filename);membership={origin[r[next(iter(r))]] for r in sample}
    archive=np.load(EXP/f'result/{split}/plans.npz',allow_pickle=False)
    meta=rows(EXP/f'result/{split}/plan-metadata.csv')
    primary[split]=[]
    for d,m in enumerate(meta):
        day=m['day'];indices=source_days[day]
        check(np.array_equal(archive['target_positions'][d],indices),'saved day positions')
        if not all(i in membership for i in indices) or not all(math.isfinite(num(satellite[i]['satellite_w_m2'])) for i in indices):continue
        primary[split].append(day)
        plans[(split,day)]={name:archive['production'][d,j] for j,name in enumerate(archive['methods'].tolist())}
        for reference in ('weather','satellite'):
            ghi=[num(weather[i]['actual']) if reference=='weather' else num(satellite[i]['satellite_w_m2']) for i in indices]
            solar=np.array([min(1700.,1.7*max(v,0.)) for v in ghi])
            inputs[(split,day,reference)]=solar
            for objective in ('cost_eur','grid_kwh'):expected_keys.add((split,day,reference,objective))
# Different model structure: 24 production, 24 grid and 25 explicit inventory variables.
eq=np.zeros((24,73));rhs=np.full(24,-120.)
for h in range(24):eq[h,h]=-1;eq[h,48+h]=-1;eq[h,49+h]=1
ub=np.zeros((24,73))
for h in range(24):ub[h,h]=3.4;ub[h,24+h]=-1
variable_bounds=[(0.,500.)]*24+[(0.,None)]*24+[(2000.,2000.)]+[(800.,4000.)]*23+[(2000.,2000.)]
solutions={};independent={};max_objective_difference=0.;max_primal_error=0.;warnings_seen=set()
with (OUT/'oracle-solutions.jsonl').open() as f:
    for line in f:
        s=json.loads(line);key=tuple(s[k] for k in ('split','day','reference','objective'))
        check(key in expected_keys and key not in solutions,'oracle solution identity')
        solutions[key]=s;solar=inputs[key[:3]];q=np.array(s['production']);grid=np.maximum(3.4*q-solar,0.)
        weights=prices if key[3]=='cost_eur' else np.ones(24)
        inventory=np.r_[2000.,2000.+np.cumsum(q-120.)]
        direct=math.fsum(float(a*b) for a,b in zip(grid,weights))
        violations=[0.,float(-q.min()),float(q.max()-500),float(800-inventory.min()),float(inventory.max()-4000),abs(float(inventory[-1]-2000)),abs(math.fsum(q)-2880),abs(direct-s['minimum'])]
        check(q.shape==(24,) and s['status']==0 and max(violations)<=1e-6,'saved primal feasibility and own objective')
        check(np.max(abs(grid-np.array(s['grid'])))<1e-9 and np.max(abs(inventory-np.array(s['inventory'])))<1e-9,'saved grid and stock')
        check(abs(math.fsum(grid)-(9792-math.fsum(solar)+math.fsum(np.maximum(solar-3.4*q,0))))<=4e-6,'oracle energy conservation')
        objective=np.r_[np.zeros(24),weights,np.zeros(25)]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always',OptimizeWarning)
            solved=linprog(objective,A_ub=ub,b_ub=solar,A_eq=eq,b_eq=rhs,bounds=variable_bounds,method='highs-ipm',options=dict(threads=1,primal_feasibility_tolerance=1e-9,dual_feasibility_tolerance=1e-9,ipm_optimality_tolerance=1e-10))
        warnings_seen.update(str(w.message) for w in caught)
        check(solved.success and solved.status==0,'independent explicit-stock IPM optimum')
        error=abs(float(solved.fun)-s['minimum']);max_objective_difference=max(max_objective_difference,error)
        check(error<=1e-6,'independent minimum agrees')
        max_primal_error=max(max_primal_error,max(violations));independent[key]=float(solved.fun)
check(set(solutions)==expected_keys and len(solutions)==1132,'all separate daily optima')
gaps=rows(OUT/'daily-gaps.csv');grouped={};seen=set();negative=[];max_gap_replay_error=0.
for r in gaps:
    key=tuple(r[k] for k in ('split','day','reference','objective'));full=key+(r['method'],)
    check(full not in seen and key in solutions,'unique daily gap');seen.add(full)
    q=plans[key[:2]][r['method']];solar=inputs[key[:3]];weights=prices if key[3]=='cost_eur' else np.ones(24)
    observed=math.fsum(float(max(3.4*float(v)-float(p),0)*w) for v,p,w in zip(q,solar,weights))
    gap=observed-solutions[key]['minimum'];error=abs(gap-float(r['gap']));max_gap_replay_error=max(max_gap_replay_error,error)
    check(abs(observed-float(r['observed']))<=1e-8 and float(r['perfect_information_bound'])==solutions[key]['minimum'] and error<=1e-8,'matching native-objective gap')
    check(gap>=-1e-6,'plan above bound within numeric tolerance')
    if float(r['gap'])<0:negative.append(float(r['gap']))
    grouped.setdefault((r['split'],r['reference'],r['objective'],r['method']),[]).append(r)
check(len(gaps)==4528 and len(seen)==4*len(expected_keys),'all plan/objective gaps')
check(len(grouped)==len(report['summaries'])==32,'all native summaries')
for summary in report['summaries']:
    key=tuple(summary[k] for k in ('split','reference','objective','method'));group=grouped[key]
    check([r['day'] for r in group]==primary[key[0]],'same full cohort')
    values=[float(r['gap']) for r in group]
    rebuilt=dict(days=len(group),mean_observed=math.fsum(float(r['observed']) for r in group)/len(group),mean_bound=math.fsum(float(r['perfect_information_bound']) for r in group)/len(group),mean_gap=math.fsum(values)/len(group),minimum_gap=min(values),maximum_gap=max(values))
    for name,value in rebuilt.items():check(abs(value-summary[name])<1e-8,'summary '+name)
# Cross-objective diagnostics make the oracle distinction visible.
cost_penalty=[];energy_penalty=[];different=0
for base,solar in inputs.items():
    cost_q=np.array(solutions[base+('cost_eur',)]['production']);energy_q=np.array(solutions[base+('grid_kwh',)]['production'])
    different+=bool(np.max(abs(cost_q-energy_q))>1e-6)
    cost_penalty.append(float(np.dot(np.maximum(3.4*energy_q-solar,0),prices))-solutions[base+('cost_eur',)]['minimum'])
    energy_penalty.append(float(np.maximum(3.4*cost_q-solar,0).sum())-solutions[base+('grid_kwh',)]['minimum'])
check(min(cost_penalty)>=-1e-6 and min(energy_penalty)>=-1e-6,'separate objectives do not substitute')
for p,h in identities.items():check(sha(p)==h,'final identity '+str(p))
result=dict(status='PASS',checks=checks,primary_days={k:len(v) for k,v in primary.items()},independent_explicit_inventory_ipm_solves=len(solutions),native_daily_gaps=len(gaps),summaries_checked=32,maximum_independent_optimum_difference=max_objective_difference,maximum_reconstructed_saved_primal_error=max_primal_error,maximum_gap_replay_error=max_gap_replay_error,signed_negative_gaps_retained=len(negative),minimum_saved_signed_gap=min(negative) if negative else 0,
    separate_oracles=dict(reference_days=len(inputs),different_plans_above_1e_6_m3=different,energy_oracle_cost_penalty_max_eur=max(cost_penalty),cost_oracle_energy_penalty_max_kwh=max(energy_penalty)),
    immutable_files=len(identities),solver='HiGHS interior point, explicit inventory variables, one thread',solver_warnings=sorted(warnings_seen),
    conclusion='Saved bounds and gaps are numerically verified in their own units. They use complete realized references and cannot be issued forecasts or guaranteed attainable gains. Cost-optimal and energy-optimal schedules remain separate.',
    source_report_sha256=sha(OUT/'report.json'),code_sha256=sha(Path(__file__)),completed_at_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-start)
(HERE/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps(result,allow_nan=False))
