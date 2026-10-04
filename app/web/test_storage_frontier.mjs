import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {storageFrontier} from './public/storage-frontier.mjs';

const bytes=name=>fs.readFileSync(new URL(`./public/${name}.json`,import.meta.url));
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const dataBytes=bytes('data'),researchBytes=bytes('research');
const data=JSON.parse(dataBytes),research=JSON.parse(researchBytes);
const sourceHashes={data_sha256:hash(dataBytes),research_sha256:hash(researchBytes)};
const compare=(d=data,r=research,dates=null)=>storageFrontier(d,r,{dates,sourceHashes});
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-6,`${a} differs from ${b}`);
const clone=value=>structuredClone(value);

function fixture(){
  const d=clone(data),r=clone(research);
  d.days=d.days.slice(0,2);r.daily.days=r.daily.days.slice(0,2);
  d.days.forEach((day,i)=>{
    const report=r.daily.days[i],fraction=i?.5:1;
    report.windows=[{start_local:'10:00',end_local:i?'10:30':'11:00',group:1}];
    report.hour_overlap_fraction=Array(24).fill(0);report.hour_overlap_fraction[10]=fraction;
    for(const tank of d.tanks){
      const plan=day.schedules[tank];plan.production=Array(24).fill(120);plan.storage=plan.storage_start=Array(24).fill(tank*.5);
      Object.assign(plan.totals,{cost_eur:1319.88,cost_saving_eur:0,min_storage_m3:tank*.5,max_storage_m3:tank*.5});
      const entry=report.overlap.find(row=>row.tank_m3===tank);
      Object.assign(entry,{reference_load_kwh:408*fraction,flat_load_kwh:408*fraction,persistence_load_kwh:300,price_only_load_kwh:i?0:500,reference_minus_flat_kwh:0,reference_minus_price_only_kwh:408*fraction-(i?0:500)});
    }
  });
  return [d,r];
}

test('62 matched days retain all four controls and exclude unknown September',()=>{
  const result=compare();assert.equal(result.status,'COMPLETE');assert.equal(result.selection.matched_days,62);assert.equal(result.selection.matched_cases,310);
  assert.equal(result.selection.excluded_no_report_dates.length,30);assert.ok(result.selection.excluded_no_report_dates.every(x=>x.startsWith('2026-09')));
  const independent=JSON.parse(fs.readFileSync(new URL('../results/curtailment-overlap.json',import.meta.url)));
  for(const row of result.tanks)for(const policy of ['reference','persistence','price_only','flat'])near(row.window_load_kwh[policy],independent.summed_kwh_by_tank[row.tank_m3][`${policy}_load_kwh`]);
  assert.equal(result.tanks[3].reference_minus.persistence.total_kwh,-816);assert.equal(result.tanks[3].reference_minus.persistence.less_days,1);assert.equal(result.tanks[3].reference_minus.persistence.tied_days,61);
  assert.equal(result.marginal[3].window_load_delta_kwh.reference,2652);near(result.marginal[3].reference_cost_change_eur,0);
  assert.equal(result.input_identity.data_sha256,hash(dataBytes));assert.equal(result.input_identity.research_sha256,hash(researchBytes));assert.equal(result.input_identity.report_sources.length,2);
});
test('independent two-day arithmetic preserves signed differences and partial hours',()=>{
  const result=compare(...fixture());
  for(const row of result.tanks){
    assert.deepEqual(row.window_load_kwh,{reference:612,persistence:600,price_only:500,flat:612});near(row.reference_cost_eur,2639.76);
    assert.deepEqual(row.reference_minus.persistence,{total_kwh:12,mean_kwh:6,min_daily_kwh:-96,max_daily_kwh:108,more_days:1,tied_days:0,less_days:1});
    assert.equal(row.reference_minus.price_only.total_kwh,112);assert.equal(row.reference_minus.flat.tied_days,2);
  }
  assert.equal(result.daily[0].window_hours,1);assert.equal(result.daily[5].window_hours,.5);
  assert.ok(result.marginal.every(row=>row.window_load_delta_kwh.reference===0));
});
test('date subsets use exactly paired cases, independent of caller ordering',()=>{
  const [d,r]=fixture(),dates=d.days.map(day=>day.date).reverse();const result=compare(d,r,dates);
  assert.deepEqual(result.selection.matched_dates,[...dates].sort());assert.equal(result.selection.matched_cases,10);
  const first=compare(d,r,[d.days[0].date]);assert.equal(first.tanks[0].window_load_kwh.reference,408);assert.equal(first.tanks[0].reference_minus.persistence.total_kwh,108);
  assert.equal(result.input_identity.report_sources.length,1);assert.deepEqual(dates,[...dates].sort().reverse());
});
test('empty and wholly unreported selections stay explicit, never zero benefit',()=>{
  for(const dates of [[],['2026-09-01']]){
    const result=compare(data,research,dates);assert.equal(result.status,'EMPTY');assert.equal(result.selection.matched_cases,0);assert.equal(result.daily.length,0);assert.equal(result.marginal.length,0);
    assert.equal(result.tanks.length,5);assert.ok(result.tanks.every(row=>row.reference_cost_eur===null&&row.window_load_kwh.reference===null&&row.reference_minus.flat===null));
  }
});
test('a retained report with no windows is a zero timing result, not missing data',()=>{
  const [d,r]=fixture();d.days=d.days.slice(0,1);r.daily.days=r.daily.days.slice(0,1);const report=r.daily.days[0];report.windows=[];report.hour_overlap_fraction.fill(0);
  for(const row of report.overlap)for(const key of Object.keys(row))if(key!=='tank_m3')row[key]=0;
  const result=compare(d,r);assert.equal(result.status,'COMPLETE');assert.equal(result.selection.matched_days,1);assert.equal(result.tanks[0].window_load_kwh.reference,0);
});
test('missing, duplicated or nonfinite paired controls fail closed',()=>{
  for(const change of [r=>delete r.daily.days[0].overlap[0].persistence_load_kwh,r=>r.daily.days[0].overlap.pop(),r=>r.daily.days[0].overlap[1].tank_m3=500,r=>r.daily.days[0].overlap[0].price_only_load_kwh=NaN,r=>r.daily.days[0].overlap[0].price_only_load_kwh='500',r=>r.daily.days[0].overlap[0].persistence_load_kwh=-1,r=>r.daily.days[0].overlap[0].persistence_load_kwh=100000]){
    const [d,r]=fixture();change(r);assert.throws(()=>compare(d,r),/Storage comparison unavailable/);
  }
});
test('water balance, terminal storage, unit capacity and energy cannot drift silently',()=>{
  for(const change of [d=>d.days[0].schedules[500].production[0]=501,d=>d.days[0].schedules[500].storage[0]=0,d=>d.days[0].schedules[500].storage_start[1]+=1,d=>d.days[0].schedules[500].totals.energy_kwh+=1,d=>d.days[0].schedules[500].totals.final_storage_m3+=1,d=>d.days[0].schedules[500].totals.cost_eur+=1,d=>delete d.days[0].schedules[8000],d=>d.days[0].prices[0]+=1]){
    const [d,r]=fixture();change(d);assert.throws(()=>compare(d,r),/Storage comparison unavailable/);
  }
});
test('Cyprus civil-time bins accept equivalent UTC timestamps and reject reordered or naive times',()=>{
  const [d,r]=fixture();d.days.forEach(day=>day.times=day.times.map(time=>new Date(time).toISOString()));assert.equal(compare(d,r).selection.matched_days,2);
  for(const change of [d=>d.days[0].times.reverse(),d=>d.days[0].times[0]='2026-07-01T00:00:00',d=>d.days[0].times.pop(),d=>d.days[0].times[0]='2026-07-01T00:30:00+03:00']){
    const [d,r]=fixture();change(d);assert.throws(()=>compare(d,r),/Storage comparison unavailable/);
  }
});
test('impossible dates and sub-hour timestamps cannot normalize into valid local bins',()=>{
  for(const time of ['2026-06-31T00:00:00+03:00','2026-07-01T00:00:00.999+03:00','2026-07-01T00:00:00.001+03:00','2026-07-01T00:00:01+03:00']){
    const [d,r]=fixture();d.days[0].times[0]=time;
    assert.throws(()=>compare(d,r),/timestamps do not match local hourly bins/,time);
  }
  const [d,r]=fixture();d.days[0].times[0]='2026-07-01T00:00:00.000+03:00';
  assert.equal(compare(d,r).selection.matched_days,2);
});
test('report windows, computed overlap and retained deltas are independently reconciled',()=>{
  for(const change of [r=>r.daily.days[0].windows[0].start_local='25:00',r=>r.daily.days[0].windows[0].end_local='09:00',r=>r.daily.days[0].windows[0].group=2,r=>r.daily.days[0].windows.push({...r.daily.days[0].windows[0]}),r=>r.daily.days[0].hour_overlap_fraction[10]=.5,r=>r.daily.days[0].overlap[0].reference_load_kwh+=1,r=>r.daily.days[0].overlap[0].flat_load_kwh+=1,r=>r.daily.days[0].overlap[0].reference_minus_flat_kwh+=1,r=>r.daily.days[0].overlap[0].reference_minus_price_only_kwh+=1]){
    const [d,r]=fixture();change(r);assert.throws(()=>compare(d,r),/Storage comparison unavailable/);
  }
});
test('dates, contract and source identities are mandatory and unambiguous',()=>{
  assert.throws(()=>storageFrontier(data,research),/data_sha256/);
  assert.throws(()=>storageFrontier(data,research,{sourceHashes:{...sourceHashes,research_sha256:'unknown'}}),/research_sha256/);
  for(const dates of [['2026-07-01','2026-07-01'],['2026-02-30'],['2026-10-01'],'2026-07-01'])assert.throws(()=>compare(data,research,dates),/Storage comparison unavailable/);
  for(const change of [(d,r)=>d.days.push(d.days[0]),(d,r)=>r.daily.days.push(r.daily.days[0]),(d,r)=>r.daily.days[0].date='2026-06-30',(d,r)=>d.kwh_per_m3=4,(d,r)=>r.daily.days[0].source_sha256='unknown',(d,r)=>r.daily.days[0].page=0,(d,r)=>r.daily.days[0].source_url='http://example.com/report',(d,r)=>r.daily.days[1].source_sha256='a'.repeat(64)]){
    const [d,r]=fixture();change(d,r);assert.throws(()=>compare(d,r),/Storage comparison unavailable/);
  }
});
test('comparison does not mutate either retained input or fit any model',()=>{
  const d=clone(data),r=clone(research),before=[JSON.stringify(d),JSON.stringify(r)];const result=compare(d,r);
  assert.deepEqual([JSON.stringify(d),JSON.stringify(r)],before);assert.match(result.scope,/not recovered electricity/);assert.match(result.comparison_limits,/not an investment optimum/);assert.match(result.comparison_limits,/absolute starting inventory changes/);
});
