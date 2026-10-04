import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {validateSchedule} from './public/core.mjs';
const sandbox={module:{exports:{}},exports:{}};vm.runInNewContext(fs.readFileSync('public/vendor/papaparse.min.js','utf8'),sandbox);const Papa=sandbox.module.exports;
const data=JSON.parse(fs.readFileSync('public/data.json','utf8')),day=data.days[0];
const make=(cap=4000,production=day.schedules[String(cap)].production,extra=[])=>Papa.unparse([['time','production_m3','tank_capacity_m3',...extra.map(x=>x[0])],...day.times.map((time,h)=>[time,production[h],cap,...extra.map(x=>x[1][h])])]);
const check=text=>validateSchedule(text,data,4000,Papa);
test('all 460 retained plans pass independent frontend balance/bound checks',()=>{for(const d of data.days)for(const cap of data.tanks){const p=d.schedules[String(cap)],text=Papa.unparse([['time','production_m3','tank_capacity_m3','storage_start_m3','storage_end_m3'],...d.times.map((time,h)=>[time,p.production[h],cap,p.storage_start[h],p.storage[h]])]),r=check(text);assert.equal(r.status,'VALIDATED',`${d.date}/${cap}: ${JSON.stringify(r.issues)}`);assert.ok(Math.abs(r.candidate.plan.totals.cost_eur-p.totals.cost_eur)<1e-6);assert.equal(r.candidate.plan.totals.safety_violations,0);}});
test('flat candidate is valid and comparison assumptions stay explicit',()=>{const r=check(make(4000,Array(24).fill(120)));assert.equal(r.status,'VALIDATED');assert.ok(Math.abs(r.candidate.plan.totals.cost_eur-1319.88)<1e-6);assert.ok(Math.abs(r.candidate.plan.totals.cost_saving_eur)<1e-9);assert.match(r.warnings.join(' '),/no ramps/);});
test('capacity, negative, nonfinite, reserve and terminal violations block',()=>{for(const [value,code]of[[501,'unit_capacity'],[-1,'invalid_number'],['Infinity','invalid_number']]){const p=Array(24).fill(120);p[0]=value;assert.ok(check(make(4000,p)).issues.some(i=>i.code===code));}assert.ok(check(make(500,[...Array(4).fill(0),...Array(20).fill(144)])).issues.some(i=>i.code==='tank_bound'));assert.ok(check(make(4000,Array(24).fill(121))).issues.some(i=>i.code==='terminal_balance'));});
test('unsupported plant assumptions are distinct from malformed CSV',()=>{const r=check(make(4000,Array(24).fill(120),[['demand_m3',Array(24).fill(130)]]));assert.ok(r.issues.every(i=>i.code==='unsupported_assumption'));const t=check(make(6000,Array(24).fill(120)));assert.ok(t.issues.some(i=>i.code==='unsupported_assumption'));});
test('complete day, strict times, unique instants and one local date required',()=>{const rows=Papa.parse(make()).data;for(const mutate of[m=>m.pop(),m=>m[2][0]=m[1][0],m=>m[2][0]='2026-07-01T01:30:00+03:00',m=>m[2][0]='2026-07-01T01:00:00',m=>m[2][0]='2026-07-02T01:00:00+03:00']){const m=structuredClone(rows);mutate(m);assert.equal(check(Papa.unparse(m)).status,'BLOCKED');}const z=structuredClone(rows);z[1][0]='2026-06-30T21:00:00Z';assert.equal(check(Papa.unparse(z)).status,'VALIDATED');});
test('reordering is normalized; supplied inventory and prices cannot override derivation',()=>{const rows=Papa.parse(make()).data;const header=rows.shift();assert.equal(check(Papa.unparse([header,...rows.reverse()])).status,'VALIDATED');const r=check(make(4000,Array(24).fill(120),[['storage_end_m3',Array(24).fill(3000)]]));assert.ok(r.issues.some(i=>i.code==='inventory_mismatch'));const p=check(make(4000,Array(24).fill(120),[['assumed_price_eur_mwh',Array(24).fill(99)]]));assert.ok(p.issues.some(i=>i.code==='unsupported_assumption'));});
test('missing tank column uses explicit context and declares it',()=>{const text=Papa.unparse([['time','production_m3'],...day.times.map(time=>[time,120])]);const r=validateSchedule(text,data,1000,Papa);assert.equal(r.candidate.tankCapacityM3,1000);assert.match(r.warnings.join(' '),/selected workspace context/);});
test('unsupported schedule assumptions and misspelled fields cannot produce a validated candidate',()=>{
 for(const field of ['maximum_power_kw','maximum_starts','demand_m3_h','method','']){
  const r=check(make(4000,Array(24).fill(120),[[field,Array(24).fill(100)]]));
  assert.equal(r.status,'BLOCKED',field);assert.equal(r.candidate,null);
  assert.ok(r.issues.some(i=>i.record===1&&i.field===field&&i.code==='unsupported_column'),field);
 }
});
test('every declared optional schedule field remains checked and accepted on the matched flat plan',()=>{
 const extra=[['demand_m3',Array(24).fill(120)],['storage_start_m3',Array(24).fill(2000)],['storage_end_m3',Array(24).fill(2000)],['storage_m3',Array(24).fill(2000)],['assumed_price_eur_mwh',day.prices],['safety_minimum_m3',Array(24).fill(800)],['unit_capacity_m3_hour',Array(24).fill(500)]];
 const r=check(make(4000,Array(24).fill(120),extra));assert.equal(r.status,'VALIDATED');assert.equal(r.issues.length,0);
});
