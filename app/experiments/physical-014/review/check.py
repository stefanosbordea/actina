"""Independent binary64 interface, water, outcome and fixed-gate reconstruction."""
import csv
from datetime import datetime, timedelta, timezone
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import time
import numpy as np

HERE = Path(__file__).resolve().parent
EXP, ROOT = HERE.parent, HERE.parent.parents[2]
OUT, OLD, EVENT = EXP / 'result', EXP.parent / 'physical-012/result', EXP.parent / 'f1-013/result'
CONTROLS = ('tariff_context', 'raw_point', 'recency_coherent', 'recency_shuffled', 'conditional_coherent', 'conditional_shuffled')
CALLS = ('raw_nwp', 'recency_robust', 'recency_pooled', 'conditional_robust', 'conditional_pooled')
CANDIDATES = tuple('mapped_' + name for name in CALLS[1:])
METHODS = CONTROLS + CANDIDATES
PRICE = [.101 if 10 <= h < 17 else .183 if 17 <= h < 23 else .130 for h in range(24)]
started, checks, max_difference, maximum_water = time.perf_counter(), 0, 0., F()


def check(ok, label):
    global checks
    checks += 1
    if not ok:
        raise AssertionError(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def rows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def dt(value):
    return datetime.fromisoformat(value)


def flag(value):
    return value in (True, 'True', '1', 1)


def near(a, b, label, tolerance=1e-9):
    global max_difference
    error = abs(float(a) - float(b))
    max_difference = max(max_difference, error)
    check(error <= tolerance, label)


def solar(values):
    return [min(1700., 1.7 * max(float(v), 0.)) for v in values]


def accounting(q, radiation):
    pv = solar(radiation)
    power = [3.4 * float(v) for v in q]
    grid = [max(a - b, 0.) for a, b in zip(power, pv)]
    return dict(cost_eur=math.fsum(a * b for a, b in zip(grid, PRICE)), grid_kwh=math.fsum(grid),
                unused_pv_kwh=math.fsum(max(b - a, 0.) for a, b in zip(power, pv)), peak_grid_kw=max(grid))


def stats(values):
    v = list(map(float, values))
    ordered = sorted(v, reverse=True)
    count, remainder = divmod(len(v), 10)
    tail = (10 * math.fsum(ordered[:count]) + remainder * ordered[count]) / len(v)
    return dict(mean=math.fsum(v) / len(v), cvar90=tail, minimum=min(v), maximum=max(v))


def verify_stats(expected, saved, label):
    for key, value in expected.items():
        near(value, saved[key], label + '/' + key)


def event_metrics(actual, predicted):
    truth, call = [v > 600 for v in actual], [v > 600 for v in predicted]
    tp = sum(a and b for a, b in zip(truth, call))
    fp = sum(not a and b for a, b in zip(truth, call))
    fn = sum(a and not b for a, b in zip(truth, call))
    result = dict(hours=len(truth), tp=tp, fp=fp, fn=fn, tn=len(truth)-tp-fp-fn, positive_calls=tp+fp)
    for name, numerator, denominator in [('precision',tp,tp+fp),('recall',tp,tp+fn),('f1',2*tp,2*tp+fp+fn)]:
        value = F(numerator, denominator) if denominator else None
        result[name] = None if value is None else dict(numerator=value.numerator, denominator=value.denominator, value=float(value))
    result['mae_w_m2'] = math.fsum(abs(a-b) for a,b in zip(actual,predicted))/len(actual)
    result['rmse_w_m2'] = math.sqrt(math.fsum((a-b)**2 for a,b in zip(actual,predicted))/len(actual))
    return result


pins = load(EXP/'inputs.json')['files_sha256']
for name,digest in pins.items():
    check(sha(ROOT/name)==digest,'input hash '+name)
for name,digest in load(OUT/'outputs.json').items():
    check(sha(OUT/name)==digest,'output hash '+name)
freeze = load(OUT/'planning-freeze.json')
for name,digest in freeze['files_sha256'].items():
    check(sha(OUT/name)==digest,'planning freeze '+name)
receipt = load(OUT/'execution-receipt.json')
check(receipt['status']=='COMPLETE' and receipt['exit_code']==0 and receipt['elapsed_seconds']<=1800,'completed within budget')
check(receipt['input_lock_sha256']==sha(EXP/'inputs.json') and receipt['protocol_sha256']==sha(EXP/'PROTOCOL.md'),'execution hashes')
check(dt(freeze['frozen_at_utc']) < dt(receipt['finished_at_utc']),'freeze before completion')
report = load(OUT/'report.json')
check(report['primary_method']=='mapped_conditional_robust' and tuple(report['methods'])==METHODS,'fixed primary and all methods')
source = rows(ROOT/'app/experiments/f1-008/result/features.csv')
origins=[dt(r['feature_time']) for r in source]
targets=[t+timedelta(hours=24) for t in origins]
nwp=np.asarray([float(r['nwp_day2_radiation']) for r in source])
weather_rows=rows(ROOT/'app/experiments/f1-006/result/feature-targets.csv')
joined=rows(ROOT/'app/experiments/reference-training-001/result/joined-reference.csv')
check(len(source)==len(weather_rows)==len(joined)==17832,'source row identity')
weather,satellite=[],[]
for i,(a,b) in enumerate(zip(weather_rows,joined)):
    check(all(dt(row['target_time'])==targets[i] and dt(row['feature_time'])==origins[i] for row in (a,b)),'reference endpoint and feature identity')
    utc=targets[i].replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc)
    check(dt(b['valid_time_utc'])==utc and dt(b['interval_start_utc'])==utc-timedelta(hours=1),'reference UTC interval')
    w,s=float(a['actual']),float(b['satellite_w_m2']) if b['satellite_w_m2'] else np.nan
    check(w==float(b['weather_actual_w_m2']) and int(b['is_missing'])==int(np.isnan(s)),'reference values and missing flag')
    weather.append(w)
    satellite.append(s)
weather,satellite=np.asarray(weather),np.asarray(satellite)
solves=[json.loads(line) for line in (OUT/'solver-records.jsonl').read_text().splitlines()]
solver={(r['stage'],r['day'],r['method']):r for r in solves}
check(len(solves)==len(solver)==299*5,'all raw reproductions and candidate solve records')
plan_count,identity_count,changed_inputs,changed_plans=0,0,0,0
period_gates={}
for stage,days,hours,common_days,common_hours in [('validation',150,3566,139,3419),('test',149,3567,144,3517)]:
    folder=OUT/stage
    with np.load(folder/'plans.npz',allow_pickle=False) as archive:
        arrays={k:archive[k] for k in archive.files}
    with np.load(OLD/stage/'plans.npz',allow_pickle=False) as archive:
        old={k:archive[k] for k in archive.files}
    with np.load(EVENT/stage/'calls.npz',allow_pickle=False) as archive:
        event={k:archive[k] for k in archive.files}
    q,raw,mapped,positions=arrays['production'],arrays['raw_forecast_ghi'],arrays['mapped_forecast_ghi'],arrays['target_positions']
    check(q.shape==(days,10,24) and mapped.shape==(days,4,24) and positions.shape==(days,24),'all plan dimensions')
    check(tuple(arrays['methods'])==METHODS and tuple(arrays['call_methods'])==CALLS,'plan method identities')
    check(np.array_equal(positions,old['target_positions']) and np.array_equal(positions,event['target_positions']),'target identity across source experiments')
    check(np.array_equal(arrays['calls'],event['calls']) and np.array_equal(raw,nwp[positions]),'raw GHI and exact calls')
    check(q[:,:6].tobytes()==old['production'].tobytes(),'all six archived controls unchanged bitwise')
    check(np.array_equal(mapped>600,event['calls'][:,1:]),'all 013 bits preserved by binary64 interface')
    metadata=rows(folder/'plan-metadata.csv')
    check(metadata==rows(OLD/stage/'plan-metadata.csv'),'source metadata unchanged')
    water_audits=load(folder/'water-audits.json')
    check(len(water_audits)==days*10,'every exact water audit')
    reproductions=rows(folder/'raw-reproduction.csv')
    check(len(reproductions)==days and all(float(r['maximum_difference_m3'])<=1e-6 for r in reproductions),'all 299 declared raw reproduction tolerances')
    for d in range(days):
        day=targets[positions[d,0]]
        check(metadata[d]['day']==str(day.date()) and [targets[i] for i in positions[d]]==[day+timedelta(hours=h) for h in range(24)],'complete forecast day')
        cutoff=dt('2025-12-04' if stage=='validation' else '2026-05-02')
        check(dt(metadata[d]['issue_time'])==day-timedelta(days=1) and dt(metadata[d]['maximum_selected_source_time'])<cutoff,'source clocks and frozen cutoff')
        for c,method in enumerate(CANDIDATES):
            expected=np.asarray([float(value) if bool(value>600)==bool(call) else math.nextafter(600.,math.inf) if call else 600.
                                 for value,call in zip(raw[d],event['calls'][d,c+1])])
            check(mapped[d,c].tobytes()==expected.tobytes(),'nearest binary64 class-consistent value')
            check(np.array_equal(arrays['mapped_pv'][d,c],solar(expected)),'mapped PV reconstruction')
            identity=expected.tobytes()==raw[d].tobytes()
            record=solver[stage,str(day.date()),method]
            if identity:
                check(q[d,6+c].tobytes()==q[d,1].tobytes() and record['status']=='EXACT_RAW_INPUT_IDENTITY','unchanged input copies exact raw plan')
                identity_count+=1
            else:
                changed_inputs+=1
                changed_plans+=int(q[d,6+c].tobytes()!=q[d,1].tobytes())
                value=accounting(q[d,6+c],expected)['cost_eur']
                near(value,record['final_direct_objective'],'new plan direct objective')
                check(all(r['status']==0 and r['success'] for r in record['solves']),'successful changed-input LP stages')
                near(sum(abs(float(v)-120) for v in q[d,6+c]),record['L1_distance'],'point-plan L1 distance')
                check(value<=record['primary_optimum']+(1e-5+1e-9 if record['anchor_returned'] else 1e-7+1e-6),'preserved action floor or primary cap')
        raw_record=solver[stage,str(day.date()),'raw_point_reproduction']
        check(all(r['status']==0 and r['success'] for r in raw_record['solves']),'successful raw reproduction LP stages')
        near(accounting(q[d,1],raw[d])['cost_eur'],raw_record['final_direct_objective'],'raw objective replay',1e-6)
        for m,method in enumerate(METHODS):
            audit=water_audits[d*10+m]
            check(audit['day']==str(day.date()) and audit['method']==method,'exact water audit identity')
            values=[F.from_float(float(v)) for v in q[d,m]]
            stocks=[F(2000)]
            for value in values:
                stocks.append(stocks[-1]+value-120)
            errors=dict(production_below_zero=max(F(),-min(values)),production_above_capacity=max(F(),max(values)-500),
                        stock_below_reserve=max(F(),800-min(stocks)),stock_above_capacity=max(F(),max(stocks)-4000),terminal_error=abs(stocks[-1]-2000),water_error=abs(sum(values)-2880))
            check(audit['exact']['residuals']=={k:str(v) for k,v in errors.items()},'exact rational water residuals')
            check(audit['exact']['maximum_residual']==str(max(errors.values())),'maximum exact residual')
            check(F(audit['exact']['total_water_m3'])==sum(values) and F(audit['exact']['nominal_energy_kwh'])==F(17,5)*sum(values),'exact water and nominal energy')
            maximum_water=max(maximum_water,max(errors.values()))
            check(max(errors.values())<=F.from_float(1e-6),'water service within frozen numerical tolerance')
            plan_count+=1
    interface=rows(folder/'interface.csv')
    check(len(interface)==days*4*24,'every projected hourly value')
    for i,row in enumerate(interface):
        d,c,h=i//96,(i//24)%4,i%24
        check(row['day']==metadata[d]['day'] and row['method']==CANDIDATES[c] and int(row['source_position'])==positions[d,h],'interface IDs')
        check(row['raw_ghi_hex']==float(raw[d,h]).hex() and row['mapped_ghi_hex']==float(mapped[d,c,h]).hex(),'serialized exact forecast bits')
        check(flag(row['corrected_call'])==bool(event['calls'][d,c+1,h]),'interface event bit')
    schedules=rows(folder/'schedules.csv')
    check(len(schedules)==days*10*24,'every hourly water schedule')
    for i,row in enumerate(schedules):
        d,m,h=i//240,(i//24)%10,i%24
        check(row['method']==METHODS[m] and int(row['source_position'])==positions[d,h] and dt(row['target_time'])==targets[positions[d,h]],'schedule endpoint identity')
        check(float(row['production_m3'])==q[d,m,h] and float(row['demand_m3'])==120 and float(row['tariff_eur_kwh'])==PRICE[h],'schedule units and flow')
        near(float(row['inventory_end_m3']),2000+math.fsum(float(v)-120 for v in q[d,m,:h+1]),'schedule inventory')
    split=rows(ROOT/'eval'/('cv_predictions.csv' if stage=='validation' else 'test_predictions.csv'))
    lookup={str(t):i for i,t in enumerate(origins)}
    selected=[lookup[row['time']] for row in split]
    check(len(selected)==len(set(selected))==hours,'original hour membership')
    selection=set(selected)
    mask=rows(folder/'evaluation-membership.csv')
    check(mask==rows(OLD/stage/'evaluation-membership.csv'),'unchanged original physical exclusion ledger')
    primary,weather_days=[],[]
    for row,block in zip(mask,positions):
        inside=all(int(i) in selection for i in block)
        available=bool(np.isfinite(satellite[block]).all())
        check(flag(row['primary'])==(inside and available) and flag(row['weather_sensitivity'])==inside,'independent physical cohort eligibility')
        if inside:
            weather_days.append(row['day'])
        if inside and available:
            primary.append(row['day'])
    check(len(primary)==common_days and len(weather_days)==148,'cohort counts')
    daily=rows(folder/'daily-outcomes.csv')
    days_index={row['day']:i for i,row in enumerate(metadata)}
    by_key={(r['day'],r['method'],r['reference']):r for r in daily}
    expected_keys={(metadata[d]['day'],method,reference) for d in range(days) for method in METHODS for reference in ('weather','satellite') if reference=='weather' or np.isfinite(satellite[positions[d]]).all()}
    check(len(by_key)==len(daily) and set(by_key)==expected_keys,'every available daily outcome with no satellite imputation')
    for row in daily:
        d,m=days_index[row['day']],METHODS.index(row['method'])
        actual=weather[positions[d]] if row['reference']=='weather' else satellite[positions[d]]
        expected=accounting(q[d,m],actual)
        baseline=accounting(q[d,1],actual)
        expected.update(cost_regret_eur=expected['cost_eur']-baseline['cost_eur'],grid_regret_kwh=expected['grid_kwh']-baseline['grid_kwh'])
        for name,value in expected.items():
            near(value,row[name],'daily '+name)
        near(float(row['grid_kwh']),3.4*math.fsum(q[d,m])-math.fsum(solar(actual))+float(row['unused_pv_kwh']),'daily energy balance')
        check(flag(row['primary'])==(row['day'] in primary),'daily paired primary mask')
    archived=rows(OLD/stage/'daily-outcomes.csv')
    for before in archived:
        now=by_key[before['day'],before['method'],before['reference']]
        for name,value in before.items():
            if name in ('day','method','reference','primary','weather_sensitivity'):
                check(now[name]==value,'archived daily identity')
            else:
                near(now[name],value,'archived daily control value',1e-9)
    for method in METHODS:
        for basis,reference,flagname in [('weather_common','weather','primary'),('satellite_common','satellite','primary'),('weather_full_days','weather','weather_sensitivity')]:
            group=[r for r in daily if r['method']==method and r['reference']==reference and flag(r[flagname])]
            for metric in ('cost_eur','grid_kwh','unused_pv_kwh','peak_grid_kw'):
                verify_stats(stats([r[metric] for r in group]),report['splits'][stage]['aggregates'][method][basis][metric],'aggregate')
    period_gates[stage]={}
    for method in CANDIDATES:
        period_gates[stage][method]={}
        for control in CONTROLS[1:]:
            saved=report['splits'][stage]['comparisons'][method][control]
            axes,risk=[],[]
            for reference in ('weather','satellite'):
                a=[r for r in daily if r['method']==method and r['reference']==reference and flag(r['primary'])]
                b=[r for r in daily if r['method']==control and r['reference']==reference and flag(r['primary'])]
                check([r['day'] for r in a]==[r['day'] for r in b],'paired daily identity')
                for metric in ('cost_eur','grid_kwh'):
                    left,right=np.asarray([float(r[metric]) for r in a]),np.asarray([float(r[metric]) for r in b])
                    delta=left-right
                    stored=saved['paired_differences'][reference][metric]
                    verify_stats(stats(delta),stored,'paired differences')
                    check([stored[name] for name in ('better','equal','worse','below_resolution')]==[int(np.count_nonzero(predicate)) for predicate in (delta<0,delta==0,delta>0,abs(delta)<1e-5)],'paired sign and reporting counts')
                    for statistic in ('mean','cvar90'):
                        row=next(r for r in saved['axes'] if r['reference']==reference and r['metric']==metric and r['statistic']==statistic)
                        near(row['candidate'],stats(left)[statistic],'candidate axis')
                        near(row['control'],stats(right)[statistic],'control axis')
                        check(row['difference']==row['candidate']-row['control'],'stored binary64 axis subtraction')
                        check(row['nonregressing']==(row['difference']<=0) and row['strict_gain']==(row['difference']<0) and row['below_resolution']==(abs(row['difference'])<1e-5),'axis signs without tolerance alteration')
                        axes.append(row)
                    if metric=='cost_eur':
                        row=next(r for r in saved['risk'] if r['reference']==reference)
                        near(row['cvar90_daily_regret'],stats(delta)['cvar90'],'daily regret CVaR')
                        check(row['nonregressing']==(row['cvar90_daily_regret']<=0) and row['strict_gain']==(row['cvar90_daily_regret']<0),'risk signs')
                        risk.append(row)
            gates=dict(all_axis_pass=all(r['nonregressing'] for r in axes) and any(r['strict_gain'] for r in axes),risk_only_pass=all(r['nonregressing'] for r in risk) and any(r['strict_gain'] for r in risk))
            check(all(saved[k]==v for k,v in gates.items()),'paired gates')
            period_gates[stage][method][control]=gates
    location={int(i):(d,h) for d,block in enumerate(positions) for h,i in enumerate(block)}
    forecasts=dict(original=[float(r['predicted']) for r in split],persistence=[float(r['baseline']) for r in split],raw_nwp=[float(raw[location[i]]) for i in selected])
    for c,method in enumerate(CANDIDATES):
        forecasts[method]=[float(mapped[location[i][0],c,location[i][1]]) for i in selected]
    available=[j for j,i in enumerate(selected) if np.isfinite(satellite[i])]
    check(len(available)==common_hours,'event common-hour mask')
    for basis,reference,ids in [('weather_full',weather,list(range(hours))),('weather_common',weather,available),('satellite_common',satellite,available)]:
        for method,values in forecasts.items():
            expected=event_metrics([reference[selected[j]] for j in ids],[values[j] for j in ids])
            saved=report['splits'][stage]['forecast_diagnostics'][basis][method]
            for key,value in expected.items():
                if key in ('mae_w_m2','rmse_w_m2'):
                    near(value,saved[key],'continuous forecast error')
                else:
                    check(value==saved[key],'exact original-hour event metric')
expected_gates={method:dict(physical_upgrade=all(period_gates[s][method][c][gate] for s in ('validation','test') for c in CONTROLS[1:] for gate in ('all_axis_pass','risk_only_pass')),
    raw_control_both_periods=all(period_gates[s][method]['raw_point'][gate] for s in ('validation','test') for gate in ('all_axis_pass','risk_only_pass'))) for method in CANDIDATES}
check(report['gates']==expected_gates,'complete physical admission gates')
for name,digest in pins.items():
    check(sha(ROOT/name)==digest,'final source identity '+name)
print(json.dumps(dict(status='PASS',checks=checks,water_plans=plan_count,candidate_raw_input_identities=identity_count,changed_candidate_inputs=changed_inputs,changed_candidate_plans=changed_plans,
    maximum_exact_water_residual_m3=str(maximum_water),maximum_independent_arithmetic_difference=max_difference,gates=expected_gates,
    input_lock_sha256=sha(EXP/'inputs.json'),planning_freeze_sha256=sha(OUT/'planning-freeze.json'),result_manifest_sha256=sha(OUT/'outputs.json'),checker_sha256=sha(Path(__file__)),
    elapsed_seconds=time.perf_counter()-started,scope='Independent mapping, exact water, archived control identity, all outcomes and pairwise gates, and all original-hour forecast metrics. No production helper imported.',
    limits=['No LP re-solving or independent optimizer optimality certificate. Solver statuses and objective caps replayed from retained source-pinned records.', 'Tiny binary64 signs are preserved with numerical reporting flags and do not establish meaningful physical gains.']),indent=2))
