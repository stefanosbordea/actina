import {test} from 'node:test';
import assert from 'node:assert/strict';
import {boundSolarTiming} from './public/solar-timing-bounds.mjs';
const piece=(original,revised,hours=1)=>({hours,original_power_kw:original,revised_power_kw:revised});
const solve=(pieces,energy=50,cap=100)=>boundSolarTiming({pieces,energy_kwh:energy,power_cap_kw:cap});
const near=(actual,expected)=>assert.ok(Math.abs(actual-expected)<=1e-12*Math.max(Math.abs(actual),Math.abs(expected),Number.MIN_VALUE),`${actual} != ${expected}`);
function bounds(actual,expected){near(actual.lower,expected[0]);near(actual.upper,expected[1]);}

test('one-piece hull bounds are sharper than subtracting independent marginal extrema',()=>{
 const r=solve([piece(20,80)]);
 bounds(r.original_solar_kwh,[10,20]);bounds(r.revised_solar_kwh,[40,50]);bounds(r.delta_solar_kwh,[22.5,37.5]);
 // Lower witness: 5/8 hour at20 kW, 3/8 at100; upper: 5/8 at80, 3/8 at0.
 near(.625*20+.375*100,50);near(.375*(80-20),r.delta_solar_kwh.lower);
 near(.625*80,50);near(.625*(80-20),r.delta_solar_kwh.upper);
});
test('shared-trace difference is zero for identical plans despite uncertain individual use',()=>{
 const r=solve([piece(100,100),piece(0,0)],100);
 bounds(r.original_solar_kwh,[0,100]);bounds(r.revised_solar_kwh,[0,100]);bounds(r.delta_solar_kwh,[0,0]);
});
test('crossed plans can gain or lose under the same interval energy',()=>{
 const r=solve([piece(100,0),piece(0,100)],100);
 bounds(r.original_solar_kwh,[0,100]);bounds(r.revised_solar_kwh,[0,100]);bounds(r.delta_solar_kwh,[-100,100]);
});
test('constant interval mean gives the opposite sign to a feasible trace for equal-energy plans',()=>{
 const p=[piece(100,0),piece(100,0),piece(0,200)],r=solve(p,300,200);
 const constantMean=p.reduce((s,x)=>s+Math.min(x.revised_power_kw,100)-Math.min(x.original_power_kw,100),0);
 assert.equal(constantMean,-100);bounds(r.delta_solar_kwh,[-200,150]);
 // Upper witness: 200 kW throughout piece3, plus half of piece1; total300 kWh.
 near(200+200*.5,300);near(200-100*.5,r.delta_solar_kwh.upper);
});
test('zero energy, zero cap, full energy and loads above cap are exact',()=>{
 const zero={original_solar_kwh:{lower:0,upper:0},revised_solar_kwh:{lower:0,upper:0},delta_solar_kwh:{lower:0,upper:0}};
 assert.deepEqual(solve([piece(20,80)],0),zero);assert.deepEqual(solve([piece(20,80)],0,0),zero);
 const full=solve([piece(20,80,.5),piece(200,50,.5)],100);
 bounds(full.original_solar_kwh,[60,60]);bounds(full.revised_solar_kwh,[65,65]);bounds(full.delta_solar_kwh,[5,5]);
 const capped=solve([piece(1e300,2e300)]);bounds(capped.original_solar_kwh,[50,50]);bounds(capped.delta_solar_kwh,[0,0]);
});
test('splitting a constant piece and reordering pieces preserve all bounds',()=>{
 const original=[piece(20,80,2),piece(95,5,.5)],split=[piece(20,80,.25),piece(95,5,.5),piece(20,80,1.75)];
 const a=solve(original,125),b=solve(split,125),c=solve([...split].reverse(),125);
 for(const key of Object.keys(a))for(const side of ['lower','upper']){near(a[key][side],b[key][side]);near(a[key][side],c[key][side]);}
 const thirds=solve(Array.from({length:3},()=>piece(20,80,1/3)),100);bounds(thirds.delta_solar_kwh,[60,60]);
});
test('full-cap integer-millisecond intervals remain feasible after fractional splits',()=>{
 const duration=2769027,cuts=[0,63835,1461133,duration],pieces=cuts.slice(1).map((end,i)=>piece(i===1?0:10,i===1?0:20,(end-cuts[i])/3600000));
 const r=solve(pieces,duration/3600000*100),expected=(duration-1397298)/3600000*10;
 bounds(r.original_solar_kwh,[expected,expected]);bounds(r.revised_solar_kwh,[expected*2,expected*2]);bounds(r.delta_solar_kwh,[expected,expected]);
 let seed=481516;
 const random=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296);
 for(let i=0;i<512;i++){
  const end=3+Math.floor(random()*7200000),a=1+Math.floor(random()*(end-2)),b=a+1+Math.floor(random()*(end-a-1)),points=[0,a,b,end];
  const split=points.slice(1).map((t,j)=>piece(20,80,(t-points[j])/3600000)),result=solve(split,end/3600000*100);
  bounds(result.delta_solar_kwh,[end/3600000*60,end/3600000*60]);
 }
});
test('capacity allowance is scale-relative roundoff only and never admits positive energy at zero cap',()=>{
 for(const cap of [1e-200,100,1e200]){
  const r=solve([piece(cap,cap)],cap*(1+Number.EPSILON),cap);bounds(r.original_solar_kwh,[cap,cap]);
  assert.throws(()=>solve([piece(cap,cap)],cap*(1+8*Number.EPSILON),cap),/Energy exceeds/);
 }
 assert.throws(()=>solve([piece(20,80)],Number.MIN_VALUE,0),/Energy exceeds/);
});
test('reversing plan labels negates and exchanges joint endpoints',()=>{
 const p=[piece(20,80,.5),piece(100,10,2)],a=solve(p,100),b=solve(p.map(x=>piece(x.revised_power_kw,x.original_power_kw,x.hours)),100);
 bounds(b.delta_solar_kwh,[-a.delta_solar_kwh.upper,-a.delta_solar_kwh.lower]);assert.deepEqual(a.original_solar_kwh,b.revised_solar_kwh);
});
test('large and small reciprocal power-duration scales preserve finite bounds',()=>{
 for(const scale of [1e-200,1e200]){
  const r=solve([piece(20*scale,80*scale,1/scale)],50,100*scale);
  bounds(r.original_solar_kwh,[10,20]);bounds(r.revised_solar_kwh,[40,50]);bounds(r.delta_solar_kwh,[22.5,37.5]);
  const tinyOrLarge=solve([piece(20*scale,80*scale)],50*scale,100*scale);
  bounds(tinyOrLarge.delta_solar_kwh,[22.5*scale,37.5*scale]);
 }
});
test('solver does not mutate frozen inputs',()=>{
 const p=Object.freeze([Object.freeze(piece(20,80))]),input=Object.freeze({pieces:p,energy_kwh:50,power_cap_kw:100}),before=JSON.stringify(input);
 bounds(boundSolarTiming(input).delta_solar_kwh,[22.5,37.5]);assert.equal(JSON.stringify(input),before);
});
test('invalid pieces, energies, caps and unrepresentable capacities fail closed',()=>{
 for(const input of [null,undefined,[],{}, {pieces:[],energy_kwh:0,power_cap_kw:0},{pieces:Array(1),energy_kwh:0,power_cap_kw:0}])assert.throws(()=>boundSolarTiming(input));
 for(const value of [-1,NaN,Infinity,'1',null,undefined]){
  assert.throws(()=>boundSolarTiming({pieces:[piece(20,80)],energy_kwh:value,power_cap_kw:100}));assert.throws(()=>boundSolarTiming({pieces:[piece(20,80)],energy_kwh:0,power_cap_kw:value}));
  for(const key of ['hours','original_power_kw','revised_power_kw'])assert.throws(()=>solve([{...piece(20,80),[key]:value}]));
 }
 assert.throws(()=>solve([piece(20,80,0)]));assert.throws(()=>solve([piece(20,80)],100.0000000001));assert.throws(()=>solve([piece(20,80)],1,0));
 assert.throws(()=>solve([piece(20,80,1e308)],1,1e308),/numeric range/);
 assert.throws(()=>solve([piece(20,80,1e-308)],0,1e-308),/numeric range/);
 assert.throws(()=>solve([piece(1e-300,2e-300,2)],1e300,1e300),/numeric range/);
});
