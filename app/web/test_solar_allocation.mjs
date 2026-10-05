import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {makeRevisionCase,revisionTemplate,compareRevision} from './public/plan-revision.mjs';
import {solarAllocationTemplate,evaluateSolarAllocation,sequenceSolarAllocationTemplate,evaluateSequenceSolarAllocation} from './public/solar-allocation.mjs';
import {sequenceRevisionTemplate,compareSequenceRevision} from './public/sequence-revision.mjs';
const box={};vm.runInNewContext(readFileSync(new URL('public/vendor/papaparse.min.js',import.meta.url),'utf8'),box);const Papa=box.Papa;
const time=h=>new Date(Date.UTC(2026,6,15,h)).toISOString();
const caseFile={name:'case.json',sha256:'b'.repeat(64)},proposalFile={name:'return.csv',sha256:'c'.repeat(64)};
function comparison({production=Array(24).fill(120),scenario={},startHour=0,sec=3.4,times=Array.from({length:24},(_,h)=>time(h)),original=Array(24).fill(120)}={}){
 const c=makeRevisionCase({assessment:{schema:1,kind:'fixed_plan_consequence_assessment',identity:{data_sha256:'a'.repeat(64)},inputs:{times,production:original,demand:120,capacity:4000,reserve:800,initial:2000,target:2000,startHour,scenario}},unit_capacity_m3_h:500,specific_energy_kwh_m3:sec});
 const rows=revisionTemplate(c,caseFile.sha256);rows.slice(1).forEach((r,i)=>r[2]=production[startHour+i]);return compareRevision({revisionCase:c,caseIdentity:caseFile,csvText:Papa.unparse(rows),proposalIdentity:proposalFile,Papa});
}
function profile(c,power=0){const p=solarAllocationTemplate(c);Object.assign(p,{source_kind:'illustrative_scenario',source_label:'Explicit synthetic allocation',plant_mapping:'One modeled unit',review_as_of:'2026-07-16T12:00:00Z'});p.intervals.forEach(r=>{r.available_at='2026-07-14T12:00:00Z';r.power_kw=power;});return p;}
const evaluate=(c,p)=>evaluateSolarAllocation({comparison:c,allocation:p}),near=(a,b)=>assert.ok(Math.abs(a-b)<1e-7,`${a} != ${b}`);
test('matched shifting increases declared solar use without changing total energy or water service',()=>{
 const production=Array(24).fill(120);production[12]=220;production[13]=20;const c=comparison({production}),p=profile(c);p.intervals[12].power_kw=1000;
 const before=JSON.stringify({c,p}),r=evaluate(c,p);assert.equal(r.status,'complete');near(r.totals.delta_solar_kwh,340);near(r.totals.delta_other_kwh,-340);near(r.totals.delta_load_kwh,0);near(c.changes.delivered_m3,0);near(c.changes.terminal_deviation_m3,0);assert.equal(JSON.stringify({c,p}),before);
});
test('saturated allocation defeats naive window-load improvement; extra load is visible separately',()=>{
 const production=Array(24).fill(120);production[12]=220;const c=comparison({production}),p=profile(c);p.intervals[12].power_kw=408;
 let r=evaluate(c,p);near(r.totals.delta_solar_kwh,0);near(r.totals.delta_other_kwh,340);near(r.totals.delta_load_kwh,340);near(c.changes.terminal_deviation_m3,100);
 p.intervals[12].power_kw=1000;r=evaluate(c,p);near(r.totals.delta_solar_kwh,340);near(r.totals.delta_other_kwh,0);near(r.totals.delta_load_kwh,340);
});
test('exact fractional outage splits exclude solar available only while stopped',()=>{
 const c=comparison({scenario:{outage:{start_hour:12.5,duration_hours:1}}}),p=profile(c);p.intervals=[{start:time(12),end:'2026-07-15T12:30:00Z',available_at:time(0),power_kw:0},{start:'2026-07-15T12:30:00Z',end:'2026-07-15T13:30:00Z',available_at:time(0),power_kw:1000},{start:'2026-07-15T13:30:00Z',end:time(24),available_at:time(0),power_kw:0},{start:time(0),end:time(12),available_at:time(0),power_kw:0}];
 const r=evaluate(c,p);assert.equal(r.status,'complete');near(r.totals.original_solar_kwh,0);near(r.totals.original_load_kwh,23*408);assert.equal(r.rows.filter(x=>x.solar_power_kw>0).every(x=>x.original_power_kw===0),true);
});
test('zero, null, missing and late allocation remain distinct; partial totals share the same support',()=>{
 const c=comparison(),p=profile(c);p.intervals[1].power_kw=null;p.intervals[2].available_at='2026-07-17T00:00:00Z';p.intervals.splice(3,1);const r=evaluate(c,p);
 assert.equal(r.status,'partial');assert.equal(r.totals,null);assert.deepEqual(r.coverage,{horizon_hours:24,known_hours:21,unknown_hours:3,late_hours:1});near(r.known_totals.original_solar_kwh,0);near(r.known_totals.original_load_kwh,21*408);near(r.full_load_totals.original_load_kwh,24*408);assert.deepEqual(new Set(r.rows.map(x=>x.status)),new Set(['known','unknown','late','missing']));
 p.intervals=[];const empty=evaluate(c,p);assert.equal(empty.totals,null);assert.equal(empty.known_totals,null);near(empty.coverage.unknown_hours,24);
});
test('unknown specific energy never becomes zero electricity and template contains no invented solar',()=>{
 const c=comparison({sec:null}),p=profile(c,1000),r=evaluate(c,p);assert.equal(r.status,'unknown_energy');assert.equal(r.totals,null);assert.equal(r.known_totals,null);assert.equal(r.full_load_totals,null);assert.equal(r.rows.every(x=>x.original_power_kw===null),true);
 const template=solarAllocationTemplate(c);assert.equal(template.intervals.every(x=>x.power_kw===null),true);assert.throws(()=>evaluate(c,template),/Declare the source/);
});
test('absolute timestamps preserve DST, remaining horizon and equivalent-offset ordering',()=>{
 const base=Date.parse('2026-10-25T00:00:00+03:00'),times=Array.from({length:24},(_,h)=>new Date(base+h*3600000).toISOString());const c=comparison({times,startHour:3}),p=profile(c,200);
 p.intervals.reverse();p.intervals.at(-1).start='2026-10-25T03:00:00+02:00';assert.throws(()=>evaluate(c,p),/positive duration/);
 p.intervals.at(-1).start=times[3];p.review_as_of='2026-10-26T00:00:00Z';const r=evaluate(c,p);near(r.coverage.horizon_hours,21);near(r.totals.original_solar_kwh,4200);
});
test('invalid contracts, interval overlaps, average/point/residual data and wrong cases are rejected',()=>{
 const c=comparison();const changes=[p=>p.case_sha256='a'.repeat(64),p=>p.source_kind='measured',p=>p.source_label='',p=>p.plant_mapping='',p=>p.power_basis='residual_surplus',p=>p.interval_semantics='average_power',p=>p.review_as_of='2026-07-16T12:00:00',p=>p.intervals[1].start=p.intervals[0].start,p=>p.intervals[0].end=p.intervals[0].start,p=>p.intervals[0].power_kw=-1,p=>p.intervals[0].power_kw='400',p=>p.intervals[0].power_kw=Infinity,p=>p.intervals[0].available_at=null,p=>p.intervals[0].start=time(-1),p=>p.intervals.at(-1).end=time(25),p=>p.intervals[0].kwh=10,p=>p.extra=1,p=>delete p.intervals[0].power_kw];
 for(const change of changes){const p=profile(c);change(p);assert.throws(()=>evaluate(c,p));}
});
test('energy includes spilled production and reconstruction ignores forged cached totals',()=>{
 const c=comparison({production:Array(24).fill(500),scenario:{initial_storage_m3:4000,production_multiplier:.9}}),p=profile(c,2000);c.revised.result.totals.available_production_m3=0;c.revised.modeled_production_energy_kwh=0;
 const r=evaluate(c,p);near(r.totals.revised_load_kwh,24*450*3.4);near(r.totals.revised_solar_kwh,r.totals.revised_load_kwh);assert.ok(c.revised.result.totals.spill_m3>0);
 const huge=profile(c,1e308);assert.throws(()=>evaluate(c,huge),/finite numeric range/);
});
function energyProfile(c,energy=0,cap=1000){
 const p=profile(c);p.interval_semantics='interval_energy';p.intervals=p.intervals.map(({power_kw,...r})=>({...r,energy_kwh:energy,power_cap_kw:cap}));return p;
}
test('shared interval energy can reverse the ranking; it is never divided evenly across hours',()=>{
 const production=Array(24).fill(120);production[12]=220;production[13]=20;const c=comparison({production}),p=energyProfile(c);
 p.intervals=[{...p.intervals[0],end:time(12)},{...p.intervals[12],end:time(14),energy_kwh:748,power_cap_kw:748},{...p.intervals[14],end:time(24)}];
 const before=JSON.stringify({c,p}),r=evaluate(c,p);assert.equal(r.status,'complete');assert.equal(r.totals,null);
 near(r.bounds.original_solar_kwh.lower,408);near(r.bounds.original_solar_kwh.upper,748);near(r.bounds.revised_solar_kwh.lower,68);near(r.bounds.revised_solar_kwh.upper,748);
 near(r.bounds.delta_solar_kwh.lower,-340);near(r.bounds.delta_solar_kwh.upper,340);near(r.bounds.delta_load_kwh.lower,0);near(r.full_load_totals.original_load_kwh,9792);
 assert.ok(r.bounds.delta_solar_kwh.lower>r.bounds.revised_solar_kwh.lower-r.bounds.original_solar_kwh.upper);assert.equal(JSON.stringify({c,p}),before);
});
test('fractional outage timing stays unknown inside an energy interval',()=>{
 const c=comparison({scenario:{outage:{start_hour:12.5,duration_hours:.5}}}),p=energyProfile(c);p.intervals[12].energy_kwh=408;p.intervals[12].power_cap_kw=816;
 const r=evaluate(c,p);near(r.bounds.original_solar_kwh.lower,0);near(r.bounds.original_solar_kwh.upper,204);near(r.bounds.delta_solar_kwh.lower,0);near(r.bounds.delta_solar_kwh.upper,0);
 near(r.full_load_totals.original_load_kwh,23.5*408);
});
test('refined interval evidence can resolve a coarse timing ambiguity',()=>{
 const production=Array(24).fill(120);production[12]=220;production[13]=20;const c=comparison({production}),p=energyProfile(c,0,748);p.intervals[12].energy_kwh=748;
 const r=evaluate(c,p);near(r.bounds.delta_solar_kwh.lower,340);near(r.bounds.delta_solar_kwh.upper,340);near(r.bounds.delta_other_kwh.lower,-340);near(r.bounds.delta_other_kwh.upper,-340);
});
test('energy profiles preserve late, null, missing and zero support without false full totals',()=>{
 const c=comparison(),p=energyProfile(c);p.intervals[1].energy_kwh=null;p.intervals[2].power_cap_kw=null;p.intervals[3].available_at='2026-07-17T00:00:00Z';p.intervals.splice(4,1);
 const r=evaluate(c,p);assert.equal(r.status,'partial');assert.equal(r.bounds,null);assert.equal(r.totals,null);assert.equal(r.coverage.unknown_hours,4);assert.equal(r.coverage.late_hours,1);near(r.known_bounds.original_load_kwh.lower,20*408);
 p.intervals=[];assert.equal(evaluate(c,p).known_bounds,null);
 const u=evaluate(comparison({sec:null}),energyProfile(comparison({sec:null})));assert.equal(u.status,'unknown_energy');assert.equal(u.known_bounds,null);assert.equal(u.full_load_totals,null);
});
test('energy profile declarations are validated even when unavailable at the review cutoff',()=>{
 const c=comparison();const mutations=[p=>p.intervals[0].power_kw=0,p=>p.intervals[0].energy_kwh=-1,p=>p.intervals[0].power_cap_kw=Infinity,p=>p.intervals[0].energy_kwh=1001,p=>delete p.intervals[0].energy_kwh,p=>delete p.intervals[0].power_cap_kw,p=>{p.intervals[0].energy_kwh=1;p.intervals[0].power_cap_kw=0;},p=>{p.intervals[0].energy_kwh=1001;p.intervals[0].available_at='2026-07-17T00:00:00Z';}];
 for(const mutate of mutations){const p=energyProfile(c);mutate(p);assert.throws(()=>evaluate(c,p));}
 const p=energyProfile(c,0,0);near(evaluate(c,p).bounds.original_solar_kwh.upper,0);
});
test('energy templates require both quantities and reject unsupported template semantics',()=>{
 const c=comparison(),p=solarAllocationTemplate(c,'interval_energy');assert.equal(p.interval_semantics,'interval_energy');assert.ok(p.intervals.every(r=>r.energy_kwh===null&&r.power_cap_kw===null&&!Object.hasOwn(r,'power_kw')));assert.throws(()=>solarAllocationTemplate(c,'average_power'));
});
test('one-day profiles reject unrepresentable positive power and energy without rejecting true zero',()=>{
 const c=comparison({original:Array(24).fill(1e-200),production:Array(24).fill(1e-200),sec:1e-200});assert.throws(()=>evaluate(c,profile(c)),/numeric range or precision/);
 const ordinary=comparison(),p=profile(ordinary);p.intervals[0].end='2026-07-15T00:00:00.001Z';p.intervals[0].power_kw=Number.MIN_VALUE;assert.throws(()=>evaluate(ordinary,p),/numeric range or precision/);
 const zero=comparison({original:Array(24).fill(0),production:Array(24).fill(0),sec:1e-200});near(evaluate(zero,profile(zero)).full_load_totals.original_load_kwh,0);
});
const padded=values=>Array.from({length:24},(_,i)=>values[i]??0);
const evidenceComparison=(original,returned,options={})=>comparison({original:padded(original),production:padded(returned),sec:1,...options});
const evidenceTime=hour=>new Date(Date.parse(time(0))+Math.round(hour*3600000)).toISOString();
const evidenceRow=(start,end,values,available_at=time(0))=>({start:evidenceTime(start),end:evidenceTime(end),available_at,...values});
function guidance(c,intervals,semantics='interval_energy'){
 const sequence=c.kind==='continuous_plan_revision_comparison',p=sequence?sequenceSolarAllocationTemplate(c,semantics):solarAllocationTemplate(c,semantics);
 Object.assign(p,{source_kind:'illustrative_scenario',source_label:'Evidence guidance fixture',plant_mapping:'Declared unit',review_as_of:time(48),intervals});
 return sequence?evaluateSequenceSolarAllocation({comparison:c,allocation:p}):evaluate(c,p);
}
const envelope=(c,rows,semantics)=>guidance(c,rows,semantics).difference_envelope;
function pairBounds(actual,lower,upper){near(actual.lower,lower);near(actual.upper,upper);}
test('missing equal-load support has an exact zero difference while absolute totals stay unknown',()=>{
 const r=guidance(comparison(),[]);assert.equal(r.status,'partial');assert.equal(r.totals,null);assert.equal(r.known_bounds,null);assert.equal(r.difference_envelope.status,'bounded');pairBounds(r.difference_envelope.delta_solar_kwh,0,0);pairBounds(r.difference_envelope.delta_other_kwh,0,0);
 assert.equal(r.difference_envelope.contributions.length,1);assert.equal(r.difference_envelope.contributions[0].method,'load_only');assert.equal(r.difference_envelope.contributions[0].status,'missing');assert.deepEqual(r.difference_envelope.contributions[0].constraints,{});
 const unknown=guidance(comparison({sec:null}),[]).difference_envelope;assert.equal(unknown.status,'unknown_energy');assert.equal(unknown.delta_solar_kwh,null);assert.equal(unknown.delta_other_kwh,null);assert.equal(unknown.width_kwh,null);assert.deepEqual(unknown.contributions,[]);
});
test('known positive evidence can dominate a bounded adverse gap without inventing absolute solar use',()=>{
 for(const [gain,expected] of [[3,[1,3]],[1,[-1,1]]]){
  const c=evidenceComparison([0,3],[gain,1]),r=guidance(c,[evidenceRow(0,1,{power_kw:gain})],'constant_power'),e=r.difference_envelope;
  assert.equal(r.totals,null);assert.equal(r.status,'partial');pairBounds(e.delta_solar_kwh,...expected);near(e.width_kwh,2);pairBounds(e.delta_other_kwh,r.full_load_totals.delta_load_kwh-expected[1],r.full_load_totals.delta_load_kwh-expected[0]);
  assert.equal(e.contributions.length,2);assert.equal(e.contributions[1].start,time(1));assert.equal(e.contributions[1].end,time(24));
 }
});
test('late numeric values never leak into the envelope or exported constraints',()=>{
 const c=evidenceComparison([0,3],[1,1]);let reference;
 for(const values of [{energy_kwh:0,power_cap_kw:0},{energy_kwh:2,power_cap_kw:3},{energy_kwh:null,power_cap_kw:1},{energy_kwh:1000,power_cap_kw:null}]){
  const e=envelope(c,[evidenceRow(0,1,{energy_kwh:1,power_cap_kw:1}),evidenceRow(1,2,values,time(49))]);if(reference)assert.deepEqual(e,reference);else reference=e;pairBounds(e.delta_solar_kwh,-1,1);assert.deepEqual(e.contributions[1].constraints,{});assert.equal(e.contributions[1].method,'load_only');
 }
});
test('timely cap-only rows exploit the cap without treating unknown energy as zero',()=>{
 for(const [c,cap,expected] of [[evidenceComparison([1],[2]),1.5,[0,.5]],[evidenceComparison([1],[2]),0,[0,0]],[evidenceComparison([1,1],[2,0]),1,[-1,0]]]){
  const r=guidance(c,[evidenceRow(0,2,{energy_kwh:null,power_cap_kw:cap})]),e=r.difference_envelope;assert.equal(r.bounds,null);assert.equal(r.known_bounds,null);pairBounds(e.delta_solar_kwh,...expected);assert.equal(e.contributions[0].method,'cap_only');assert.deepEqual(e.contributions[0].constraints,{power_cap_kw:cap});
 }
});
test('energy-only fractional allocation uses favorable-sign densities and permits excess energy',()=>{
 const cases=[[[1],[2],1,[0,.5]],[[2],[1],1,[-.5,0]],[[1],[2],10,[0,1]],[[0],[2],1,[0,1]],[[0,1],[4,2],5,[0,4.5]],[[0],[0],10,[0,0]],[[3],[0],0,[0,0]],[[1,2],[2,1],2,[-1,1]]];
 for(const [a,b,E,expected] of cases){const r=guidance(evidenceComparison(a,b),[evidenceRow(0,a.length,{energy_kwh:E,power_cap_kw:null})]),e=r.difference_envelope;pairBounds(e.delta_solar_kwh,...expected);assert.equal(r.bounds,null);assert.equal(e.contributions[0].method,'energy_only');assert.deepEqual(e.contributions[0].constraints,{energy_kwh:E});assert.match(e.scope.join(' '),/limiting values rather than attainable/);}
});
test('energy-only zero endpoint can be a limit: finite-peak traces preserve energy while approaching it',()=>{
 const c=evidenceComparison([0],[2]),closed=envelope(c,[evidenceRow(0,1,{energy_kwh:1,power_cap_kw:null})]);pairBounds(closed.delta_solar_kwh,0,1);
 let last=Infinity;for(const peak of [2,20,2000]){const duration=1/peak,used=2*duration;near(peak*duration,1);assert.ok(used>0&&used<last);last=used;const finite=envelope(c,[evidenceRow(0,1,{energy_kwh:1,power_cap_kw:peak})]);near(finite.delta_solar_kwh.lower,used);assert.ok(finite.delta_solar_kwh.lower>closed.delta_solar_kwh.lower);}
});
test('coarse energy intervals preserve coupled equal-load pieces and do not promise resolution at finer cadence',()=>{
 const c=evidenceComparison([0,1],[0,2]),coarse=envelope(c,[evidenceRow(0,2,{energy_kwh:2,power_cap_kw:2})]);pairBounds(coarse.delta_solar_kwh,0,1);assert.equal(coarse.contributions[0].end,time(2));assert.equal(coarse.contributions[0].method,'shared_interval_energy');
 for(const [first,expected] of [[0,1],[2,0]])pairBounds(envelope(c,[evidenceRow(0,1,{energy_kwh:first,power_cap_kw:2}),evidenceRow(1,2,{energy_kwh:2-first,power_cap_kw:2})]).delta_solar_kwh,expected,expected);
 const d=evidenceComparison([1],[2]);for(const count of [1,4,60]){const e=envelope(d,Array.from({length:count},(_,i)=>evidenceRow(i/count,(i+1)/count,{energy_kwh:1/count,power_cap_kw:2})));pairBounds(e.delta_solar_kwh,0,.5);}
});
test('source order, equivalent-offset clocks, harmless splits and plan swapping preserve the envelope',()=>{
 const a=[0,1,3,1],b=[4,2,1,2],rows=[evidenceRow(0,2,{energy_kwh:5,power_cap_kw:null}),evidenceRow(2,4,{energy_kwh:null,power_cap_kw:2})],c=evidenceComparison(a,b),forward=envelope(c,rows),reverse=envelope(evidenceComparison(b,a),rows);
 pairBounds(reverse.delta_solar_kwh,-forward.delta_solar_kwh.upper,-forward.delta_solar_kwh.lower);near(reverse.width_kwh,forward.width_kwh);forward.contributions.forEach((row,index)=>pairBounds(reverse.contributions[index].delta_solar_kwh,-row.delta_solar_kwh.upper,-row.delta_solar_kwh.lower));
 const shuffled=structuredClone(rows).reverse();shuffled[1].start='2026-07-15T03:00:00+03:00';assert.deepEqual(envelope(c,shuffled),forward);
 const unsplit=envelope(c,[evidenceRow(0,2,{energy_kwh:null,power_cap_kw:2})]),split=envelope(c,[evidenceRow(0,1,{energy_kwh:null,power_cap_kw:2}),evidenceRow(1,2,{energy_kwh:null,power_cap_kw:2})]);pairBounds(split.delta_solar_kwh,unsplit.delta_solar_kwh.lower,unsplit.delta_solar_kwh.upper);near(split.width_kwh,unsplit.width_kwh);
});
test('full and fractional outages, derating and spilled production use the existing effective power pieces',()=>{
 const c=evidenceComparison([1,1],[2,0],{scenario:{production_multiplier:.5,outage:{start_hour:.5,duration_hours:1}}}),e=envelope(c,[]);pairBounds(e.delta_solar_kwh,-.25,.25);near(e.width_kwh,.5);
 const stopped=evidenceComparison([1],[2],{scenario:{outage:{start_hour:0,duration_hours:24}}});pairBounds(envelope(stopped,[]).delta_solar_kwh,0,0);
 const spilled=comparison({production:Array(24).fill(500),scenario:{initial_storage_m3:4000}}),r=guidance(spilled,[evidenceRow(0,24,{power_kw:2000})],'constant_power');assert.ok(spilled.revised.result.totals.spill_m3>0);near(r.difference_envelope.delta_solar_kwh.lower,r.totals.delta_solar_kwh);
});
test('continuous sparse evidence resolves a matched-production difference while absolute use stays unknown',()=>{
 const input={blocks:[0,1].map(index=>({times:Array.from({length:24},(_,h)=>time(index*24+h)),production:Array(24).fill(1),demand:1})),capacity:100,reserve:0,initial:10,target:10,unitCapacity:4},rows=sequenceRevisionTemplate({input,block_index:0,case_sha256:caseFile.sha256});rows[24][2]=2;rows[25][2]=.5;rows[26][2]=.5;
 const c=compareSequenceRevision({input,block_index:0,caseIdentity:caseFile,csvText:Papa.unparse(rows),proposalIdentity:proposalFile,specific_energy_kwh_m3:1,Papa}),r=guidance(c,[evidenceRow(23,24,{power_kw:2}),evidenceRow(24,25,{power_kw:0})],'constant_power'),e=r.difference_envelope;
 pairBounds(e.delta_solar_kwh,.5,1);near(c.changes.delivered_m3,0);near(c.changes.available_production_m3,0);near(c.changes.final_storage_m3,0);assert.equal(r.totals,null);assert.equal(e.contributions[0].status,'missing');pairBounds(e.contributions[0].delta_solar_kwh,0,0);assert.equal(e.contributions.length,4);
 assert.deepEqual(e.contributions[0].focus_intervals,[]);assert.equal(e.contributions[3].end,time(48));assert.deepEqual(e.contributions[3].focus_intervals,[{start:time(25),end:time(26),delta_solar_kwh:{lower:-.5,upper:0},width_kwh:.5}]);
 rows[25][2]=0;rows[26][2]=1;const d=compareSequenceRevision({input,block_index:0,caseIdentity:caseFile,csvText:Papa.unparse(rows),proposalIdentity:proposalFile,specific_energy_kwh_m3:1,Papa});pairBounds(envelope(d,[evidenceRow(23,25,{energy_kwh:2,power_cap_kw:2})]).delta_solar_kwh,-1,1);
});
test('load-only focus merges adjacent changed pieces, excludes equal loads and never splits energy-coupled evidence',()=>{
 const c=evidenceComparison([1,1,1,1,1],[2,0,1,2,1],{scenario:{outage:{start_hour:3.5,duration_hours:.5}}}),missing=envelope(c,[]).contributions[0];
 assert.equal(missing.start,time(0));assert.equal(missing.end,time(24));assert.deepEqual(missing.focus_intervals,[{start:time(0),end:time(2),delta_solar_kwh:{lower:-1,upper:1},width_kwh:2},{start:time(3),end:evidenceTime(3.5),delta_solar_kwh:{lower:0,upper:.5},width_kwh:.5}]);
 const late=envelope(c,[evidenceRow(0,24,{energy_kwh:0,power_cap_kw:0},time(49))]).contributions[0];assert.deepEqual(late.focus_intervals,missing.focus_intervals);assert.deepEqual(late.constraints,{});
 const empty=envelope(c,[evidenceRow(0,24,{energy_kwh:null,power_cap_kw:null})]).contributions[0];assert.deepEqual(empty.focus_intervals,missing.focus_intervals);
 for(const values of [{energy_kwh:1,power_cap_kw:null},{energy_kwh:1,power_cap_kw:2},{energy_kwh:null,power_cap_kw:2}])assert.equal(Object.hasOwn(envelope(c,[evidenceRow(0,24,values)]).contributions[0],'focus_intervals'),false);
 assert.equal(missing.focus_intervals.reduce((sum,row)=>sum+row.width_kwh,0),missing.width_kwh);
});
test('closed contribution sums preserve small values and reject positive underflow or overflowing widths',()=>{
 for(const sec of [1e-200,1e200]){const c=evidenceComparison([1],[2],{sec}),e=envelope(c,[evidenceRow(0,1,{energy_kwh:sec,power_cap_kw:null})]);assert.ok(Math.abs(e.delta_solar_kwh.upper/(sec*.5)-1)<1e-12);assert.ok(e.width_kwh>0);}
 assert.throws(()=>envelope(evidenceComparison([1],[2]),[evidenceRow(0,1,{energy_kwh:Number.MIN_VALUE,power_cap_kw:null})]),/numeric range or precision/);
 assert.throws(()=>envelope(evidenceComparison([1,0],[0,1],{sec:1e308}),[]),/finite numeric range/);
 const c=evidenceComparison([0,1,3],[4,2,1]),e=envelope(c,[evidenceRow(0,2,{energy_kwh:5,power_cap_kw:null})]);near(e.width_kwh,e.contributions.reduce((total,row)=>total+row.width_kwh,0));near(e.width_kwh,e.delta_solar_kwh.upper-e.delta_solar_kwh.lower);
});
test('a small change beside a huge common load retains its direction in load, solar and other-electricity differences',()=>{
 const c=evidenceComparison([1,0],[1,1e-20],{sec:1e100}),relative=(actual,expected)=>assert.ok(Math.abs(actual/expected-1)<1e-12,`${actual} != ${expected}`);
 for(const [semantics,rows] of [['constant_power',[]],['constant_power',[evidenceRow(0,24,{power_kw:1e100})]],['interval_energy',[evidenceRow(0,24,{energy_kwh:0,power_cap_kw:0})]]]){
  const r=guidance(c,rows,semantics),e=r.difference_envelope;relative(r.full_load_totals.delta_load_kwh,1e80);
  if(!rows.length){assert.equal(e.delta_solar_kwh.lower,0);relative(e.delta_solar_kwh.upper,1e80);assert.equal(e.delta_other_kwh.lower,0);relative(e.delta_other_kwh.upper,1e80);}
  else if(semantics==='constant_power'){relative(e.delta_solar_kwh.lower,1e80);relative(e.delta_solar_kwh.upper,1e80);assert.equal(e.delta_other_kwh.lower,0);assert.equal(e.delta_other_kwh.upper,0);relative(r.totals.delta_load_kwh,1e80);relative(r.totals.delta_solar_kwh,1e80);assert.equal(r.totals.delta_other_kwh,0);}
  else{relative(e.delta_other_kwh.lower,1e80);relative(e.delta_other_kwh.upper,1e80);relative(r.bounds.delta_load_kwh.lower,1e80);relative(r.bounds.delta_other_kwh.lower,1e80);}
 }
 const swapped=evidenceComparison([1,1e-20],[1,0],{sec:1e100}),r=guidance(swapped,[],'constant_power');relative(r.full_load_totals.delta_load_kwh,-1e80);relative(r.difference_envelope.delta_other_kwh.lower,-1e80);assert.equal(r.difference_envelope.delta_other_kwh.upper,0);
});
