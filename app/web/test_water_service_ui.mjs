import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import vm from 'node:vm';
import {JSDOM} from 'jsdom';
import {makeRevisionCase,revisionTemplate} from './public/plan-revision.mjs';
import {sequenceRevisionTemplate} from './public/sequence-revision.mjs';
import {solarAllocationTemplate} from './public/solar-allocation.mjs';
import {planRevisionTemplate,setupPlanRevision,waterServiceDisplay,waterServiceRows,waterServiceProofMatches} from './public/plan-revision-ui.mjs';
import {planSequenceTemplate,setupPlanSequence} from './public/plan-sequence-ui.mjs';
const parser={};vm.runInNewContext(readFileSync(new URL('public/vendor/papaparse.min.js',import.meta.url),'utf8'),parser);const Papa=parser.Papa;
const hash=value=>createHash('sha256').update(typeof value==='string'?value:Buffer.from(value)).digest('hex'),raw=(name,value)=>{const text=typeof value==='string'?value:JSON.stringify(value,null,2)+'\n';return {name,text,sha256:hash(text)};};
const start=Date.parse('2026-07-01T00:00:00+03:00'),at=hour=>new Date(start+hour*3600000).toISOString(),pad=values=>[...values,...Array(24-values.length).fill(0)];
const daily=()=>makeRevisionCase({assessment:{schema:1,kind:'fixed_plan_consequence_assessment',date:'2026-07-01',identity:{data_sha256:'a'.repeat(64)},inputs:{times:Array.from({length:24},(_,h)=>at(h)),production:pad([2,0]),demand:pad([0,4]),capacity:2,reserve:0,initial:0,target:0}},unit_capacity_m3_h:4,specific_energy_kwh_m3:1});
function boot(kind='daily'){
 const dom=new JSDOM(kind==='daily'?planRevisionTemplate:planSequenceTemplate),w=dom.window,$=id=>w.document.getElementById(id),downloads=[];globalThis.document=w.document;globalThis.Option=w.Option;
 const text=(id,value)=>{$(id).textContent=value;},table=(id,heads,rows)=>{const t=w.document.createElement('table');for(const values of [heads,...rows]){const tr=t.insertRow();for(const value of values)tr.insertCell().textContent=value??'—';}$(id).replaceChildren(t);};
 const args={$,fmt:(v,d=2)=>Number.isFinite(v)?v.toFixed(d):'—',text,table,facts:(id,rows)=>table(id,[],rows),reviewTrace:()=>{},reviewBoundary:(id,rows)=>table(id,[],rows),lineChart:()=>{},download:(name,text)=>downloads.push({name,text}),json:(name,value)=>downloads.push({name,text:JSON.stringify(value)}),csv:(name,value)=>downloads.push({name,text:Papa.unparse(value)}),sha256:async value=>hash(value),getAssessment:()=>null,getDataIdentity:()=> 'a'.repeat(64),getReference:()=>({files:{data:{sha256:'a'.repeat(64)}}}),openDay:async()=>{},Papa};
 const ui=kind==='daily'?setupPlanRevision(args):setupPlanSequence(args);
 async function load(id,file,read){const bytes=new TextEncoder().encode(file.text);Object.defineProperty($(id),'files',{configurable:true,value:[{name:file.name,size:bytes.length,arrayBuffer:read??(async()=>bytes.buffer)}]});await $(id).onchange();}
 return {w,$,ui,downloads,load,close:()=>{w.close();delete globalThis.document;delete globalThis.Option;}};
}
async function openDaily(a){const c=daily(),file=raw('case.json',c);await a.load('revision-case-file',file);const rows=revisionTemplate(c,file.sha256);rows[1][2]=0;rows[2][2]=2;await a.load('revision-proposal-file',raw('return.csv',Papa.unparse(rows)));assert.ok(a.ui.snapshot(),a.$('revision-proposal-status').textContent);return file;}
function exportDaily(a){a.$('revision-note').value='Historical review of the supplied trade-off';a.$('revision-decision').value='Ready for next simulation';a.$('revision-review-form').onsubmit({preventDefault(){}});return JSON.parse(a.downloads.at(-1).text);}

test('subhour service finding focuses the annotated inspector and keeps exact proof separately accessible',async()=>{
 const a=boot();try{await openDaily(a);const s=a.ui.snapshot().water_service;assert.equal(s.status,'regression_detected');assert.equal(a.ui.snapshot().changes.unmet_m3,0);assert.equal(a.$('revision-service-heading').textContent,'Water delivery reduced');assert.match(a.$('revision-service-detail').textContent,/Added shortfall: 1 m³.*≈.*01:00–01:30/);assert.match(a.$('revision-service-proof').textContent,/\[1, 1\.5\)/);assert.match(a.$('revision-hours').textContent,/Original delivered m³Returned delivered m³Original unmet m³Returned unmet m³/);a.$('revision-service-inspect').click();assert.equal(a.$('revision-inspect-hour').value,'1');assert.equal(a.$('revision-inspect').open,true);assert.equal(a.$('revision-plan-details').open,false);assert.equal(a.$('revision-hour-detail').open,false);assert.equal(a.w.document.activeElement.id,'revision-inspect');assert.equal(a.w.document.activeElement.closest('[hidden]'),null);assert.match(a.$('revision-first-interval').textContent,/Unserved rate: original 0; returned 2 m³\/h/);a.$('revision-plan-details').open=true;a.$('revision-hour-detail').open=true;a.$('revision-service-proof').focus();assert.equal(a.w.document.activeElement.id,'revision-service-proof');const profile=solarAllocationTemplate(a.ui.snapshot());Object.assign(profile,{source_kind:'illustrative_scenario',source_label:'Analytical hourly solar',plant_mapping:'Single modeled plant'});profile.intervals.forEach((row,h)=>row.power_kw=h===1?2:0);await a.load('revision-solar-file',raw('solar.json',profile));assert.match(a.$('revision-solar-timing').textContent,/More solar use.*Water comparison fails on delivery/);}finally{a.close();}
});

test('reopen recalculates false cached service and clears undisclosed ready text, while identical proof preserves history',async()=>{
 const a=boot();let saved;try{await openDaily(a);saved=exportDaily(a);assert.equal(saved.comparison.water_service.status,'regression_detected');const unchanged=structuredClone(saved);unchanged.comparison.water_service=Object.fromEntries(Object.entries(unchanged.comparison.water_service).reverse());await a.load('revision-case-file',raw('review.json',unchanged));assert.equal(a.$('revision-decision').value,'Ready for next simulation');assert.equal(a.$('revision-note').value,saved.reason);assert.match(a.$('revision-review-status').textContent,/historical/);saved.comparison.water_service.status='no_modeled_regression';saved.comparison.water_service.criteria.delivery_no_worse=true;await a.load('revision-case-file',raw('review.json',saved));assert.equal(a.ui.snapshot().water_service.status,'regression_detected');assert.equal(a.$('revision-decision').value,'Needs team review');assert.equal(a.$('revision-note').value,'');assert.match(a.$('revision-review-status').textContent,/Prior decision and reason cleared/);assert.equal(a.$('revision-decision-panel').open,true);}finally{a.close();}
});

test('pending proposal replacement and assumption edits cannot restore a stale service finding',async()=>{
 const a=boot();try{await openDaily(a);const file=raw('return.csv','bad');let release;const pending=a.load('revision-proposal-file',file,()=>new Promise(resolve=>{release=()=>resolve(new TextEncoder().encode(file.text).buffer);}));assert.equal(a.ui.snapshot(),null);assert.equal(a.$('revision-result').hidden,true);assert.equal(a.$('revision-service-heading').textContent,'');a.$('revision-unit').value='3';a.$('revision-unit').dispatchEvent(new a.w.Event('input'));release();await pending;assert.equal(a.ui.snapshot(),null);assert.equal(a.$('revision-review-export').disabled,true);assert.equal(a.$('revision-service-inspect').hidden,true);}finally{a.close();}
});

function continuous(){
 const blocks=[0,1].map(day=>({times:Array.from({length:24},(_,h)=>at(day*24+h)),production:pad(day?[0,1,0]:[]),demand:pad(day?[2,1,1]:[])})),input={blocks,capacity:2,reserve:1,initial:1,target:1,unitCapacity:4,scenario:{demand_multiplier:1,production_multiplier:1},outages:[]};
 const source=raw('sequence.json',{schema:1,kind:'fixed_plan_sequence_source',label:'Analytical cross-midnight supply',control_rate_m3_h:0,specific_energy_kwh_m3:1,inputs:input}),file=raw('sequence-case.json',{schema:1,kind:'continuous_plan_revision_case',source_file:source,conditions:{initial:1,demand_multiplier:1,production_multiplier:1,outages:[]},block_index:1}),rows=sequenceRevisionTemplate({input,block_index:1,case_sha256:file.sha256});rows[2][2]=0;rows[3][2]=1;return {file,returned:raw('sequence-return.csv',Papa.unparse(rows))};
}
test('continuous service inspect selects the affected day and exported proof is recomputed on reopen',async()=>{
 const a=boot('sequence'),c=continuous();try{await a.load('sequence-file',c.file);await a.load('sequence-return-file',c.returned);assert.equal(a.$('sequence-error').hidden,true,a.$('sequence-error').textContent);assert.equal(a.$('sequence-service-heading').textContent,'Water delivery reduced');assert.match(a.$('sequence-service-detail').textContent,/02 Jul 2026.*01:00/);a.$('sequence-day').value='0';a.$('sequence-day').onchange();a.$('sequence-service-inspect').click();assert.equal(a.$('sequence-day').value,'1');assert.equal(a.$('sequence-accounting-details').open,true);assert.equal(a.w.document.activeElement.id,'sequence-service-proof');assert.match(a.$('sequence-service-hours').textContent,/Original delivered m³Returned delivered m³/);a.$('sequence-reason').value='Historical continuous decision';a.$('sequence-export').click();const saved=JSON.parse(a.downloads.at(-1).text);assert.equal(saved.results.water_service.status,'regression_detected');assert.deepEqual(saved.case_file,c.file);assert.deepEqual(saved.proposal_file,c.returned);saved.results.water_service.status='no_modeled_regression';await a.load('sequence-file',raw('review.json',saved));assert.equal(a.$('sequence-service-heading').textContent,'Water delivery reduced');assert.equal(a.$('sequence-reason').value,'');a.$('sequence-return-remove').click();assert.equal(a.$('sequence-service-heading').hidden,true);assert.equal(a.$('sequence-service-proof').hidden,true);assert.equal(a.$('sequence-conclusion').hidden,false);}finally{a.close();}
});

test('exact positive values outside numeric display range never read as zero or unknown',()=>{
 const q=(n,d='1',value=Number(n)/Number(d))=>({value,exact:{numerator:String(n),denominator:String(d)}}),tiny=q('1','1'+'0'.repeat(400),null),zero=q(0),one=q(1),w={start_hour:zero,end_hour:one,original_unserved_rate_m3_h:zero,revised_unserved_rate_m3_h:tiny,added_unserved_rate_m3_h:tiny},s={schema:1,kind:'modeled_paired_water_service',status:'regression_detected',criteria:{delivery_no_worse:false,reserve_no_worse:true,end_stock_no_lower:true},horizon:{start_epoch:start,start_hour:zero,end_hour:one,duration_hours:one},delivery:{interval_count:1,duration_hours:one,shifted_shortfall_m3:tiny,max_added_unserved_rate_m3_h:tiny,first:w,maximum:w},reserve:{interval_count:0,duration_hours:zero,max_added_deficit_m3:zero,first:null,maximum:null},end_stock:{original_m3:zero,revised_m3:zero,delta_m3:zero}};
 assert.equal(waterServiceDisplay(s).title,'Water delivery reduced');const rendered=waterServiceRows(s).flat().join(' ');assert.match(rendered,/Positive; outside numeric display range/);assert.match(rendered,/exact nonzero retained in exported review/);assert.ok(!rendered.includes('0'.repeat(40)));assert.ok(!rendered.includes('Delivery / maximum'));assert.match(rendered,/1 affected interval \/ 1 h/);assert.doesNotMatch(rendered,/1 affected intervals/);assert.doesNotMatch(rendered,/Unknown/);assert.equal(waterServiceProofMatches(s,Object.fromEntries(Object.entries(s).reverse())),true);const compact=structuredClone(s);compact.criteria={delivery_no_worse:true,reserve_no_worse:false,end_stock_no_lower:true};Object.assign(compact.delivery,{interval_count:0,duration_hours:zero,shifted_shortfall_m3:zero,first:null,maximum:null});Object.assign(compact.reserve,{interval_count:1,duration_hours:q(1,4),max_added_deficit_m3:q(1,6)});compact.end_stock.delta_m3=q(1,2);const rows=waterServiceRows(compact),details=rows.flat().join(' ');assert.equal(rows.length,5);assert.match(details,/0\.166667 m³ \(exact 1\/6\)/);assert.match(details,/1 affected interval \/ 0\.25 h/);assert.match(details,/0\.5 m³/);assert.doesNotMatch(details,/exact 1\/2|exact 1\/4|Shifted shortfall|Delivery duration/);
});


test('loaded case identity remains visible for a no-regression return and fresh saved-review reopen',async()=>{
 const a=boot();let saved,label;
 try{
  assert.equal(a.$('revision-active-case').hidden,true);
  const c=daily(),file=raw('same-case.json',c);await a.load('revision-case-file',file);
  label=a.$('revision-active-case').textContent;
  assert.equal(a.$('revision-active-case').hidden,false);assert.equal(a.$('revision-active-case').closest('details'),null);
  assert.match(label,/01 Jul 2026/);assert.match(label,/02 Jul 2026/);assert.match(label,/2 m³ tank \/ 24 h/);
  await a.load('revision-proposal-file',raw('unchanged.csv',Papa.unparse(revisionTemplate(c,file.sha256))));
  assert.equal(a.ui.snapshot().water_service.status,'no_modeled_regression');assert.equal(a.$('revision-inputs').open,false);assert.equal(a.$('revision-assumptions').open,false);
  assert.equal(a.$('revision-active-case').hidden,false);assert.equal(a.$('revision-active-case').textContent,label);assert.equal(a.$('revision-service-inspect').hidden,true);
  saved=exportDaily(a);
 }finally{a.close();}
 const b=boot();try{await b.load('revision-case-file',raw('reopened.json',saved));assert.equal(b.$('revision-active-case').hidden,false);assert.equal(b.$('revision-active-case').textContent,label);assert.equal(b.$('revision-active-case').closest('[hidden]'),null);assert.equal(b.$('revision-inputs').open,false);assert.equal(b.ui.snapshot().water_service.status,'no_modeled_regression');}finally{b.close();}
});

test('case identity clears while replaced and a stale case read cannot overwrite the newer horizon',async()=>{
 const a=boot();try{
  await openDaily(a);const old=raw('old.json',daily());let release;
  const pending=a.load('revision-case-file',old,()=>new Promise(resolve=>{release=()=>resolve(new TextEncoder().encode(old.text).buffer);}));
  assert.equal(a.$('revision-active-case').hidden,true);assert.equal(a.$('revision-active-case').textContent,'');
  const next=daily();next.assessment.inputs.capacity=3;next.assessment.inputs.startHour=10;
  await a.load('revision-case-file',raw('new.json',next));assert.match(a.$('revision-active-case').textContent,/10:00/);assert.match(a.$('revision-active-case').textContent,/3 m³ tank \/ 14 h/);
  const label=a.$('revision-active-case').textContent;release();await pending;assert.equal(a.$('revision-active-case').textContent,label);
  a.$('revision-unit').value='3';a.$('revision-unit').dispatchEvent(new a.w.Event('input'));assert.equal(a.$('revision-active-case').hidden,true);assert.equal(a.$('revision-active-case').textContent,'');
 }finally{a.close();}
});
