import {test} from 'node:test';
import assert from 'node:assert/strict';
import {replayPlan} from './public/plan-resilience.mjs';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
const legacy=JSON.parse(readFileSync(new URL('fixtures/joint-water-legacy-hashes.json',import.meta.url)));


const times=Array.from({length:24},(_,h)=>`2026-07-01T${String(h).padStart(2,'0')}:00:00+03:00`);
const fixture=(patch={})=>({times,production:Array(24).fill(100),demand:100,capacity:4000,reserve:800,initial:2000,target:2000,startHour:10,...patch});
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-7,`${a} != ${b}`);
const margin=input=>replayPlan(input).margins;
const tail=(a,b)=>[...Array(22).fill(0),a,b];

test('terminal requirement exposes the actual demand/extra-energy tradeoff',()=>{
 const original=fixture(),returned=fixture();returned.production[10]=200;
 const a=margin(original),b=margin(returned);
 near(a.maximum_demand_multiplier,26/14);near(b.maximum_demand_multiplier,27/14);
 near(a.joint_maximum_demand_multiplier,1);near(b.joint_maximum_demand_multiplier,15/14);
 near(a.joint_minimum_initial_storage_m3,2000);near(b.joint_minimum_initial_storage_m3,1900);
 assert.equal(b.joint_maximum_demand_limits[0].constraint,'terminal_target');
 assert.equal(b.joint_maximum_demand_limits[0].hour,24);
 assert.equal(b.joint_maximum_demand_limits[0].time,'2026-07-01T21:00:00.000Z');
 const at=(plan,demand_multiplier)=>replayPlan({...plan,scenario:{demand_multiplier}}).totals;
 near(at(original,1.05).terminal_deficit_m3,70);near(at(returned,1.05).terminal_deficit_m3,0);
 near(at(returned,1.08).terminal_deficit_m3,12);
 near((at(returned,1).available_production_m3-at(original,1).available_production_m3)*3.4,340);
});
test('below-reserve initial inventory is infeasible even if production repairs it immediately',()=>{
 const m=margin(fixture({initial:799}));
 assert.equal(m.joint_maximum_demand_status,'initial_below_reserve');
 assert.equal(m.joint_maximum_demand_multiplier,null);
 assert.equal(m.joint_maximum_demand_limits[0].hour,10);
 assert.equal(m.joint_minimum_initial_storage_m3,2000);
});
test('zero demand distinguishes impossible terminal inventory from an unbounded multiplier',()=>{
 const input=fixture({production:tail(10,10),demand:0,capacity:1000,reserve:80,initial:100,target:150,startHour:22});
 const m=margin(input);assert.equal(m.joint_maximum_demand_status,'infeasible_even_without_demand');
 assert.equal(m.joint_maximum_demand_multiplier,null);near(m.joint_minimum_initial_storage_m3,130);
 const enough=margin({...input,production:tail(50,50)});
 assert.equal(enough.joint_maximum_demand_status,'unbounded');assert.equal(enough.joint_maximum_demand_multiplier,null);near(enough.joint_minimum_initial_storage_m3,80);
});
test('a genuine zero upper bound remains bounded zero, not an infeasibility sentinel',()=>{
 const m=margin(fixture({production:tail(50,50),demand:100,capacity:1000,reserve:80,initial:100,target:200,startHour:22,scenario:{demand_multiplier:0}}));
 assert.equal(m.joint_maximum_demand_status,'bounded');assert.equal(m.joint_maximum_demand_multiplier,0);
});
test('spill cannot be carried into the final hour to satisfy target',()=>{
 const input=fixture({production:tail(100,0),demand:tail(0,100),capacity:100,reserve:20,initial:100,target:80,startHour:22,scenario:{demand_multiplier:.1}});
 const m=margin(input);near(m.maximum_demand_multiplier,.8);near(m.joint_maximum_demand_multiplier,.2);near(m.joint_minimum_initial_storage_m3,20);
 assert.deepEqual(m.joint_maximum_demand_limits.map(x=>[x.constraint,x.interval_start_hour,x.hour]),[['terminal_target',23,24]]);
 const impossible=margin({...input,scenario:{demand_multiplier:.3}});
 assert.equal(impossible.joint_minimum_initial_status,'capacity_insufficient');assert.equal(impossible.joint_minimum_initial_storage_m3,null);
 assert.ok(impossible.joint_minimum_initial_limits.some(x=>x.constraint==='storage_capacity'&&x.hour===23&&x.required_storage_m3===110));
});
test('fractional outage and production multiplier preserve exact remaining production',()=>{
 const input=fixture({capacity:1000,reserve:50,initial:200,target:200,startHour:22,scenario:{outage:{start_hour:22.25,duration_hours:.5}}});
 const m=margin(input);near(m.joint_maximum_demand_multiplier,.75);near(m.joint_minimum_initial_storage_m3,250);
 const derated=margin({...input,scenario:{...input.scenario,production_multiplier:.8,demand_multiplier:.5}});
 near(derated.joint_maximum_demand_multiplier,.6);near(derated.joint_minimum_initial_storage_m3,180);
});
test('hourly demand arrays and a zero current multiplier do not alter the maximum multiplier denominator',()=>{
 const input=fixture({demand:tail(50,150),capacity:1000,reserve:50,initial:200,target:200,startHour:22,scenario:{production_multiplier:.5,demand_multiplier:.75}});
 const m=margin(input);near(m.joint_maximum_demand_multiplier,.5);near(m.joint_minimum_initial_storage_m3,250);
 const zero=margin({...input,scenario:{...input.scenario,demand_multiplier:0}});
 near(zero.joint_maximum_demand_multiplier,.5);near(zero.joint_minimum_initial_storage_m3,100);
 assert.ok(!Object.keys(zero).some(k=>/headroom|percent/.test(k)));
});
test('hour 24 has no controllable future; only the current storage predicates remain',()=>{
 const input=fixture({startHour:24,capacity:1000,reserve:80,initial:200,target:250});
 const m=margin(input);assert.equal(m.joint_maximum_demand_status,'infeasible_even_without_demand');assert.equal(m.joint_maximum_demand_multiplier,null);near(m.joint_minimum_initial_storage_m3,250);
 assert.equal(margin({...input,initial:300}).joint_maximum_demand_status,'unbounded');
 assert.equal(margin({...input,initial:70}).joint_maximum_demand_status,'initial_below_reserve');
});
test('tied reserve and terminal limits are retained with their actual boundary',()=>{
 const m=margin(fixture({capacity:1000,reserve:80,initial:200,target:80,startHour:22}));
 near(m.joint_maximum_demand_multiplier,1.6);
 assert.deepEqual(m.joint_maximum_demand_limits.map(x=>[x.constraint,x.hour]),[['reserve',24],['terminal_target',24]]);
 assert.ok(m.joint_minimum_initial_limits.some(x=>x.constraint==='terminal_target'&&x.hour===24));
 assert.ok(m.joint_minimum_initial_limits.some(x=>x.constraint==='reserve'&&x.hour===22));
});
test('an intermediate reserve can bind before a lower terminal requirement',()=>{
 const input=fixture({production:tail(0,200),demand:tail(100,100),capacity:1000,reserve:100,initial:200,target:0,startHour:22});
 const m=margin(input);near(m.joint_maximum_demand_multiplier,1);near(m.joint_minimum_initial_storage_m3,200);
 assert.deepEqual(m.joint_maximum_demand_limits.map(x=>[x.constraint,x.hour]),[['reserve',23]]);
});
test('all original reserve-only fields and replay results remain byte-equivalent across seeded inputs',()=>{
 let seed=38107;const random=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296);
 for(let i=0;i<120;i++){
  const capacity=500+Math.floor(random()*5000),startHour=Math.floor(random()*25),input=fixture({production:Array.from({length:24},()=>Math.floor(random()*500)),demand:Array.from({length:24},()=>Math.floor(random()*300)),capacity,reserve:capacity*.2,initial:capacity*random(),target:capacity*random(),startHour,scenario:{production_multiplier:.5+random()*.5,demand_multiplier:random()*2,outage:{start_hour:23.25,duration_hours:.5}}});
  const after=replayPlan(input);
  for(const key of Object.keys(after.margins))if(key.startsWith('joint_'))delete after.margins[key];
  assert.equal(createHash('sha256').update(JSON.stringify(after)).digest('hex'),legacy.hashes[i]);
 }
});
test('finite inputs cannot silently turn an unrepresentable demand bound into an unbounded claim',()=>{
 assert.throws(()=>margin(fixture({production:Array(24).fill(0),demand:1e-300,capacity:1e100,reserve:0,initial:1e100,target:0})),/finite numeric range/);
});
test('a required inventory outside capacity is never returned as a usable starting value',()=>{
 const m=margin(fixture({production:Array(24).fill(0),demand:1e-9,capacity:100,reserve:20,initial:100,target:100,startHour:23}));
 assert.equal(m.joint_minimum_initial_storage_m3,null);assert.equal(m.joint_minimum_initial_status,'capacity_insufficient');
});
test('directed maximum and minimum boundaries pass exactly and fail on the wrong side',()=>{
 const cases=[fixture(),fixture({production:tail(100,0),demand:tail(0,100),capacity:100,reserve:20,initial:100,target:80,startHour:22,scenario:{demand_multiplier:.1}}),fixture({capacity:1000,reserve:50,initial:200,target:200,startHour:22,scenario:{outage:{start_hour:22.25,duration_hours:.5}}}),fixture({startHour:24,capacity:1000,reserve:80,initial:300,target:250})];
 const feasible=input=>{const t=replayPlan(input).totals;return t.unmet_m3<=1e-7&&t.max_reserve_deficit_m3<=1e-7&&t.terminal_deficit_m3<=1e-7;};
 for(const input of cases){
  const m=margin(input),max=m.joint_maximum_demand_multiplier,min=m.joint_minimum_initial_storage_m3;
  if(max!==null){const at=x=>({...input,scenario:{...input.scenario,demand_multiplier:x}});assert.ok(feasible(at(max)));assert.ok(feasible(at(max-1e-5)));assert.equal(feasible(at(max+1e-5)),false);}
  const at=x=>({...input,scenario:{...input.scenario,initial_storage_m3:x}});assert.ok(feasible(at(min)));assert.ok(feasible(at(min+1e-4)));assert.equal(feasible(at(min-1e-4)),false);
 }
});
test('huge finite bounds remain bounded and subnormal demand cannot masquerade as absent demand',()=>{
 const input=fixture({production:Array(24).fill(0),demand:1e-200,capacity:1e100,reserve:0,initial:1e100,target:0});
 const m=margin(input);assert.equal(m.joint_maximum_demand_status,'bounded');assert.ok(Number.isFinite(m.joint_maximum_demand_multiplier));assert.ok(m.joint_maximum_demand_multiplier>7e298);
 assert.throws(()=>margin({...input,demand:Number.MIN_VALUE}),/finite numeric range/);
});
