import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {makeRevisionCase,validateRevisionCase,revisionTemplate,compareRevision} from './public/plan-revision.mjs';
const box={};vm.runInNewContext(readFileSync(new URL('public/vendor/papaparse.min.js',import.meta.url),'utf8'),box);const Papa=box.Papa;
const data=JSON.parse(readFileSync(new URL('public/data.json',import.meta.url)));
const day=data.days.find(d=>d.date==='2026-07-15');
export const makeCase=(overrides={})=>makeRevisionCase({assessment:{schema:1,kind:'fixed_plan_consequence_assessment',date:day.date,identity:{data_sha256:'a'.repeat(64)},inputs:{times:day.times,production:day.schedules['4000'].production,demand:120,capacity:4000,reserve:800,initial:2000,target:2000,startHour:10,scenario:{initial_storage_m3:700},...overrides}},unit_capacity_m3_h:500,specific_energy_kwh_m3:3.4});
const file={name:'case.json',sha256:'b'.repeat(64)},proposal={name:'returned.csv',sha256:'c'.repeat(64)};
const rows=c=>revisionTemplate(c,file.sha256);
const compare=(c,r=rows(c))=>compareRevision({revisionCase:c,caseIdentity:file,csvText:Papa.unparse(r),proposalIdentity:proposal,Papa});
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-7,`${a} != ${b}`);
test('July 15 returned +100 m³ closes terminal gap with +340 modeled kWh and identical conditions',()=>{
 const c=makeCase(),before=JSON.stringify(c),r=rows(c);r[1][2]=220;const v=compare(c,r);
 near(v.original.result.totals.final_storage_m3,1900);near(v.revised.result.totals.final_storage_m3,2000);near(v.changes.available_production_m3,100);near(v.changes.modeled_production_energy_kwh,340);
 near(v.original.result.totals.terminal_deficit_m3,100);near(v.revised.result.totals.terminal_deficit_m3,0);near(v.changes.unmet_m3,0);near(v.revised.result.totals.max_reserve_deficit_m3,100);
 assert.deepEqual({...v.revised.inputs,production:undefined},{...v.original.inputs,production:undefined});assert.deepEqual(v.revised.inputs.production.slice(0,10),v.original.inputs.production.slice(0,10));assert.equal(JSON.stringify(c),before);
});
test('zero change parity, unequal terminal surplus, missing SEC and less service remain explicit',()=>{
 const c=makeCase(),same=compare(c);assert.deepEqual(same.original.result,same.revised.result);
 const extra=rows(c);extra[1][2]=320;near(compare(c,extra).revised.result.totals.terminal_deviation_m3,100);
 const zero=rows(c);zero.slice(1).forEach(r=>r[2]=0);const loss=compare(c,zero);near(loss.revised.result.totals.unmet_m3,980);assert.ok(loss.changes.modeled_production_energy_kwh<0);assert.match(loss.scope.join(' '),/Less service is not credited as savings/);
 c.specific_energy_kwh_m3=null;const unknown=compare(c);assert.equal(unknown.original.modeled_production_energy_kwh,null);assert.equal(unknown.changes.modeled_production_energy_kwh,null);
});
test('production loss, fractional outage and overflow apply identically and energy includes spill',()=>{
 const c=makeCase({scenario:{initial_storage_m3:3990,production_multiplier:.9,demand_multiplier:1.1,outage:{start_hour:12.5,duration_hours:1}}});
 const r=rows(c);r.slice(1).forEach(row=>row[2]=500);const v=compare(c,r);
 assert.ok(v.revised.result.totals.spill_m3>0);near(v.revised.modeled_production_energy_kwh,13*500*.9*3.4);near(v.revised.result.totals.mass_balance_error_m3,0);
 assert.deepEqual(v.original.inputs.scenario,v.revised.inputs.scenario);
});
test('restart uses exact remaining suffix; row order and equivalent offsets do not change mapping',()=>{
 const c=makeCase({startHour:undefined,scenario:{restart:{hour:10,storage_m3:700}}});delete c.assessment.inputs.startHour;
 const r=rows(c);assert.equal(r.length,15);r.slice(1).forEach(row=>row[1]=new Date(row[1]).toISOString());const shuffled=[r[0],...r.slice(1).reverse()];assert.deepEqual(compare(c,shuffled).revised.result,compare(c).original.result);
});
test('case canonicalization discards stale computed totals; validates physical inputs and no remaining day',()=>{
 const c=makeCase();const assessment={...c.assessment,selected:{totals:{final_storage_m3:999999}},sensitivity:[{fake:1}],control:{fake:1}};
 const frozen=makeRevisionCase({assessment,unit_capacity_m3_h:500,specific_energy_kwh_m3:null});assert.equal(frozen.assessment.selected,undefined);near(compare(frozen).original.result.totals.final_storage_m3,1900);
 for(const mutate of [v=>v.assessment.inputs.startHour=24,v=>v.assessment.inputs.times[1]=v.assessment.inputs.times[0],v=>v.assessment.inputs.scenario.extra=1,v=>v.unit_capacity_m3_h=100,v=>v.specific_energy_kwh_m3=0,v=>v.assessment.identity.data_sha256='bad',v=>v.fake=1]){const bad=structuredClone(c);mutate(bad);assert.throws(()=>validateRevisionCase(bad));}
});
test('wrong identity, missing/duplicate/outside hours, extra columns and malformed rates are rejected',()=>{
 const c=makeCase();for(const mutate of [r=>r[1][0]='d'.repeat(64),r=>r.pop(),r=>r[2][1]=r[1][1],r=>r[1][1]=day.times[0],r=>r[1][1]='2026-07-15T10:00:00',r=>r[0].push('other'),r=>r[1].push('other'),...['',-1,501,'Infinity','NaN','0x10','1e999'].map(value=>r=>r[1][2]=value)]){const r=rows(c);mutate(r);assert.throws(()=>compare(c,r));}
 assert.throws(()=>compareRevision({revisionCase:c,caseIdentity:{name:'x',sha256:'bad'},csvText:Papa.unparse(rows(c)),proposalIdentity:proposal,Papa}));
 assert.throws(()=>compareRevision({revisionCase:c,caseIdentity:file,csvText:'"unterminated',proposalIdentity:proposal,Papa}));
});
test('paired production and electricity changes survive a huge common total and cancellation',()=>{
 const production=Array(24).fill(0);production[0]=1;
 const c=makeCase({production,demand:0,startHour:0,scenario:{}});c.specific_energy_kwh_m3=1e100;
 const r=rows(c);r[2][2]=1e-20;const v=compare(c,r);
 assert.equal(v.original.result.totals.available_production_m3,v.revised.result.totals.available_production_m3);
 assert.equal(v.original.modeled_production_energy_kwh,v.revised.modeled_production_energy_kwh);
 assert.equal(v.changes.available_production_m3,1e-20);assert.equal(v.changes.modeled_production_energy_kwh,1e-20*1e100);
 c.assessment.inputs.production[1]=1e-20;const cancel=rows(c);cancel[1][2]=0;cancel[2][2]=0;cancel[3][2]=1;
 const reversed=compare(c,cancel);assert.equal(reversed.changes.available_production_m3,-1e-20);assert.equal(reversed.changes.modeled_production_energy_kwh,-1e-20*1e100);
 c.specific_energy_kwh_m3=null;const unknown=compare(c,cancel);assert.equal(unknown.changes.available_production_m3,-1e-20);assert.equal(unknown.changes.modeled_production_energy_kwh,null);
 c.assessment.inputs.production[1]=0;c.specific_energy_kwh_m3=1e-200;const tiny=rows(c);tiny[2][2]=1e-200;assert.throws(()=>compare(c,tiny),/numeric range or precision/);
});
