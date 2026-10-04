import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {evaluateOperatingEnvelope} from './operating-envelope.mjs';

const evidence=new URL('../results/operating-envelope/',import.meta.url);
const fixtureBytes=readFileSync(new URL('protocol-fixtures.json',evidence));
const fixtures=JSON.parse(fixtureBytes).fixtures;
const input=id=>structuredClone(fixtures.find(f=>f.id===id).input);
const base=()=>input('flat_matched_water_control');
const fraction=(actual,expected)=>{
 const [numerator,denominator='1']=String(expected).split('/');
 assert.deepEqual(actual.exact,{numerator,denominator});
};
const first=(result,check)=>result.checks[check].violations[0];
const statuses=result=>Object.fromEntries(Object.entries(result.checks).map(([key,value])=>[key,value.status]));
const quantity=value=>`${value.exact.numerator}/${value.exact.denominator}`;
const tailSummary=result=>result.tail_obligations.map(t=>[t.state,quantity(t.at_hour),quantity(t.remaining_min_hours),quantity(t.remaining_max_hours)]);
const states=(values,start=0)=>values.map((state,i)=>({from_hour:start+i,to_hour:start+i+1,state,producing:state==='online'}));

test('operating-envelope expectations remain the independently frozen protocol',()=>{
 assert.equal(createHash('sha256').update(fixtureBytes).digest('hex'),'84dfa25fe16b0cdf11f20db11625590737fec1035cfac2463ca367ff21afe40e');
 assert.equal(createHash('sha256').update(readFileSync(new URL('PROTOCOL.md',evidence))).digest('hex'),'d52999f323e1da379b355ef19d5b9a7636230677fe0ed334e09255a19076b46d');
 assert.equal(fixtures.filter(f=>f.expected).length,23);
 assert.equal(fixtures.filter(f=>f.expected_error).length,5);
});

for(const fixture of fixtures)test(`operating-envelope frozen: ${fixture.id}`,()=>{
 const before=structuredClone(fixture.input);
 if(fixture.expected_error){assert.throws(()=>evaluateOperatingEnvelope(fixture.input));assert.deepEqual(fixture.input,before);return;}
 const result=evaluateOperatingEnvelope(fixture.input),expected=fixture.expected;
 assert.deepEqual(fixture.input,before);
 assert.equal(result.kind,'supplied_unit_operating_envelope_review');
 assert.equal(result.schema,1);
 assert.equal(result.status,expected.status);
 assert.equal(result.decision,expected.decision);
 assert.deepEqual(statuses(result),expected.checks);
 assert.equal(result.tail_obligations.length,expected.tail_obligations.length);
 for(const [index,tail] of expected.tail_obligations.entries())for(const [key,value] of Object.entries(tail)){
  if(key==='state')assert.equal(result.tail_obligations[index][key],value);else fraction(result.tail_obligations[index][key],value);
 }
 for(const [name,check] of Object.entries(result.checks)){
  assert.ok(Array.isArray(check.reasons),name);assert.ok(Array.isArray(check.violations),name);
  assert.equal(check.violations.length>0,check.status==='violated',name);
  for(const witness of check.violations){
   assert.ok(BigInt(witness.excess_or_shortfall.exact.numerator)>0n);
   assert.ok(witness.sources.length>0);
   for(const source of witness.sources){
    assert.ok(source.startsWith('/'));
    const value=source.slice(1).split('/').reduce((object,key)=>object?.[key.replaceAll('~1','/').replaceAll('~0','~')],fixture.input);
    assert.notEqual(value,undefined,source);
   }
  }
 }
});

test('frozen numerical failures retain exact values and evidence intervals',()=>{
 const checks=[
  ['triangle_water_feasible_ramp_failure','ramp_up','4','1','0','1','segment_slope'],
  ['triangle_water_feasible_ramp_failure','ramp_down','4','1','1','2','segment_slope'],
  ['minimum_product_rate_failure','minimum_production_rate','1','1',null,null,'productive_rate'],
  ['short_online_completed_run','minimum_online','1','1','0','1','completed_duration'],
  ['short_offline_completed_run','minimum_offline','1','1','0','1','completed_duration'],
  ['initial_boundary_transition_failure','minimum_offline','1','1','-1','0','completed_duration'],
  ['mean_above_maximum_proves_failure','maximum_rate','6','1','0','2','interval_mean_bound'],
  ['productive_mean_below_minimum_proves_failure','minimum_production_rate','1','1','0','2','interval_mean_bound'],
  ['binary64_just_above_maximum','maximum_rate','4503599627370497/4503599627370496','1/4503599627370496',null,null,'point_rate']
 ];
 for(const [id,check,observed,gap,from,to,kind] of checks){
  const witness=first(evaluateOperatingEnvelope(input(id)),check);
  fraction(witness.observed,observed);fraction(witness.excess_or_shortfall,gap);assert.equal(witness.kind,kind);
  if(from!==null){fraction(witness.from_hour,from);fraction(witness.to_hour,to);}
 }
});

test('integer transition enumeration independently checks initial history and unfinished runs',()=>{
 // Count elapsed unit intervals between state changes; no evaluator helpers or fractional arithmetic.
 let cases=0;
 for(let bits=0;bits<32;bits++)for(const prior of [null,'online','offline'])for(const age of [null,0,1])for(const online of [0,1,3])for(const offline of [0,1,3]){
  if(prior===null&&age!==null)continue;
  const values=Array.from({length:5},(_,i)=>(bits>>i)&1?'online':'offline');
  const minima={online,offline},outcomes={online:[],offline:[]},tails=[];
  if(prior===null){const opposite=values[0]==='online'?'offline':'online';outcomes[opposite].push(minima[opposite]>0?'unknown':'met');}
  if(prior!==null&&prior!==values[0])outcomes[prior].push(age===null?(minima[prior]===0?'met':'unknown'):(age<minima[prior]?'violated':'met'));
  const transitions=[0,...values.flatMap((v,i)=>i&&v!==values[i-1]?[i]:[]),values.length];
  for(let index=0;index<transitions.length-1;index++){
   const start=transitions[index],end=transitions[index+1],state=values[start],minimum=minima[state];
   const known=start>0||(prior!==null&&(prior!==state||age!==null));
   const elapsed=end-start+(start===0&&prior===state&&age!==null?age:0);
   if(elapsed>=minimum)outcomes[state].push('met');
   else if(end<values.length)outcomes[state].push(known?'violated':'unknown');
   else{outcomes[state].push('unknown');tails.push([state,'5/1',`${known?minimum-elapsed:0}/1`,`${minimum-elapsed}/1`]);}
  }
  const expected=Object.fromEntries(Object.entries(outcomes).map(([state,list])=>[`minimum_${state}`,list.includes('violated')?'violated':list.includes('unknown')?'unknown':list.length?'met':'not_applicable']));
  const model=base();model.horizon.end_hour=5;model.trajectory.points[1].hour=5;model.states=states(values);model.initial_state=prior===null?null:{state:prior,age_hours:age};Object.assign(model.limits,{minimum_online_hours:online,minimum_offline_hours:offline});
  const result=evaluateOperatingEnvelope(model),label=JSON.stringify({bits,prior,age,online,offline});
  for(const [key,value] of Object.entries(expected))assert.equal(result.checks[key].status,value,label);
  assert.deepEqual(tailSummary(result),tails,label);cases++;
 }
 assert.equal(cases,2016);
});

test('integer cross-products independently check continuous rate and ramp extrema',()=>{
 let cases=0;
 for(let a=0;a<=4;a++)for(let b=0;b<=4;b++)for(let c=0;c<=4;c++)for(let limit=0;limit<=4;limit++){
  const model=base();model.horizon.end_hour=3;model.states[0].to_hour=3;
  model.trajectory.points=[{hour:0,rate_m3_h:a},{hour:1,rate_m3_h:b},{hour:3,rate_m3_h:c}];
  Object.assign(model.limits,{maximum_rate_m3_h:limit,ramp_up_m3_h2:limit,ramp_down_m3_h2:limit});
  const result=evaluateOperatingEnvelope(model),label=JSON.stringify({a,b,c,limit});
  assert.equal(result.checks.maximum_rate.status,Math.max(a,b,c)>limit?'violated':'met',label);
  assert.equal(result.checks.ramp_up.status,b-a>limit||c-b>2*limit?'violated':'met',label);
  assert.equal(result.checks.ramp_down.status,a-b>limit||b-c>2*limit?'violated':'met',label);cases++;
 }
 assert.equal(cases,625);
});

test('production boundaries use the continuous path and do not borrow nonproductive minima',()=>{
 const model=base();model.trajectory.points=[{hour:0,rate_m3_h:0},{hour:2,rate_m3_h:4}];
 model.states=[{from_hour:0,to_hour:.75,state:'online',producing:false},{from_hour:.75,to_hour:1.25,state:'online',producing:true},{from_hour:1.25,to_hour:2,state:'online',producing:false}];
 model.limits.minimum_production_rate_m3_h=1.5;
 assert.equal(evaluateOperatingEnvelope(model).checks.minimum_production_rate.status,'met');
 model.limits.minimum_production_rate_m3_h=1.5+2**-52;
 const witness=first(evaluateOperatingEnvelope(model),'minimum_production_rate');
 fraction(witness.observed,'3/2');fraction(witness.excess_or_shortfall,'1/4503599627370496');
});

test('nonproducing and offline declarations do not manufacture rate or state evidence',()=>{
 for(const producing of [false,null]){
  const model=base();model.trajectory.points.forEach(p=>p.rate_m3_h=0);model.states[0].producing=producing;
  model.limits.minimum_production_rate_m3_h=1;model.limits.minimum_online_hours=5;model.initial_state.age_hours=0;
  const result=evaluateOperatingEnvelope(model);
  assert.equal(result.checks.minimum_production_rate.status,producing===false?'not_applicable':'unknown');
  assert.equal(result.checks.minimum_online.status,'unknown');assert.equal(result.tail_obligations[0].state,'online');fraction(result.tail_obligations[0].remaining_min_hours,3);
 }
 const offline=base();offline.states[0]={...offline.states[0],state:'offline',producing:null};offline.initial_state={state:'offline',age_hours:2};offline.limits.minimum_production_rate_m3_h=3;
 assert.equal(evaluateOperatingEnvelope(offline).checks.minimum_production_rate.status,'not_applicable');
});

test('known failure survives unknown production applicability and unfinished obligations',()=>{
 const model=base();model.states=[{from_hour:0,to_hour:1,state:'online',producing:null},{from_hour:1,to_hour:2,state:'online',producing:true}];
 model.limits.minimum_production_rate_m3_h=3;model.limits.minimum_online_hours=8;
 const result=evaluateOperatingEnvelope(model);
 assert.equal(result.checks.minimum_production_rate.status,'violated');assert.equal(result.checks.minimum_online.status,'unknown');assert.equal(result.status,'violated');assert.equal(result.decision,'revise_trace');assert.equal(result.tail_obligations.length,1);
});

test('interval means can prove failures across productive partitions without inventing a point path',()=>{
 const model=input('productive_mean_below_minimum_proves_failure');
 model.states=[{from_hour:0,to_hour:.5,state:'online',producing:true},{from_hour:.5,to_hour:2,state:'online',producing:true}];
 let result=evaluateOperatingEnvelope(model);assert.equal(result.checks.minimum_production_rate.status,'violated');assert.equal(first(result,'minimum_production_rate').kind,'interval_mean_bound');
 model.states[0].producing=null;result=evaluateOperatingEnvelope(model);assert.equal(result.checks.minimum_production_rate.status,'unknown');
 model.trajectory.intervals[0].rate_m3_h=6;result=evaluateOperatingEnvelope(model);assert.equal(result.checks.maximum_rate.status,'violated');assert.equal(result.checks.ramp_up.status,'unknown');assert.equal(result.checks.ramp_down.status,'unknown');
});

test('interval endpoints exclude an adjacent nonproduction record from applicability',()=>{
 const model=base();model.trajectory={representation:'interval_mean',intervals:[{from_hour:0,to_hour:1,rate_m3_h:1},{from_hour:1,to_hour:2,rate_m3_h:4}]};
 model.states=[{from_hour:0,to_hour:1,state:'online',producing:true},{from_hour:1,to_hour:2,state:'online',producing:false}];model.limits.minimum_production_rate_m3_h=2;
 const witness=first(evaluateOperatingEnvelope(model),'minimum_production_rate');fraction(witness.from_hour,0);fraction(witness.to_hour,1);fraction(witness.observed,1);
});

test('absent limits and absent histories never become defaults or authorization',()=>{
 const model=base();delete model.limits;
 assert.ok(Object.values(evaluateOperatingEnvelope(model).checks).every(check=>check.status==='unknown'));
 const missing=base();missing.states=null;Object.assign(missing.limits,{minimum_online_hours:0,minimum_offline_hours:0});
 const result=evaluateOperatingEnvelope(missing);
 for(const key of ['minimum_online','minimum_offline','minimum_production_rate'])assert.equal(result.checks[key].status,'unknown');
 assert.equal(result.decision,'supply_evidence');
});

test('subnormal slope violations survive display underflow',()=>{
 const model=base();model.trajectory.points=[{hour:0,rate_m3_h:0},{hour:2,rate_m3_h:Number.MIN_VALUE}];model.limits.ramp_up_m3_h2=0;
 const result=evaluateOperatingEnvelope(model),witness=first(result,'ramp_up');
 assert.equal(result.status,'violated');fraction(witness.observed,`1/${1n<<1075n}`);fraction(witness.excess_or_shortfall,`1/${1n<<1075n}`);assert.equal(witness.observed.value,null);assert.equal(witness.excess_or_shortfall.value,null);
});

test('overflowing slope retains finite-input exact evidence',()=>{
 const model=base();model.horizon.end_hour=.5;model.states[0].to_hour=.5;model.trajectory.points=[{hour:0,rate_m3_h:0},{hour:.5,rate_m3_h:Number.MAX_VALUE}];
 model.limits.maximum_rate_m3_h=Number.MAX_VALUE;model.limits.ramp_up_m3_h2=Number.MAX_VALUE;
 const witness=first(evaluateOperatingEnvelope(model),'ramp_up');fraction(witness.observed,2n*BigInt(Number.MAX_VALUE));fraction(witness.excess_or_shortfall,BigInt(Number.MAX_VALUE));assert.equal(witness.observed.value,null);
});

test('exact time subtraction retains a slope violation that native subtraction rounds away',()=>{
 const model=base();model.horizon={start_hour:.1,end_hour:1};model.trajectory.points=[{hour:.1,rate_m3_h:0},{hour:1,rate_m3_h:.9}];
 model.states=[{from_hour:.1,to_hour:1,state:'online',producing:true}];model.limits.ramp_up_m3_h2=1;
 assert.equal(.9/(1-.1),1);
 const witness=first(evaluateOperatingEnvelope(model),'ramp_up');
 fraction(witness.observed,'32425917317067572/32425917317067571');fraction(witness.excess_or_shortfall,'1/32425917317067571');
});

test('fractional restart carries history and qualifies a tail without inventing shutdown',()=>{
 const model=base();model.horizon={start_hour:5.5,end_hour:6};model.trajectory.points=[{hour:5.5,rate_m3_h:2},{hour:6,rate_m3_h:2}];
 model.states=[{from_hour:5.5,to_hour:6,state:'offline',producing:false}];model.initial_state={state:'offline',age_hours:.25};model.limits.minimum_offline_hours=1;
 const result=evaluateOperatingEnvelope(model);assert.equal(result.status,'unknown');assert.equal(result.checks.minimum_offline.violations.length,0);fraction(result.tail_obligations[0].at_hour,6);fraction(result.tail_obligations[0].remaining_min_hours,'1/4');fraction(result.tail_obligations[0].remaining_max_hours,'1/4');
});

test('completed duration and carried age retain positive gaps hidden by native rounding',()=>{
 const completed=base();completed.horizon.start_hour=.1;completed.trajectory.points[0].hour=.1;
 completed.states=[{from_hour:.1,to_hour:1,state:'online',producing:true},{from_hour:1,to_hour:2,state:'offline',producing:false}];completed.initial_state={state:'offline',age_hours:2};completed.limits.minimum_online_hours=.9;
 const witness=first(evaluateOperatingEnvelope(completed),'minimum_online');
 fraction(witness.observed,'32425917317067571/36028797018963968');fraction(witness.excess_or_shortfall,'1/36028797018963968');
 const tail=base();tail.horizon.end_hour=.2;tail.trajectory.points[1].hour=.2;tail.states[0].to_hour=.2;tail.initial_state.age_hours=.1;tail.limits.minimum_online_hours=.1+.2;
 const result=evaluateOperatingEnvelope(tail);assert.equal(result.checks.minimum_online.status,'unknown');assert.equal(result.checks.minimum_online.violations.length,0);
 fraction(result.tail_obligations[0].remaining_min_hours,'1/36028797018963968');fraction(result.tail_obligations[0].remaining_max_hours,'1/36028797018963968');
});

test('schema errors reject instead of coercing, sorting, bridging or silently dropping fields',()=>{
 const mutations=[
  m=>{m.extra=true;},m=>{m.schema=2;},m=>{m.kind='other';},m=>{m.unit_id=' ';},m=>{m.horizon.end_hour=m.horizon.start_hour;},m=>{m.horizon.start_hour=-1;},m=>{m.horizon.extra=true;},
  m=>{m.trajectory.extra=0;},m=>{m.trajectory.points=[];},m=>{m.trajectory.points.reverse();},m=>{m.trajectory.points[0].hour=.5;},m=>{m.trajectory.points[1].hour=1.5;},m=>{m.trajectory.points[0].rate_m3_h='2';},m=>{m.trajectory.points[0].rate_m3_h=NaN;},m=>{m.trajectory.points[0].rate_m3_h=Infinity;},m=>{m.trajectory.points[0].extra=0;},
  m=>{m.states=[];},m=>{m.states[0].producing='true';},m=>{delete m.states[0].producing;},m=>{m.states[0].state='idle';},m=>{m.states[0].to_hour=0;},m=>{m.states[0].extra=0;},m=>{m.initial_state.age_hours=-1;},m=>{m.initial_state.state='idle';},m=>{m.initial_state.extra=0;},m=>{m.limits.extra=0;},m=>{m.limits.maximum_rate_m3_h='5';},m=>{m.limits.minimum_production_rate_m3_h=6;}
 ];
 for(const [index,mutate] of mutations.entries()){const model=base();mutate(model);assert.throws(()=>evaluateOperatingEnvelope(model),undefined,`mutation ${index}`);}
 for(const trajectory of [
  {representation:'interval_mean',intervals:[]},
  {representation:'interval_mean',intervals:[{from_hour:0,to_hour:1,rate_m3_h:2},{from_hour:1.5,to_hour:2,rate_m3_h:2}]},
  {representation:'interval_mean',intervals:[{from_hour:0,to_hour:1.5,rate_m3_h:2},{from_hour:1,to_hour:2,rate_m3_h:2}]},
  {representation:'interval_mean',intervals:[{from_hour:0,to_hour:2,rate_m3_h:2,extra:0}]}
 ])assert.throws(()=>evaluateOperatingEnvelope({...base(),trajectory}));
});

test('input resource bounds reject excess records before returning a certificate',()=>{
 for(const kind of ['points','intervals','states']){
  const model=base();
  if(kind==='points')model.trajectory.points=Array.from({length:26353},(_,i)=>({hour:2*i/26352,rate_m3_h:2}));
  if(kind==='intervals')model.trajectory={representation:'interval_mean',intervals:Array.from({length:26353},(_,i)=>({from_hour:2*i/26353,to_hour:2*(i+1)/26353,rate_m3_h:2}))};
  if(kind==='states')model.states=Array.from({length:26353},(_,i)=>({from_hour:2*i/26353,to_hour:2*(i+1)/26353,state:'online',producing:true}));
  assert.throws(()=>evaluateOperatingEnvelope(model),undefined,kind);
 }
});
