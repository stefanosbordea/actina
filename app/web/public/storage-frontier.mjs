// Retrospective comparison of retained cases; no optimization or model fitting.
import {isoHour} from './core.mjs';
const TANKS=[500,1000,2000,4000,8000];
const POLICIES=['reference','persistence','price_only','flat'];
const EPS=1e-6;
const civilTime=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Nicosia',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
const sum=values=>values.reduce((a,b)=>a+b,0);
const fail=message=>{throw Error(`Storage comparison unavailable: ${message}`);};
const finite=value=>typeof value==='number'&&Number.isFinite(value);
const equal=(a,b,label)=>{if(!finite(a)||!finite(b)||Math.abs(a-b)>EPS)fail(label);};
function dateKey(value) {
  if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value)||!Number.isFinite(Date.parse(value))||new Date(value).toISOString().slice(0,10)!==value)fail('invalid date');
  return value;
}
function datedMap(rows,label) {
  if(!Array.isArray(rows))fail(`missing ${label}`);
  const map=new Map();
  for(const row of rows){const key=dateKey(row?.date);if(map.has(key))fail(`duplicate ${label} date ${key}`);map.set(key,row);}
  return map;
}
function vector(value,label) {
  if(!Array.isArray(value)||value.length!==24||!value.every(finite))fail(`${label} requires 24 finite values`);
  return value;
}
function weightsFor(report) {
  if(!Array.isArray(report.windows))fail(`${report.date}: missing Group 1 windows`);
  const weights=Array(24).fill(0);let end=-1;
  const minute=value=>{if(typeof value!=='string'||!/^([01]\d|2[0-3]):[0-5]\d$/.test(value))fail(`${report.date}: invalid window time`);return Number(value.slice(0,2))*60+Number(value.slice(3));};
  for(const window of report.windows){
    const a=minute(window.start_local),b=minute(window.end_local);
    if(window.group!==1||a>=b||a<end)fail(`${report.date}: overlapping, unordered or non-Group 1 window`);
    end=b;
    for(let h=0;h<24;h++)weights[h]+=Math.max(0,Math.min(b,(h+1)*60)-Math.max(a,h*60))/60;
  }
  vector(report.hour_overlap_fraction,'reported hourly fractions').forEach((v,h)=>equal(v,weights[h],`${report.date}: window fraction mismatch`));
  return weights;
}
function differences(values) {
  return {total_kwh:sum(values),mean_kwh:sum(values)/values.length,min_daily_kwh:Math.min(...values),max_daily_kwh:Math.max(...values),
    more_days:values.filter(x=>x>EPS).length,tied_days:values.filter(x=>Math.abs(x)<=EPS).length,less_days:values.filter(x=>x< -EPS).length};
}

/** sourceHashes must describe the exact input bytes, computed by the caller before parsing. */
export function storageFrontier(data,research,{dates=null,sourceHashes}={}) {
  for(const key of ['data_sha256','research_sha256'])if(typeof sourceHashes?.[key]!=='string'||!/^[a-f0-9]{64}$/.test(sourceHashes[key]))fail(`missing exact ${key}`);
  if(data?.schema!==1||research?.schema!==1||JSON.stringify(data.tanks)!==JSON.stringify(TANKS)||data.unit_capacity!==500||data.demand!==120||data.kwh_per_m3!==3.4)fail('unsupported retained scenario contract');
  const canonical=datedMap(data.days,'scenario'),reports=datedMap(research.daily?.days,'report');
  for(const date of reports.keys())if(!canonical.has(date))fail(`${date}: report has no retained scenario`);
  if(dates!==null&&!Array.isArray(dates))fail('selected dates must be an array');
  const selected=dates===null?[...canonical.keys()]:dates.map(dateKey);
  if(new Set(selected).size!==selected.length)fail('duplicate selected date');
  for(const date of selected)if(!canonical.has(date))fail(`${date}: selected date has no retained scenario`);
  selected.sort();
  const matched=selected.filter(date=>reports.has(date)),excluded=selected.filter(date=>!reports.has(date));
  const daily=[],sources=new Map();
  for(const date of matched){
    const day=canonical.get(date),report=reports.get(date),weights=weightsFor(report),windowHours=sum(weights);
    if(!Array.isArray(day.times)||day.times.length!==24)fail(`${date}: 24 local hourly timestamps required`);
    day.times.forEach((time,h)=>{
      const parsed=isoHour(time);
      if(typeof time!=='string'||parsed.error||civilTime.format(new Date(parsed.epoch))!==`${date} ${String(h).padStart(2,'0')}:00:00`)fail(`${date}: timestamps do not match local hourly bins`);
    });
    if(typeof report.source_sha256!=='string'||!/^[a-f0-9]{64}$/.test(report.source_sha256)||typeof report.source_id!=='string'||!report.source_id||!Number.isInteger(report.page)||report.page<1)fail(`${date}: missing report source identity`);
    if(typeof report.source_url!=='string')fail(`${date}: invalid report URL`);
    let sourceURL;try{sourceURL=new URL(report.source_url);}catch{fail(`${date}: invalid report URL`);}
    if(sourceURL.protocol!=='https:')fail(`${date}: invalid report URL`);
    const source={id:report.source_id,url:report.source_url,sha256:report.source_sha256};
    if(sources.has(source.id)&&JSON.stringify(sources.get(source.id))!==JSON.stringify(source))fail(`${date}: conflicting report source identity`);
    sources.set(source.id,source);
    const prices=vector(day.prices,`${date}: prices`),flatCost=120*3.4*sum(prices)/1000;
    prices.forEach((v,h)=>equal(v,h>=10&&h<17?101:h>=17&&h<23?183:130,`${date}: tariff differs from retained scenario`));
    if(!Array.isArray(report.overlap)||report.overlap.length!==TANKS.length||new Set(report.overlap.map(row=>row.tank_m3)).size!==TANKS.length)fail(`${date}: incomplete paired tank cases`);
    for(const tank of TANKS){
      const entry=report.overlap.find(row=>row.tank_m3===tank),plan=day.schedules?.[String(tank)],totals=plan?.totals;
      if(!entry||!plan||!totals)fail(`${date}: missing paired ${tank} m³ case`);
      const production=vector(plan.production,`${date}: production`),storage=vector(plan.storage,`${date}: storage`),starts=vector(plan.storage_start,`${date}: storage start`);
      let inventory=tank*.5;
      for(let h=0;h<24;h++){
        if(production[h]<-EPS||production[h]>500+EPS||storage[h]<tank*.2-EPS||storage[h]>tank+EPS)fail(`${date}: ${tank} m³ water/capacity constraint`);
        equal(starts[h],inventory,`${date}: storage continuity`);inventory+=production[h]-120;
        equal(storage[h],inventory,`${date}: hourly water balance`);
      }
      equal(inventory,tank*.5,`${date}: terminal inventory`);
      const energy=3.4*sum(production),cost=sum(production.map((v,h)=>v*3.4*prices[h]))/1000;
      for(const [key,value] of Object.entries({water_produced_m3:2880,water_demand_m3:2880,unmet_demand_m3:0,energy_kwh:9792,baseline_energy_kwh:9792,cost_eur:cost,baseline_cost_eur:flatCost,cost_saving_eur:flatCost-cost,safety_violations:0,safety_minimum_m3:tank*.2,initial_storage_m3:tank*.5,final_storage_m3:tank*.5}))equal(totals[key],value,`${date}: ${key} mismatch`);
      equal(energy,9792,`${date}: matched energy`);
      const load={};
      for(const policy of POLICIES){
        const value=entry[`${policy}_load_kwh`];
        if(!finite(value)||value<-EPS||value>Math.min(energy,windowHours*1700)+EPS)fail(`${date}: missing or invalid ${policy} control`);
        load[policy]=value;
      }
      equal(load.reference,sum(production.map((v,h)=>v*3.4*weights[h])),`${date}: reference overlap mismatch`);
      equal(load.flat,windowHours*120*3.4,`${date}: flat overlap mismatch`);
      equal(entry.reference_minus_flat_kwh,load.reference-load.flat,`${date}: flat delta mismatch`);
      equal(entry.reference_minus_price_only_kwh,load.reference-load.price_only,`${date}: price-only delta mismatch`);
      daily.push({date,tank_m3:tank,window_hours:windowHours,window_load_kwh:load,reference_cost_eur:cost,flat_cost_eur:flatCost,
        reference_minus_kwh:Object.fromEntries(POLICIES.slice(1).map(policy=>[policy,load.reference-load[policy]])),source_id:source.id,source_page:report.page});
    }
  }
  const tanks=TANKS.map(tank=>{
    const cases=daily.filter(row=>row.tank_m3===tank);
    return {tank_m3:tank,matched_days:cases.length,window_load_kwh:Object.fromEntries(POLICIES.map(policy=>[policy,cases.length?sum(cases.map(row=>row.window_load_kwh[policy])):null])),
      reference_cost_eur:cases.length?sum(cases.map(row=>row.reference_cost_eur)):null,flat_cost_eur:cases.length?sum(cases.map(row=>row.flat_cost_eur)):null,
      reference_minus:Object.fromEntries(POLICIES.slice(1).map(policy=>[policy,cases.length?differences(cases.map(row=>row.reference_minus_kwh[policy])):null]))};
  });
  const marginal=matched.length?TANKS.slice(1).map((tank,i)=>{
    const low=tanks[i],high=tanks[i+1];
    return {from_tank_m3:low.tank_m3,to_tank_m3:tank,additional_capacity_m3:tank-low.tank_m3,matched_days:matched.length,
      window_load_delta_kwh:Object.fromEntries(POLICIES.map(policy=>[policy,high.window_load_kwh[policy]-low.window_load_kwh[policy]])),
      reference_cost_change_eur:high.reference_cost_eur-low.reference_cost_eur};
  }):[];
  return {schema:1,status:matched.length?'COMPLETE':'EMPTY',selection:{requested_dates:selected,matched_dates:matched,excluded_no_report_dates:excluded,matched_days:matched.length,matched_cases:daily.length},
    input_identity:{data_sha256:sourceHashes.data_sha256,research_sha256:sourceHashes.research_sha256,report_sources:[...sources.values()]},
    assumptions:{unit_capacity_m3_h:500,demand_m3_h:120,specific_energy_kwh_m3:3.4,reserve_fraction:.2,initial_and_terminal_fraction:.5,water_m3_per_day:2880,energy_kwh_per_day:9792},
    scope:'Retrospective load during reported Group 1 windows, assuming uniform within-hour production and Cyprus civil time. Temporal coincidence is not recovered electricity, local renewable availability or permission to operate. Missing reports remain unknown. No forecast fitting or schedule optimization occurs.',
    comparison_limits:'Only the five retained tank cases are compared. Each starts and ends half full, so absolute starting inventory changes with tank size. Costs use illustrative clock tariffs, with no capital, maintenance or plant feasibility model. This is not an investment optimum. Persistence and price-only window totals are retained scalar controls; their hourly plans are not re-audited here. Input hashes identify caller-supplied bytes, not source authentication.',
    tanks,marginal,daily};
}
