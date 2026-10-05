import test from 'node:test';
import assert from 'node:assert/strict';
import {performance} from 'node:perf_hooks';
import {makeExecutionCase,evaluateExecution} from './public/execution-review.mjs';

const at=h=>new Date(Date.UTC(2026,6,1)+h*3600000).toISOString();
const bounds=(lower,upper=lower)=>({lower,upper});
const caseIdentity={name:'case.json',sha256:'a'.repeat(64)},sourceIdentity={name:'measurements.json',sha256:'b'.repeat(64)};
const interval=(start,end,lower,upper=lower)=>({start:at(start),end:at(end),available_at:at(end),lower,upper});
const stream=(role,readings)=>({role,unit:role==='energy'?'kWh':'m3',semantics:'interval_total',readings});
const counter=(role,readings)=>({role,unit:'m3',semantics:'cumulative_counter',no_reset:true,readings:readings.map(([time,lower,upper=lower])=>({time:at(time),available_at:at(time),lower,upper}))});
function fixture(){
 const executionCase=makeExecutionCase({input:{times:Array.from({length:24},(_,i)=>at(i)),production:Array(24).fill(10),demand:10,capacity:1000,reserve:0,initial:100,target:100},unit_capacity_m3_h:20,specific_energy_kwh_m3:3.4,identity:{data_sha256:'c'.repeat(64)}});
 const source={schema:1,kind:'plant_execution_measurements',case_sha256:caseIdentity.sha256,source_kind:'illustrative_scenario',source_label:'Temporal analytical fixture',plant_mapping:'Declared plant',tank_mapping:'Declared tank',electricity_basis:'gross_plant_load',review_as_of:at(24),streams:[stream('energy',[interval(0,24,816)]),stream('produced',[interval(0,12,0),interval(12,24,240)]),stream('delivered',[interval(0,12,240),interval(12,24,0)])],declared_zero:['other_inflow','other_outflow','spill'],tank:[0,24].map(time=>({time:at(time),available_at:at(time),...bounds(100)}))};
 return {executionCase,source,caseIdentity,sourceIdentity};
}
const run=f=>evaluateExecution(f).temporal_water;
const replace=(f,value)=>{f.source.streams=f.source.streams.filter(s=>s.role!==value.role).concat(value);};
function stock(f,initial,final=initial,capacity=1000){f.executionCase.input.capacity=capacity;f.executionCase.input.initial=initial;f.executionCase.input.target=final;Object.assign(f.source.tank[0],bounds(initial));Object.assign(f.source.tank[1],bounds(final));}

test('matching daily totals cannot conceal a negative intermediate stock',()=>{
 const f=fixture(),before=JSON.stringify(f),r=evaluateExecution(f);
 assert.equal(r.water_balance.status,'compatible');assert.equal(r.volume_stock_comparison.status,'compatible');assert.equal(r.temporal_water.status,'inconsistent');assert.equal(r.temporal_water.evidence_complete,true);assert.equal(r.temporal_water.boundary_count,3);assert.deepEqual(r.temporal_water.unresolved_roles,[]);assert.ok(r.issues.some(i=>i.code==='temporal_inconsistency'));assert.equal(JSON.stringify(f),before);
});
test('reversing the same totals exposes intermediate overflow',()=>{
 const f=fixture();stock(f,100,100,200);replace(f,stream('produced',[interval(0,12,240),interval(12,24,0)]));replace(f,stream('delivered',[interval(0,12,0),interval(12,24,240)]));assert.equal(run(f).status,'inconsistent');
});
test('a coarse production interval permits feasible timing without a uniform split',()=>{
 const f=fixture();replace(f,stream('produced',[interval(0,24,240)]));assert.equal(run(f).status,'compatible');
});
test('shared uncertain production counter and stock endpoints remain jointly coupled',()=>{
 const f=fixture();stock(f,0);Object.assign(f.source.tank[0],bounds(0,10));replace(f,counter('produced',[[0,0],[12,0,5],[24,10]]));replace(f,stream('delivered',[interval(0,12,10),interval(12,24,0)]));const r=evaluateExecution(f);assert.equal(r.water_balance.status,'compatible');assert.equal(r.temporal_water.status,'inconsistent');
});
test('outgoing cumulative readings constrain shared withdrawals',()=>{
 const f=fixture();stock(f,0,0,4);replace(f,stream('produced',[interval(0,12,10),interval(12,24,0)]));replace(f,counter('delivered',[[0,0],[12,0,5],[24,10]]));assert.equal(run(f).status,'inconsistent');f.executionCase.input.capacity=5;assert.equal(run(f).status,'compatible');
});
test('a one-unit capacity contradiction survives a 1e100 common tank level',()=>{
 const f=fixture();stock(f,1e100,1e100,1e100);replace(f,stream('produced',[interval(0,12,1),interval(12,24,0)]));replace(f,stream('delivered',[interval(0,12,0),interval(12,24,1)]));assert.equal(evaluateExecution(f).water_balance.status,'compatible');assert.equal(run(f).status,'inconsistent');
});
test('a huge unchanged counter cannot conceal a small physical prefix deficit',()=>{
 const f=fixture();stock(f,0);replace(f,counter('produced',[[0,1e100],[12,1e100],[24,1e100]]));replace(f,stream('delivered',[interval(0,12,1),interval(12,24,0)]));f.source.declared_zero=['other_outflow','spill'];replace(f,stream('other_inflow',[interval(0,12,0),interval(12,24,1)]));assert.equal(evaluateExecution(f).water_balance.status,'compatible');assert.equal(run(f).status,'inconsistent');
});
test('unknown inflow alone cannot rescue a contradiction when endpoints force its total to zero',()=>{
 const f=fixture();f.source.declared_zero=['other_outflow','spill'];let r=run(f);assert.equal(r.status,'inconsistent');assert.equal(r.evidence_complete,false);assert.deepEqual(r.unresolved_roles,['other_inflow']);f.source.declared_zero=['spill'];r=run(f);assert.equal(r.status,'unknown');assert.deepEqual(r.unresolved_roles,['other_inflow','other_outflow']);
});
test('late and null numerical records supply no constraints or false zeros',()=>{
 const f=fixture(),p=f.source.streams.find(s=>s.role==='produced');Object.assign(p.readings[1],bounds(0));p.readings[0].available_at=at(25);let r=run(f);assert.equal(r.status,'unknown');p.readings[0].lower=1e200;p.readings[0].upper=2e200;assert.deepEqual(run(f),r);Object.assign(p.readings[0],{available_at:at(12),lower:null,upper:null});assert.deepEqual(run(f),r);
});
test('a timely interior counter constrains an unavailable final total',()=>{
 const f=fixture();replace(f,counter('produced',[[0,0],[12,0]]));const r=run(f);assert.equal(r.status,'inconsistent');assert.equal(r.evidence_complete,false);assert.ok(r.unresolved_roles.includes('produced'));
});
test('missing counter endpoints are unknown when their constrained completion is feasible',()=>{
 const f=fixture();replace(f,counter('produced',[[12,240]]));assert.equal(run(f).status,'unknown');
});
test('monotonic counter contradictions are retained, reset uncertainty is not treated as continuity',()=>{
 const f=fixture(),p=counter('produced',[[0,100],[12,90],[24,340]]);replace(f,p);let r=run(f);assert.equal(r.status,'inconsistent');assert.equal(r.evidence_complete,true);for(const no_reset of [false,null]){p.no_reset=no_reset;r=run(f);assert.equal(r.status,'unknown');assert.ok(r.unresolved_roles.includes('produced'));}
});
test('ambiguous overlapping or duplicate evidence does not select a convenient constraint',()=>{
 const f=fixture();f.source.streams.find(s=>s.role==='produced').readings.push(interval(0,24,240));assert.equal(run(f).status,'unknown');replace(f,counter('produced',[[0,0],[12,0],[12,240],[24,240]]));assert.equal(run(f).status,'unknown');
});
test('missing or duplicate tank endpoints use capacity bounds rather than modeled stock',()=>{
 const f=fixture();f.source.tank.shift();assert.equal(run(f).status,'inconsistent');assert.ok(run(f).unresolved_roles.includes('initial_storage'));f.source.tank=[{time:at(0),available_at:at(0),...bounds(100)},{time:at(0),available_at:at(0),...bounds(200)}];assert.equal(run(f).status,'unknown');
});
test('a known tank lower bound above capacity is inconsistent despite missing flows',()=>{
 const f=fixture();Object.assign(f.source.tank[0],bounds(1001,1002));f.source.declared_zero=[];assert.equal(run(f).status,'inconsistent');
});
test('zero flow and exact capacity contact are permitted',()=>{
 const f=fixture();stock(f,0,0,240);replace(f,stream('produced',[interval(0,12,240),interval(12,24,0)]));replace(f,stream('delivered',[interval(0,12,0),interval(12,24,240)]));assert.equal(run(f).status,'compatible');replace(f,stream('produced',[interval(0,24,0)]));replace(f,stream('delivered',[interval(0,24,0)]));assert.equal(run(f).status,'compatible');
});
test('subnormal positive volumes remain distinct from zero',()=>{
 const f=fixture(),tiny=Number.MIN_VALUE;stock(f,0,0,tiny);replace(f,stream('produced',[interval(0,12,tiny),interval(12,24,0)]));replace(f,stream('delivered',[interval(0,12,0),interval(12,24,tiny)]));assert.equal(run(f).status,'compatible');replace(f,stream('produced',[interval(0,12,2*tiny),interval(12,24,0)]));replace(f,stream('delivered',[interval(0,12,0),interval(12,24,2*tiny)]));assert.equal(run(f).status,'inconsistent');
});
test('different partitions, equivalent UTC offsets and record order preserve feasibility',()=>{
 const f=fixture();replace(f,stream('produced',[interval(0,8,80),interval(8,16,80),interval(16,24,80)]));replace(f,stream('delivered',[interval(0,6,60),interval(6,12,60),interval(12,18,60),interval(18,24,60)]));const expected=run(f);assert.equal(expected.status,'compatible');f.source.streams.reverse();for(const s of f.source.streams)s.readings.reverse();f.source.streams.find(s=>s.role==='produced').readings.at(-1).start='2026-07-01T03:00:00+03:00';assert.deepEqual(run(f),expected);
});
test('energy evidence neither changes the water grid nor resolves missing water evidence',()=>{
 const f=fixture();replace(f,stream('produced',[interval(0,24,240)]));const expected=run(f);replace(f,stream('energy',Array.from({length:24},(_,i)=>interval(i,i+1,34))));assert.deepEqual(run(f),expected);f.source.streams=f.source.streams.filter(s=>s.role!=='energy');assert.deepEqual(run(f),expected);
});
test('maximum record count handles a long water grid without recursive traversal',()=>{
 const f=fixture(),n=4092,start=Date.parse(at(0)),time=i=>new Date(start+Math.floor(24*3600000*i/n)).toISOString();replace(f,stream('produced',Array.from({length:n},(_,i)=>({start:time(i),end:time(i+1),available_at:time(i+1),...bounds(1)}))));replace(f,stream('delivered',[interval(0,24,n)]));const before=performance.now(),r=run(f),elapsed_ms=performance.now()-before;assert.equal(r.status,'compatible');assert.equal(r.boundary_count,n+1);console.log(JSON.stringify({workload:'4096 total records; 4092 produced intervals and one coarse delivery interval',records:n+4,boundaries:r.boundary_count,circulation_nodes:2*n+2,bounded_edges:4*n+2,elapsed_ms,status:r.status}));
});
