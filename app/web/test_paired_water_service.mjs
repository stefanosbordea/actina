import test from 'node:test';
import assert from 'node:assert/strict';
import {performance} from 'node:perf_hooks';
import {readFileSync} from 'node:fs';
import {waterServiceModel,replayPlan} from './public/plan-resilience.mjs';
import {compareWaterService,waterProductionBudget} from './public/paired-water-service.mjs';

const pad=values=>[...values,...Array(24-values.length).fill(0)];
const times=Array.from({length:24},(_,hour)=>new Date(Date.UTC(2026,6,1,hour)).toISOString());
function pair({a,b,demand,initial=0,capacity=2,reserve=0,target=0,scenario={},startHour=0}){
 const shared={times,demand:pad(demand),initial,capacity,reserve,target,scenario,startHour};
 return {original:waterServiceModel({...shared,production:pad(a)}),revised:waterServiceModel({...shared,production:pad(b)})};
}
const check=(value,numerator,denominator=1)=>assert.deepEqual(value.exact,{numerator:String(numerator),denominator:String(denominator)});
function direct({end=1,start=0,initial=0,capacity=1,reserve=0,target=0,production=0,demand=0}={}){
 return {start_epoch:0,start_hour:start,end_hour:end,initial,capacity,reserve,target,segments:start===end?[]:[{from:start,to:end,production,demand}]};
}
const clone=value=>JSON.parse(JSON.stringify(value));

test('production budget matches 98 independently frozen exact fixtures without changing supplied models',()=>{
 const fixtures=JSON.parse(readFileSync(new URL('../results/water-budget-certificate/independent-inputs-v1.json',import.meta.url),'utf8'));
 for(const c of fixtures.cases){const before=JSON.stringify(c.input);if(c.expected.accepted)assert.deepEqual(waterProductionBudget(c.input),c.expected.certificate,c.id);else assert.throws(()=>waterProductionBudget(c.input),undefined,c.id);assert.equal(JSON.stringify(c.input),before,c.id);}
});

test('shared model exposes effective normalized rates without changing ordinary replay or inputs',()=>{
 const input={times,production:pad([8]),demand:pad([12]),initial:1,capacity:10,reserve:0,target:0,scenario:{production_multiplier:.5,demand_multiplier:.25,outage:{start_hour:.25,duration_hours:.5}}};
 const saved=JSON.stringify(input),before=replayPlan(input),model=waterServiceModel(input);
 assert.deepEqual(model.segments.slice(0,3),[{from:0,to:.25,production:4,demand:3},{from:.25,to:.75,production:0,demand:3},{from:.75,to:1,production:4,demand:3}]);assert.deepEqual(replayPlan(input),before);assert.equal(JSON.stringify(input),saved);assert.equal(model.start_epoch,Date.parse(times[0]));
});
test('new effective-rate gate rejects positive normalization underflow without changing ordinary replay',()=>{
 const input={times,production:pad([1e-200]),demand:pad([1e-200]),initial:0,capacity:1,reserve:0,target:0,scenario:{production_multiplier:1e-200}};
 assert.equal(replayPlan(input).totals.available_production_m3,0);assert.throws(()=>waterServiceModel(input),/underflows/);input.scenario={demand_multiplier:1e-200};assert.throws(()=>waterServiceModel(input),/underflows/);input.scenario={production_multiplier:0,demand_multiplier:0};assert.doesNotThrow(()=>waterServiceModel(input));
});
test('identical alternatives retain exact zero summaries and no witnesses',()=>{
 const args=pair({a:[1,0,2],b:[1,0,2],demand:[1,1,1],initial:1,reserve:1,target:1}),before=JSON.stringify(args),r=compareWaterService(args);
 assert.equal(r.status,'no_modeled_regression');assert.ok(Object.values(r.criteria).every(Boolean));check(r.delivery.shifted_shortfall_m3,0);check(r.reserve.max_added_deficit_m3,0);check(r.end_stock.delta_m3,0);assert.equal(r.delivery.interval_count,0);assert.equal(r.reserve.first,null);assert.equal(r.delivery.maximum,null);assert.equal(JSON.stringify(args),before);
});
test('equal aggregates and first events do not excuse a newly underserved hour',()=>{
 const r=compareWaterService(pair({a:[0,1,0],b:[0,0,1],demand:[2,1,1],initial:1,capacity:2,reserve:1,target:1}));
 assert.equal(r.status,'regression_detected');assert.deepEqual(r.criteria,{delivery_no_worse:false,reserve_no_worse:true,end_stock_no_lower:true});check(r.delivery.shifted_shortfall_m3,1);check(r.delivery.duration_hours,1);check(r.delivery.first.start_hour,1);check(r.delivery.first.end_hour,2);check(r.end_stock.delta_m3,0);
});
test('identical hourly unmet totals can hide a positive within-hour service regression',()=>{
 const r=compareWaterService(pair({a:[2,0],b:[0,2],demand:[0,4]}));
 check(r.delivery.shifted_shortfall_m3,1);check(r.delivery.duration_hours,1,2);check(r.delivery.max_added_unserved_rate_m3_h,2);check(r.delivery.first.start_hour,1);check(r.delivery.first.end_hour,3,2);assert.equal(r.delivery.interval_count,1);assert.equal(r.criteria.delivery_no_worse,false);assert.equal(r.criteria.reserve_no_worse,true);
});
test('a common fractional outage retains the returned late-quarter shortfall',()=>{
 const r=compareWaterService(pair({a:[0,1],b:[.75,0],demand:[0,1],capacity:1,scenario:{outage:{start_hour:1.5,duration_hours:.25}}}));
 check(r.delivery.shifted_shortfall_m3,1,4);check(r.delivery.duration_hours,1,4);check(r.delivery.first.start_hour,7,4);check(r.delivery.first.end_hour,2);check(r.end_stock.delta_m3,0);
});
test('reserve sign crossing and interior peak are exact despite improved final stock',()=>{
 const r=compareWaterService(pair({a:[3,0],b:[1.5,2],demand:[3,3],capacity:6,reserve:1,initial:3}));
 assert.deepEqual(r.criteria,{delivery_no_worse:true,reserve_no_worse:false,end_stock_no_lower:true});assert.equal(r.reserve.interval_count,1);check(r.reserve.duration_hours,1,4);check(r.reserve.max_added_deficit_m3,1,6);check(r.reserve.first.start_hour,3,2);check(r.reserve.first.end_hour,7,4);check(r.reserve.maximum.peak_hour,5,3);check(r.reserve.maximum.original_deficit_m3,0);check(r.reserve.maximum.revised_deficit_m3,1,6);assert.equal(r.reserve.first.start_open,true);assert.equal(r.reserve.first.end_open,true);check(r.end_stock.delta_m3,1,2);
});
test('meeting the terminal target does not hide spending more final stock',()=>{
 const r=compareWaterService(pair({a:[1],b:[0],demand:[1],initial:1}));
 assert.deepEqual(r.criteria,{delivery_no_worse:true,reserve_no_worse:true,end_stock_no_lower:false});check(r.end_stock.original_m3,1);check(r.end_stock.revised_m3,0);check(r.end_stock.delta_m3,-1);
});
test('a supplied shift can preserve all modeled service and stock conditions',()=>{
 const r=compareWaterService(pair({a:[1,1],b:[0,2],demand:[1,1],initial:1,capacity:1,target:1}));assert.equal(r.status,'no_modeled_regression');check(r.delivery.shifted_shortfall_m3,0);check(r.reserve.max_added_deficit_m3,0);check(r.end_stock.delta_m3,0);
});
test('relative preservation never certifies absolute adequacy',()=>{
 const r=compareWaterService(pair({a:[0],b:[0],demand:[1],capacity:1,reserve:.5,target:.5}));assert.equal(r.status,'no_modeled_regression');assert.match(r.scope.join(' '),/Both plans may still undersupply demand/);check(r.end_stock.original_m3,0);check(r.end_stock.revised_m3,0);
});
test('positive regressions below existing event thresholds remain positive',()=>{
 const tiny=1e-12,r=compareWaterService(pair({a:[tiny],b:[0],demand:[tiny],capacity:1}));assert.equal(r.criteria.delivery_no_worse,false);assert.ok(BigInt(r.delivery.shifted_shortfall_m3.exact.numerator)>0n);assert.equal(r.delivery.shifted_shortfall_m3.value,tiny);check(r.reserve.max_added_deficit_m3,0);
});
test('positive volume below numeric display range keeps its original rational proof',()=>{
 const args={original:direct({end:.5,production:Number.MIN_VALUE,demand:Number.MIN_VALUE}),revised:direct({end:.5,demand:Number.MIN_VALUE})},r=compareWaterService(args);
 assert.equal(r.status,'regression_detected');check(r.delivery.shifted_shortfall_m3,1n,1n<<1075n);assert.equal(r.delivery.shifted_shortfall_m3.value,null);assert.equal(r.delivery.max_added_unserved_rate_m3_h.value,Number.MIN_VALUE);assert.equal(r.reserve.max_added_deficit_m3.value,0);
});
test('finite supplied rates with out-of-range total volume retain exact overflow evidence',()=>{
 const rate=Number.MAX_VALUE,r=compareWaterService({original:direct({end:8784,production:rate,demand:rate}),revised:direct({end:8784,demand:rate})});
 assert.equal(r.status,'regression_detected');assert.equal(r.delivery.shifted_shortfall_m3.value,null);assert.equal(r.delivery.max_added_unserved_rate_m3_h.value,rate);assert.ok(BigInt(r.delivery.shifted_shortfall_m3.exact.numerator)>BigInt(rate));check(r.delivery.duration_hours,8784);check(r.end_stock.delta_m3,0);
});
test('arbitrary equal-rate segment splits preserve counts and actionable witnesses',()=>{
 const original=direct({end:2,production:1,demand:1}),revised=direct({end:2,demand:1}),expected=compareWaterService({original,revised});
 original.segments=[{from:0,to:.5,production:1,demand:1},{from:.5,to:2,production:1,demand:1}];revised.segments=[{from:0,to:1,production:0,demand:1},{from:1,to:2,production:0,demand:1}];const actual=compareWaterService({original,revised});assert.deepEqual(actual,expected);assert.equal(actual.delivery.interval_count,1);check(actual.delivery.first.end_hour,2);
});
test('touching loss pieces with different rates count once while witness rates retain their interval',()=>{
 const original=direct({end:2,production:1,demand:1}),revised=direct({end:2,demand:1});revised.segments=[{from:0,to:1,production:0,demand:1},{from:1,to:2,production:.5,demand:1}];const r=compareWaterService({original,revised});assert.equal(r.delivery.interval_count,1);check(r.delivery.duration_hours,2);check(r.delivery.shifted_shortfall_m3,3,2);check(r.delivery.first.end_hour,1);check(r.delivery.first.added_unserved_rate_m3_h,1);
});
test('restart offsets and a zero-duration remaining horizon are retained exactly',()=>{
 const p=pad([]);p[10]=1;const args=pair({a:p,b:pad([]),demand:p,startHour:10,capacity:1}),r=compareWaterService(args);check(r.horizon.start_hour,10);check(r.horizon.duration_hours,14);check(r.delivery.first.start_hour,10);assert.equal(r.horizon.start_epoch,Date.parse(times[0]));
 const model=waterServiceModel({times,production:pad([]),demand:0,initial:1,capacity:2,reserve:0,target:1,startHour:24});assert.equal(model.segments.length,0);const empty=compareWaterService({original:model,revised:model});assert.equal(empty.status,'no_modeled_regression');check(empty.horizon.duration_hours,0);
});
test('exact physical stock keeps a tiny deficit beside a huge common tank level',()=>{
 const original=direct({end:2,initial:1e100,capacity:1e100,reserve:1e100,target:0}),revised=clone(original);original.segments=[{from:0,to:1,production:1,demand:1},{from:1,to:2,production:0,demand:0}];revised.segments=[{from:0,to:1,production:0,demand:1},{from:1,to:2,production:1,demand:0}];const r=compareWaterService({original,revised});assert.equal(r.criteria.delivery_no_worse,true);assert.equal(r.criteria.reserve_no_worse,false);check(r.reserve.max_added_deficit_m3,1);check(r.end_stock.delta_m3,0);
});
test('malformed and incomparable segment models reject before a favorable result',()=>{
 const original=direct({end:2,production:1,demand:1});
 const mutations=[m=>{m.initial=.5;},m=>{m.capacity=2;},m=>{m.reserve=.5;},m=>{m.target=.5;},m=>{m.start_epoch=1;},m=>{m.end_hour=1;},m=>{m.segments[0].demand=2;},m=>{m.segments[0].production=-1;},m=>{m.segments[0].production=Infinity;},m=>{m.segments[0].to=NaN;},m=>{m.segments[0].from=.5;},m=>{m.segments.push({...m.segments[0]});},m=>{m.segments=[];},m=>{m.extra=1;},m=>{delete m.target;},m=>{m.segments[0].extra=1;},m=>{m.start_epoch=.5;}];
 for(const mutate of mutations){const revised=clone(original);mutate(revised);assert.throws(()=>compareWaterService({original,revised}),/Paired water service/);}
 assert.throws(()=>compareWaterService({original:direct({end:8785}),revised:direct({end:8785})}),/8,784/);
 const excessive=direct();excessive.segments=Array(26353).fill(excessive.segments[0]);assert.throws(()=>compareWaterService({original:excessive,revised:excessive}),/26,352/);
 const changed=clone(original);changed.segments=[{from:0,to:1,production:1,demand:1},{from:1,to:2,production:1,demand:0}];assert.throws(()=>compareWaterService({original,revised:changed}),/Demanded rates/);
});
test('maximum 8784-hour model uses continuous stock carry and bounded summary output',()=>{
 const count=8784,original=direct({end:count,initial:1,capacity:1,target:1}),revised=clone(original);
 original.segments=Array.from({length:count},(_,hour)=>({from:hour,to:hour+1,production:1,demand:1}));revised.segments=original.segments.map((segment,hour)=>({...segment,production:hour%2?2:0}));
 const started=performance.now(),result=compareWaterService({original,revised}),elapsed_ms=performance.now()-started,output_bytes=Buffer.byteLength(JSON.stringify(result));assert.equal(result.status,'no_modeled_regression');check(result.end_stock.original_m3,1);check(result.end_stock.revised_m3,1);check(result.horizon.duration_hours,count);assert.ok(output_bytes<12000);assert.equal(result.segments,undefined);console.log(JSON.stringify({workload:'8784 supplied hourly segments per plan; alternating depletion/refill, one initial stock',hours:count,segments:count*2,elapsed_ms,output_bytes,status:result.status}));
});
