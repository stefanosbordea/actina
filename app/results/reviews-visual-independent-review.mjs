import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {webcrypto,createHash} from 'node:crypto';
import {createRequire} from 'node:module';
const {JSDOM}=createRequire(new URL('../web/package.json',import.meta.url))('jsdom');
const root=new URL('../',import.meta.url),checked=new Map();
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
const read=name=>{const path=`web/public/${name}`,bytes=fs.readFileSync(new URL(path,root)),sha=digest(bytes);if(checked.has(path))assert.equal(checked.get(path),sha,`Input changed: ${path}`);checked.set(path,sha);return bytes.toString('utf8');};
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

const probes=[];let failure=null,boundaryChecks=0,vertexChecks=0;
const passed=(name,detail)=>probes.push({name,status:'PASS',detail});
const close=(x,y)=>assert.ok(Math.abs(x-y)<1e-8,`${x} vs ${y}`);
const points=el=>el.getAttribute('points').trim().split(/\s+/).map(p=>p.split(',').map(Number));
const set=(a,id,value)=>{a.$(id).value=value;a.$(id).dispatchEvent(new a.w.Event('input'));};
const visible=(element)=>{for(let e=element;e;e=e.parentElement){assert.equal(e.hidden,false,`Hidden ${e.id}`);if(e.tagName==='DETAILS')assert.equal(e.open,true,`Closed ${e.id}`);}};
const css=read('workspace.css');
try{
 const a=await boot();try{
  a.route('reviews');const plan=fixture.days.find(d=>d.date==='2026-07-15').schedules['4000'],nominal=[plan.totals.initial_storage_m3,...plan.storage];
  let svg=a.$('review-inventory-chart').querySelector('svg'),vertices=points(svg.querySelector('polyline'));assert.equal(vertices.length,25);
  for(let h=0;h<25;h++){close(vertices[h][0],72+h/24*591);close(vertices[h][1],257-nominal[h]/4000*241);vertexChecks++;}
  for(const h of [0,13,24]){set(a,'review-inspect-hour',h);assert.equal(a.$('review-inspect-time').textContent,`${String(h).padStart(2,'0')}:00`);const cursor=a.$('review-inventory-chart').querySelector('circle');close(Number(cursor.getAttribute('cx')),72+h/24*591);close(Number(cursor.getAttribute('cy')),257-nominal[h]/4000*241);boundaryChecks++;}
  passed('nominal geometry and range input','All 25 midnight-aligned inventory vertices match retained source storage; range input moves cursor to boundaries 0, 13 and 24 with matching values.');
  a.route('resilience');for(const[id,value]of[['resilience-initial',700],['resilience-start',10],['resilience-demand',10]])set(a,id,value);a.$('resilience-form').onsubmit({preventDefault(){}});a.$('resilience-export').click();const assessment=JSON.parse(await a.downloads.at(-1).text());
  a.route('reviews');svg=a.$('review-inventory-chart').querySelector('svg');const traces=svg.querySelectorAll('polyline');assert.equal(traces.length,2);const tested=points(traces[1]);assert.equal(tested.length,15);close(tested[0][0],72+10/24*591);close(tested[0][1],257-700/4000*241);vertexChecks++;
  for(let k=1;k<tested.length;k++){close(tested[k][0],72+(10+k)/24*591);close(tested[k][1],257-assessment.selected.rows[k-1].storage_end_m3/4000*241);vertexChecks++;}
  set(a,'review-inspect-hour',9);assert.equal(a.$('review-inventory-chart').querySelectorAll('circle').length,1);assert.match(a.$('review-boundary-values').textContent,/Tested at 09:00—/);
  set(a,'review-inspect-hour',10);assert.equal(a.$('review-inventory-chart').querySelectorAll('circle').length,2);assert.match(a.$('review-boundary-values').textContent,/Tested at 10:00700/);boundaryChecks+=2;
  passed('restart prefix and geometry','Tested trace starts at hour 10 with exactly 700 m³; all preceding values remain absent, and all 15 retained boundaries align.');
  assert.equal(a.$('review-inventory-chart').querySelector('path').getAttribute('d'),'M657 131.5l6 5-6 5');
  passed('terminal target marker','Final target is a marker at the terminal x position and correct physical y value, not an all-day target line.');
  a.$('review-tab-revision').click();await a.$('revision-current').onclick();a.$('revision-case-export').click();const savedCase=JSON.parse(await a.downloads.at(-1).text());a.$('revision-template').click();let template=await a.downloads.at(-1).text();await a.importRevision('revision-proposal-file',template,'same.csv');
  assert.equal(a.$('revision-inspect-hour').max,'14');let returned=points(a.$('revision-inventory-chart').querySelectorAll('polyline')[1]);assert.equal(returned.length,15);for(let k=0;k<returned.length;k++){close(returned[k][0],72+k/14*591);close(returned[k][1],tested[k][1]);vertexChecks++;}
  set(a,'revision-inspect-hour',14);assert.equal(a.$('revision-inspect-time').textContent,'00:00 GMT+3');assert.match(a.$('revision-inspect-time').title,/16 Jul 2026/);close(Number(a.$('revision-inventory-chart').querySelector('circle').getAttribute('cx')),663);boundaryChecks++;
  passed('returned matched partial horizon','Both plans use the same 15 boundaries across 14 remaining hours; final selected label reflects next-day midnight, with full date in title.');
  a.$('review-tab-current').click();a.change('tank','8000');assert.equal(a.$('review-inventory-chart').querySelectorAll('polyline').length,1);assert.doesNotMatch(a.$('review-inventory-chart').textContent,/Tested conditions/);assert.match(a.$('review-assessment-state').textContent,/not assessed/);
  passed('stale selected-plan trace','Changing tank removes the previous tested trace and marks conditions unassessed.');
  a.$('review-tab-revision').click();assert.equal(a.$('revision-result').hidden,false);assert.equal(a.w.document.querySelector('.context').hidden,true);assert.match(a.$('revision-horizon').textContent,/700\.00 m³/);
  passed('frozen returned-case independence','Global tank change does not reinterpret the separately frozen returned case or expose unrelated global context.');
  const cases=[
   {name:'non-midnight shifted start',first:Date.parse('2026-07-14T22:00:00Z'),start:10,date:'2026-07-15',checks:{0:'11:00 GMT+3',14:'01:00 GMT+3'},endTitle:/16 Jul 2026, 01:00 GMT\+3/},
   {name:'autumn repeated hour',first:Date.parse('2026-10-24T21:00:00Z'),start:0,date:'2026-10-25',checks:{0:'00:00 GMT+3',3:'03:00 GMT+3',4:'03:00 GMT+2',24:'23:00 GMT+2'},endTitle:/25 Oct 2026, 23:00 GMT\+2/},
   {name:'spring skipped hour',first:Date.parse('2026-03-28T22:00:00Z'),start:0,date:'2026-03-29',checks:{0:'00:00 GMT+2',2:'02:00 GMT+2',3:'04:00 GMT+3',24:'01:00 GMT+3'},endTitle:/30 Mar 2026, 01:00 GMT\+3/},
   {name:'one remaining interval',first:Date.parse('2026-07-14T21:00:00Z'),start:23,date:'2026-07-15',checks:{0:'23:00 GMT+3',1:'00:00 GMT+3'},endTitle:/16 Jul 2026, 00:00 GMT\+3/}
  ];
  for(const c of cases){
   const v=structuredClone(savedCase);v.assessment.date=c.date;v.assessment.inputs.startHour=c.start;v.assessment.inputs.times=Array.from({length:24},(_,h)=>new Date(c.first+h*3600000).toISOString());
   await a.importRevision('revision-case-file',JSON.stringify(v),`${c.name}.json`);assert.equal(a.$('revision-template').disabled,false,a.$('revision-case-status').textContent);a.$('revision-template').click();template=await a.downloads.at(-1).text();await a.importRevision('revision-proposal-file',template,`${c.name}.csv`);assert.equal(a.$('revision-result').hidden,false,a.$('revision-proposal-status').textContent);
   a.$('revision-note').value='Synthetic timestamp and chart review only.';a.$('revision-review-form').onsubmit({preventDefault(){}});const output=JSON.parse(await a.downloads.at(-1).text()),r=output.comparison.original.result,values=[r.totals.initial_storage_m3,...r.rows.map(row=>row.storage_end_m3)];
   const actual=points(a.$('revision-inventory-chart').querySelectorAll('polyline')[0]);assert.equal(actual.length,values.length);
   for(let k=0;k<values.length;k++){close(actual[k][0],72+k/(values.length-1)*591);close(actual[k][1],257-values[k]/4000*241);vertexChecks++;set(a,'revision-inspect-hour',k);const expected=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Nicosia',hour:'2-digit',minute:'2-digit',timeZoneName:'shortOffset'}).format(new Date(c.first+(c.start+k)*3600000));assert.equal(a.$('revision-inspect-time').textContent,expected);const circle=a.$('revision-inventory-chart').querySelector('circle');close(Number(circle.getAttribute('cx')),actual[k][0]);close(Number(circle.getAttribute('cy')),actual[k][1]);boundaryChecks++;}
   for(const [k,expected]of Object.entries(c.checks)){set(a,'revision-inspect-hour',k);assert.equal(a.$('revision-inspect-time').textContent,expected);}
   set(a,'revision-inspect-hour',values.length-1);assert.match(a.$('revision-inspect-time').title,c.endTitle);
   const labels=[...a.$('revision-inventory-chart').querySelectorAll('text[y="280"]')].map(x=>x.textContent);
   const expectedClock=k=>new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Nicosia',hour:'2-digit',minute:'2-digit'}).format(new Date(c.first+(c.start+k)*3600000));assert.equal(labels[0],expectedClock(0));assert.equal(labels.at(-1),expectedClock(values.length-1));
   passed(c.name,{declared_start:v.assessment.inputs.times[c.start],hard_coded_expected_boundaries:c.checks,final_title:a.$('revision-inspect-time').title,boundaries_checked:values.length,chart_first_label:labels[0],chart_final_label:labels.at(-1)});
  }
  set(a,'revision-sec',4);assert.equal(a.$('revision-result').hidden,true);assert.equal(a.$('revision-inventory-chart').childElementCount,0);assert.equal(a.$('revision-boundary-values').childElementCount,0);assert.equal(a.$('revision-review-export').disabled,true);
  passed('returned assumptions invalidation','Editing specific energy clears the chart and boundary readout and disables review export.');
 }finally{a.close();}
 const b=await boot();try{
  b.route('pilot');await b.$('pilot-example').onclick();b.route('resilience');b.$('assessment-tab-observed').click();b.$('reconciliation-day').click();b.$('reconciliation-map-unit_power').value='unit-demo';b.$('reconciliation-map-available_power').value='grid-demo';b.$('reconciliation-cutoff').value='2026-07-01T10:02:00+03:00';b.$('reconciliation-form').dispatchEvent(new b.w.Event('submit',{cancelable:true}));b.route('reviews');assert.match(b.$('review-observation-alert').textContent,/16 unknown/);visible(b.$('review-observation-alert'));
  b.route('resilience');b.$('reconciliation-cutoff').value='2026-07-01T10:05:00+03:00';b.$('reconciliation-form').dispatchEvent(new b.w.Event('submit',{cancelable:true}));b.route('reviews');assert.match(b.$('review-observation-alert').textContent,/1 require explanation/);visible(b.$('review-observation-alert'));b.change('tank','8000');assert.equal(b.$('review-observation-alert').textContent,'');
  passed('evidence survives new inspector hierarchy','Unknown and nonzero explanation findings remain visible in the inspector and clear when the selected tank invalidates their comparison.');
 }finally{b.close();}
 assert.match(css,/\[hidden\]\{display:none!important\}/);assert.match(css,/\.chart\{overflow:auto/);assert.match(css,/textarea\{width:100%;resize:vertical/);assert.match(css,/summary:focus-visible/);
 passed('global style source inspection','Panel/background changes retain hidden-state precedence, chart overflow access, resizable textareas and summary/control focus styles. No obvious functional loss identified from source; browser geometry not asserted.');
 for(const[path,sha]of checked)assert.equal(digest(fs.readFileSync(new URL(path,root))),sha,`Source changed during audit: ${path}`);
}catch(error){failure={name:error.name,message:error.message,stack:error.stack};}
const receipt={schema:1,status:failure?'FAIL':'PASS',completed_at:new Date().toISOString(),command:'node --experimental-vm-modules results/reviews-visual-independent-review.mjs',exit_status:failure?1:0,runner_sha256:digest(fs.readFileSync(new URL('./reviews-visual-independent-review.mjs',import.meta.url))),checked_source_sha256:Object.fromEntries(checked),boundary_checks:boundaryChecks,vertex_checks:vertexChecks,probes,failure,scope:['Narrow JSDOM behavior and SVG-coordinate checks; no browser or native pointer simulation.','Range input event/cursor alignment tested; native pointer and keyboard mechanics require browser QA.','Shifted/DST cases are synthetic declared case variants, not newly sourced plant data or new schedules.','Lines are documented as hourly sample connectors, not exact within-hour trajectories.','Global stylesheet checked for obvious functional loss only, not rendered pixel/layout correctness.','No source or existing test modifications, deployment, external messages or full-suite run.']};
fs.writeFileSync(new URL('results/reviews-visual-independent-review.json',root),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify({status:receipt.status,probes:probes.length,boundary_checks:boundaryChecks,vertex_checks:vertexChecks,checked_sources:checked.size,exit_status:receipt.exit_status,failure}));process.exitCode=receipt.exit_status;
