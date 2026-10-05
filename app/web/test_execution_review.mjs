import test from 'node:test';
import assert from 'node:assert/strict';
import {makeExecutionCase,executionMeasurementTemplate,evaluateExecution} from './public/execution-review.mjs';

const at=h=>new Date(Date.UTC(2026,6,1)+h*3600000).toISOString();
const caseIdentity={name:'case.json',sha256:'a'.repeat(64)},sourceIdentity={name:'measurements.json',sha256:'b'.repeat(64)};
const range=(lower,upper=lower)=>({lower,upper});
function makeCase(){return makeExecutionCase({input:{times:Array.from({length:24},(_,i)=>at(i)),production:Array(24).fill(10),demand:10,capacity:1000,reserve:10,initial:100,target:100,startHour:0},unit_capacity_m3_h:20,specific_energy_kwh_m3:3.4,identity:{data_sha256:'c'.repeat(64)}});}
const total=(role,value)=>({role,unit:role==='energy'?'kWh':'m3',semantics:'interval_total',readings:[{start:at(0),end:at(24),available_at:at(24),...(typeof value==='number'?range(value):value)}]});
function source(c=makeCase()){const s=executionMeasurementTemplate({executionCase:c,case_sha256:caseIdentity.sha256});Object.assign(s,{source_kind:'illustrative_scenario',source_label:'Analytical fixture',plant_mapping:'Declared gross plant boundary',tank_mapping:'Declared single tank',streams:[total('energy',816),total('produced',240),total('delivered',240)],declared_zero:['other_inflow','other_outflow','spill']});s.tank.forEach(row=>Object.assign(row,range(100)));return s;}
const review=(s=source(),c=makeCase())=>evaluateExecution({executionCase:c,caseIdentity,source:s,sourceIdentity});
const counter=(values,no_reset=true)=>({role:'produced',unit:'m3',semantics:'cumulative_counter',no_reset,readings:values.map(([time,lower,upper])=>({time:at(time),available_at:at(time),lower,upper}))});

test('complete run recomputes the frozen plan and preserves measurement identity without mutating inputs',()=>{
 const c=makeCase(),s=source(c),before=JSON.stringify([c,s]),r=review(s,c);
 assert.deepEqual(r.measured.energy,range(816));assert.equal(r.modeled.energy,816);assert.deepEqual(r.water_balance,{status:'compatible',residual_m3:range(0)});assert.equal(r.volume_stock_comparison.status,'compatible');assert.ok(Object.values(r.differences).every(b=>b.lower===0&&b.upper===0));assert.equal(r.coverage.other_inflow.status,'declared_zero');assert.equal(JSON.stringify([c,s]),before);assert.deepEqual(r.case_identity,caseIdentity);assert.equal(r.horizon.end,at(24));assert.equal(r.issues.length,0);
 assert.deepEqual(makeExecutionCase(c),c);assert.throws(()=>makeExecutionCase({...c,totals:{energy:1}}),/Unsupported/);
});
test('less electricity with drained stock remains a distinct production and final-inventory shortfall',()=>{
 const s=source();s.streams[0]=total('energy',680);s.streams[1]=total('produced',200);Object.assign(s.tank[1],range(60));const r=review(s);
 assert.deepEqual(r.differences.energy,range(-136));assert.deepEqual(r.differences.produced,range(-40));assert.deepEqual(r.differences.final_storage,range(-40));assert.deepEqual(r.water_balance.residual_m3,range(0));assert.equal(r.water_balance.status,'compatible');assert.equal(r.volume_stock_comparison.status,'different');assert.equal(r.restoration_energy,undefined);assert.equal(r.savings,undefined);
});
test('bounded conservation distinguishes possible closure from inconsistent evidence without leak diagnosis',()=>{
 const s=source();Object.assign(s.tank[0],range(99,101));Object.assign(s.tank[1],range(98,102));s.streams[1]=total('produced',range(238,242));s.streams[2]=total('delivered',range(237,243));let r=review(s);assert.deepEqual(r.water_balance.residual_m3,range(-8,8));assert.equal(r.volume_stock_comparison.status,'compatible');Object.assign(s.tank[1],range(85,87));r=review(s);assert.deepEqual(r.water_balance.residual_m3,range(7,21));assert.equal(r.water_balance.status,'inconsistent');assert.equal(r.volume_stock_comparison.status,'different');assert.doesNotMatch(JSON.stringify(r),/detected leak/);
});
test('counter shared-endpoint uncertainty telescopes and timely interior readings tighten feasible totals',()=>{
 const s=source();s.streams[1]=counter([[0,999,1001],[12,1119,1121],[24,1239,1241]]);assert.deepEqual(review(s).measured.produced,range(238,242));s.streams[1]=counter([[0,0,100],[6,90,95],[12,10,92],[24,90,100]]);assert.deepEqual(review(s).measured.produced,range(0,100));s.streams[1]=counter([[0,0,100],[6,10,20],[12,80,90],[24,0,100]]);assert.deepEqual(review(s).measured.produced,range(60,100));
 s.streams[1]=counter([[0,1000,1000],[24,1240,1240]]);assert.deepEqual(review(s).measured.produced,range(240));
});
test('counter reset ambiguity, infeasible monotonic bounds and unavailable endpoints remain unknown',()=>{
 const s=source();for(const declaration of [false,null]){s.streams[1]=counter([[0,1000,1000],[24,1240,1240]],declaration);assert.equal(review(s).measured.produced,null);}
 s.streams[1]=counter([[0,1000,1000],[12,1300,1310],[24,1240,1240]]);assert.equal(review(s).measured.produced,null);assert.ok(review(s).issues.some(issue=>issue.code==='infeasible_counter'));
 s.streams[1].readings[1].available_at=at(25);assert.deepEqual(review(s).measured.produced,range(240));s.streams[1].readings[1].lower=1e100;s.streams[1].readings[1].upper=2e100;assert.deepEqual(review(s).measured.produced,range(240));s.streams[1].readings[2].available_at=at(25);assert.equal(review(s).measured.produced,null);
});
test('mixed interval partitions yield whole-period totals without inventing hourly allocations',()=>{
 const s=source();s.streams[1].readings=Array.from({length:4},(_,i)=>({start:at(i*6),end:at((i+1)*6),available_at:at((i+1)*6),...range(60)}));s.streams[2].readings=Array.from({length:3},(_,i)=>({start:at(i*8),end:at((i+1)*8),available_at:at((i+1)*8),...range(80)}));const r=review(s);assert.deepEqual(r.measured.produced,range(240));assert.deepEqual(r.measured.delivered,range(240));assert.equal(r.rows,undefined);assert.equal(r.coverage.produced.known_hours,24);
});
test('missing, null and late intervals retain partial known support without zero filling',()=>{
 const s=source();s.streams[0].readings=[{start:at(0),end:at(12),available_at:at(12),...range(400)},{start:at(12),end:at(24),available_at:at(25),...range(416)}];let r=review(s);assert.equal(r.measured.energy,null);assert.deepEqual(r.coverage.energy.known_support,range(400));assert.equal(r.coverage.energy.known_hours,12);s.streams[0].readings[1].lower=10000;s.streams[0].readings[1].upper=10001;r=review(s);assert.equal(r.measured.energy,null);assert.deepEqual(r.coverage.energy.known_support,range(400));Object.assign(s.streams[0].readings[1],{available_at:at(24),lower:null,upper:null});assert.equal(review(s).measured.energy,null);s.streams[0].readings.pop();assert.equal(review(s).measured.energy,null);
});
test('overlaps and duplicate records never select a convenient total or tank reading',()=>{
 const s=source();s.streams[1].readings.push({...s.streams[1].readings[0],start:at(12)});assert.equal(review(s).measured.produced,null);s.streams[1]=counter([[0,1000,1000],[24,1240,1240],[24,1240,1240]]);assert.equal(review(s).measured.produced,null);s.tank.push({...s.tank[0]});assert.equal(review(s).measured.initial_storage,null);
});
test('missing ancillary flows stay unknown while known water mismatch retains priority',()=>{
 const s=source();s.declared_zero=[];let r=review(s);assert.equal(r.measured.other_inflow,null);assert.equal(r.water_balance.status,'unknown');assert.equal(r.volume_stock_comparison.status,'unknown');Object.assign(s.tank[1],range(60));r=review(s);assert.equal(r.volume_stock_comparison.status,'different');assert.equal(r.water_balance.residual_m3,null);
});
test('unknown specific energy preserves measured electricity without a modeled energy comparison',()=>{
 const c=makeCase();c.specific_energy_kwh_m3=null;const r=review(source(c),c);assert.equal(r.modeled.energy,null);assert.deepEqual(r.measured.energy,range(816));assert.equal(r.differences.energy,null);assert.equal(r.volume_stock_comparison.status,'compatible');
});
test('strict boundaries, units and cases reject incompatible measurements and unsupported semantics',()=>{
 const mutations=[s=>s.case_sha256='d'.repeat(64),s=>s.electricity_basis='grid_imports',s=>s.streams[0].unit='kW',s=>s.streams[1].unit='m3/h',s=>s.streams[0].semantics='point',s=>s.streams[0].readings[0].end=at(25),s=>s.streams[0].readings[0].available_at=at(23),s=>s.tank[0].time=at(1),s=>s.tank[0].upper=NaN,s=>s.tank[0].lower=-1,s=>s.declared_zero.push('energy'),s=>s.extra=1,s=>s.streams[0].readings[0].lower=Infinity,s=>s.streams[0].readings[0].end='2026-07-02T00:00:00'];
 for(const change of mutations){const s=source();change(s);assert.throws(()=>review(s));}
 const c=makeCase();c.input.production[0]=21;assert.throws(()=>review(source(),c),/unit capacity/);c.input.production[0]=10;c.input.startHour=1;assert.throws(()=>makeExecutionCase(c),/entire 24-hour/);
});
test('equivalent offsets preserve exact boundaries, and source records are bounded',()=>{
 const s=source();s.tank[0].time='2026-07-01T03:00:00+03:00';s.streams[1].readings[0].end='2026-07-02T03:00:00+03:00';assert.deepEqual(review(s).water_balance.residual_m3,range(0));s.tank=Array(4097).fill(s.tank[0]);assert.throws(()=>review(s),/at most 4096/);
});
test('maximum supported record count remains usable with exact whole-period coverage',()=>{
 const s=source(),n=4092,start=Date.parse(at(0)),time=i=>new Date(start+Math.floor(24*3600000*i/n)).toISOString();s.streams[0].readings=Array.from({length:n},(_,i)=>({start:time(i),end:time(i+1),available_at:time(i+1),...range(816/n)}));const r=review(s);assert.equal(r.coverage.energy.status,'complete');assert.equal(r.coverage.energy.known_hours,24);assert.ok(Math.abs(r.measured.energy.lower-816)<1e-9);assert.equal(r.volume_stock_comparison.status,'compatible');assert.equal(r.issues.length,0);
});
test('compensated accounting retains small energy and water differences beside common large terms',()=>{
 const c=makeCase();c.input.production=Array(24).fill(0);c.input.production[0]=1;c.input.demand=0;c.specific_energy_kwh_m3=1e100;const s=source(c);s.streams[0].readings=[{start:at(0),end:at(1),available_at:at(1),...range(1e100)},{start:at(1),end:at(24),available_at:at(24),...range(1e80)}];s.streams[1]=total('produced',1);s.streams[2]=total('delivered',0);Object.assign(s.tank[1],range(101));assert.deepEqual(review(s,c).differences.energy,range(1e80));
 c.input.initial=1e100;c.input.target=1e100;c.input.capacity=2e100;c.input.production.fill(0);s.streams[1]=total('produced',1e-20);Object.assign(s.tank[0],range(1e100));Object.assign(s.tank[1],range(1e100));const r=review(s,c);assert.deepEqual(r.water_balance.residual_m3,range(1e-20));assert.equal(r.water_balance.status,'inconsistent');assert.equal(r.volume_stock_comparison.status,'different');
});
test('overflow and positive modeled-energy underflow are rejected instead of a false zero',()=>{
 const s=source();s.streams[0].readings=[{start:at(0),end:at(12),available_at:at(12),...range(1e308)},{start:at(12),end:at(24),available_at:at(24),...range(1e308)}];assert.throws(()=>review(s),/finite numeric/);const c=makeCase();c.input.production.fill(1e-200);c.specific_energy_kwh_m3=1e-200;assert.throws(()=>makeExecutionCase(c),/precision/);
});
