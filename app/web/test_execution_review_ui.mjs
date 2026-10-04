import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {JSDOM} from 'jsdom';
import {makeExecutionCase,executionMeasurementTemplate} from './public/execution-review.mjs';
import {executionReviewTemplate,setupExecutionReview} from './public/execution-review-ui.mjs';

const hash=value=>createHash('sha256').update(typeof value==='string'?value:Buffer.from(value)).digest('hex');
const clone=value=>JSON.parse(JSON.stringify(value));
function frozen({capacity=200,day=15,bom=false}={}){
 const executionCase=makeExecutionCase({input:{times:Array.from({length:24},(_,h)=>new Date(Date.UTC(2026,6,day,h)).toISOString()),production:Array(24).fill(10),demand:10,capacity,reserve:20,initial:100,target:100},unit_capacity_m3_h:20,specific_energy_kwh_m3:3.4,identity:{fixture_sha256:'a'.repeat(64)}});
 const text=(bom?'\uFEFF':'')+JSON.stringify(executionCase,null,2)+(bom?'\r\n':'\n');return {name:'frozen-plan.json',text,sha256:hash(text)};
}
function source(file,{drain=true,unknown=false}={}){
 const value=executionMeasurementTemplate({executionCase:JSON.parse(file.text.replace(/^\uFEFF/,'')),case_sha256:file.sha256});
 Object.assign(value,{source_kind:'illustrative_scenario',source_label:'Synthetic accounting fixture',plant_mapping:'One test unit',tank_mapping:'One test tank'});
 const totals={energy:drain?680:816,produced:drain?200:240,delivered:240};
 value.streams=value.streams.filter(stream=>Object.hasOwn(totals,stream.role));
 value.streams.forEach(stream=>{stream.readings[0].lower=stream.readings[0].upper=unknown&&stream.role==='energy'?null:totals[stream.role];});
 value.declared_zero=['other_inflow','other_outflow','spill'];value.tank.forEach((row,i)=>row.lower=row.upper=i&&drain?60:100);return value;
}
function boot(plan=frozen()){
 const dom=new JSDOM(`<main>${executionReviewTemplate}<details id="review-decision-editor"><form id="review-form"><textarea id="review-note"></textarea><button id="save-review" type="submit">Save locally</button><button id="download-current-review" type="button">Export review</button></form></details><textarea id="export-preview"></textarea></main>`),w=dom.window,$=id=>w.document.getElementById(id),downloads=[],opened=[],invalidated=[];
 let globalPlan=plan;
 const text=(id,value)=>{$(id).textContent=value;};
 const table=(id,headers,rows)=>{const node=w.document.createElement('table');for(const row of [headers,...rows]){const tr=node.insertRow();for(const value of row)tr.insertCell().textContent=value??'—';}$(id).replaceChildren(node);};
 const json=(name,value)=>{const raw=typeof value==='string'?value:JSON.stringify(value,null,2)+'\n';downloads.push({name,raw,blob:new Blob([raw],{type:'application/json'})});$('export-preview').value=raw;};
 const ui=setupExecutionReview({$,text,table,facts:(id,rows)=>table(id,[],rows),json,sha256:async value=>hash(value),freezeSelectedPlan:async()=>clone(globalPlan),openFrozenPlan:async context=>{if(context.isCurrent())opened.push(context);},invalidateDecision:reason=>{invalidated.push(reason);$('review-note').value='';},onResultChange:()=>{}});
 async function load(raw,name='measurements.json',arrayBuffer){const bytes=typeof raw==='string'?new TextEncoder().encode(raw):raw;Object.defineProperty($('execution-file'),'files',{configurable:true,value:[{name,size:bytes.byteLength,arrayBuffer:arrayBuffer??(async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength))}]});await $('execution-file').onchange();}
 return {ui,$,w,downloads,opened,invalidated,load,plan,replaceGlobal:value=>{globalPlan=value;},close:()=>dom.window.close()};
}
const note={reviewer:'Loucas',decision:'Needs team review',reason:'Check the stock drawn down.'};

test('measured entry is restrained and file handlers export exact frozen bytes and bound template',async()=>{
 const a=boot(frozen({bom:true}));try{
  assert.equal(a.$('execution-summary').hidden,true);assert.equal(a.$('execution-result').hidden,true);assert.equal(a.$('execution-files').open,false);assert.equal(a.$('execution-details').hidden,true);
  await a.$('execution-case-export').onclick();assert.equal(a.downloads[0].raw,a.plan.text);assert.deepEqual(Buffer.from(await a.downloads[0].blob.arrayBuffer()),Buffer.from(a.plan.text,'utf8'));assert.equal(a.$('export-preview').value,a.plan.text.replace(/\r\n?/g,'\n'));
  await a.$('execution-template-export').onclick();const value=JSON.parse(a.downloads[1].raw);assert.equal(value.case_sha256,a.plan.sha256);assert.equal(value.kind,'plant_execution_measurements');assert.ok(value.streams.every(s=>s.readings[0].lower===null));
 }finally{a.close();}
});

test('stock-draw import gives observed totals and finding without an observed curve',async()=>{
 const a=boot();try{
  a.$('review-note').value='Old decision';await a.load(JSON.stringify(source(a.plan)));
  assert.match(a.$('execution-summary').textContent,/Lower electricity/);assert.match(a.$('execution-outcomes').textContent,/200 m³/);assert.match(a.$('execution-outcomes').textContent,/680 kWh/);assert.match(a.$('execution-outcomes').textContent,/-136 kWh/);
  assert.equal(a.$('review-note').value,'');assert.equal(a.$('execution-details').open,false);assert.equal(a.$('execution-result').querySelector('svg'),null);
  a.$('execution-next').click();assert.equal(a.$('execution-details').open,true);assert.equal(a.w.document.activeElement.id,'execution-findings');assert.match(a.$('execution-balance').textContent,/permit balance/);
  const value=a.ui.exportReview(note);assert.equal(value.results.water_balance.status,'compatible');assert.equal(value.results.volume_stock_comparison.status,'different');assert.equal(value.results.source,undefined);assert.equal(value.results.execution_case,undefined);
 }finally{a.close();}
});

test('export and fresh reopen preserve BOM bytes, ignore cached results and start a new decision',async()=>{
 const original=boot(frozen({bom:true}));let packet,raw;try{
  raw='\uFEFF'+JSON.stringify(source(original.plan),null,2)+'\r\n';await original.load(raw);packet=original.ui.exportReview(note);packet.results.measured.energy={lower:0,upper:0};packet.results.water_balance.status='inconsistent';
 }finally{original.close();}
 const fresh=boot(frozen({day:20,capacity:400}));try{
  fresh.$('review-note').value='Must not survive';await fresh.load(JSON.stringify(packet),'saved-review.json');const reopened=fresh.ui.snapshot();
  assert.equal(reopened.measurement_file.text,raw);assert.equal(reopened.measurement_file.sha256,hash(raw));assert.equal(reopened.case_file.sha256,packet.case_file.sha256);assert.equal(reopened.results.measured.energy.lower,680);assert.equal(reopened.results.water_balance.status,'compatible');assert.equal(reopened.note,undefined);assert.equal(fresh.$('review-note').value,'');
  assert.equal(fresh.opened[0].executionCase.input.capacity,200);assert.equal(fresh.opened[0].case_file.text,packet.case_file.text);assert.match(fresh.$('execution-summary').textContent,/Recalculated/);
  await fresh.$('execution-case-export').onclick();assert.equal(fresh.downloads.at(-1).raw,packet.case_file.text);
 }finally{fresh.close();}
});

test('raw replacement retains a reopened external frozen case instead of global selection',async()=>{
 const external=frozen({day:3,capacity:300,bom:true}),builder=boot(external);let packet;
 try{await builder.load(JSON.stringify(source(external)));packet=builder.ui.exportReview(note);}finally{builder.close();}
 const a=boot(frozen({day:15,capacity:4000}));try{
  await a.load(JSON.stringify(packet));await a.load(JSON.stringify(source(external,{drain:false})),'corrected-measurements.json');
  assert.equal(a.ui.snapshot().case_file.sha256,external.sha256);assert.equal(a.ui.snapshot().measurement_file.name,'corrected-measurements.json');assert.equal(a.ui.snapshot().results.measured.energy.lower,816);assert.equal(a.opened.at(-1).executionCase.input.capacity,300);
  const wrong=source(a.plan);await a.load(JSON.stringify(wrong),'wrong-case.json');assert.equal(a.ui.snapshot(),null);assert.equal(a.$('execution-result').hidden,true);assert.match(a.$('execution-summary').textContent,/different frozen case/);
 }finally{a.close();}
});

test('hash tampering and unsupported envelopes fail before frozen context installation',async()=>{
 const a=boot();try{
  await a.load(JSON.stringify(source(a.plan)));const packet=a.ui.exportReview(note),opened=a.opened.length;
  packet.measurement_file.text+=' ';await a.load(JSON.stringify(packet));assert.equal(a.ui.snapshot(),null);assert.equal(a.opened.length,opened);assert.match(a.$('execution-summary').textContent,/hash does not match/);
  packet.measurement_file.sha256=hash(packet.measurement_file.text);packet.unexpected='unsupported';await a.load(JSON.stringify(packet));assert.equal(a.opened.length,opened);assert.match(a.$('execution-summary').textContent,/Unsupported measured review field/);
 }finally{a.close();}
});

test('unknown totals stay unknown; complete compatible run uses existing decision editor',async()=>{
 const a=boot();try{
  await a.load(JSON.stringify(source(a.plan,{unknown:true})));assert.match(a.$('execution-summary').textContent,/incomplete/);assert.equal(a.ui.snapshot().results.measured.energy,null);assert.match(a.$('execution-outcomes').textContent,/Unknown/);
  a.$('execution-next').click();assert.equal(a.$('execution-details').open,true);assert.match(a.$('execution-findings').textContent,/unknown intervals/);
  await a.load(JSON.stringify(source(a.plan,{drain:false})));assert.equal(a.$('execution-next').textContent,'Record next step');a.$('execution-next').click();assert.equal(a.$('review-decision-editor').open,true);assert.equal(a.w.document.activeElement.id,'review-note');
 }finally{a.close();}
});

test('late async imports and plan invalidation cannot reinstall stale measured evidence',async()=>{
 const a=boot();try{
  let release;const raw=JSON.stringify(source(a.plan)),waiting=a.load(raw,'slow.json',()=>new Promise(resolve=>{release=()=>resolve(new TextEncoder().encode(raw).buffer);}));
  assert.equal(a.ui.isPending(),true);assert.equal(a.$('save-review').disabled,true);assert.equal(a.$('download-current-review').disabled,true);assert.throws(()=>a.ui.exportReview(note),/Wait/);
  await a.load(JSON.stringify(source(a.plan,{drain:false})),'new.json');release();await waiting;
  assert.equal(a.ui.snapshot().measurement_file.name,'new.json');assert.equal(a.ui.snapshot().results.measured.energy.lower,816);assert.equal(a.ui.isPending(),false);assert.equal(a.$('save-review').disabled,false);
  a.ui.clear('Selected plan changed.');assert.equal(a.ui.snapshot(),null);assert.equal(a.$('execution-result').hidden,true);assert.equal(a.$('download-current-review').disabled,false);assert.throws(()=>a.ui.exportReview(note),/Open a measured run/);
 }finally{a.close();}
});

test('idle clear preserves ordinary decisions; active and pending imports invalidate them',async()=>{
 const a=boot();try{
  a.$('review-note').value='Ordinary plan review';a.ui.clear('Selected plan changed.');assert.equal(a.$('review-note').value,'Ordinary plan review');assert.equal(a.invalidated.length,0);assert.equal(a.$('execution-summary').hidden,true);
  await a.$('execution-case-export').onclick();a.ui.clear('Prepared measurement case changed.');assert.equal(a.$('review-note').value,'Ordinary plan review');assert.equal(a.invalidated.length,0);assert.match(a.$('execution-summary').textContent,/Prepared measurement case/);
  const raw=JSON.stringify(source(a.plan));let release;const waiting=a.load(raw,'pending.json',()=>new Promise(resolve=>{release=()=>resolve(new TextEncoder().encode(raw).buffer);}));
  assert.equal(a.$('review-note').value,'');assert.equal(a.ui.isPending(),true);assert.equal(a.$('save-review').disabled,true);
  a.$('review-note').value='Pending note';a.ui.clear('Selected plan changed.');assert.equal(a.$('review-note').value,'');assert.equal(a.ui.isPending(),false);assert.equal(a.$('save-review').disabled,false);assert.equal(a.$('download-current-review').disabled,false);
  release();await waiting;assert.equal(a.ui.snapshot(),null);assert.equal(a.opened.length,0);
  await a.load(raw);a.$('review-note').value='Measured decision';a.ui.clear();assert.equal(a.$('review-note').value,'');assert.equal(a.ui.snapshot(),null);
 }finally{a.close();}
});

test('raw byte limits and malformed UTF-8 reject without retaining earlier findings',async()=>{
 const a=boot();try{
  await a.load(JSON.stringify(source(a.plan)));await a.load(JSON.stringify(source(a.plan))+' '.repeat(4*1024*1024));assert.equal(a.ui.snapshot(),null);assert.match(a.$('execution-summary').textContent,/4 MiB/);
  await a.load(new Uint8Array([0xc3,0x28]));assert.equal(a.ui.snapshot(),null);assert.equal(a.$('execution-result').hidden,true);assert.match(a.$('execution-summary').textContent,/not accepted/);
 }finally{a.close();}
});
