import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {webcrypto,createHash} from 'node:crypto';
import {createRequire} from 'node:module';
const {JSDOM}=createRequire(new URL('../web/package.json',import.meta.url))('jsdom');
const root=new URL('../',import.meta.url),checked=new Map();
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
const read=name=>{const path=`web/public/${name}`,bytes=fs.readFileSync(new URL(path,root)),sha=digest(bytes);if(checked.has(path))assert.equal(checked.get(path),sha,`Input changed while auditing: ${path}`);checked.set(path,sha);return bytes.toString('utf8');};
const fixture=JSON.parse(read('data.json'));
async function boot(saved={},override={},cryptoProvider=webcrypto){
 const dom=new JSDOM(read('index.html'),{url:'http://localhost:8788',runScripts:'outside-only'}),w=dom.window,downloads=[];
 Object.defineProperty(w,'crypto',{value:cryptoProvider});w.Blob=Blob;w.structuredClone=structuredClone;
 w.URL.createObjectURL=blob=>{downloads.push(blob);return 'blob:test';};w.URL.revokeObjectURL=()=>{};
 w.HTMLAnchorElement.prototype.click=function(){};
 w.TextEncoder=TextEncoder;w.TextDecoder=TextDecoder;w.fetch=async url=>({ok:true,arrayBuffer:async()=>{const value=override[url]??read(url);return (typeof value==='string'?new TextEncoder().encode(value):value).buffer;}});
 Object.entries(saved).forEach(([k,v])=>w.localStorage.setItem(k,v));
 w.eval(read('vendor/papaparse.min.js'));
 const context=dom.getInternalVMContext(),modules=new Map();
 async function moduleFor(spec){if(modules.has(spec))return modules.get(spec);const mod=new vm.SourceTextModule(read(spec.replace(/^.\//,'')),{context});modules.set(spec,mod);await mod.link(moduleFor);return mod;}
 const app=await moduleFor('./workspace.js');await app.evaluate();
 for(let i=0;i<50&&w.document.getElementById('download').disabled&&!w.document.getElementById('status').textContent.includes('could not load');i++)await new Promise(r=>setTimeout(r,5));
 const $=id=>w.document.getElementById(id),click=sel=>w.document.querySelector(sel).dispatchEvent(new w.MouseEvent('click',{bubbles:true})),change=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new w.Event('change'));},route=view=>click(`[data-view="${view}"]`);
 async function importCSV(text,name='test.csv'){Object.defineProperty($('handoff-file'),'files',{value:[{name,size:Buffer.byteLength(text),arrayBuffer:async()=>new TextEncoder().encode(text).buffer}],configurable:true});await $('handoff-file').onchange();}
 async function importPlan(text,name='plan.csv'){Object.defineProperty($('schedule-file'),'files',{value:[{name,size:Buffer.byteLength(text),arrayBuffer:async()=>new TextEncoder().encode(text).buffer}],configurable:true});await $('schedule-file').onchange();}
 async function importRevision(id,text,name){Object.defineProperty($(id),'files',{value:[{name,size:Buffer.byteLength(text),arrayBuffer:async()=>new TextEncoder().encode(text).buffer}],configurable:true});await $(id).onchange();}
 return {dom,w,$,click,change,route,downloads,importCSV,importPlan,importRevision,close:()=>w.close()};
}

const probes=[];let failure=null;
const passed=(name,detail)=>probes.push({name,status:'PASS',detail});
const visible=(a,element)=>{for(let e=element;e;e=e.parentElement){assert.equal(e.hidden,false,`Hidden ancestor ${e.id}`);if(e.tagName==='DETAILS')assert.equal(e.open,true,`Closed ancestor ${e.id}`);}};
read('workspace.css');
try{
 const a=await boot();try{
  a.route('reviews');assert.equal(a.$('review-observation-alert').textContent,'');
  assert.equal(a.w.document.querySelector('.context').parentElement.id,'review-plan-selection');assert.equal(a.w.document.querySelectorAll('#review-outcomes th').length,2);
  a.$('review-plan-selection').open=true;a.change('date','2026-07-16');assert.match(a.$('review-case-title').textContent,/16 Jul 2026/);
  a.route('operations');assert.equal(a.w.document.querySelector('.context').parentElement.tagName,'MAIN');assert.equal(a.w.document.querySelector('.context').hidden,false);
  passed('context relocation and unassessed state','Review selectors move into Change plan, restore outside Reviews, preserve selected date, and omit the unavailable tested column without false zero values.');
  a.route('reviews');a.$('reviewer').value='';a.$('review-note').value='Probe';a.$('review-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
  assert.equal(a.$('review-decision-editor').open,true);assert.equal(a.w.document.querySelector('.review-record-details').open,true);assert.equal(a.w.document.activeElement.id,'reviewer');visible(a,a.$('reviewer'));
  passed('current reviewer recovery','Missing reviewer reveals both collapsed ancestors and focuses the required field.');
  a.route('resilience');a.$('resilience-form').onsubmit({preventDefault(){}});a.route('reviews');a.$('review-tab-revision').click();await a.$('revision-current').onclick();
  assert.equal(a.$('revision-template').closest('details').id,'revision-inputs');assert.equal(a.$('revision-template').disabled,false);visible(a,a.$('revision-template'));
  a.$('revision-template').click();const csv=await a.downloads.at(-1).text();await a.importRevision('revision-proposal-file',csv,'same.csv');
  assert.equal(a.w.document.querySelectorAll('#revision-comparison tbody tr').length,4);assert.equal(a.w.document.querySelectorAll('#revision-water-balance tbody tr').length,4);
  assert.match(a.$('revision-water-balance').textContent,/Water produced/);assert.match(a.$('revision-comparison').textContent,/Modeled production energy/);
  passed('returned template and metric preservation','Template is available without opening assumptions; returned results retain four primary and four water-balance rows.');
  assert.equal(a.w.document.querySelector('.context').hidden,true);a.route('operations');assert.equal(a.w.document.querySelector('.context').hidden,false);a.route('reviews');assert.equal(a.w.document.querySelector('.context').hidden,true);a.$('review-tab-current').click();assert.equal(a.w.document.querySelector('.context').hidden,false);a.$('review-tab-revision').click();
  passed('returned context isolation','Global selection remains hidden on Returned revision and restores on Current plan and other routes.');
  const submit=()=>a.$('revision-review-form').onsubmit({preventDefault(){}}),count=a.downloads.length;
  a.$('revision-note').value='Probe';a.$('revision-reviewer').value='';a.$('revision-decision-panel').open=false;submit();
  assert.match(a.$('revision-review-status').textContent,/valid reviewer/);visible(a,a.$('revision-review-status'));visible(a,a.$('revision-reviewer'));assert.equal(a.w.document.activeElement.id,'revision-reviewer');assert.equal(a.downloads.length,count);
  a.$('revision-reviewer').value='Loucas';a.$('revision-note').value='';a.$('revision-decision-panel').open=false;submit();
  assert.match(a.$('revision-review-status').textContent,/valid reason/);visible(a,a.$('revision-review-status'));assert.equal(a.w.document.activeElement.id,'revision-note');assert.equal(a.downloads.length,count);
  a.$('revision-note').value='Probe';a.$('revision-author').value='x'.repeat(121);a.$('revision-decision-panel').open=false;submit();
  assert.match(a.$('revision-review-status').textContent,/valid declared author/);visible(a,a.$('revision-review-status'));assert.equal(a.downloads.length,count);
  passed('returned export error recovery','Missing reviewer, missing reason and invalid author each reveal error status inside the previously closed decision panel; invalid reviews never export. Required missing fields receive focus.');
  a.$('revision-sec').value='4';a.$('revision-sec').dispatchEvent(new a.w.Event('input'));assert.equal(a.$('revision-result').hidden,true);assert.equal(a.$('revision-water-balance').textContent,'');assert.equal(a.$('revision-comparison').textContent,'');assert.equal(a.$('revision-review-export').disabled,true);
  passed('changed assumptions invalidate results','Changing specific energy clears both result tables and disables review export.');
 }finally{a.close();}
 const b=await boot();try{
  b.route('pilot');await b.$('pilot-example').onclick();b.route('resilience');b.$('assessment-tab-observed').click();b.$('reconciliation-day').click();
  b.$('reconciliation-map-unit_power').value='unit-demo';b.$('reconciliation-map-available_power').value='grid-demo';b.$('reconciliation-cutoff').value='2026-07-01T10:02:00+03:00';
  b.$('reconciliation-form').dispatchEvent(new b.w.Event('submit',{cancelable:true}));b.route('reviews');
  assert.equal(b.w.document.querySelector('.review-evidence').open,false);assert.equal(b.$('review-observation-alert').textContent,'Observations: 0 require explanation; 16 unknown.');visible(b,b.$('review-observation-alert'));
  passed('unknown observations remain visible','At the early cutoff the closed evidence disclosure does not hide the explicit 16 unknown comparisons.');
  b.route('resilience');b.$('reconciliation-cutoff').value='2026-07-01T10:05:00+03:00';b.$('reconciliation-form').dispatchEvent(new b.w.Event('submit',{cancelable:true}));b.$('reconciliation-export').click();const observed=JSON.parse(await b.downloads.at(-1).text());
  assert.ok(observed.coverage.requires_explanation>0);b.route('reviews');assert.equal(b.$('review-observation-alert').textContent,`Observations: ${observed.coverage.requires_explanation} require explanation; ${observed.coverage.unknown_comparisons} unknown.`);visible(b,b.$('review-observation-alert'));assert.equal(b.w.document.querySelector('.review-evidence').open,false);
  passed('known departures remain visible','Later cutoff produces actual explanation findings; visible summary matches retained comparison coverage while full evidence stays collapsed.');
  b.change('tank','8000');assert.equal(b.$('review-observation-alert').textContent,'');
  passed('revoked observation evidence clears','Changing selected tank invalidates the comparison and removes the previous visible finding.');
 }finally{b.close();}
 for(const [path,sha]of checked)assert.equal(digest(fs.readFileSync(new URL(path,root))),sha,`Source changed during audit: ${path}`);
}catch(error){failure={name:error.name,message:error.message,stack:error.stack};}
const receipt={schema:1,status:failure?'FAIL':'PASS',completed_at:new Date().toISOString(),command:'node --experimental-vm-modules results/reviews-sheet-independent-review.mjs',exit_status:failure?1:0,runner_sha256:digest(fs.readFileSync(new URL('./reviews-sheet-independent-review.mjs',import.meta.url))),checked_source_sha256:Object.fromEntries(checked),probes,failure,scope:['Narrow independent JSDOM behavior probes; no browser launched.','No source, production test, mathematical engine or fixture edits.','DOM visibility checks cover hidden attributes and collapsed details; no pixel or browser-layout claim.','No full verifier or suite run.']};
fs.writeFileSync(new URL('results/reviews-sheet-independent-review.json',root),JSON.stringify(receipt,null,2)+'\n');
console.log(JSON.stringify({status:receipt.status,probes:probes.length,checked_sources:checked.size,exit_status:receipt.exit_status,failure}));process.exitCode=receipt.exit_status;
