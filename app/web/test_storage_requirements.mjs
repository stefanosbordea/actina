import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {performance} from 'node:perf_hooks';
import {storageRequirements, assessWaterService, waterProductionBudget} from './public/paired-water-service.mjs';
import {replaySequence} from './public/plan-sequence.mjs';

const fixturesPath=new URL('../results/storage-requirements/analytical-fixtures-v1.json',import.meta.url);
const fixtureBytes=readFileSync(fixturesPath),fixtures=JSON.parse(fixtureBytes).fixtures;
const fixture=id=>structuredClone(fixtures.find(value=>value.id===id).model);
const fraction=(value,expected)=>{
 const [numerator,denominator='1']=String(expected).split('/');
 assert.deepEqual(value.exact,{numerator,denominator});
};
const model=(segments=[],overrides={})=>({start_epoch:0,start_hour:0,end_hour:segments.at(-1)?.to??0,initial:0,capacity:10,reserve:0,target:0,segments,...overrides});
const hour=(from,production,demand)=>({from,to:from+1,production,demand});
const times=block=>Array.from({length:24},(_,h)=>new Date(Date.UTC(2026,6,1)+3600000*(block*24+h)).toISOString());

test('storage bounds match the independently frozen analytical expectations without mutating input',()=>{
 assert.equal(createHash('sha256').update(fixtureBytes).digest('hex'),'cc2947d01142e75951de6db8f4168aca1cf69933c2e664047d3798c1f608d034');
 const check=(actual,expected)=>{for(const [key,value] of Object.entries(expected))if(typeof value==='string')fraction(actual[key],value);else if(typeof value==='boolean')assert.equal(actual[key],value);else check(actual[key],value);};
 for(const value of fixtures){const before=JSON.stringify(value.model),result=storageRequirements(value.model);check(result,value.expected);assert.equal(JSON.stringify(value.model),before,value.id);assert.equal(result.kind,'fixed_plan_storage_requirements');}
});

test('sufficient total production does not hide a starting-water shortage or invite capacity-only repair',()=>{
 const input=fixture('initial_shortage'),result=storageRequirements(input);
 assert.equal(waterProductionBudget(input).status,'budget_not_excluded');
 fraction(result.initial_shortfall_m3,1);fraction(result.with_spill.capacity_shortfall_m3,0);
 assert.equal(result.with_spill.feasible,false);assert.equal(storageRequirements({...input,capacity:100}).with_spill.feasible,false);
 assert.equal(assessWaterService({...input,initial:2}).status,'modeled_requirements_met');
 const witness=result.witnesses.initial;assert.equal(witness.constraint,'reserve');fraction(witness.start_hour,0);fraction(witness.end_hour,1);fraction(witness.net_supply_m3,-1);fraction(witness.required_storage_m3,2);
});

test('more starting water cannot repair a later storage bottleneck after the tank fills',()=>{
 const input=fixture('capacity_shortage'),result=storageRequirements(input);
 assert.equal(waterProductionBudget(input).status,'budget_not_excluded');fraction(result.initial_shortfall_m3,0);fraction(result.with_spill.capacity_shortfall_m3,2);
 for(const initial of [1,1.5,2])assert.equal(storageRequirements({...input,initial}).with_spill.feasible,false);
 const witness=result.witnesses.with_spill;assert.equal(witness.constraint,'reserve');fraction(witness.start_hour,1);fraction(witness.end_hour,2);fraction(witness.net_supply_m3,-3);fraction(witness.required_storage_m3,4);
 assert.equal(assessWaterService({...input,capacity:4}).status,'modeled_requirements_met');
});

test('a starting-water top-up includes the capacity it needs to avoid spilling unchanged production',()=>{
 const input=fixture('topup_causes_no_spill_capacity_shortage'),result=storageRequirements(input);
 fraction(result.minimum_initial_m3,2);fraction(result.without_spill.capacity_shortfall_m3,0);fraction(result.without_spill.minimum_capacity_after_initial_topup_m3,3);fraction(result.without_spill.capacity_shortfall_after_initial_topup_m3,1);
 assert.equal(storageRequirements({...input,initial:2}).with_spill.feasible,true);assert.equal(storageRequirements({...input,initial:2}).without_spill.feasible,false);
 assert.equal(storageRequirements({...input,initial:2,capacity:3}).without_spill.feasible,true);
});

test('permitted overflow and no-spill requirements remain explicitly different',()=>{
 const input=fixture('spill_changes_capacity'),result=storageRequirements(input);
 assert.equal(assessWaterService(input).status,'modeled_requirements_met');assert.equal(result.with_spill.feasible,true);assert.equal(result.without_spill.feasible,false);
 fraction(result.with_spill.minimum_capacity_m3,3);fraction(result.without_spill.minimum_capacity_m3,5);
 const witness=result.witnesses.without_spill;assert.equal(witness.constraint,'no_spill');fraction(witness.start_hour,0);fraction(witness.end_hour,1);fraction(witness.net_supply_m3,4);fraction(witness.required_storage_m3,5);
 assert.match(result.scope.join(' '),/not reduced production or permission to discharge/);
});

test('the terminal target has a distinct peak-to-end witness after overflow',()=>{
 const input=fixture('budget_passes_target_fails'),result=storageRequirements(input),witness=result.witnesses.with_spill;
 assert.equal(waterProductionBudget(input).status,'budget_not_excluded');assert.equal(witness.constraint,'terminal_target');fraction(witness.start_hour,1);fraction(witness.end_hour,2);fraction(witness.net_supply_m3,-2);fraction(witness.required_storage_m3,5);
 assert.equal(assessWaterService(input).criteria.terminal_target_met,false);
});

test('bounds accept exact equality and reject a representable shortfall on either side',()=>{
 const input=fixture('boundary_equality');
 for(const change of [{},{capacity:2.125},{initial:1.125,capacity:2.125}])assert.equal(storageRequirements({...input,...change}).without_spill.feasible,true);
 assert.equal(storageRequirements({...input,capacity:1.875}).with_spill.feasible,false);
 assert.equal(storageRequirements({...input,initial:.875}).with_spill.feasible,false);
 fraction(storageRequirements({...input,capacity:1.875}).with_spill.capacity_shortfall_m3,'1/8');
});

test('earliest witnesses survive repeated peaks, flat segments and equivalent segment splits',()=>{
 const input=model([hour(5,2,1),hour(6,0,1),hour(7,2,1),hour(8,0,1)],{start_hour:5,initial:1,capacity:2,reserve:1,target:1});
 const result=storageRequirements(input);assert.equal(result.witnesses.initial.constraint,'reserve');fraction(result.witnesses.initial.end_hour,5);
 fraction(result.witnesses.with_spill.start_hour,6);fraction(result.witnesses.with_spill.end_hour,7);fraction(result.witnesses.without_spill.end_hour,6);
 const split=structuredClone(input);split.segments=split.segments.flatMap(s=>[{...s,to:s.from+.5},{...s,from:s.from+.5}]);assert.deepEqual(storageRequirements(split),result);
 const flat=storageRequirements(model([hour(0,1,1)],{initial:2,capacity:2,reserve:2,target:2}));assert.equal(flat.witnesses.with_spill.constraint,'reserve');fraction(flat.witnesses.with_spill.end_hour,0);fraction(flat.witnesses.without_spill.end_hour,0);
});

test('stored initial water can bind capacity independently of service constraints',()=>{
 const result=storageRequirements(model([hour(0,1,1)],{initial:4,capacity:5}));
 assert.equal(result.witnesses.with_spill.constraint,'stored_initial');fraction(result.witnesses.with_spill.start_hour,0);fraction(result.witnesses.with_spill.end_hour,0);fraction(result.with_spill.minimum_capacity_m3,4);
});

test('fractional restart and zero-duration models preserve original witness coordinates',()=>{
 const restart=storageRequirements(fixture('fractional_restart'));fraction(restart.horizon.start_hour,5);fraction(restart.horizon.duration_hours,1);fraction(restart.witnesses.initial.end_hour,'11/2');fraction(restart.witnesses.without_spill.end_hour,6);
 const empty=storageRequirements(model([],{start_hour:7,end_hour:7,initial:1,capacity:3,target:2}));fraction(empty.horizon.duration_hours,0);fraction(empty.minimum_initial_m3,2);assert.equal(empty.witnesses.initial.constraint,'terminal_target');fraction(empty.witnesses.initial.start_hour,7);fraction(empty.witnesses.initial.end_hour,7);assert.equal(empty.with_spill.feasible,false);
});

test('tiny binary64 residuals are retained exactly rather than rounded to feasibility',()=>{
 const result=storageRequirements(fixture('binary64_positive_residual'));
 fraction(result.without_spill.capacity_shortfall_m3,'1/36028797018963968');assert.equal(result.without_spill.minimum_capacity_m3.value,1);assert.equal(result.without_spill.feasible,false);
 assert.equal(result.with_spill.feasible,true);
});

test('positive requirements below display range and overflowing requirements keep exact evidence',()=>{
 const small=storageRequirements(model([{from:0,to:.5,production:0,demand:Number.MIN_VALUE}],{capacity:1}));
 assert.equal(small.minimum_initial_m3.value,null);fraction(small.minimum_initial_m3,`1/${1n<<1075n}`);assert.equal(small.with_spill.feasible,false);assert.equal(small.initial_shortfall_m3.value,null);
 const large=storageRequirements(model([{from:0,to:2,production:0,demand:Number.MAX_VALUE}],{capacity:Number.MAX_VALUE}));
 assert.equal(large.minimum_initial_m3.value,null);fraction(large.minimum_initial_m3,BigInt(Number.MAX_VALUE)*2n);fraction(large.with_spill.capacity_shortfall_m3,BigInt(Number.MAX_VALUE));assert.equal(large.with_spill.feasible,false);
});

test('continuous integration carries one initial stock and one final target across day boundaries',()=>{
 const input={blocks:[0,1].map(i=>({times:times(i),production:Array(24).fill(0),demand:1})),capacity:100,initial:30,reserve:0,target:0,unitCapacity:2},before=JSON.stringify(input);
 const result=replaySequence(input);fraction(result.storage_requirements.minimum_initial_m3,48);fraction(result.storage_requirements.initial_shortfall_m3,18);fraction(result.storage_requirements.witnesses.initial.end_hour,48);
 assert.equal(result.blocks.some(block=>Object.hasOwn(block,'storage_requirements')),false);assert.equal(JSON.stringify(input),before);
});

test('continuous storage bounds use effective rates and a subhour outage crossing midnight',()=>{
 const input={blocks:[0,1].map(i=>({times:times(i),production:Array(24).fill(4),demand:1})),capacity:100,initial:1,reserve:1,target:0,unitCapacity:4,scenario:{production_multiplier:.5},outages:[{start:'2026-07-01T23:30:00Z',end:'2026-07-02T00:30:00Z'}]};
 const result=replaySequence(input).storage_requirements;
 fraction(result.minimum_initial_m3,1);fraction(result.with_spill.minimum_capacity_m3,2);fraction(result.without_spill.minimum_capacity_m3,47);
 fraction(result.witnesses.with_spill.start_hour,'47/2');fraction(result.witnesses.with_spill.end_hour,'49/2');fraction(result.witnesses.with_spill.net_supply_m3,-1);
});

test('malformed models reject before any favorable capacity certificate',()=>{
 const base=model([hour(0,1,1)],{capacity:2});
 const mutations=[m=>{m.capacity=0;},m=>{m.initial=3;},m=>{m.reserve=3;},m=>{m.target=3;},m=>{m.start_epoch=.5;},m=>{m.start_hour=-1;},m=>{m.end_hour=8785;},m=>{m.segments[0].from=.5;},m=>{m.segments[0].to=0;},m=>{m.segments[0].production=Infinity;},m=>{m.segments[0].demand=-1;},m=>{m.segments=[];},m=>{m.segments[0].extra=0;},m=>{m.extra=1;}];
 for(const mutate of mutations){const input=structuredClone(base);mutate(input);assert.throws(()=>storageRequirements(input),/Paired water service/);}
 assert.throws(()=>storageRequirements({...base,segments:Array(26353).fill(base.segments[0])}),/26,352/);
});

test('maximum-duration review retains a compact certificate and the first critical interval',()=>{
 const count=8784,input=model(Array.from({length:count},(_,h)=>hour(h,h%2?0:2,1)),{initial:1,capacity:2,reserve:1,target:1});
 const started=performance.now(),result=storageRequirements(input),elapsed_ms=performance.now()-started,output_bytes=Buffer.byteLength(JSON.stringify(result));
 assert.equal(result.without_spill.feasible,true);fraction(result.witnesses.with_spill.start_hour,1);fraction(result.witnesses.with_spill.end_hour,2);assert.ok(output_bytes<12000);
 console.log(JSON.stringify({workload:'8784 unchanged hourly production and demand segments, one initial stock',elapsed_ms,output_bytes,status:'requirements_met'}));
});

// The no-spill boundary can differ while rounded totals look identical.
test('capacity diagnosis retains a binary64-scale gap instead of rounding it away',async()=>{
 const {storageRequirementFinding}=await import('./public/plan-sequence-ui.mjs');
 const fixtures=JSON.parse(readFileSync(new URL('../results/storage-requirements/analytical-fixtures-v1.json',import.meta.url)));
 const fixture=(Array.isArray(fixtures)?fixtures:fixtures.fixtures).find(item=>item.id==='binary64_positive_residual');
 const result=storageRequirements(fixture.model);
 assert.equal(result.without_spill.minimum_capacity_m3.value,fixture.model.capacity);
 assert.match(storageRequirementFinding(result),/2\.776e-17 m³/);
 assert.match(storageRequirementFinding(result),/does not establish a physical shortage/);
});


test('starting-water diagnosis qualifies a binary64-scale gap',async()=>{
 const {storageRequirementFinding}=await import('./public/plan-sequence-ui.mjs');
 const result=storageRequirements(model([hour(0,.3,.1),hour(1,0,.2)],{initial:1,capacity:2,reserve:0,target:1}));
 fraction(result.initial_shortfall_m3,'1/36028797018963968');
 assert.match(storageRequirementFinding(result),/Starting-water gap: 2\.776e-17 m³/);
 assert.match(storageRequirementFinding(result),/does not establish a physical shortage/);
 assert.doesNotMatch(storageRequirementFinding(result),/more starting water is needed/);
});
