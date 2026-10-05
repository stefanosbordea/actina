"""Fixed physical-value experiment with plans frozen before outcome masks."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import resource
import sys
import time
import numpy as np
import pandas as pd
import scipy
from optimizer import pv, cvar, evaluate, solve, audit, shuffled, PRICE, SEC, PRIMARY_TOL, AUDIT_TOL

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
METHODS=('tariff_context','raw_point','coherent','shuffled')
REFERENCES=('weather','satellite')
FAMILIES=('coherent','shuffled')


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return pd.read_csv(p,float_precision='round_trip')
def save(p,value):p.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def now():return datetime.now(timezone.utc).isoformat()


def bank_for(target,nwp,weather,satellite,cutoff):
    days=sorted(set(t.date() for t in target))
    records=[];eligible=[]
    for day in days:
        positions=np.flatnonzero(np.array([t.date()==day for t in target]))
        before=bool(np.all(target[positions]<cutoff))
        complete=len(positions)==24 and list(target[positions].hour)==list(range(24))
        finite_weather=bool(np.isfinite(weather[positions]).all())
        finite_satellite=bool(np.isfinite(satellite[positions]).all())
        if before and complete and finite_weather and finite_satellite:eligible.append((day,positions))
        records.append(dict(day=str(day),first_endpoint=str(target[positions[0]]),last_endpoint=str(target[positions[-1]]),
            strictly_before_cutoff=before,complete_24=complete,weather_complete=finite_weather,satellite_complete=finite_satellite))
    if len(eligible)<64:raise ValueError('Fewer than64 complete paired historical days')
    chosen=eligible[-64:];ids={str(day) for day,positions in chosen}
    for record in records:record['selected']=record['day'] in ids
    positions=np.stack([position for day,position in chosen])
    if np.any(target[positions.reshape(-1)]>=cutoff):raise ValueError('Bank chronology violation')
    residual=np.stack((weather[positions]-nwp[positions],satellite[positions]-nwp[positions]))
    return residual,positions,records


def summary(values):
    values=np.asarray(values,dtype=float)
    if values.ndim!=1 or not len(values) or not np.isfinite(values).all():raise ValueError('Finite daily outcomes required')
    return dict(mean=float(values.mean()),cvar90=cvar(values),maximum=float(values.max()),minimum=float(values.min()))


def gates(daily,method):
    subset=daily.loc[daily.primary]
    risk=[];axes=[]
    for reference in REFERENCES:
        rows=subset.loc[(subset.reference==reference)&(subset.method==method)]
        control=subset.loc[(subset.reference==reference)&(subset.method=='raw_point')]
        if not np.array_equal(rows.day,control.day) or not len(rows):raise ValueError('Primary comparison membership')
        regrets=rows.cost_eur.to_numpy()-control.cost_eur.to_numpy()
        value=cvar(regrets)
        risk.append(dict(reference=reference,cvar90_daily_regret=value,nonregressing=bool(value<=0),strict_gain=bool(value<0),below_resolution=abs(value)<1e-5))
        for metric in ('cost_eur','grid_kwh'):
            a,b=summary(rows[metric]),summary(control[metric])
            for statistic in ('mean','cvar90'):
                difference=a[statistic]-b[statistic]
                axes.append(dict(reference=reference,metric=metric,statistic=statistic,candidate=a[statistic],control=b[statistic],difference=difference,
                    nonregressing=bool(difference<=0),strict_gain=bool(difference<0),below_resolution=abs(difference)<1e-5))
    return dict(risk_only_pass=all(v['nonregressing'] for v in risk) and any(v['strict_gain'] for v in risk),risk=risk,
        all_axis_pass=all(v['nonregressing'] for v in axes) and any(v['strict_gain'] for v in axes),axes=axes,
        caution='Strict numerical signs are reported separately from1e-5 native-unit reporting resolution. Numerical water checks are not exact physical certification.')


def main(out):
    start,cpu=time.perf_counter(),time.process_time()
    pins=json.loads((HERE/'inputs.json').read_text())
    for name,digest in pins.items():
        if sha(ROOT/name)!=digest:raise ValueError('Changed frozen input: '+name)
    if HERE not in out.parents:raise ValueError('Output outside experiment')
    out.mkdir(exist_ok=False)
    data=read(ROOT/'app/experiments/f1-008/result/features.csv')
    target_file=read(ROOT/'app/experiments/f1-006/result/feature-targets.csv')
    ref=read(ROOT/'app/experiments/reference-training-001/result/joined-reference.csv')
    if len(data)!=17832 or not data.feature_time.is_unique or any(not data.feature_time.equals(v.feature_time) for v in (target_file,ref)):raise ValueError('Source membership')
    origin=pd.DatetimeIndex(data.feature_time);target=pd.DatetimeIndex(target_file.target_time)
    if not np.all(target==origin+pd.Timedelta(hours=24)) or not np.all(target[1:]-target[:-1]==pd.Timedelta(hours=1)):raise ValueError('Source chronology')
    if not np.array_equal(target,pd.DatetimeIndex(ref.target_time)) or not np.array_equal(target_file.actual,ref.weather_actual_w_m2):raise ValueError('Reference join')
    if not np.array_equal(target.tz_localize('Etc/GMT-3').tz_convert('UTC'),pd.DatetimeIndex(ref.valid_time_utc)):raise ValueError('UTC join')
    nwp=data.nwp_day2_radiation.to_numpy();weather=target_file.actual.to_numpy();satellite=ref.satellite_w_m2.to_numpy()
    if not np.isfinite(nwp).all() or not np.isfinite(weather).all() or np.isinf(satellite).any() or np.any(nwp<0) or np.any(weather<0) or np.any(satellite<0):raise ValueError('Source values')
    if not np.array_equal(np.isnan(satellite),ref.is_missing.astype(bool)):raise ValueError('Satellite missingness')
    spec=importlib.util.spec_from_file_location('tariff_context',ROOT/'app/model/scheduler.py')
    context=importlib.util.module_from_spec(spec);spec.loader.exec_module(context)
    report=dict(status='PLANNING',started_at_utc=now(),protocol_sha256=sha(HERE/'PROTOCOL.md'),input_sha256=pins,
        versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,pandas=pd.__version__),
        methods=list(METHODS),references=list(REFERENCES),scenario_families=list(FAMILIES),splits={},gates={},scope='Illustrative retrospective water/PV/grid scenario. No field savings or novelty claim.',
        total_plant_energy_kwh_per_day=9792,solver_threads=1,primary_objective_tolerance_eur=PRIMARY_TOL,additional_numerical_audit_tolerance=AUDIT_TOL)
    stage_cache={}
    log=(out/'solver-records.jsonl').open('x')
    for stage,filename in [('validation','cv_predictions.csv'),('test','test_predictions.csv')]:
        split=read(ROOT/'eval'/filename);names=split.iloc[:,0]
        positions=pd.Index(data.feature_time).get_indexer(names)
        if np.any(positions<0) or not names.is_unique or len(names)!={'validation':3566,'test':3567}[stage]:raise ValueError('Split membership')
        if not np.array_equal(weather[positions],split.actual):raise ValueError('Original truth identity')
        days=sorted(set(target[positions].normalize()))
        cutoff=days[0]-pd.Timedelta(days=1)
        residual,bank_positions,bank_records=bank_for(target,nwp,weather,satellite,cutoff)
        directory=out/stage;directory.mkdir()
        pd.DataFrame(bank_records).to_csv(directory/'bank-membership.csv',index=False)
        rng=np.random.default_rng(20261004)
        permutations=np.stack([rng.permutation(64) for _ in range(24)])
        changed=shuffled(residual,permutations)
        if not np.array_equal(np.sort(residual,axis=1),np.sort(changed,axis=1)):raise AssertionError('Changed marginal')
        np.savez_compressed(directory/'bank.npz',residuals=residual,permutations=permutations,source_positions=bank_positions,
            source_target_time=target[bank_positions.reshape(-1)].astype(str).to_numpy().reshape(64,24),
            weather=weather[bank_positions],satellite=satellite[bank_positions],nwp=nwp[bank_positions])
        plans=np.empty((len(days),4,24));raw_ghi=np.empty((len(days),24))
        scenarios=np.empty((len(days),2,2,64,24))
        replay_cost=np.empty((len(days),2,4,2,64));replay_grid=np.empty_like(replay_cost);replay_unused=np.empty_like(replay_cost)
        day_positions=[];metadata=[]
        for number,day in enumerate(days):
            indices=np.flatnonzero(target.normalize()==day)
            if len(indices)!=24 or list(target[indices].hour)!=list(range(24)):raise ValueError('Incomplete planning day')
            issue=day-pd.Timedelta(days=1)
            if np.any(target[indices]-pd.Timedelta(hours=48)>=issue) or np.any(target[bank_positions.reshape(-1)]>=issue):raise ValueError('Issued source violation')
            day_positions.append(indices)
            forecast=nwp[indices];raw_ghi[number]=forecast
            scenarios[number,0]=forecast[None,None,:]+residual
            scenarios[number,1]=forecast[None,None,:]+changed
            raw_solar=pv(forecast)
            q0,record=solve(raw_solar)
            plans[number,1]=q0
            record.update(stage=stage,day=str(day.date()),method='raw_point');log.write(json.dumps(record,allow_nan=False)+'\n')
            old=context.schedule_day(forecast,np.zeros(24),np.full(24,28.),tank_capacity=4000.,unit_capacity=500.,season='summer',forecast_temperature_c=28.)
            tariff_q=old['frame'].scheduled_m3.to_numpy()
            if not np.array_equal(old['frame'].price_eur_mwh.to_numpy()/1000,PRICE):raise AssertionError('Context tariff mismatch')
            plans[number,0]=tariff_q
            log.write(json.dumps(dict(stage=stage,day=str(day.date()),method='tariff_context',status=old['status'],water=audit(tariff_q)),allow_nan=False)+'\n')
            for family,name in enumerate(FAMILIES):
                q,record=solve(pv(scenarios[number,family]),q0)
                plans[number,2+family]=q
                record.update(stage=stage,day=str(day.date()),method=name);log.write(json.dumps(record,allow_nan=False)+'\n')
            for family in range(2):
                solar=pv(scenarios[number,family])
                for method in range(4):
                    evaluated=evaluate(plans[number,method],solar)
                    replay_cost[number,family,method]=evaluated['cost']
                    replay_grid[number,family,method]=evaluated['grid_energy']
                    replay_unused[number,family,method]=evaluated['unused_pv']
            if not np.allclose(replay_cost[number,0].mean(axis=-1),replay_cost[number,1].mean(axis=-1),rtol=0,atol=1e-9):raise AssertionError('Expected-cost shuffle invariance')
            metadata.append(dict(day=str(day.date()),issue_time=str(issue),issue_utc=issue.tz_localize('Etc/GMT-3').tz_convert('UTC').isoformat(),
                interval_start=str(day-pd.Timedelta(hours=1)),interval_end=str(day+pd.Timedelta(hours=23)),maximum_bank_source_time=str(target[bank_positions.reshape(-1)].max()),
                maximum_nwp_nominal_time=str(day-pd.Timedelta(hours=25)),minimum_endpoint_lead_hours=24,maximum_endpoint_lead_hours=47))
            if (number+1)%10==0:print('PLANNED',stage,number+1,'of',len(days),flush=True)
        log.flush()
        np.savez_compressed(directory/'plans.npz',production=plans,raw_forecast_ghi=raw_ghi,target_positions=np.stack(day_positions),methods=np.asarray(METHODS))
        np.savez_compressed(directory/'scenario-replay.npz',unclipped_ghi=scenarios,cost_eur=replay_cost,grid_kwh=replay_grid,unused_pv_kwh=replay_unused)
        pd.DataFrame(metadata).to_csv(directory/'plan-metadata.csv',index=False)
        schedule=[]
        for d,indices in enumerate(day_positions):
            for m,method in enumerate(METHODS):
                q=plans[d,m];stock=2000+np.cumsum(q-120)
                for h in range(24):schedule.append(dict(day=str(days[d].date()),method=method,endpoint_time=str(target[indices[h]]),
                    interval_start=str(target[indices[h]]-pd.Timedelta(hours=1)),production_m3=float(q[h]),demand_m3=120.,
                    inventory_start_m3=float(2000 if h==0 else stock[h-1]),inventory_end_m3=float(stock[h]),tariff_eur_kwh=float(PRICE[h])))
        pd.DataFrame(schedule).to_csv(directory/'schedules.csv',index=False)
        report['splits'][stage]=dict(planned_days=len(days),planned_hours=24*len(days),original_hours=len(positions),bank_days=64,
            bank_first_day=next(v['day'] for v in bank_records if v['selected']),bank_last_day=[v['day'] for v in bank_records if v['selected']][-1],
            bank_cutoff=str(cutoff),last_bank_source=str(target[bank_positions.reshape(-1)].max()),
            plan_changes={label:dict(exactly_different_horizons=int(np.any(plans[:,a]!=plans[:,b],axis=1).sum()),
                above_1e_minus6_m3_resolution_horizons=int((np.max(abs(plans[:,a]-plans[:,b]),axis=1)>1e-6).sum()),
                maximum_hourly_difference_m3=float(np.max(abs(plans[:,a]-plans[:,b]))))
                for label,a,b in [('coherent_vs_raw',2,1),('shuffled_vs_raw',3,1),('coherent_vs_shuffled',2,3)]})
        stage_cache[stage]=(days,day_positions,positions,plans)
    log.close()
    plan_files={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    save(out/'planning-freeze.json',dict(all_plans_created_at_utc=now(),files_sha256=plan_files,statement='All299 horizons and1196 schedules exist before any outcome mask or realized cost is evaluated.'))
    report['planning_freeze_sha256']=sha(out/'planning-freeze.json')
    print('ALL PLANS FROZEN BEFORE SCORING',flush=True)
    for stage,(days,day_positions,positions,plans) in stage_cache.items():
        membership=set(positions);exclusions=[];daily=[]
        for d,indices in enumerate(day_positions):
            inside=all(i in membership for i in indices)
            satellite_complete=bool(np.isfinite(satellite[indices]).all())
            primary=inside and satellite_complete
            reasons=[]
            if not inside:reasons.append('partial_original_period')
            if not satellite_complete:reasons.append('missing_satellite_endpoint')
            exclusions.append(dict(day=str(days[d].date()),primary=primary,weather_sensitivity=inside,original_hours=sum(i in membership for i in indices),
                available_satellite_hours=int(np.isfinite(satellite[indices]).sum()),exclusion_reasons='|'.join(reasons)))
            for r,reference in enumerate(REFERENCES):
                if reference=='satellite' and not satellite_complete:continue
                actual=weather[indices] if reference=='weather' else satellite[indices]
                solar=pv(actual)
                base=evaluate(plans[d,1],solar)
                for m,method in enumerate(METHODS):
                    q=plans[d,m];evaluated=evaluate(q,solar)
                    daily.append(dict(day=str(days[d].date()),method=method,reference=reference,primary=primary,
                        weather_sensitivity=inside and reference=='weather',cost_eur=float(evaluated['cost']),grid_kwh=float(evaluated['grid_energy']),
                        unused_pv_kwh=float(evaluated['unused_pv']),peak_grid_kw=float(np.maximum(SEC*q-solar,0).max()),
                        cost_regret_eur=float(evaluated['cost']-base['cost']),grid_regret_kwh=float(evaluated['grid_energy']-base['grid_energy']),**audit(q)))
        pd.DataFrame(exclusions).to_csv(out/stage/'evaluation-membership.csv',index=False)
        frame=pd.DataFrame(daily);frame.to_csv(out/stage/'daily-outcomes.csv',index=False)
        aggregate={}
        for subset in ('primary','weather_sensitivity'):
            aggregate[subset]={}
            for (method,reference),rows in frame.loc[frame[subset]].groupby(['method','reference'],sort=False):
                item={metric:summary(rows[metric]) for metric in ('cost_eur','grid_kwh','unused_pv_kwh','peak_grid_kw','cost_regret_eur','grid_regret_kwh')}
                regret=rows.cost_regret_eur.to_numpy()
                item.update(days=len(rows),worse_days=int(np.sum(regret>0)),better_days=int(np.sum(regret<0)),equal_days=int(np.sum(regret==0)),
                    cost_regret_below_reporting_resolution_days=int(np.sum(abs(regret)<1e-5)))
                aggregate[subset][method+'/'+reference]=item
        report['splits'][stage].update(primary_days=sum(v['primary'] for v in exclusions),weather_sensitivity_days=sum(v['weather_sensitivity'] for v in exclusions))
        report.setdefault('outcomes',{})[stage]=aggregate
        report['gates'][stage]={method:gates(frame,method) for method in ('coherent','shuffled','tariff_context')}
        comparisons={}
        for reference in REFERENCES:
            rows=frame.loc[frame.primary & (frame.reference==reference)]
            a=rows.loc[rows.method=='coherent'];b=rows.loc[rows.method=='shuffled']
            comparisons[reference]={metric:summary(a[metric].to_numpy()-b[metric].to_numpy()) for metric in ('cost_eur','grid_kwh')}
        report.setdefault('coherent_minus_shuffled',{})[stage]=comparisons
    if any(sha(out/name)!=digest for name,digest in plan_files.items()):raise AssertionError('Frozen plans changed during scoring')
    if any(sha(ROOT/name)!=digest for name,digest in pins.items()):raise AssertionError('Source changed during run')
    report.update(status='COMPLETE',completed_at_utc=now(),wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        experiment_all_axis_gate={m:all(report['gates'][s][m]['all_axis_pass'] for s in ('validation','test')) for m in ('coherent','shuffled')})
    save(out/'report.json',report)
    save(out/'outputs.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='outputs.json'})
    print('COMPLETE',json.dumps(dict(gates=report['experiment_all_axis_gate'],wall_seconds=report['wall_seconds'])),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=HERE/'result')
    main(parser.parse_args().out.resolve())
