import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {JSDOM} from 'jsdom';
import {roadmapHandoffTemplate,setupRoadmapHandoff} from './public/roadmap-handoff-ui.mjs';

const box={};vm.runInNewContext(readFileSync(new URL('public/vendor/papaparse.min.js',import.meta.url),'utf8'),box);const Papa=box.Papa;
const hash=value=>createHash('sha256').update(value).digest('hex');
const raw=(name,text)=>({name,text,sha256:hash(text)});
function packet({initial=2,empty=false,sec=1,bom=false,late=false,confounded=false,label='Illustrative supplied decision'}={}){
 const start=Date.parse('2026-07-01T00:00:00+03:00'),time=h=>new Date(start+h*3600000).toISOString(),prefix=bom?'\uFEFF':'',csv=rows=>prefix+rows.map(row=>row.join(',')).join('\r\n')+'\r\n';
 const input={blocks:Array.from({length:2},(_,day)=>({times:Array.from({length:24},(_,h)=>time(day*24+h)),production:Array(24).fill(empty?0:1),demand:1})),capacity:4,reserve:0,initial,target:initial,unitCapacity:2};
 const caseFile=raw('case-Δ.json',prefix+JSON.stringify(input,null,2)+'\r\n'),files={case:caseFile,returned:raw('return.csv',csv([['case_sha256','time','production_m3'],...Array.from({length:48},(_,h)=>[caseFile.sha256,time(h),empty?0:h===0?0:h===1?2:1])])),weather:raw('weather.csv',csv([['time','radiation_w_m2'],...Array.from({length:48},(_,h)=>[time(h),100])])),candidate_forecast:raw('candidate.csv',csv([['time','predicted_radiation_w_m2'],...Array.from({length:48},(_,h)=>[time(h),100])])),control_forecast:raw('control.csv',csv([['time','predicted_radiation_w_m2'],...Array.from({length:48},(_,h)=>[time(h),110])])),tariffs:raw('tariffs.csv',csv([['time','eur_kwh'],...Array.from({length:48},(_,h)=>[time(h),h===1?.1:1])]))};
 const run=arm=>({forecast_sha256:files[arm+'_forecast'].sha256,plan_sha256:files[arm==='control'?'case':'returned'].sha256,case_sha256:caseFile.sha256,tariffs_sha256:files.tariffs.sha256,controller_sha256:(confounded&&arm==='candidate'?'3':'1').repeat(64),settings_sha256:'2'.repeat(64),randomness:'deterministic',forecast_issue_time:time(-4),forecast_first_observed_time:time(-3),features_available_time:time(late&&arm==='candidate'?-.5:-5),plan_first_observed_time:time(-2)});
 const declaration={schema:1,kind:'forecast_decision_declaration',source_kind:'illustrative_scenario',source_label:label,decision_cutoff:time(-1),specific_energy_kwh_m3:sec,candidate:run('candidate'),control:run('control')};
 return {schema:1,kind:'forecast_decision_review',declaration_file:raw('declaration.json',prefix+JSON.stringify(declaration,null,2)+'\r\n'),files,createdAt:'2026-10-03T00:00:00Z',results:{forged:true},note:{decision:'Ready',reason:'Prior approval must not survive.'}};
}
function boot(digest=async value=>hash(value)){
 const dom=new JSDOM(`<section id="test-pane">${roadmapHandoffTemplate}</section><textarea id="ordinary-note">Keep the plan decision</textarea>`),w=dom.window,$=id=>w.document.getElementById(id),downloads=[];
 const text=(id,value)=>{$(id).textContent=value;},table=(id,headers,rows)=>{const t=w.document.createElement('table');for(const row of [headers,...rows]){const tr=t.insertRow();row.forEach(value=>{tr.insertCell().textContent=value??'—';});}$(id).replaceChildren(t);};
 const ui=setupRoadmapHandoff({$,text,table,facts:(id,rows)=>table(id,[],rows),lineChart:()=>{},json:(name,value)=>downloads.push({name,text:JSON.stringify(value,null,2)+'\n'}),sha256:digest,Papa,reveal:()=>{$('test-pane').hidden=false;}});
 async function load(value,read){const text=typeof value==='string'?value:JSON.stringify(value),bytes=new TextEncoder().encode(text);Object.defineProperty($('roadmap-file'),'files',{configurable:true,value:[{name:'review.json',size:bytes.byteLength,arrayBuffer:read??(async()=>bytes.buffer)}]});await $('roadmap-file').onchange();}
 return {$,w,ui,load,downloads,close:()=>w.close()};
}

test('better forecast error cannot hide candidate water loss; the exact first witness receives focus',async()=>{
 const a=boot();try{await a.load(packet({initial:0}));assert.ok(a.ui.snapshot(),a.$('roadmap-status').textContent);assert.equal(a.$('roadmap-power-result').hidden,true);assert.equal(a.$('roadmap-decision-result').hidden,false);assert.equal(a.$('roadmap-decision-heading').textContent,'Water delivery reduced');assert.match(a.$('roadmap-decision-comparison').textContent,/Forecast MAE10 W\/m²0 W\/m²/);assert.match(a.$('roadmap-decision-adequacy').textContent,/control: met; candidate: unserved demand/);assert.match(a.$('roadmap-water-proof').textContent,/\[0, 1\) elapsed h/);assert.match(a.$('roadmap-water-proof').textContent,/Control 0 m³\/h; candidate 1 m³\/h/);assert.equal(a.$('roadmap-water-details').open,false);a.$('roadmap-finding').click();assert.equal(a.$('roadmap-water-details').open,true);assert.equal(a.w.document.activeElement.id,'roadmap-water-details');assert.equal(a.w.document.activeElement.closest('[hidden]'),null);assert.match(a.$('roadmap-decision-scope').textContent,/attribution is not established/);assert.equal(a.$('ordinary-note').value,'Keep the plan decision');}finally{a.close();}
});

test('equal inadequate plans never look ready; adequate cheaper plans still receive no forecast attribution',async()=>{
 const a=boot();try{await a.load(packet({initial:0,empty:true}));assert.equal(a.ui.snapshot().results.water_service.status,'no_modeled_regression');assert.equal(a.$('roadmap-decision-heading').textContent,'Modeled water requirements not met');assert.match(a.$('roadmap-decision-adequacy').textContent,/control: unserved demand; candidate: unserved demand/);await a.load(packet());assert.equal(a.$('roadmap-decision-heading').textContent,'Lower cost with no modeled water regression');assert.equal(a.ui.snapshot().results.forecast_attribution.status,'not_established');assert.match(a.$('roadmap-declaration').textContent,/execution unverified/);await a.load(packet({sec:null}));assert.equal(a.$('roadmap-decision-heading').textContent,'Modeled cost unknown');assert.match(a.$('roadmap-decision-comparison').textContent,/Modeled tariff costUnknownUnknown/);}finally{a.close();}
});

test('method and timing gaps stay separate from numerical outcomes and focus their existing evidence disclosure',async()=>{
 const a=boot();try{await a.load(packet({late:true,confounded:true,label:'<img src=x onerror=alert(1)>'}));assert.equal(a.$('roadmap-result').querySelector('img'),null);assert.equal(a.ui.snapshot().results.method.status,'confounded_declaration');assert.equal(a.ui.snapshot().results.timing.status,'late_declared');assert.equal(a.ui.snapshot().results.forecast_attribution.status,'not_established');assert.equal(a.$('roadmap-finding').textContent,'Inspect method difference');a.$('roadmap-finding').click();assert.equal(a.$('roadmap-source-details').open,true);assert.equal(a.w.document.activeElement.id,'roadmap-gaps');assert.match(a.$('roadmap-gaps').textContent,/different controllers/);assert.match(a.$('roadmap-gaps').textContent,/feature availability/);assert.match(a.$('roadmap-scope').textContent,/Exact evidence/);}finally{a.close();}
});

test('export and reopen preserve exact UTF-8 sources while recomputing cached adequacy and clearing prior notes',async()=>{
 const input=packet({initial:0,bom:true}),a=boot();let saved;try{await a.load(input);a.$('roadmap-export').click();assert.equal(a.downloads[0].name,'aktina-forecast-decision-review.json');saved=JSON.parse(a.downloads[0].text);assert.deepEqual(saved.files,input.files);assert.deepEqual(saved.declaration_file,input.declaration_file);assert.equal(saved.note,undefined);saved.results.adequacy.candidate.status='modeled_requirements_met';saved.results.water_service.status='no_modeled_regression';saved.note=input.note;}finally{a.close();}
 const b=boot();try{await b.load(saved);assert.equal(b.ui.snapshot().results.adequacy.candidate.status,'modeled_requirements_failed');assert.equal(b.ui.snapshot().results.water_service.status,'regression_detected');assert.equal(b.ui.snapshot().note,undefined);assert.deepEqual(b.ui.snapshot().files,input.files);assert.match(b.$('roadmap-status').textContent,/Prior note cleared/);assert.equal(b.w.document.activeElement.id,'roadmap-status');assert.equal(b.$('roadmap-water-details').open,false);}finally{b.close();}
});

test('invalid replacement clears all export authority and cannot retain a prior water conclusion',async()=>{
 const a=boot();try{await a.load(packet());const bad=packet();bad.files.weather.text+=' ';await a.load(bad);assert.equal(a.ui.snapshot(),null);assert.equal(a.$('roadmap-export').disabled,true);assert.equal(a.$('roadmap-result').hidden,true);assert.match(a.$('roadmap-status').textContent,/hash does not match/);assert.equal(a.w.document.activeElement.id,'roadmap-file');assert.throws(()=>a.ui.exportReview(),/Open a complete/);}finally{a.close();}
});

test('pending byte reads and hashes cannot restore a cleared or replaced decision review',async()=>{
 let gate=false,releaseHash;const a=boot(async value=>{if(gate&&value.includes('forecast_decision_declaration')){gate=false;return new Promise(resolve=>{releaseHash=()=>resolve(hash(value));});}return hash(value);});
 try{await a.load(packet());gate=true;const old=a.load(packet({initial:0}));await new Promise(resolve=>setTimeout(resolve,0));assert.equal(a.ui.isPending(),true);assert.equal(a.ui.snapshot(),null);assert.equal(a.$('roadmap-export').disabled,true);assert.throws(()=>a.ui.exportReview(),/Wait/);await a.load(packet({sec:null}));releaseHash();await old;assert.equal(a.ui.snapshot().results.energy.cost_eur,null);let releaseRead;const input=JSON.stringify(packet()),pending=a.load(input,()=>new Promise(resolve=>{releaseRead=()=>resolve(new TextEncoder().encode(input).buffer);}));a.ui.clear();releaseRead();await pending;assert.equal(a.ui.snapshot(),null);assert.equal(a.ui.isPending(),false);assert.equal(a.$('roadmap-export').disabled,true);}finally{a.close();}
});

test('the shared opener switches back to the original four-file review without leaving decision fields visible',async()=>{
 const input=JSON.parse(readFileSync(new URL('../results/roadmap-handoff/independent-inputs-v1.json',import.meta.url),'utf8')).cases.find(row=>row.id==='nonconsecutive_48h_shifted_equal_energy').input,prior={schema:1,kind:'roadmap_handoff_review',declaration_file:raw('declaration.json',JSON.stringify(input.declaration)),files:input.files,createdAt:'2026-10-03T00:00:00Z'};
 const a=boot();try{await a.load(packet());await a.load(prior);assert.equal(a.ui.snapshot().kind,'roadmap_handoff_review',a.$('roadmap-status').textContent);assert.equal(a.$('roadmap-power-result').hidden,false);assert.equal(a.$('roadmap-decision-result').hidden,true);assert.match(a.$('roadmap-support').textContent,/48 supplied schedule hours/);assert.equal(a.$('roadmap-preparation').parentElement,a.$('roadmap-source-details'));await a.load(packet());assert.equal(a.$('roadmap-preparation').hidden,true);assert.equal(a.ui.snapshot().kind,'forecast_decision_review');assert.equal(a.$('roadmap-power-result').hidden,true);}finally{a.close();}
});
