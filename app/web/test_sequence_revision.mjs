import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {sequenceRevisionTemplate,compareSequenceRevision,validateSequenceRevisionComparison} from './public/sequence-revision.mjs';
import {sequenceSolarAllocationTemplate,evaluateSequenceSolarAllocation,solarAllocationTemplate,evaluateSolarAllocation} from './public/solar-allocation.mjs';
import {makeRevisionCase,revisionTemplate,compareRevision} from './public/plan-revision.mjs';

const box={};vm.runInNewContext(readFileSync(new URL('public/vendor/papaparse.min.js',import.meta.url),'utf8'),box);const Papa=box.Papa;
const at=h=>new Date(Date.UTC(2026,6,1)+h*3600000).toISOString(),caseIdentity={name:'sequence-case.json',sha256:'b'.repeat(64)},proposalIdentity={name:'sequence-return.csv',sha256:'c'.repeat(64)};
const block=index=>({times:Array.from({length:24},(_,hour)=>at(index*24+hour)),production:Array(24).fill(1),demand:1});
const input=(options={})=>({blocks:[block(0),block(1)],capacity:100,reserve:0,initial:10,target:10,unitCapacity:4,...options});
const near=(actual,expected)=>assert.ok(Math.abs(actual-expected)<=1e-7,`${actual} != ${expected}`);
function args(i=input(),first=0,sec=1){return {input:i,block_index:first,caseIdentity,proposalIdentity,specific_energy_kwh_m3:sec,Papa};}
function compare(options={},mutate=()=>{}){const a={...args(),...options},rows=sequenceRevisionTemplate({input:a.input,block_index:a.block_index,case_sha256:caseIdentity.sha256});mutate(rows);return compareSequenceRevision({...a,csvText:Papa.unparse(rows)});}
function shift(rows){rows[24][2]=2;rows[25][2]=0;}
function allocation(c,semantics='constant_power'){
 const p=sequenceSolarAllocationTemplate(c,semantics);Object.assign(p,{source_kind:'illustrative_scenario',source_label:'Analytical fixture',plant_mapping:'Declared unit',review_as_of:at(49)});
 p.intervals.forEach(r=>{r.available_at=at(-1);if(semantics==='constant_power')r.power_kw=0;else Object.assign(r,{energy_kwh:0,power_cap_kw:2});});return p;
}
const solar=(c,p)=>evaluateSequenceSolarAllocation({comparison:c,allocation:p});
function coarse(c,energy=2){const p=allocation(c,'interval_energy');p.intervals=[{...p.intervals[0],end:at(23)},{...p.intervals[23],end:at(25),energy_kwh:energy},{...p.intervals[25],end:at(48)}];return p;}

test('template covers every remaining block unchanged and comparison replays the full prefix',()=>{
 const i=input({blocks:[block(0),block(1),block(2)]}),a=args(i,1),rows=sequenceRevisionTemplate({input:i,block_index:1,case_sha256:caseIdentity.sha256});
 assert.equal(rows.length,49);assert.equal(rows[1][1],at(24));assert.equal(rows.at(-1)[1],at(71));assert.ok(rows.slice(1).every(row=>row[2]===1));
 const before=JSON.stringify(i);rows[1][2]=3;const c=compareSequenceRevision({...a,csvText:Papa.unparse(rows)});
 assert.equal(c.original.result.rows.length,72);assert.deepEqual(c.revised.inputs.blocks[0],i.blocks[0]);near(c.revised.result.blocks[1].initial_storage_m3,10);near(c.revised.result.blocks[2].initial_storage_m3,12);near(c.changes.final_storage_m3,2);near(c.changes.modeled_production_energy_kwh,2);assert.equal(JSON.stringify(i),before);
});
test('unchanged return reproduces every water row and joint solar change is exactly zero',()=>{
 const c=compare(),p=coarse(c),r=solar(c,p);assert.deepEqual(c.original.result,c.revised.result);assert.ok(Object.values(c.changes).every(v=>v===0));assert.deepEqual(r.bounds.delta_solar_kwh,{lower:0,upper:0});
});
test('complete CSV allows reordered columns and rows, equivalent-offset instants and BOM',()=>{
 const a=args(input(),1),rows=sequenceRevisionTemplate({input:a.input,block_index:1,case_sha256:caseIdentity.sha256});rows[1][1]='2026-07-02T03:00:00+03:00';
 const matrix=[['time','production_m3','case_sha256'],...rows.slice(1).reverse().map(r=>[r[1],r[2],r[0]])];const c=compareSequenceRevision({...a,csvText:'\uFEFF'+Papa.unparse(matrix)});near(c.changes.delivered_m3,0);near(c.changes.final_storage_m3,0);
});
test('strict return rejects absent, extra, duplicate, prefix and wrong-case rows plus malformed rates',()=>{
 const a=args(input(),1),make=()=>sequenceRevisionTemplate({input:a.input,block_index:1,case_sha256:caseIdentity.sha256});
 const mutations=[r=>r.pop(),r=>r.push([...r[1]]),r=>r[2][1]=r[1][1],r=>r[1][1]=at(23),r=>r[1][0]='d'.repeat(64),r=>r[1][2]=-1,r=>r[1][2]=5,r=>r[1][2]='Infinity',r=>r[1][2]='1e309',r=>r[1][2]='',r=>r[1][2]='0x1',r=>r[1][2]='+1',r=>r[1][1]='2026-07-02T00:00:00',r=>r[0].push('ignored'),r=>r[0][0]='time',r=>r[1].push('extra')];
 for(const mutate of mutations){const rows=make();mutate(rows);assert.throws(()=>compareSequenceRevision({...a,csvText:Papa.unparse(rows)}));}
 assert.throws(()=>compareSequenceRevision({...a,csvText:'"unterminated'}),/Malformed/);
});
test('invalid editable block, source, identities and specific energy fail before creating a result',()=>{
 for(const first of [-1,2,.5,undefined])assert.throws(()=>sequenceRevisionTemplate({input:input(),block_index:first,case_sha256:caseIdentity.sha256}));
 assert.throws(()=>sequenceRevisionTemplate({input:input(),block_index:0,case_sha256:'bad'}));
 for(const sec of [undefined,-1,0,Infinity,'1'])assert.throws(()=>compare({specific_energy_kwh_m3:sec}));
 for(const identity of [{name:'',sha256:caseIdentity.sha256},{name:'x',sha256:'bad'},{...caseIdentity,extra:true},{name:'x\n',sha256:caseIdentity.sha256}])assert.throws(()=>compare({caseIdentity:identity}));
 const i=input();i.blocks[1].times[0]=at(25);assert.throws(()=>compare({input:i}));assert.throws(()=>compare({specific_energy_kwh_m3:1e308}),/finite numeric range/);
});
test('one cross-midnight energy constraint admits both signs without inventing daily energy',()=>{
 const c=compare({},shift),p=coarse(c),before=JSON.stringify({c,p}),r=solar(c,p);
 assert.equal(r.status,'complete');near(r.bounds.delta_solar_kwh.lower,-1);near(r.bounds.delta_solar_kwh.upper,1);near(c.original.result.totals.delivered_m3,48);near(c.revised.result.totals.delivered_m3,48);near(c.changes.final_storage_m3,0);near(r.full_load_totals.delta_load_kwh,0);assert.equal(r.rows.length,3);assert.equal(JSON.stringify({c,p}),before);
});
test('hourly evidence resolves the same cross-midnight comparison in opposite directions',()=>{
 const c=compare({},shift);for(const [hour,expected] of [[23,1],[24,-1]]){const p=allocation(c,'interval_energy');p.intervals[hour].energy_kwh=2;const r=solar(c,p);near(r.bounds.delta_solar_kwh.lower,expected);near(r.bounds.delta_solar_kwh.upper,expected);}
});
test('cross-midnight fractional outage stays inside the single shared energy constraint',()=>{
 const c=compare({input:input({outages:[{start:at(23.5),end:at(24.5)}]})},shift),r=solar(c,coarse(c,1));
 near(r.bounds.delta_solar_kwh.lower,-.5);near(r.bounds.delta_solar_kwh.upper,.5);near(r.full_load_totals.original_load_kwh,47);near(r.full_load_totals.revised_load_kwh,47);near(c.revised.result.blocks[1].initial_storage_m3,10);
});
test('more solar never hides service loss or higher final inventory after a shortage',()=>{
 const c=compare({input:input({initial:0,target:0})},rows=>{rows[24][2]=0;rows[25][2]=2;}),p=allocation(c);p.intervals[24].power_kw=2;const r=solar(c,p);
 near(r.totals.delta_solar_kwh,1);near(c.original.result.totals.delivered_m3,48);near(c.revised.result.totals.delivered_m3,47);near(c.changes.unmet_m3,1);near(c.changes.final_storage_m3,1);
});
test('spill, inventory depletion and extra production remain separate from solar change',()=>{
 const spill=compare({input:input({capacity:10})},shift);near(spill.changes.spill_m3,1);near(spill.changes.final_storage_m3,-1);near(spill.changes.modeled_production_energy_kwh,0);
 const depletion=compare({},rows=>rows[25][2]=0);near(depletion.changes.modeled_production_energy_kwh,-1);near(depletion.changes.delivered_m3,0);near(depletion.changes.final_storage_m3,-1);
 const extra=compare({},rows=>rows[24][2]=2),p=allocation(extra);p.intervals[23].power_kw=2;const r=solar(extra,p);near(r.totals.delta_solar_kwh,1);near(r.totals.delta_load_kwh,1);near(extra.changes.final_storage_m3,1);
 const all=allocation(spill, 'constant_power');all.intervals.forEach(row=>row.power_kw=10);near(solar(spill,all).totals.revised_load_kwh,48);
});
test('partial, late and unknown solar support never establishes whole-period totals or bounds',()=>{
 const c=compare({},shift);for(const semantics of ['constant_power','interval_energy']){
  const p=allocation(c,semantics);if(semantics==='constant_power')p.intervals[23].power_kw=2;else p.intervals[23].energy_kwh=2;
  p.intervals[24].available_at=at(50);p.intervals[25][semantics==='constant_power'?'power_kw':'power_cap_kw']=null;p.intervals.splice(26,1);
  const r=solar(c,p);assert.equal(r.status,'partial');assert.equal(r.totals,null);if(semantics==='interval_energy')assert.equal(r.bounds,null);assert.deepEqual(r.coverage,{horizon_hours:48,known_hours:45,unknown_hours:3,late_hours:1});near(r.full_load_totals.original_load_kwh,48);
 }
 const c2=compare({specific_energy_kwh_m3:null}),r2=solar(c2,allocation(c2));assert.equal(r2.status,'unknown_energy');assert.equal(r2.full_load_totals,null);assert.equal(c2.changes.modeled_production_energy_kwh,null);
});
test('solar recomputes cached water and electricity, but rejects altered shared conditions or prefix',()=>{
 const c=compare({input:input({blocks:[block(0),block(1),block(2)]}),block_index:1},rows=>rows[1][2]=2),p=allocation(c);p.intervals.forEach(row=>row.power_kw=10);
 c.original.result={};c.revised.result={};c.original.modeled_production_energy_kwh=0;c.revised.modeled_production_energy_kwh=0;c.changes={};const r=solar(c,p);near(r.totals.original_load_kwh,72);near(r.totals.revised_load_kwh,73);
 const mutations=[v=>v.revised.inputs.blocks[0].production[0]=2,v=>v.revised.inputs.blocks[1].demand=2,v=>v.revised.inputs.initial=11,v=>v.revised.inputs.target=11,v=>v.revised.inputs.unitCapacity=5,v=>v.revised.inputs.scenario={production_multiplier:.9},v=>v.block_index=3,v=>v.specific_energy_kwh_m3=0];
 for(const change of mutations){const bad=structuredClone(c);change(bad);assert.throws(()=>solar(bad,p));}assert.equal(validateSequenceRevisionComparison(c).revised.result.rows.length,72);
});
test('solar rejects profile mismatches and invalid intervals across block boundaries',()=>{
 const c=compare();for(const change of [p=>p.case_sha256='d'.repeat(64),p=>p.intervals[24].start=at(23),p=>p.intervals[0].start=at(-1),p=>p.intervals.at(-1).end=at(49),p=>p.intervals[0].energy_kwh=3,p=>p.power_basis='regional_curtailment',p=>p.interval_semantics='hourly_average']){const p=allocation(c,'interval_energy');change(p);assert.throws(()=>solar(c,p));}
});
test('sequence hourly template supports 366 elapsed-day blocks without raising one-day limits',()=>{
 const c=compare({input:input({blocks:Array.from({length:366},(_,index)=>block(index))})}),p=allocation(c);assert.equal(p.intervals.length,8784);assert.equal(solar(c,p).coverage.horizon_hours,8784);p.intervals.push({...p.intervals[0]});assert.throws(()=>solar(c,p),/8784/);
 const i=input().blocks[0],revisionCase=makeRevisionCase({assessment:{schema:1,kind:'fixed_plan_consequence_assessment',identity:{data_sha256:'a'.repeat(64)},inputs:{...i,capacity:100,reserve:0,initial:10,target:10}},unit_capacity_m3_h:4,specific_energy_kwh_m3:1});
 const daily=compareRevision({revisionCase,caseIdentity,csvText:Papa.unparse(revisionTemplate(revisionCase,caseIdentity.sha256)),proposalIdentity,Papa}),profile=solarAllocationTemplate(daily);Object.assign(profile,{source_label:'Fixture',plant_mapping:'Unit'});profile.intervals=Array(4097).fill({...profile.intervals[0],power_kw:0});assert.throws(()=>evaluateSolarAllocation({comparison:daily,allocation:profile}),/4096/);
});
test('positive electricity cannot silently underflow to zero in totals or individual load pieces',()=>{
 const tiny=rate=>input({blocks:[0,1].map(index=>({...block(index),production:Array(24).fill(rate),demand:0})),initial:0,target:0});
 assert.throws(()=>compare({input:tiny(1e-200),specific_energy_kwh_m3:1e-200}),/numeric range or precision/);
 const c=compare({input:tiny(1e-124),specific_energy_kwh_m3:1e-200});assert.ok(c.original.modeled_production_energy_kwh>0);assert.throws(()=>solar(c,allocation(c)),/numeric range or precision/);
 const d=compare(),p=allocation(d);p.intervals[0].end=at(.25);p.intervals[0].power_kw=Number.MIN_VALUE;assert.throws(()=>solar(d,p),/numeric range or precision/);
 const zero=compare({input:tiny(0),specific_energy_kwh_m3:1e-200});near(solar(zero,allocation(zero)).full_load_totals.original_load_kwh,0);
 const stopped=compare({input:{...tiny(1e-200),outages:[{start:at(0),end:at(48)}]},specific_energy_kwh_m3:1e-200});near(solar(stopped,allocation(stopped)).full_load_totals.original_load_kwh,0);
});
test('whole-period electricity agrees with comparison across varied flows, derating and fractional outages at maximum horizon',()=>{
 const n=366,i=input({blocks:Array.from({length:n},(_,day)=>({...block(day),production:Array.from({length:24},(_,hour)=>((day*29+hour*113)%50000)/100),demand:120})),capacity:4000,reserve:800,initial:2000,target:2000,unitCapacity:500,scenario:{production_multiplier:.723},outages:Array.from({length:n},(_,day)=>({start:at(day*24+12.125),end:at(day*24+12.875)}))});
 const c=compare({input:i,specific_energy_kwh_m3:3.4},rows=>rows.slice(1).forEach((row,index)=>{if(index%3===0)row[2]=Math.min(500,Number(row[2])+7.31);}));
 for(const semantics of ['constant_power','interval_energy']){
  const p=allocation(c,semantics);p.intervals.forEach(row=>{if(semantics==='constant_power')row.power_kw=300;else Object.assign(row,{energy_kwh:300,power_cap_kw:600});});
  const r=solar(c,p);for(const side of ['original','revised'])assert.ok(Math.abs(r.full_load_totals[`${side}_load_kwh`]-c[side].modeled_production_energy_kwh)<=1e-6);
  assert.ok(Math.abs(r.full_load_totals.delta_load_kwh-c.changes.modeled_production_energy_kwh)<=1e-6);
 }
});
test('paired full-period changes preserve a small suffix edit beside an unchanged huge prefix',()=>{
 const i=input({blocks:[0,1].map(index=>({...block(index),production:Array(24).fill(0),demand:0}))});i.blocks[0].production[0]=1;
 const c=compare({input:i,block_index:1,specific_energy_kwh_m3:1e100},rows=>rows[1][2]=1e-20);
 assert.equal(c.original.modeled_production_energy_kwh,c.revised.modeled_production_energy_kwh);assert.equal(c.changes.available_production_m3,1e-20);assert.equal(c.changes.modeled_production_energy_kwh,1e-20*1e100);
 const p=allocation(c);p.intervals=[];assert.equal(solar(c,p).full_load_totals.delta_load_kwh,c.changes.modeled_production_energy_kwh);
 i.blocks[1].production[0]=1e-20;const cancellation=rows=>{rows[1][2]=0;rows[25][2]=0;rows[26][2]=1;};
 const reverse=compare({input:i,specific_energy_kwh_m3:1e100},cancellation);assert.equal(reverse.changes.available_production_m3,-1e-20);assert.equal(reverse.changes.modeled_production_energy_kwh,-1e-20*1e100);
 const unknown=compare({input:i,specific_energy_kwh_m3:null},cancellation);assert.equal(unknown.changes.available_production_m3,-1e-20);assert.equal(unknown.changes.modeled_production_energy_kwh,null);
 i.blocks[1].production[0]=0;assert.throws(()=>compare({input:i,specific_energy_kwh_m3:1e-200},rows=>rows[25][2]=1e-200),/numeric range or precision/);
});
