import {test as nodeTest} from 'node:test';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {webcrypto,createHash} from 'node:crypto';
import {JSDOM} from 'jsdom';
// VM module contexts survive window.close(); one fresh process per DOM case bounds suite memory.
function test(name,body){
 const selected=process.env.AQUASHIFT_WORKSPACE_TEST_CHILD;
 if(selected){if(name===selected)nodeTest(name,body);return;}
 nodeTest(name,()=>{const env={...process.env,AQUASHIFT_WORKSPACE_TEST_CHILD:name};delete env.NODE_TEST_CONTEXT;const result=spawnSync(process.execPath,['--experimental-vm-modules',fileURLToPath(import.meta.url)],{env,encoding:'utf8',timeout:120000,maxBuffer:2*1024*1024});assert.equal(result.status,0,`${result.error??''}\n${result.stdout}\n${result.stderr}`);assert.match(result.stdout,/# pass 1\b|ℹ pass 1\b/,'The isolated case must execute and pass.');});
}
const read=name=>fs.readFileSync(new URL(`public/${name}`,import.meta.url),'utf8');
const fixture=JSON.parse(read('data.json'));
async function boot(saved={},override={},cryptoProvider=webcrypto,initialHash='#reviews'){
 const dom=new JSDOM(read('index.html'),{url:'http://localhost:8788'+initialHash,runScripts:'outside-only'}),w=dom.window,downloads=[];
 Object.defineProperty(w,'crypto',{value:cryptoProvider});w.Blob=Blob;w.structuredClone=structuredClone;
 w.URL.createObjectURL=blob=>{downloads.push(blob);return 'blob:test';};w.URL.revokeObjectURL=()=>{};
 w.HTMLAnchorElement.prototype.click=function(){};
 w.TextEncoder=TextEncoder;w.TextDecoder=TextDecoder;w.fetch=async url=>({ok:true,arrayBuffer:async()=>{const value=await(override[url]??read(url));return (typeof value==='string'?new TextEncoder().encode(value):value).buffer;}});
 Object.entries(saved).forEach(([k,v])=>w.localStorage.setItem(k,v));
 w.eval(read('vendor/papaparse.min.js'));
 const context=dom.getInternalVMContext(),modules=new Map();
 function moduleFor(spec){if(modules.has(spec))return modules.get(spec);const mod=new vm.SourceTextModule(read(spec.replace(/^.\//,'')),{context});modules.set(spec,mod);return mod;}
 const app=moduleFor('./workspace.js');await app.link(moduleFor);await app.evaluate();
 for(let i=0;i<50&&w.document.getElementById('download').disabled&&!w.document.getElementById('status').textContent.includes('could not load');i++)await new Promise(r=>setTimeout(r,5));
 const $=id=>w.document.getElementById(id),click=sel=>w.document.querySelector(sel).dispatchEvent(new w.MouseEvent('click',{bubbles:true})),change=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new w.Event('change'));},route=view=>click(`nav button[data-view="${view}"]`);
 async function importCSV(text,name='test.csv'){Object.defineProperty($('handoff-file'),'files',{value:[{name,size:Buffer.byteLength(text),arrayBuffer:async()=>new TextEncoder().encode(text).buffer}],configurable:true});await $('handoff-file').onchange();}
 async function importPlan(text,name='plan.csv'){Object.defineProperty($('schedule-file'),'files',{value:[{name,size:Buffer.byteLength(text),arrayBuffer:async()=>new TextEncoder().encode(text).buffer}],configurable:true});await $('schedule-file').onchange();}
 async function importRevision(id,text,name){if(id==='revision-solar-file'){$('revision-solar').open=true;$('revision-solar-profile').open=true;}else if(id==='revision-case-file'){$('revision-inputs').open=true;$('revision-open-case').open=true;}else if(id==='revision-proposal-file')$('revision-inputs').open=true;Object.defineProperty($(id),'files',{value:[{name,size:Buffer.byteLength(text),arrayBuffer:async()=>new TextEncoder().encode(text).buffer}],configurable:true});await $(id).onchange();}
 return {dom,w,$,click,change,route,downloads,importCSV,importPlan,importRevision,close:()=>{w.close();modules.clear();downloads.length=0;}};
}
const oneRow=()=>`time,predicted\n${fixture.days[0].times[0]},0\n`;
test('all nine views render real controls and reference data',async()=>{const a=await boot();try{const logo=a.w.document.querySelector('.appbar .wordmark img');assert.ok(logo);assert.equal(logo.getAttribute('src'),'mark.svg');assert.equal(logo.hasAttribute('onerror'),false);assert.equal(a.w.document.querySelectorAll('.appbar img').length,1);assert.equal(a.$('download').disabled,false);assert.equal(a.$('date').options.length,92);assert.equal(a.$('tank').options.length,5);for(const view of['overview','operations','scenarios','data','evaluation','alerts','reviews','evidence','pilot']){a.route(view);assert.equal(a.$(`view-${view}`).hidden,false);assert.equal(a.w.document.querySelectorAll('.view:not([hidden])').length,1);assert.ok(a.$(`view-${view}`).textContent.length>150);}assert.match(a.$('evaluation-kpis').textContent,/8\.81/);assert.match(a.$('evaluation-kpis').textContent,/7\.64/);assert.equal(a.w.document.querySelectorAll('#evidence-sources article').length,11);}finally{a.close();}});
test('date edges, every capacity and schedule export use exact canonical production',async()=>{const a=await boot();try{a.route('operations');for(const day of[fixture.days[0],fixture.days.at(-1)])for(const tank of fixture.tanks){a.change('date',day.date);a.change('tank',String(tank));assert.match(a.$('operations-kpis').textContent,/2,880/);a.$('download').click();const matrix=a.w.Papa.parse(await a.downloads.at(-1).text()).data;assert.equal(matrix.length,26);for(let i=0;i<24;i++){assert.equal(matrix[i+1][0],day.times[i]);assert.equal(Number(matrix[i+1][5]),day.schedules[String(tank)].production[i]);assert.equal(Number(matrix[i+1][8]),day.schedules[String(tank)].storage[i]);}}}finally{a.close();}});
test('topology inspector and hourly inspection follow selection',async()=>{const a=await boot();try{a.route('overview');a.change('date','2026-09-30');a.$('hour').value=23;a.$('hour').dispatchEvent(new a.w.Event('input'));a.click('[data-asset="unit"]');assert.match(a.$('asset-inspector').textContent,/500 m³\/h/);a.route('operations');assert.match(a.$('hour-inspector').textContent,/23:00/);a.route('scenarios');a.change('compare-a','500');a.change('compare-b','8000');assert.match(a.$('comparison-summary').textContent,/8,000 m³/);a.w.document.querySelectorAll('#comparison-table button')[0].click();assert.equal(a.$('tank').value,'500');assert.equal(a.$('view-reviews').hidden,false);}finally{a.close();}});
test('full import evaluates paired controls and exports reproducible feedback',async()=>{const a=await boot();try{a.route('data');a.$('download-template').click();const template=await a.downloads.at(-1).text();await a.importCSV(template);assert.match(a.$('import-status').textContent,/COMPLETE \/ 2208/);a.route('evaluation');a.change('evaluation-source','imported');assert.match(a.$('evaluation-kpis').textContent,/8\.81/);assert.match(a.$('evaluation-scope').textContent,/2,208 matching hours/);a.$('download-feedback').click();const report=await a.downloads.at(-1).text();assert.match(report,/model_mae_w_m2/);assert.match(report,/8\.812139833/);assert.match(report,/input_sha256/);}finally{a.close();}});
test('partial handoff has matching-row metrics and missing-day chart',async()=>{const a=await boot();try{a.route('data');await a.importCSV(oneRow());assert.match(a.$('import-status').textContent,/PARTIAL \/ 1/);a.route('evaluation');a.change('evaluation-source','imported');assert.match(a.$('evaluation-scope').textContent,/1 matching hours \/ 1 days/);assert.match(a.$('forecast-chart').textContent,/No matching predictions/);a.$('download-validation').click();assert.match(await a.downloads.at(-1).text(),/missing_hour/);}finally{a.close();}});
test('invalid handoff is blocked and cannot remain an active analysis',async()=>{const a=await boot();try{a.route('data');await a.importCSV(oneRow());a.route('evaluation');a.change('evaluation-source','imported');a.route('data');await a.importCSV('time,predicted\n2026-07-01T00:00:00,10\n');assert.match(a.$('import-status').textContent,/BLOCKED/);assert.equal(a.$('evaluation-source').value,'frozen');assert.equal(a.$('evaluation-source').options[1].disabled,true);assert.match(a.$('validation-table').textContent,/invalid_time/);}finally{a.close();}});
test('user CSV filename cannot inject markup into the workspace',async()=>{const a=await boot();try{a.route('data');await a.importCSV(oneRow(),'<img src=x onerror=alert(1)>.csv');assert.equal(a.w.document.querySelectorAll('#views img').length,0);assert.match(a.$('validation-kpis').textContent,/<img/);a.route('evaluation');a.change('evaluation-source','imported');assert.equal(a.w.document.querySelectorAll('#views img').length,0);}finally{a.close();}});
test('synthetic queue acknowledgement persists and no-leak control removes fixture findings',async()=>{const a=await boot();try{a.route('alerts');assert.match(a.$('alerts-kpis').textContent,/4 flags/);a.w.document.querySelector('#alerts-table button').click();assert.ok(a.w.localStorage.getItem('aquashift.alerts.v1'));assert.match(a.$('alerts-table').textContent,/Reviewed/);a.$('leak').checked=false;a.$('leak').dispatchEvent(new a.w.Event('change'));assert.match(a.$('alerts-kpis').textContent,/0 flags/);assert.doesNotMatch(a.$('alerts-table').textContent,/Injected fixture anomaly/);}finally{a.close();}});
test('review save, reload and exports retain plan and analysis identity',async()=>{const a=await boot();let saved;try{a.route('reviews');openDecision(a,'review-decision-editor');a.$('review-note').value='QA fixture: inspect assumptions with Stefanos';a.$('decision').value='Needs team review';a.$('review-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));saved=a.w.localStorage.getItem('aquashift.review.v1');const record=JSON.parse(saved)[0];assert.equal(record.date,'2026-07-15');assert.equal(record.hourly.times.length,24);assert.equal(record.datasetSHA256,JSON.parse(read('manifest.json')).data_sha256);assert.match(record.scope,/no plant authorization/);a.$('download-current-review').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).totals.energy_kwh,9792);}finally{a.close();}const b=await boot({'aquashift.review.v1':saved});try{b.route('reviews');assert.match(b.$('review-history').textContent,/QA fixture/);b.$('download-history').click();assert.equal(JSON.parse(await b.downloads.at(-1).text()).reviews.length,1);}finally{b.close();}});
test('July report is date-linked, September missing is unknown rather than zero',async()=>{const a=await boot();try{a.route('evidence');a.change('date','2026-07-01');assert.match(a.$('daily-grid-context').textContent,/10:00–15:30/);assert.match(a.$('daily-grid-context').textContent,/704\.3 MWh/);assert.match(a.$('daily-grid-context').textContent,/not recovered energy/);assert.match(a.$('daily-grid-context').textContent,/7,242 \/|2,244 \/ 7,242/);a.change('date','2026-09-30');assert.match(a.$('daily-grid-context').textContent,/No report retained/);assert.match(a.$('daily-grid-context').textContent,/absence is not zero/);}finally{a.close();}});
test('manifest mismatch fails closed before usable plan controls',async()=>{const a=await boot({}, {'manifest.json':JSON.stringify({data_sha256:'bad'})});try{assert.equal(a.$('download').disabled,true);assert.match(a.$('status').textContent,/identity does not match/);}finally{a.close();}});
test('source ratio discrepancy is shown without changing window or plan',async()=>{const research=JSON.parse(read('research.json'));research.daily.days.find(d=>d.date==='2026-08-25').source_ratio_discrepancy=true;const a=await boot({}, {'research.json':JSON.stringify(research)});try{a.route('evidence');a.change('date','2026-08-25');assert.match(a.$('daily-grid-context').textContent,/Source integrity note/);assert.match(a.$('daily-grid-context').textContent,/published 9\.49%/);assert.match(a.$('daily-grid-context').textContent,/10:30–14:15/);a.$('download').click();const rows=a.w.Papa.parse(await a.downloads.at(-1).text()).data,day=fixture.days.find(d=>d.date==='2026-08-25');for(let i=0;i<24;i++)assert.equal(Number(rows[i+1][5]),day.schedules['4000'].production[i]);}finally{a.close();}});
test('report ledger filters, opens dates and exports exact retained public fields',async()=>{const a=await boot();try{a.route('evidence');assert.equal(a.w.document.querySelectorAll('#report-ledger tbody tr').length,62);a.change('report-month','2026-08');assert.equal(a.w.document.querySelectorAll('#report-ledger tbody tr').length,31);a.w.document.querySelector('#report-ledger button').click();assert.equal(a.$('date').value,'2026-08-01');a.$('download-reports').click();const rows=a.w.Papa.parse(await a.downloads.at(-1).text()).data;assert.equal(rows[1][0],'2026-08-01');assert.equal(rows[31][0],'2026-08-31');assert.equal(rows[1][8],'4000');assert.match(rows[1][11],/not recovered energy/);}finally{a.close();}});
test('exact-equal imported MAE is reported as equal',async()=>{const a=await boot();try{a.route('data');await a.importCSV(oneRow());a.route('evaluation');a.change('evaluation-source','imported');assert.match(a.$('evaluation-note').textContent,/match persistence MAE/);assert.match(a.$('evaluation-kpis').textContent,/Equal MAE/);assert.doesNotMatch(a.$('evaluation-note').textContent,/have lower/);}finally{a.close();}});
test('raw BOM file hash and explicit manual provenance survive review export',async()=>{const a=await boot();try{a.route('data');const raw='\uFEFF'+oneRow();await a.importCSV(raw);a.$('model-version').value='Fixture v1';a.$('training-review').value='Metadata inspected; questions remain';a.$('timing-review').value='Not reviewed';a.route('evaluation');a.change('evaluation-source','imported');a.route('reviews');openDecision(a,'review-decision-editor');a.$('review-note').value='QA fixture';a.$('download-current-review').click();const r=JSON.parse(await a.downloads.at(-1).text());assert.equal(r.analysis.sha256,createHash('sha256').update(raw).digest('hex'));assert.equal(r.analysis.issueProvenanceSupplied,false);assert.equal(r.analysis.modelVersion,'Fixture v1');assert.equal(r.analysis.trainingReview,'Metadata inspected; questions remain');assert.equal(r.analysis.featureTimingReview,'Not reviewed');assert.match(r.analysis.warnings.join(' '),/does not certify/);assert.match(a.$('export-status').textContent,/Last export/);assert.match(a.w.document.querySelector('#export-status a').href,/blob:/);}finally{a.close();}});
test('failed manifest leaves all view navigation safe and action controls disabled',async()=>{const a=await boot({}, {'manifest.json':JSON.stringify({data_sha256:'bad'})});try{for(const view of['overview','operations','scenarios','data','evaluation','alerts','reviews','evidence']){assert.doesNotThrow(()=>a.route(view));assert.equal(a.$(`view-${view}`).querySelector('.unavailable').hidden,false);}assert.equal(a.$('download-template').disabled,true);assert.equal(a.$('download-feedback').disabled,true);assert.equal(a.$('handoff-file').disabled,true);}finally{a.close();}});
const flatPlan=(day,tank=4000)=>[['time','production_m3','tank_capacity_m3'],...day.times.map(time=>[time,120,tank])];
test('candidate plan import, matched comparison, explicit selection and review preserve provenance',async()=>{const a=await boot();try{a.route('data');const raw='\uFEFF'+a.w.Papa.unparse(flatPlan(fixture.days[0],1000));await a.importPlan(raw);assert.match(a.$('schedule-import-status').textContent,/VALIDATED/);assert.equal(a.$('plan-source').value,'frozen');assert.equal(a.$('date').value,'2026-07-15');a.$('plan-method').value='QA fixture flat plan';a.$('plan-timing').value='Metadata inspected; questions remain';a.route('scenarios');assert.match(a.$('candidate-comparison').textContent,/2026-07-01 \/ 1000 m³/);assert.match(a.$('candidate-comparison').textContent,/1,319\.88/);a.$('select-candidate').click();assert.equal(a.$('plan-source').value,'imported');assert.equal(a.$('date').value,'2026-07-01');assert.equal(a.$('tank').value,'1000');assert.match(a.$('production-chart').textContent,/Imported CSV candidate/);assert.match(a.$('production-chart').textContent,/Frozen reference control/);a.$('download').click();const rows=a.w.Papa.parse(await a.downloads.at(-1).text()).data;for(let i=1;i<=24;i++)assert.equal(rows[i][5],'120');a.route('reviews');openDecision(a,'review-decision-editor');a.$('review-note').value='QA fixture / compare candidate';a.$('download-current-review').click();const record=JSON.parse(await a.downloads.at(-1).text());assert.match(record.planSource,/Imported CSV candidate/);assert.equal(record.planProvenance.sha256,createHash('sha256').update(raw).digest('hex'));assert.equal(record.planProvenance.methodLabel,'QA fixture flat plan');assert.equal(record.planProvenance.decisionTimingReview,'Metadata inspected; questions remain');assert.deepEqual(record.hourly.productionM3,Array(24).fill(120));assert.match(record.scope,/no plant authorization/);a.route('evidence');assert.match(a.$('daily-grid-context').textContent,/Imported candidate load during window2,244 kWh/);}finally{a.close();}});
test('candidate never contaminates another date, canonical plans or forecast evaluation',async()=>{const a=await boot();try{a.route('data');await a.importPlan(a.w.Papa.unparse(flatPlan(fixture.days[0])));a.$('inspect-candidate').click();a.change('date','2026-09-30');assert.equal(a.$('plan-source').value,'frozen');a.$('download').click();const rows=a.w.Papa.parse(await a.downloads.at(-1).text()).data;for(let i=0;i<24;i++)assert.equal(Number(rows[i+1][5]),fixture.days.at(-1).schedules['4000'].production[i]);a.route('evaluation');assert.match(a.$('evaluation-kpis').textContent,/8\.81/);a.route('scenarios');assert.match(a.$('candidate-comparison').textContent,/2026-07-01/);}finally{a.close();}});
test('unsupported schedule assumptions have explicit findings and cannot be selected',async()=>{const a=await boot();try{a.route('data');const rows=flatPlan(fixture.days[0]);rows[0].push('demand_m3');rows.slice(1).forEach(r=>r.push(130));await a.importPlan(a.w.Papa.unparse(rows));assert.match(a.$('schedule-validation').textContent,/unsupported_assumption/);assert.equal(a.$('plan-source').options[1].disabled,true);assert.equal(a.$('inspect-candidate').disabled,true);a.$('download-schedule-validation').click();assert.match(await a.downloads.at(-1).text(),/unsupported_assumption/);}finally{a.close();}});
test('unsupported handoff headers are visible, exported and cannot remain active inputs',async()=>{
 const a=await boot();try{
  a.route('data');await a.importCSV(oneRow());a.change('evaluation-source','imported');
  await a.importCSV(`time,predicted,forecast_issued_at\n${fixture.days[0].times[0]},0,2030-01-01T00:00:00Z\n`);
  assert.match(a.$('validation-table').textContent,/forecast_issued_at/);assert.match(a.$('validation-table').textContent,/unsupported_column/);assert.equal(a.$('evaluation-source').value,'frozen');assert.equal(a.$('evaluation-source').options[1].disabled,true);
  a.$('download-validation').click();assert.match(await a.downloads.at(-1).text(),/unsupported_column,Unsupported forecast column forecast_issued_at/);
  const rows=flatPlan(fixture.days[0]);await a.importPlan(a.w.Papa.unparse(rows));a.$('inspect-candidate').click();assert.equal(a.$('plan-source').value,'imported');a.route('data');
  rows[0].push('maximum_power_kw');rows.slice(1).forEach(r=>r.push(100));await a.importPlan(a.w.Papa.unparse(rows));
  assert.match(a.$('schedule-validation').textContent,/maximum_power_kw/);assert.match(a.$('schedule-validation').textContent,/unsupported_column/);assert.equal(a.$('plan-source').value,'frozen');assert.equal(a.$('plan-source').options[1].disabled,true);assert.equal(a.$('inspect-candidate').disabled,true);
  a.$('download-schedule-validation').click();assert.match(await a.downloads.at(-1).text(),/unsupported_column,Unsupported schedule column maximum_power_kw/);
 }finally{a.close();}
});
test('production step geometry has constant hourly bins and inventory includes both endpoints',async()=>{const a=await boot();try{a.route('operations');const points=a.w.document.querySelector('#production-chart polyline').getAttribute('points').split(' ').map(p=>p.split(',').map(Number));assert.equal(points.length,48);for(let i=0;i<48;i+=2){assert.equal(points[i][1],points[i+1][1]);assert.ok(points[i+1][0]>points[i][0]);}const inventory=a.w.document.querySelector('#storage-chart polyline').getAttribute('points').split(' ');assert.equal(inventory.length,25);assert.match(a.$('storage-chart').textContent,/24:00/);}finally{a.close();}});
test('control source provenance is verified and retained in exported analysis',async()=>{const a=await boot();try{a.route('data');a.$('download-template').click();await a.importCSV(await a.downloads.at(-1).text());a.route('evaluation');a.change('evaluation-source','imported');a.route('reviews');openDecision(a,'review-decision-editor');a.$('review-note').value='QA control source';a.$('download-current-review').click();const r=JSON.parse(await a.downloads.at(-1).text());assert.equal(r.analysis.baselineSourceProvenanceSupplied,true);a.route('data');const day=fixture.days[0];await a.importCSV(`time,predicted,baseline_source_time\n${day.times[0]},0,${day.times[0]}`);assert.match(a.$('validation-table').textContent,/baseline_source_mismatch/);assert.equal(a.$('evaluation-source').options[1].disabled,true);}finally{a.close();}});
test('CSV and JSON export previews match exact UTF-8 Blob bytes and can be selected',async()=>{const a=await boot();try{a.$('download').click();assert.equal(a.$('export-preview-panel').hidden,false);assert.equal(a.$('export-preview').readOnly,true);assert.equal(a.$('export-preview').value,await a.downloads.at(-1).text());a.$('select-export').click();assert.equal(a.$('export-preview').selectionStart,0);assert.equal(a.$('export-preview').selectionEnd,a.$('export-preview').value.length);assert.match(a.$('export-status').textContent,/Last export/);a.route('reviews');openDecision(a,'review-decision-editor');a.$('review-note').value='QA ελληνικά, quotes " / newline\nnext';a.$('download-current-review').click();assert.equal(a.$('export-preview').value,await a.downloads.at(-1).text());assert.deepEqual(Buffer.from(a.$('export-preview').value,'utf8'),Buffer.from(await a.downloads.at(-1).arrayBuffer()));assert.match(a.$('review-status').textContent,/ready for download/);assert.doesNotMatch(a.$('review-status').textContent,/saved|exported/i);}finally{a.close();}});

async function pilotFile(a,id,text,name){Object.defineProperty(a.$(id),'files',{value:[{name,size:Buffer.byteLength(text),arrayBuffer:async()=>new TextEncoder().encode(text).buffer}],configurable:true});await a.$(id).onchange();}
const pilotFixture=name=>fs.readFileSync(new URL(`fixtures/${name}`,import.meta.url),'utf8');
test('synthetic pilot intake shows real gap, distinct source and exact export identity without changing plans',async()=>{const a=await boot();try{a.$('download').click();const frozen=await a.downloads.at(-1).text();a.route('pilot');assert.equal(a.w.document.querySelector('.context').hidden,true);await a.$('pilot-example').onclick();assert.match(a.$('pilot-kpis').textContent,/NEEDS REVIEW/);assert.match(a.$('pilot-kpis').textContent,/15 \/ 16/);assert.match(a.$('pilot-findings').textContent,/No observation supplied/);assert.match(a.$('pilot-contract-status').textContent,/invented/);a.$('pilot-review-export').click();const r=JSON.parse(await a.downloads.at(-1).text());assert.equal(r.status,'PARTIAL');assert.equal(r.sourceDeclaration.source_kind,'synthetic_fixture');assert.equal(r.missing.length,1);assert.equal(r.observations.length,15);assert.equal(r.identity.contract.sha256.length,64);assert.equal(r.identity.observations.sha256.length,64);assert.match(r.scope,/No source authentication/);assert.equal(a.w.document.querySelectorAll('#pilot-chart circle').length,4);assert.equal(a.w.document.querySelectorAll('#pilot-chart polyline').length,0);a.route('operations');a.$('download').click();assert.equal(await a.downloads.at(-1).text(),frozen);}finally{a.close();}});
test('pilot review-time cutoff distinguishes late observations and exports every gap',async()=>{const a=await boot();try{a.route('pilot');await a.$('pilot-example').onclick();a.$('pilot-as-of').value='2026-07-01T11:30:00+03:00';a.$('pilot-apply-time').click();assert.match(a.$('pilot-kpis').textContent,/8 \/ 16/);assert.match(a.$('pilot-findings').textContent,/Not available at review time/);assert.match(a.$('pilot-findings').textContent,/No observation supplied/);a.$('pilot-review-export').click();const r=JSON.parse(await a.downloads.at(-1).text());assert.equal(r.knownSlots,8);assert.equal(r.observations.length,15);assert.equal(r.missing.length,8);assert.equal(r.reviewTimeBasis,'Reviewer override');assert.equal(r.reviewAsOf,'2026-07-01T08:30:00.000Z');}finally{a.close();}});
test('pilot raw BOM identity, malicious labels and exact raw CSV export remain safe',async()=>{const a=await boot();try{a.route('pilot');const c=JSON.parse(pilotFixture('pilot-synthetic-declaration.json'));c.label='<img src=x onerror=alert(1)>';c.source_label='<script>malicious()</script>';c.assets[0].label='<svg onload=alert(1)>';const rawContract='\uFEFF'+JSON.stringify(c);await pilotFile(a,'pilot-contract-file',rawContract,'<img>.json');const rawCSV='\uFEFF'+pilotFixture('pilot-synthetic-observations.csv');await pilotFile(a,'pilot-observations-file',rawCSV,'<script>.csv');assert.equal(a.w.document.querySelectorAll('#views img').length,0);assert.equal(a.w.document.querySelectorAll('#view-pilot script').length,0);assert.match(a.$('pilot-streams').textContent,/<svg/);a.$('pilot-review-export').click();const r=JSON.parse(await a.downloads.at(-1).text());assert.equal(r.identity.contract.sha256,createHash('sha256').update(rawContract).digest('hex'));assert.equal(r.identity.observations.sha256,createHash('sha256').update(rawCSV).digest('hex'));a.$('pilot-raw-export').click();assert.deepEqual(Buffer.from(await a.downloads.at(-1).arrayBuffer()),Buffer.from(rawCSV));}finally{a.close();}});
test('pilot blocked observations contribute no displayed values; bad declaration preserves accepted intake',async()=>{const a=await boot();try{a.route('pilot');await a.$('pilot-example').onclick();await pilotFile(a,'pilot-contract-file','{"schema":2}','unsupported.json');assert.match(a.$('pilot-contract-status').textContent,/BLOCKED/);assert.match(a.$('pilot-kpis').textContent,/15 \/ 16/);await pilotFile(a,'pilot-observations-file',pilotFixture('pilot-wrong-unit.csv'),'wrong-unit.csv');assert.match(a.$('pilot-status').textContent,/BLOCKED/);assert.match(a.$('pilot-findings').textContent,/wrong_unit/);assert.equal(a.w.document.querySelectorAll('#pilot-streams tbody tr').length,0);assert.equal(a.$('pilot-observations-export').disabled,true);a.$('pilot-review-export').click();const r=JSON.parse(await a.downloads.at(-1).text());assert.equal(r.observations.length,0);assert.equal(r.status,'BLOCKED');}finally{a.close();}});
test('large blocked pilot input has a bounded findings table and exports every finding',async()=>{
 const a=await boot();try{a.route('pilot');await a.$('pilot-example').onclick();
  const raw='time,available_at,asset_id,measurement,value,unit\n'+'2026-07-01T10:00:00+03:00,2026-07-01T10:01:00+03:00,tank-demo,tank_storage_m3,1000,L\n'.repeat(15000);
  await pilotFile(a,'pilot-observations-file',raw,'many-findings.csv');
  assert.match(a.$('pilot-findings-scope').textContent,/15000 blocking findings/);assert.match(a.$('pilot-findings-scope').textContent,/up to 100 blocking findings or gaps/);
  assert.equal(a.w.document.querySelectorAll('#pilot-findings tbody tr').length,100);assert.equal(a.w.document.querySelectorAll('#pilot-streams tbody tr').length,0);
  a.$('pilot-review-export').click();const r=JSON.parse(await a.downloads.at(-1).text());assert.equal(r.status,'BLOCKED');assert.equal(r.issues.length,15000);assert.equal(r.issues[0].record,2);assert.equal(r.issues.at(-1).record,15001);assert.equal(r.observations.length,0);
  a.$('pilot-raw-export').click();assert.equal(await a.downloads.at(-1).text(),raw);
 }finally{a.close();}
});
test('pilot file size and invalid UTF-8 failures preserve previous accepted intake',async()=>{const a=await boot();try{a.route('pilot');await a.$('pilot-example').onclick();for(const [id,file,expected]of[['pilot-contract-file',{name:'large.json',size:256*1024+1,arrayBuffer:async()=>{throw Error('must not read');}},/Maximum declaration/],['pilot-observations-file',{name:'large.csv',size:10*1024*1024+1,arrayBuffer:async()=>{throw Error('must not read');}},/Maximum observation/],['pilot-observations-file',{name:'invalid.csv',size:2,arrayBuffer:async()=>new Uint8Array([0xff,0xfe]).buffer},/encoded data/]]){Object.defineProperty(a.$(id),'files',{value:[file],configurable:true});await a.$(id).onchange();assert.match(a.$(id==='pilot-contract-file'?'pilot-contract-status':'pilot-status').textContent,expected);assert.match(a.$('pilot-kpis').textContent,/15 \/ 16/);}}finally{a.close();}});
test('independent pilot intake remains usable if canonical reference fails verification',async()=>{const a=await boot({}, {'manifest.json':JSON.stringify({data_sha256:'bad'})});try{a.route('pilot');assert.equal(a.$('pilot-example').disabled,false);await a.$('pilot-example').onclick();assert.match(a.$('pilot-kpis').textContent,/15 \/ 16/);assert.equal(a.$('download').disabled,true);assert.equal(a.$('view-pilot').querySelector('.unavailable').hidden,true);a.$('pilot-review-export').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).status,'PARTIAL');}finally{a.close();}});
test('original CSV keeps CRLF and BOM bytes while preview states native textarea normalization',async()=>{const a=await boot();try{a.route('pilot');await pilotFile(a,'pilot-contract-file',pilotFixture('pilot-synthetic-declaration.json'),'declaration.json');const raw='\uFEFF'+pilotFixture('pilot-synthetic-observations.csv').replaceAll('\n','\r\n');await pilotFile(a,'pilot-observations-file',raw,'crlf.csv');a.$('pilot-raw-export').click();assert.deepEqual(Buffer.from(await a.downloads.at(-1).arrayBuffer()),Buffer.from(raw));assert.equal(a.$('export-preview').value,raw.replaceAll('\r\n','\n'));assert.match(a.$('export-meta').textContent,/preview normalizes carriage-return/);assert.match(a.$('export-meta').textContent,/download retains original UTF-8 bytes/);a.$('pilot-review-export').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).identity.observations.sha256,createHash('sha256').update(raw).digest('hex'));}finally{a.close();}});
test('repeated autumn local hours expose distinct offsets, point times and review cutoff',async()=>{const a=await boot();try{a.route('pilot');const c={schema:1,label:'DST QA',source_kind:'synthetic_fixture',source_label:'Invented repeated-hour readings',timezone:'Europe/Nicosia',window:{start:'2026-10-25T03:00:00+03:00',end:'2026-10-25T04:00:00+02:00'},cadence_minutes:60,assets:[{asset_id:'tank',label:'Tank',measurements:[{measurement:'tank_storage_m3',unit:'m3',min:0,max:4000}]}]};await pilotFile(a,'pilot-contract-file',JSON.stringify(c),'dst.json');const raw='time,available_at,asset_id,measurement,value,unit\n2026-10-25T03:00:00+03:00,2026-10-25T03:01:00+03:00,tank,tank_storage_m3,1000,m3\n2026-10-25T03:00:00+02:00,2026-10-25T03:01:00+02:00,tank,tank_storage_m3,1100,m3\n';await pilotFile(a,'pilot-observations-file',raw,'dst.csv');assert.match(a.$('pilot-streams').textContent,/03:00:00 GMT\+2/);assert.match(a.$('pilot-kpis').textContent,/03:01:00 GMT\+2/);let titles=[...a.w.document.querySelectorAll('#pilot-chart circle title')].map(t=>t.textContent);assert.equal(titles.length,2);assert.match(titles[0],/03:00:00\+03:00/);assert.match(titles[1],/03:00:00\+02:00/);a.$('pilot-as-of').value='2026-10-25T03:30:00+03:00';a.$('pilot-apply-time').click();assert.match(a.$('pilot-streams').textContent,/03:00:00 GMT\+3/);assert.match(a.$('pilot-kpis').textContent,/03:30:00 GMT\+3/);assert.match(a.$('pilot-kpis').textContent,/1 \/ 2/);assert.equal(a.w.document.querySelectorAll('#pilot-chart circle').length,1);a.$('pilot-review-export').click();const r=JSON.parse(await a.downloads.at(-1).text());assert.equal(r.knownSlots,1);assert.equal(r.observations.length,2);assert.equal(r.missing[0].reason,'Not available at review time');}finally{a.close();}});
test('tank overview labels end inventory at its correct hour boundary including midnight',async()=>{const a=await boot();try{a.route('overview');for(const h of [13,23]){a.$('hour').value=h;a.$('hour').dispatchEvent(new a.w.Event('input'));const detail=a.w.document.querySelectorAll('#overview-kpis .detail')[1].textContent;assert.match(detail,new RegExp(`At ${h+1}:00 / end of ${h}:00–${h+1}:00`));const d=fixture.days.find(d=>d.date===a.$('date').value);assert.ok(detail.includes(Math.round(d.schedules['4000'].storage[h]).toLocaleString('en-GB')));}assert.doesNotMatch(a.$('overview-kpis').textContent,/End of 23:00/);}finally{a.close();}});
test('meter nighttime chart preserves the full clock axis and separate known segments',async()=>{const a=await boot();try{a.route('alerts');const lines=[...a.w.document.querySelectorAll('#meter-chart polyline')].map(p=>p.getAttribute('points').split(' ').map(v=>v.split(',').map(Number)));assert.equal(lines.length,4);assert.deepEqual(lines.map(p=>p.length),[6,2,6,2]);const x0=lines[0][0][0],x5=lines[0][5][0],x22=lines[1][0][0],x23=lines[1][1][0];assert.ok(Math.abs((x22-x5)/(x5-x0)-17/5)<1e-9);assert.ok(x23>x22);assert.match(a.$('meter-chart').textContent,/00:00/);assert.match(a.$('meter-chart').textContent,/12:00/);assert.match(a.$('meter-chart').textContent,/23:00/);assert.match(a.$('view-alerts').textContent,/blank span is not zero flow/);}finally{a.close();}});
test('review hold records guide decisions without promising simulation authorization',async()=>{const a=await boot();try{a.route('reviews');assert.match(a.$('view-reviews').textContent,/For the next team simulation/);assert.doesNotMatch(a.$('view-reviews').textContent,/authorizes/);a.$('decision').value='Hold for correction';openDecision(a,'review-decision-editor');a.$('review-note').value='QA hold: inspect constraints';a.$('download-current-review').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).decision,'Hold for correction');}finally{a.close();}});
test('historical radiation and friendly pilot displays preserve machine schema names',async()=>{const a=await boot();try{a.route('overview');assert.match(a.$('weather-chart').textContent,/Historical radiation reference/);a.route('evaluation');assert.match(a.$('forecast-chart').textContent,/Historical radiation reference/);assert.doesNotMatch(a.$('forecast-chart').textContent,/Actual/);a.route('pilot');await a.$('pilot-example').onclick();assert.match(a.$('pilot-streams').textContent,/Tank storage/);assert.match(a.$('pilot-streams').textContent,/m³/);assert.doesNotMatch(a.$('pilot-streams').textContent,/tank_storage_m3/);a.change('pilot-stream-select','unit-demo|production_rate_m3_h');assert.match(a.$('pilot-chart').textContent,/Production rate/);assert.match(a.$('pilot-chart').textContent,/m³\/h/);a.$('pilot-observations-export').click();const rows=a.w.Papa.parse(await a.downloads.at(-1).text()).data;assert.ok(rows.some(r=>r[3]==='tank_storage_m3'&&r[5]==='m3'));assert.ok(rows.some(r=>r[3]==='production_rate_m3_h'&&r[5]==='m3/h'));}finally{a.close();}});
test('one blocking finding uses singular status in forecast and pilot intake',async()=>{const a=await boot();try{a.route('data');await a.importCSV('time,predicted\n2026-07-01T00:00:00,10\n');assert.match(a.$('import-status').textContent,/1 blocking finding\./);assert.doesNotMatch(a.$('import-status').textContent,/1 blocking findings/);a.route('pilot');await a.$('pilot-example').onclick();await pilotFile(a,'pilot-observations-file',pilotFixture('pilot-wrong-unit.csv'),'wrong-unit.csv');assert.match(a.$('pilot-status').textContent,/1 blocking finding\./);assert.match(a.$('pilot-findings-scope').textContent,/1 blocking finding;/);assert.doesNotMatch(a.$('pilot-status').textContent,/1 blocking findings/);}finally{a.close();}});
test('undated operator procedure does not turn PDF creation metadata into publication evidence',async()=>{const a=await boot();try{a.route('evidence');const source=JSON.parse(read('research.json')).sources.find(s=>s.id==='eac-process');assert.equal(source.year,'Undated');const card=[...a.w.document.querySelectorAll('#evidence-sources article')].find(el=>el.querySelector('h3').textContent===source.title);assert.ok(card);assert.match(card.querySelector('.micro').textContent,/Undated/);assert.doesNotMatch(card.querySelector('.micro').textContent,/2025/);assert.match(card.querySelector('details').textContent,/creation|publication/i);}finally{a.close();}});
test('chart edge labels face inward without shifting observation points or clock-axis spans',async()=>{const a=await boot();try{a.route('pilot');await a.$('pilot-example').onclick();const labels=[...a.w.document.querySelectorAll('#pilot-chart svg text')].filter(t=>/\d{2}\/\d{2}/.test(t.textContent));assert.equal(labels.length,3);assert.equal(labels[0].getAttribute('text-anchor'),'start');assert.equal(labels[1].getAttribute('text-anchor'),'middle');assert.equal(labels[2].getAttribute('text-anchor'),'end');assert.equal(Number(labels[0].getAttribute('x')),49);assert.equal(Number(labels[2].getAttribute('x')),663);const points=[...a.w.document.querySelectorAll('#pilot-chart circle')];assert.equal(Number(points[0].getAttribute('cx')),49);assert.equal(Number(points.at(-1).getAttribute('cx')),663);a.route('alerts');const clockLabels=[...a.w.document.querySelectorAll('#meter-chart svg text')].filter(t=>/^\d{2}:00$/.test(t.textContent));assert.equal(clockLabels[0].textContent,'00:00');assert.equal(clockLabels[0].getAttribute('text-anchor'),'start');assert.equal(clockLabels.at(-1).textContent,'23:00');assert.equal(clockLabels.at(-1).getAttribute('text-anchor'),'end');}finally{a.close();}});

function builderDraft(a,{id='__proto__',label='<svg onload=alert(1)>',kind='synthetic_fixture',start='2026-07-01T10:00:00+03:00',end='2026-07-01T14:00:00+03:00'}={}){
 for(const [key,value]of Object.entries({label:'Hand-entered QA declaration','source-kind':kind,'source-label':'<script>Invented observations</script>',cadence:'60',start,end}))a.$('builder-'+key).value=value;
 const asset=a.w.document.querySelector('.builder-asset');for(const [field,value]of Object.entries({asset_id:id,label,min:'0',max:'4000'}))asset.querySelector(`[data-field="${field}"]`).value=value;
 const m=asset.querySelector('[data-field="measurement"]');m.value='tank_storage_m3';m.dispatchEvent(new a.w.Event('change'));
}
async function applyBuilder(a){await a.$('pilot-builder-form').onsubmit(new a.w.Event('submit',{cancelable:true}));}
test('blank builder has no assumed source/capacity; invalid drafts and valid exports preserve accepted intake',async()=>{
 const a=await boot();try{a.route('pilot');for(const id of['builder-label','builder-source-kind','builder-source-label','builder-cadence','builder-start','builder-end'])assert.equal(a.$(id).value,'');for(const field of['asset_id','label','min','max','tank_reserve_m3'])assert.equal(a.w.document.querySelector(`[data-field="${field}"]`).value,'');
 await a.$('pilot-example').onclick();await applyBuilder(a);assert.match(a.$('builder-status').textContent,/Draft blocked/);assert.match(a.$('pilot-kpis').textContent,/15 \/ 16/);
 builderDraft(a);a.$('builder-export').click();assert.match(a.$('builder-status').textContent,/export ready/);assert.match(a.$('pilot-kpis').textContent,/15 \/ 16/);const generated=JSON.parse(await a.downloads.at(-1).text());assert.equal(generated.assets[0].measurements[0].min,0);assert.equal(generated.assets[0].measurements[0].max,4000);assert.equal(generated.assets[0].asset_id,'__proto__');
 a.w.document.querySelector('[data-field="max"]').value='';await applyBuilder(a);assert.match(a.$('builder-status').textContent,/Bounds must be finite/);assert.match(a.$('pilot-kpis').textContent,/15 \/ 16/);
 }finally{a.close();}
});
test('applying generated declaration resets observations and preserves exact UTF-8 identity and unverified labels',async()=>{
 const a=await boot();try{a.route('pilot');await a.$('pilot-example').onclick();builderDraft(a,{kind:'operator_observations'});a.$('builder-export').click();const serialized=await a.downloads.at(-1).text(),bytes=Buffer.from(await a.downloads.at(-1).arrayBuffer());assert.equal(serialized.endsWith('\n'),true);
 await applyBuilder(a);assert.match(a.$('builder-status').textContent,/Prior observations were cleared/);assert.equal(a.$('pilot-kpis').textContent,'');assert.equal(a.$('pilot-stream-select').options.length,0);assert.equal(a.$('pilot-stream-select').disabled,true);assert.equal(a.$('pilot-review-export').disabled,true);assert.equal(a.$('pilot-observations-file').disabled,false);assert.match(a.$('pilot-source-badge').textContent,/unverified origin/);
 await pilotFile(a,'pilot-observations-file','time,available_at,asset_id,measurement,value,unit\n2026-07-01T10:00:00+03:00,2026-07-01T10:01:00+03:00,__proto__,tank_storage_m3,1234,m3\n','generated.csv');assert.match(a.$('pilot-streams').textContent,/<svg onload/);assert.equal(a.w.document.querySelectorAll('#view-pilot svg[onload],#view-pilot script,#view-pilot img').length,0);
 a.$('pilot-review-export').click();const r=JSON.parse(await a.downloads.at(-1).text());assert.equal(r.identity.contract.origin,'Form-generated declaration');assert.equal(r.identity.contract.sha256,createHash('sha256').update(bytes).digest('hex'));assert.equal(r.identity.contract.bytes,bytes.length);assert.equal(r.sourceDeclaration.source_kind,'operator_observations');assert.equal(r.knownSlots,1);assert.equal(r.expectedSlots,4);assert.match(r.scope,/No source authentication/);
 }finally{a.close();}
});
test('builder supports explicit additional measurements/assets and rejects duplicates without resetting intake',async()=>{
 const a=await boot();try{a.route('pilot');await a.$('pilot-example').onclick();builderDraft(a);const asset=a.w.document.querySelector('.builder-asset');asset.querySelector('[data-add-measurement]').click();const second=asset.querySelectorAll('.builder-measurement')[1];second.querySelector('[data-field="measurement"]').value='tank_storage_m3';second.querySelector('[data-field="measurement"]').dispatchEvent(new a.w.Event('change'));second.querySelector('[data-field="min"]').value='0';second.querySelector('[data-field="max"]').value='4000';await applyBuilder(a);assert.match(a.$('builder-status').textContent,/each supported measurement once/);assert.match(a.$('pilot-kpis').textContent,/15 \/ 16/);
 second.querySelector('button').click();a.$('builder-add-asset').click();assert.equal(a.w.document.querySelectorAll('.builder-asset').length,2);await applyBuilder(a);assert.match(a.$('builder-status').textContent,/Draft blocked/);assert.match(a.$('pilot-kpis').textContent,/15 \/ 16/);const secondAsset=a.w.document.querySelectorAll('.builder-asset')[1];secondAsset.querySelector('[data-remove-asset]').click();await applyBuilder(a);assert.match(a.$('builder-status').textContent,/Declaration applied/);
 }finally{a.close();}
});
test('96-slot navigation preserves gaps and absolute timestamps; latest follows review cutoff rather than late future rows',async()=>{
 const a=await boot();try{a.route('pilot');const start=Date.parse('2026-10-24T21:00:00Z'),iso=h=>new Date(start+h*3600000).toISOString(),c={schema:1,label:'Paged DST QA',source_kind:'synthetic_fixture',source_label:'Invented sparse observations',timezone:'Europe/Nicosia',window:{start:iso(0),end:iso(199)},cadence_minutes:60,review_as_of:new Date(start+97*3600000).toISOString(),assets:[{asset_id:'tank',label:'Paged tank',measurements:[{measurement:'tank_storage_m3',unit:'m3',min:0,max:4000}]}]};
 await pilotFile(a,'pilot-contract-file',JSON.stringify(c),'paged.json');const raw='time,available_at,asset_id,measurement,value,unit\n'+[0,95,96,198].map(h=>`${iso(h)},${new Date(start+h*3600000+60000).toISOString()},tank,tank_storage_m3,${1000+h},m3`).join('\n')+'\n';await pilotFile(a,'pilot-observations-file',raw,'paged.csv');assert.match(a.$('pilot-page').textContent,/Slots 1–96 \/ 199/);assert.equal(a.$('pilot-previous').disabled,true);assert.equal(a.w.document.querySelectorAll('#pilot-chart circle').length,2);assert.equal(a.w.document.querySelectorAll('#pilot-chart polyline').length,0);
 a.$('pilot-next').click();assert.match(a.$('pilot-page').textContent,/97–192/);assert.equal(a.w.document.querySelectorAll('#pilot-chart circle').length,1);assert.match(a.w.document.querySelector('#pilot-chart circle title').textContent,new RegExp(iso(96).replaceAll('.', '\\.')));
 a.$('pilot-next').click();assert.match(a.$('pilot-page').textContent,/193–199/);assert.equal(a.$('pilot-next').disabled,true);assert.equal(a.w.document.querySelectorAll('#pilot-chart circle').length,0);a.$('pilot-latest').click();assert.match(a.$('pilot-page').textContent,/97–192/);
 a.$('pilot-as-of').value=iso(1);a.$('pilot-apply-time').click();a.$('pilot-latest').click();assert.match(a.$('pilot-page').textContent,/1–96/);assert.equal(a.w.document.querySelectorAll('#pilot-chart circle').length,1);a.$('pilot-review-export').click();const r=JSON.parse(await a.downloads.at(-1).text());assert.equal(r.observations.length,4);assert.equal(r.knownSlots,1);assert.equal(r.missing.length,198);assert.ok(r.missing.some(x=>x.reason==='Not available at review time'));
 }finally{a.close();}
});
test('empty observations remain navigable unknown declared slots with latest disabled',async()=>{
 const a=await boot();try{a.route('pilot');const c=JSON.parse(pilotFixture('pilot-synthetic-declaration.json'));await pilotFile(a,'pilot-contract-file',JSON.stringify(c),'empty.json');await pilotFile(a,'pilot-observations-file','time,available_at,asset_id,measurement,value,unit\n','empty.csv');assert.equal(a.$('pilot-stream-select').disabled,false);assert.equal(a.$('pilot-latest').disabled,true);assert.equal(a.w.document.querySelectorAll('#pilot-chart circle').length,0);assert.match(a.$('pilot-page').textContent,/1–4/);assert.match(a.$('pilot-kpis').textContent,/0 \/ 16/);
 }finally{a.close();}
});
test('Evaluation exposes exact daylight/cloud paired groups and exports their scoped results',async()=>{
 const a=await boot();try{a.route('evaluation');assert.match(a.$('weather-diagnostics').textContent,/1200 \/ 92/);assert.match(a.$('weather-diagnostics').textContent,/1090 \/ 92/);assert.match(a.$('weather-diagnostics').textContent,/92 \/ 25/);assert.match(a.$('weather-diagnostics').textContent,/18 \/ 9/);a.change('evaluation-hours','daylight');assert.match(a.$('evaluation-scope').textContent,/1,200 matching daylight hours/);assert.match(a.$('evaluation-kpis').textContent,/15\.84/);assert.match(a.$('evaluation-kpis').textContent,/13\.99/);assert.match(a.$('weather-diagnostics-scope').textContent,/never a new forecast input/);
 a.$('download-feedback').click();const rows=a.w.Papa.parse(await a.downloads.at(-1).text()).data;assert.equal(Number(rows.find(r=>r[0]==='all')[2]),1200);assert.equal(Number(rows.find(r=>r[0]==='daylight')[2]),1200);assert.equal(rows.filter(r=>r[0]==='cloud_daylight').length,4);assert.match(rows.find(r=>r[0]==='scope')[1],/Daylight reference/);
 }finally{a.close();}
});
test('night-only imported subset has no daylight numbers or frozen fallback; changing scope restores its own rows',async()=>{
 const a=await boot();try{a.route('data');await a.importCSV(oneRow(),'night-only.csv');a.route('evaluation');a.change('evaluation-source','imported');a.change('evaluation-hours','daylight');assert.equal(a.$('evaluation-source').value,'imported');assert.match(a.$('evaluation-scope').textContent,/0 matching daylight hours/);assert.match(a.$('evaluation-note').textContent,/No matching daylight observations/);assert.doesNotMatch(a.$('evaluation-kpis').textContent,/8\.81|7\.64|Equal MAE|Lower MAE|Higher MAE/);assert.match(a.$('evaluation-kpis').textContent,/No paired observations/);assert.equal(a.w.document.querySelectorAll('#forecast-chart polyline').length,0);a.$('download-feedback').click();const rows=a.w.Papa.parse(await a.downloads.at(-1).text()).data,all=rows.find(r=>r[0]==='all');assert.equal(Number(all[2]),0);assert.equal(all[3],'');assert.ok(rows.some(r=>r[0]==='input'&&r[1]==='night-only.csv'));
 a.change('evaluation-hours','all');assert.match(a.$('evaluation-scope').textContent,/1 matching hours/);assert.match(a.$('evaluation-kpis').textContent,/0\.00 W\/m²/);assert.equal(a.$('evaluation-source').value,'imported');
 }finally{a.close();}
});
test('incoming daylight diagnostics evaluate only paired imported predictions against retained realized cloud',async()=>{
 const a=await boot();try{const rows=fixture.days.flatMap(day=>day.actual.map((actual,h)=>({time:day.times[h],actual,cloud:day.cloud_cover[h]}))).filter(r=>r.actual>20&&r.cloud>=20).slice(0,2);a.route('data');await a.importCSV('time,predicted,cloud_cover\n'+rows.map(r=>`${r.time},${r.actual},0`).join('\n'),'two-daylight.csv');a.route('evaluation');a.change('evaluation-source','imported');a.change('evaluation-hours','daylight');assert.match(a.$('evaluation-scope').textContent,/2 matching daylight hours/);assert.match(a.$('evaluation-kpis').textContent,/0\.00 W\/m²/);const table=[...a.w.document.querySelectorAll('#weather-diagnostics tbody tr')].map(r=>[...r.cells].map(c=>c.textContent));assert.equal(table[1][1],'0 / 0');assert.equal(Number(table[2][1].split(' / ')[0])+Number(table[3][1].split(' / ')[0]),2);assert.equal(table[4][1],'0 / 0');a.route('data');assert.match(a.$('validation-table').textContent,/Supplied cloud_cover is not used/);
 }finally{a.close();}
});
test('later invalid builder Apply cancels older pending digest without losing accepted intake or replacing status',async()=>{
 let hold=false,release;const cryptoProvider={randomUUID:()=>webcrypto.randomUUID(),subtle:{digest:async(...args)=>{if(hold){hold=false;await new Promise(resolve=>{release=resolve;});}return webcrypto.subtle.digest(...args);}}};
 const a=await boot({}, {},cryptoProvider);try{a.route('pilot');await a.$('pilot-example').onclick();builderDraft(a);hold=true;const pending=applyBuilder(a);assert.equal(typeof release,'function');a.w.document.querySelector('[data-field="max"]').value='';await applyBuilder(a);assert.match(a.$('builder-status').textContent,/Draft blocked/);release();await pending;assert.match(a.$('builder-status').textContent,/Draft blocked/);assert.match(a.$('pilot-kpis').textContent,/15 \/ 16/);assert.equal(a.$('pilot-stream-select').options.length,4);a.$('pilot-review-export').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).identity.contract.origin,'Bundled synthetic fixture');
 a.w.document.querySelector('[data-field="max"]').value='4000';await applyBuilder(a);assert.match(a.$('builder-status').textContent,/Declaration applied/);assert.equal(a.$('pilot-kpis').textContent,'');
 }finally{a.close();}
});
test('diagnostic display and feedback include MAE and RMSE for all three paired comparators',async()=>{
 const a=await boot();try{a.route('evaluation');const d=a.w.document.querySelector('#weather-diagnostics tbody tr').cells;assert.equal(d[2].textContent,'15.84 / 24.33');assert.equal(d[3].textContent,'13.99 / 26.36');assert.match(d[4].textContent,/^\d+\.\d{2} \/ \d+\.\d{2}$/);assert.match(a.$('weather-diagnostics').textContent,/Climatology MAE \/ RMSE/);a.$('download-feedback').click();const rows=a.w.Papa.parse(await a.downloads.at(-1).text()).data,index=rows[0].indexOf('climatology_rmse_w_m2');assert.equal(index,8);assert.ok(Number(rows.find(r=>r[0]==='daylight')[index])>0);
 }finally{a.close();}
});
test('cancelled older builder digest failure cannot replace the newer blocked-draft status',async()=>{
 let hold=false,reject;const cryptoProvider={randomUUID:()=>webcrypto.randomUUID(),subtle:{digest:async(...args)=>{if(hold){hold=false;await new Promise((_,fail)=>{reject=fail;});}return webcrypto.subtle.digest(...args);}}};
 const a=await boot({}, {},cryptoProvider);try{a.route('pilot');await a.$('pilot-example').onclick();builderDraft(a);hold=true;const pending=applyBuilder(a);a.w.document.querySelector('[data-field="max"]').value='';await applyBuilder(a);reject(Error('Earlier digest interrupted'));await pending;assert.match(a.$('builder-status').textContent,/Draft blocked/);assert.doesNotMatch(a.$('builder-status').textContent,/Earlier digest interrupted/);assert.match(a.$('pilot-kpis').textContent,/15 \/ 16/);
 }finally{a.close();}
});

test('storage comparison uses matched period cases and exports exact identities, daily controls and increments',async()=>{
 const a=await boot();try{
  a.route('scenarios');assert.match(a.$('frontier-status').textContent,/62 matched report days \/ 310 tank cases, 30 days/);
  assert.match(a.$('frontier-kpis').textContent,/2,652 kWh/);assert.match(a.$('frontier-kpis').textContent,/-816 kWh/);
  a.$('download-frontier').click();const report=JSON.parse(await a.downloads.at(-1).text());
  assert.equal(report.selection.matched_days,62);assert.equal(report.daily.length,310);
  assert.equal(report.input_identity.data_sha256,createHash('sha256').update(read('data.json')).digest('hex'));
  assert.equal(report.input_identity.research_sha256,createHash('sha256').update(read('research.json')).digest('hex'));
  assert.equal(report.marginal.at(-1).window_load_delta_kwh.reference,2652);
  assert.ok(Math.abs(report.marginal.at(-1).reference_cost_change_eur)<1e-7);
  assert.match(report.scope,/not recovered electricity/);
  const topDay=a.w.document.querySelector('#frontier-daily tbody tr td').textContent;
  a.w.document.querySelector('#frontier-daily button').click();assert.equal(a.$('date').value,topDay);assert.equal(a.$('view-evidence').hidden,false);assert.equal(a.$('plan-source').value,'frozen');assert.match(a.$('daily-grid-context').textContent,/Persistence load during window7,208 kWh/);a.route('scenarios');
  a.change('date','2026-09-30');assert.match(a.$('frontier-status').textContent,/62 matched report days/);
  a.change('frontier-period','2026-08');a.$('download-frontier').click();
  const august=JSON.parse(await a.downloads.at(-1).text());assert.equal(august.selection.matched_days,31);
  assert.equal(august.daily.length,155);assert.ok(august.daily.every(r=>r.date.startsWith('2026-08')));
 }finally{a.close();}
});
test('missing September reports produce empty export and no numeric zero comparison',async()=>{
 const a=await boot();try{
  a.route('scenarios');a.change('frontier-period','2026-09');
  assert.match(a.$('frontier-status').textContent,/0 matched report days \/ 0 tank cases, 30 days/);
  assert.match(a.$('frontier-chart').textContent,/unknown, not zero/);
  assert.equal(a.$('frontier-chart').querySelectorAll('svg').length,0);
  a.$('download-frontier').click();const report=JSON.parse(await a.downloads.at(-1).text());
  assert.equal(report.status,'EMPTY');assert.equal(report.daily.length,0);
  assert.ok(report.tanks.every(r=>r.window_load_kwh.reference===null&&r.reference_cost_eur===null));
  a.change('frontier-period','all');assert.match(a.$('frontier-status').textContent,/62 matched/);
  assert.equal(a.$('frontier-chart').querySelectorAll('svg').length,1);
 }finally{a.close();}
});
test('incomplete paired storage controls block that analysis while single-day operations remain usable',async()=>{
 const research=JSON.parse(read('research.json'));delete research.daily.days[0].overlap[0].persistence_load_kwh;
 const a=await boot({}, {'research.json':JSON.stringify(research)});try{
  a.route('scenarios');assert.match(a.$('frontier-status').textContent,/missing or invalid persistence control/);
  assert.equal(a.$('download-frontier').disabled,true);assert.equal(a.$('frontier-table').textContent,'');
  a.route('operations');assert.match(a.$('operations-kpis').textContent,/2,880/);
 }finally{a.close();}
});


test('retained response identities hash original bytes and malformed UTF-8 fails closed',async()=>{
 const bomData='\uFEFF'+read('data.json'),blocked=await boot({}, {'data.json':bomData});
 try{assert.equal(blocked.$('download').disabled,true);assert.match(blocked.$('status').textContent,/identity does not match/);}finally{blocked.close();}
 const bomResearch='\uFEFF'+read('research.json'),accepted=await boot({}, {'research.json':bomResearch});
 try{accepted.route('scenarios');accepted.$('download-frontier').click();const record=JSON.parse(await accepted.downloads.at(-1).text());assert.equal(record.input_identity.research_sha256,createHash('sha256').update(bomResearch).digest('hex'));assert.equal(record.selection.matched_days,62);}finally{accepted.close();}
 const malformed=await boot({}, {'data.json':new Uint8Array([0xff,0xfe,0x7b])});
 try{assert.equal(malformed.$('download').disabled,true);assert.match(malformed.$('status').textContent,/could not load/);}finally{malformed.close();}
});

test('scenario tabs have one active panel, roving keyboard focus and context matched to the active view',async()=>{
 const a=await boot();try{
  a.route('scenarios');
  const check=name=>{
   assert.equal(a.w.document.body.dataset.scenarioTab,name);
   assert.equal(a.w.document.querySelectorAll('.scenario-pane:not([hidden])').length,1);
   for(const tab of a.w.document.querySelectorAll('[role="tab"][data-scenario-tab]')){
    const active=tab.dataset.scenarioTab===name;
    assert.equal(tab.getAttribute('aria-selected'),String(active));assert.equal(tab.tabIndex,active?0:-1);
    assert.equal(a.$(tab.getAttribute('aria-controls')).hidden,!active);
    assert.equal(a.$(tab.getAttribute('aria-controls')).getAttribute('aria-labelledby'),tab.id);
   }
   assert.equal(a.w.document.querySelector('.context').hidden,name!=='daily');
  };
  check('study');assert.equal(a.w.document.body.dataset.view,'scenarios');
  const key=(name,key)=>a.$('scenario-tab-'+name).dispatchEvent(new a.w.KeyboardEvent('keydown',{key,bubbles:true,cancelable:true}));
  key('study','ArrowLeft');check('imported');assert.equal(a.w.document.activeElement.id,'scenario-tab-imported');
  key('imported','Home');check('study');key('study','ArrowRight');check('daily');
  key('daily','End');check('imported');a.$('scenario-tab-daily').click();check('daily');
  a.route('overview');assert.equal(a.w.document.querySelector('.context').hidden,false);
  a.route('scenarios');check('daily');a.$('scenario-tab-study').click();check('study');
  assert.match(a.$('status').textContent,/Historical storage study/);
 }finally{a.close();}
});

test('scenario tabs preserve period, daily selections and imported review metadata across navigation',async()=>{
 const a=await boot();try{
  a.route('data');await a.importCSV(oneRow(),'team-forecast.csv');a.$('model-version').value='Team forecast v1';
  await a.importPlan(a.w.Papa.unparse(flatPlan(fixture.days[0])),'team-plan.csv');a.$('plan-method').value='Team plan v1';
  a.route('evaluation');a.change('evaluation-source','imported');
  a.route('scenarios');a.change('frontier-period','2026-08');a.$('scenario-tab-daily').click();
  a.change('compare-a','500');a.change('compare-b','8000');a.change('date','2026-09-30');a.change('tank','2000');a.$('hour').value=7;
  a.$('scenario-tab-imported').click();assert.match(a.$('candidate-comparison').textContent,/team-plan.csv/);
  a.$('scenario-tab-study').click();assert.equal(a.$('frontier-period').value,'2026-08');a.$('download-frontier').click();
  const study=JSON.parse(await a.downloads.at(-1).text());assert.equal(study.selection.matched_days,31);assert.ok(study.selection.matched_dates.every(date=>date.startsWith('2026-08')));
  a.$('scenario-tab-daily').click();assert.equal(a.$('compare-a').value,'500');assert.equal(a.$('compare-b').value,'8000');assert.equal(a.$('date').value,'2026-09-30');assert.equal(a.$('tank').value,'2000');assert.equal(a.$('hour').value,'7');
  a.route('data');assert.equal(a.$('model-version').value,'Team forecast v1');assert.equal(a.$('plan-method').value,'Team plan v1');assert.equal(a.$('evaluation-source').value,'imported');
  a.route('scenarios');assert.equal(a.$('scenario-daily').hidden,false);a.$('scenario-tab-imported').click();a.$('select-candidate').click();
  assert.equal(a.$('view-operations').hidden,false);assert.equal(a.$('plan-source').value,'imported');assert.equal(a.$('date').value,'2026-07-01');assert.equal(a.$('tank').value,'4000');
  a.route('reviews');openDecision(a,'review-decision-editor');a.$('review-note').value='Verify team candidate';a.$('download-current-review').click();const review=JSON.parse(await a.downloads.at(-1).text());assert.equal(review.planProvenance.methodLabel,'Team plan v1');assert.equal(review.analysis.modelVersion,'Team forecast v1');
 }finally{a.close();}
});

test('tables align numeric values without treating dates or descriptive text as numbers',async()=>{
 const a=await boot();try{
  a.route('scenarios');const row=a.w.document.querySelector('#frontier-table tbody tr');
  assert.ok([...row.cells].every(cell=>cell.classList.contains('number')));
  const day=a.w.document.querySelector('#frontier-daily tbody tr');assert.equal(day.cells[0].classList.contains('number'),false);assert.equal(day.cells[2].classList.contains('number'),true);assert.equal(day.cells[4].classList.contains('number'),false);
  a.$('scenario-tab-daily').click();assert.equal(a.w.document.querySelector('#comparison-table tbody tr').cells[2].classList.contains('number'),true);
 }finally{a.close();}
});

test('pilot intake shows an actionable empty state and visible review reasons before stream inspection',async()=>{
 const a=await boot();try{
  a.route('pilot');for(const id of ['pilot-kpis','pilot-streams-panel','pilot-history-panel','pilot-findings-panel'])assert.equal(a.$(id).hidden,true);
  assert.equal(a.$('pilot-empty-state').hidden,false);assert.match(a.$('pilot-empty-state').textContent,/Choose a declaration/);
  await a.$('pilot-example').onclick();assert.equal(a.$('pilot-empty-state').hidden,true);assert.equal(a.$('pilot-review-reasons').hidden,false);assert.equal(a.$('pilot-review-reasons').closest('details'),null);assert.match(a.$('pilot-review-reasons').textContent,/1 declared slot is unknown/);
  for(const id of ['pilot-streams-panel','pilot-history-panel','pilot-findings-panel'])assert.equal(a.$(id).hidden,false);
  a.$('pilot-as-of').value='2026-07-01T11:30:00+03:00';a.$('pilot-apply-time').click();assert.match(a.$('pilot-review-reasons').textContent,/8 declared slots are unknown/);assert.match(a.$('pilot-review-reasons').textContent,/7 readings arrived after the review cutoff/);
  await pilotFile(a,'pilot-observations-file',pilotFixture('pilot-wrong-unit.csv'),'wrong-unit.csv');assert.match(a.$('pilot-review-reasons').textContent,/1 blocking finding; observations are excluded/);assert.equal(a.$('pilot-streams-panel').hidden,true);assert.equal(a.$('pilot-history-panel').hidden,true);assert.equal(a.$('pilot-findings-panel').hidden,false);
  await pilotFile(a,'pilot-contract-file',pilotFixture('pilot-synthetic-declaration.json'),'new-declaration.json');assert.equal(a.$('pilot-review-reasons').hidden,true);assert.equal(a.$('pilot-empty-state').hidden,false);assert.match(a.$('pilot-empty-state').textContent,/Declaration ready/);
 }finally{a.close();}
});

test('below-reserve pilot readings retain a visible reason when detailed methods are collapsed',async()=>{
 const a=await boot();try{
  a.route('pilot');await pilotFile(a,'pilot-contract-file',pilotFixture('pilot-synthetic-declaration.json'),'declaration.json');
  const raw=pilotFixture('pilot-synthetic-observations.csv').replace('tank_storage_m3,1800,m3','tank_storage_m3,700,m3');await pilotFile(a,'pilot-observations-file',raw,'below-reserve.csv');
  assert.equal(a.$('pilot-review-reasons').hidden,false);assert.equal(a.$('pilot-review-reasons').closest('details'),null);assert.match(a.$('pilot-review-reasons').textContent,/1 tank reading is below a declared reserve/);
  a.$('pilot-review-export').click();const record=JSON.parse(await a.downloads.at(-1).text());assert.equal(record.reviewRequired,true);assert.equal(record.observations.length,15);assert.equal(record.streams.find(s=>s.measurement==='tank_storage_m3').belowDeclaredReserve,1);
 }finally{a.close();}
});

test('storage daily inspector exposes its tank and preserves the aggregate study when it changes',async()=>{
 const a=await boot();try{
  a.route('scenarios');const selector=a.$('frontier-daily-tank');assert.equal(selector.closest('label').textContent.startsWith('Tank'),true);assert.equal(selector.options.length,5);assert.equal(selector.value,'4000');
  a.$('download-frontier').click();const before=JSON.parse(await a.downloads.at(-1).text());const totals=a.$('frontier-table').textContent;
  a.change('frontier-daily-tank','1000');assert.equal(a.$('tank').value,'1000');assert.match(a.$('frontier-daily-scope').textContent,/selected 1,000 m³ tank/);assert.equal(a.$('frontier-table').textContent,totals);
  a.$('download-frontier').click();assert.deepEqual(JSON.parse(await a.downloads.at(-1).text()),before);
  const selectedDay=a.w.document.querySelector('#frontier-daily tbody tr td').textContent;a.w.document.querySelector('#frontier-daily button').click();assert.equal(a.$('view-evidence').hidden,false);assert.equal(a.$('date').value,selectedDay);assert.equal(a.$('tank').value,'1000');assert.equal(a.$('plan-source').value,'frozen');
  a.change('tank','8000');a.route('scenarios');assert.equal(selector.value,'8000');assert.match(a.$('frontier-daily-scope').textContent,/selected 8,000 m³ tank/);
 }finally{a.close();}
});

test('daily plan labels describe frozen A and B independently of the global candidate',async()=>{
 const a=await boot();try{
  a.route('data');await a.importPlan(a.w.Papa.unparse(flatPlan(fixture.days[0])));a.$('inspect-candidate').click();assert.equal(a.$('plan-source').value,'imported');
  a.route('scenarios');a.$('scenario-tab-daily').click();assert.equal(a.$('status').textContent,'Frozen daily plan comparison.');assert.match(a.$('workspace-case-label').textContent,/2026-07-01/);
  const kpi=a.$('comparison-summary').children[3];assert.equal(kpi.querySelector('.label').textContent,'End inventory');assert.equal(kpi.querySelector('.value').textContent,'50%');assert.match(kpi.querySelector('.detail').textContent,/same demand and energy/);
  const chart=a.$('compare-production').innerHTML;a.change('tank','1000');a.$('hour').value=20;a.$('hour').dispatchEvent(new a.w.Event('input'));assert.equal(a.$('compare-production').innerHTML,chart);assert.equal(a.$('status').textContent,'Frozen daily plan comparison.');assert.match(a.$('workspace-case-label').textContent,/2026-07-01/);
  a.change('date','2026-09-30');assert.equal(a.$('status').textContent,'Frozen daily plan comparison.');assert.match(a.$('workspace-case-label').textContent,/2026-09-30/);
 }finally{a.close();}
});

test('hour inspector groups each label with its value without changing the selected observations',async()=>{
 const a=await boot();try{
  a.route('operations');const pairs=[...a.$('hour-inspector').querySelector('dl').children];assert.equal(pairs.length,4);
  for(const pair of pairs){assert.equal(pair.className,'fact');assert.deepEqual([...pair.children].map(el=>el.tagName),['DT','DD']);}
  assert.deepEqual(pairs.map(pair=>pair.querySelector('dt').textContent),['Hour','Production','Tank movement','Assumed price']);
  assert.equal(pairs[0].querySelector('dd').textContent,'13:00 Cyprus civil time');
  const day=fixture.days.find(d=>d.date==='2026-07-15'),plan=day.schedules['4000'];assert.equal(pairs[1].querySelector('dd').textContent,Math.round(plan.production[13]).toLocaleString('en-GB')+' m³');
  a.$('hour').value=23;a.$('hour').dispatchEvent(new a.w.Event('input'));assert.equal(a.$('hour-inspector').querySelector('.fact dd').textContent,'23:00 Cyprus civil time');
  a.route('data');const dataFacts=a.$('data-health').querySelector('dl');assert.ok([...dataFacts.children].every(pair=>pair.className==='fact'&&pair.children.length===2));assert.match(dataFacts.textContent,/2,208/);
 }finally{a.close();}
});

test('skip link focuses and scrolls to the active workspace without changing its route',async()=>{
 const a=await boot();try{
  const target=a.$('views'),focus=target.focus.bind(target),scrolls=[];let preventScroll;
  target.focus=options=>{preventScroll=options.preventScroll;focus(options);};target.scrollIntoView=options=>scrolls.push(options.block);
  for(const view of ['evaluation','pilot']){
   a.route(view);const hash=a.w.location.hash,link=a.w.document.querySelector('.skip-link');link.focus();
   const event=new a.w.MouseEvent('click',{bubbles:true,cancelable:true});link.dispatchEvent(event);
   await new Promise(resolve=>setTimeout(resolve,0));
   assert.equal(event.defaultPrevented,true);assert.equal(preventScroll,true);assert.equal(a.w.document.activeElement,target);assert.equal(a.w.location.hash,hash);assert.equal(a.w.document.body.dataset.view,view);assert.equal(a.$('view-'+view).hidden,false);assert.equal(a.$('view-overview').hidden,true);
  }
  assert.deepEqual(scrolls,['start','start']);
 }finally{a.close();}
});


test('horizontally scrollable charts expose a named keyboard focus target',async()=>{
 const a=await boot();try{for(const chart of a.w.document.querySelectorAll('.chart')){assert.equal(chart.tabIndex,0);assert.equal(chart.getAttribute('role'),'region');assert.ok(chart.getAttribute('aria-label'));}}finally{a.close();}
});

test('fixed-plan assessment exposes demand fragility and exports matched accounting',async()=>{
 const a=await boot();try{
  a.route('resilience');assert.equal(a.$('resilience-verdict').textContent,'Reserve breached');assert.match(a.$('resilience-explanation').textContent,/132/);
  a.$('resilience-export').click();const r=JSON.parse(await a.downloads.at(-1).text());
  assert.equal(r.kind,'fixed_plan_consequence_assessment');assert.equal(r.date,'2026-07-15');assert.equal(r.inputs.scenario.demand_multiplier,1.1);assert.equal(r.selected.rows[9].storage_end_m3,680);assert.equal(r.selected.rows[9].reserve_deficit_m3,120);assert.equal(r.sensitivity.length,36);
  assert.equal(r.control.inputs.initial,r.inputs.initial);assert.deepEqual(r.control.inputs.scenario,r.inputs.scenario);assert.equal(r.identity.data_sha256,JSON.parse(read('manifest.json')).data_sha256);
  a.$('resilience-reset').click();assert.match(a.$('resilience-verdict').textContent,/hold/);a.$('resilience-export').click();const nominal=JSON.parse(await a.downloads.at(-1).text());assert.ok(Math.abs(nominal.selected.totals.terminal_deficit_m3)<1e-6);
 }finally{a.close();}
});
test('assessment edits invalidate export and review until recomputed; a changed tank cannot inherit proof',async()=>{
 const a=await boot();try{
  a.route('resilience');a.$('resilience-demand').value='20';a.$('resilience-demand').dispatchEvent(new a.w.Event('input'));assert.equal(a.$('resilience-export').disabled,true);assert.match(a.$('resilience-verdict').textContent,/needs recalculation/);assert.equal(a.$('resilience-chart').children.length,0);
  a.route('reviews');openDecision(a,'review-decision-editor');a.$('review-note').value='Check the changed case';a.$('download-current-review').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).fixedPlanAssessment,null);
  a.route('resilience');assert.equal(a.$('resilience-export').disabled,true);a.$('resilience-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));a.route('reviews');a.$('download-current-review').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).fixedPlanAssessment.inputs.scenario.demand_multiplier,1.2);
  a.change('tank','8000');a.$('download-current-review').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).fixedPlanAssessment,null);
  a.route('resilience');assert.equal(a.$('resilience-initial').value,'4000');a.$('resilience-initial').value='9000';a.$('resilience-form').onsubmit(new a.w.Event('submit',{cancelable:true}));assert.equal(a.$('resilience-export').disabled,true);assert.equal(a.$('resilience-chart').children.length,0);
 }finally{a.close();}
});
test('known pilot tank reading starts only the remaining plan after an explicit stream mapping',async()=>{
 const a=await boot();try{
  a.route('pilot');await a.$('pilot-example').onclick();a.change('date','2026-07-01');a.route('resilience');assert.ok(a.$('resilience-reading').options.length>1);
  a.$('resilience-reading').value='0';a.$('resilience-use-reading').click();assert.match(a.$('resilience-reading-status').textContent,/explicitly map/);
  a.$('resilience-map').checked=true;a.$('resilience-use-reading').click();assert.equal(a.$('resilience-start').value,'10');assert.match(a.$('resilience-reading-status').textContent,/Synthetic/);
  a.$('resilience-export').click();const r=JSON.parse(await a.downloads.at(-1).text());assert.equal(r.selected.start_hour,10);assert.equal(r.selected.rows.length,14);assert.equal(r.observation.sourceKind,'synthetic_fixture');assert.equal(r.inputs.scenario.initial_storage_m3,r.observation.value);assert.equal(r.observation.identity.observations.sha256.length,64);
  a.route('pilot');a.$('pilot-as-of').value='2026-07-01T09:00:00+03:00';a.$('pilot-apply-time').click();a.route('reviews');openDecision(a,'review-decision-editor');a.$('review-note').value='Earlier information cutoff';a.$('download-current-review').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).fixedPlanAssessment,null);
  a.route('resilience');assert.equal(a.$('resilience-reading').options.length,1);assert.equal(a.$('resilience-use-reading').disabled,true);
 }finally{a.close();}
});
test('imported candidate assessment retains exact plan identity and compares the frozen plan',async()=>{
 const a=await boot();try{
  a.route('data');const d=fixture.days[0];await a.importPlan('time,production_m3,tank_capacity_m3\n'+d.times.map(t=>`${t},120,4000`).join('\n'),'team-plan.csv');a.$('inspect-candidate').click();a.route('resilience');a.$('resilience-export').click();const r=JSON.parse(await a.downloads.at(-1).text());
  assert.equal(r.planLabel,'Imported CSV candidate');assert.equal(r.control.label,'Frozen reference');assert.deepEqual(r.inputs.production,Array(24).fill(120));assert.equal(r.identity.plan.name,'team-plan.csv');assert.equal(r.identity.plan.sha256.length,64);
  const before=JSON.stringify(r.inputs.production);const cell=a.w.document.querySelector('#resilience-matrix button[aria-label^="Demand +20%, production loss 50%"]');cell.click();a.$('resilience-export').click();const changed=JSON.parse(await a.downloads.at(-1).text());assert.equal(JSON.stringify(changed.inputs.production),before);assert.equal(changed.inputs.scenario.production_multiplier,.5);assert.ok(changed.selected.totals.available_production_m3<r.selected.totals.available_production_m3);
 }finally{a.close();}
});

test('revoked tank mapping cannot remain attached to a review or export',async()=>{
 const a=await boot();try{
  a.route('pilot');await a.$('pilot-example').onclick();a.change('date','2026-07-01');a.route('resilience');a.$('resilience-reading').value='0';a.$('resilience-map').checked=true;a.$('resilience-use-reading').click();
  a.$('resilience-map').checked=false;a.$('resilience-map').dispatchEvent(new a.w.Event('change'));assert.equal(a.$('resilience-export').disabled,true);assert.match(a.$('resilience-reading-status').textContent,/Mapping removed/);
  a.route('reviews');openDecision(a,'review-decision-editor');a.$('review-note').value='Mapping withdrawn';a.$('download-current-review').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).fixedPlanAssessment,null);
  a.route('resilience');assert.equal(a.$('resilience-export').disabled,true);a.$('resilience-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));a.$('resilience-export').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).observation,null);
 }finally{a.close();}
});

test('empty readings show the import step, then reveal mapping and completed comparison',async()=>{
 const a=await boot();try{
  a.route('resilience');a.$('assessment-tab-observed').click();
  assert.equal(a.$('reconciliation-workbench').dataset.state,'empty');assert.equal(a.$('reconciliation-mapping').hidden,true);assert.equal(a.$('reconciliation-results').hidden,true);assert.equal(a.$('reconciliation-actions').hidden,true);assert.equal(a.$('reconciliation-import').hidden,false);
  assert.match(a.$('reconciliation-explanation').textContent,/source declaration and readings CSV/);assert.equal(a.$('reconciliation-filter').closest('[hidden]').id,'reconciliation-results');assert.equal(a.$('reconciliation-next').closest('[hidden]').id,'reconciliation-results');
  a.$('reconciliation-import').click();assert.equal(a.$('view-pilot').hidden,false);await a.$('pilot-example').onclick();a.route('resilience');a.$('assessment-tab-observed').click();
  assert.equal(a.$('reconciliation-workbench').dataset.state,'mapping');assert.equal(a.$('reconciliation-mapping').hidden,false);assert.equal(a.$('reconciliation-results').hidden,true);assert.equal(a.$('reconciliation-import').hidden,true);
  a.$('reconciliation-day').click();a.$('reconciliation-map-tank').value='tank-demo';a.$('reconciliation-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
  assert.equal(a.$('reconciliation-workbench').dataset.state,'result');assert.equal(a.$('reconciliation-results').hidden,false);assert.equal(a.$('reconciliation-export').disabled,false);assert.ok(a.$('reconciliation-ledger').querySelector('tbody tr'));assert.match(a.$('reconciliation-identity').textContent,/Observations SHA-256/);
  a.$('reconciliation-export').click();const record=JSON.parse(await a.downloads.at(-1).text());assert.equal(record.mapping.tank,'tank-demo');assert.equal(record.source.identity.observations.sha256.length,64);
  a.route('pilot');await pilotFile(a,'pilot-observations-file',pilotFixture('pilot-wrong-unit.csv'),'wrong-unit.csv');a.route('resilience');a.$('assessment-tab-observed').click();
  assert.equal(a.$('reconciliation-workbench').dataset.state,'empty');assert.equal(a.$('reconciliation-results').hidden,true);assert.equal(a.$('reconciliation-mapping').hidden,true);assert.equal(a.$('reconciliation-import').hidden,false);assert.equal(a.$('reconciliation-export').disabled,true);assert.match(a.$('reconciliation-explanation').textContent,/intake errors/);
 }finally{a.close();}
});

test('mapped observations compare with the selected plan and retain the result in a review',async()=>{
 const a=await boot();try{
  a.route('pilot');await a.$('pilot-example').onclick();a.route('resilience');a.$('assessment-tab-observed').click();
  assert.equal(a.$('assessment-conditions').hidden,true);assert.equal(a.$('assessment-observed').hidden,false);
  a.$('reconciliation-day').click();assert.equal(a.$('date').value,'2026-07-01');assert.match(a.$('workspace-case-label').textContent,/2026-07-01/);
  for(const [role,asset] of Object.entries({tank:'tank-demo',production:'unit-demo',unit_power:'unit-demo',available_power:'grid-demo'}))a.$('reconciliation-map-'+role).value=asset;
  a.$('reconciliation-sec').value='3.4';a.$('reconciliation-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
  assert.equal(a.$('reconciliation-export').disabled,false,a.$('reconciliation-error').textContent);
  assert.match(a.$('reconciliation-verdict').textContent,/require explanation/);assert.match(a.$('reconciliation-source').textContent,/Synthetic/);
  assert.match(a.$('reconciliation-summary').textContent,/\+358\.0 kW/);a.$('reconciliation-export').click();
  const record=JSON.parse(await a.downloads.at(-1).text());assert.equal(record.mapping.tank,'tank-demo');assert.equal(record.source.kind,'synthetic_fixture');
  assert.equal(record.plan.capacity,4000);assert.equal(record.rows.length,16);assert.equal(record.specific_energy_kwh_m3,3.4);
  a.route('reviews');openDecision(a,'review-decision-editor');a.$('review-note').value='Inspect observed differences';a.$('download-current-review').click();const review=JSON.parse(await a.downloads.at(-1).text());assert.deepEqual(review.observedDepartures,record);
 }finally{a.close();}
});

test('observation comparisons require explicit mappings and respect the review cutoff',async()=>{
 const a=await boot();try{
  a.route('resilience');a.$('assessment-tab-observed').click();a.$('reconciliation-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));assert.match(a.$('reconciliation-error').textContent,/Load observations/);
  a.route('pilot');await a.$('pilot-example').onclick();a.route('resilience');a.$('reconciliation-day').click();
  a.$('reconciliation-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));assert.match(a.$('reconciliation-error').textContent,/Map at least one/);
  a.$('reconciliation-map-unit_power').value='unit-demo';a.$('reconciliation-map-available_power').value='grid-demo';a.$('reconciliation-cutoff').value='2026-07-01T10:02:00+03:00';
  a.$('reconciliation-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));a.$('reconciliation-export').click();const early=JSON.parse(await a.downloads.at(-1).text());
  assert.equal(early.rows.find(row=>row.kind==='reported_power_difference').difference,null);assert.equal(early.coverage.known_observations,3);
  assert.equal(early.rows.find(row=>row.kind==='modeled_power').expected,null);
  a.route('reviews');assert.match(a.$('review-gates').textContent,/No comparable observations \/ 16 unknown comparisons/);a.route('resilience');
  a.$('reconciliation-cutoff').value='2026-07-01T10:05:00+03:00';a.$('reconciliation-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
  a.$('reconciliation-export').click();const ready=JSON.parse(await a.downloads.at(-1).text());assert.equal(ready.rows.find(row=>row.kind==='reported_power_difference').difference,358);
  a.change('reconciliation-filter','requires_explanation');assert.equal(a.$('reconciliation-ledger').querySelectorAll('tbody tr').length,1);
 }finally{a.close();}
});

test('changed comparison settings, plan and source cannot leave stale observation evidence',async()=>{
 const a=await boot();try{
  a.route('pilot');await a.$('pilot-example').onclick();a.route('resilience');a.$('assessment-tab-observed').click();a.$('reconciliation-day').click();a.$('reconciliation-map-tank').value='tank-demo';
  const compare=()=>a.$('reconciliation-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));compare();assert.equal(a.$('reconciliation-export').disabled,false);
  a.$('reconciliation-tolerance-tank_storage_m3').value='20';a.$('reconciliation-tolerance-tank_storage_m3').dispatchEvent(new a.w.Event('input'));
  assert.equal(a.$('reconciliation-export').disabled,true);assert.equal(a.$('reconciliation-ledger').children.length,0);
  compare();a.change('tank','8000');assert.equal(a.$('reconciliation-export').disabled,true);assert.match(a.$('reconciliation-verdict').textContent,/plan changed/);
  compare();a.route('pilot');a.$('pilot-as-of').value='2026-07-01T10:02:00+03:00';a.$('pilot-apply-time').click();a.route('reviews');openDecision(a,'review-decision-editor');a.$('review-note').value='Source cutoff changed';a.$('download-current-review').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).observedDepartures,null);
  a.route('resilience');assert.equal(a.$('reconciliation-map-tank').value,'');assert.equal(a.$('reconciliation-export').disabled,true);
  a.$('assessment-tab-observed').dispatchEvent(new a.w.KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true}));assert.equal(a.$('assessment-tab-conditions').getAttribute('aria-selected'),'true');
 }finally{a.close();}
});

test('small observed departures remain visible at the declared tolerance',async()=>{
 const a=await boot();try{
  a.route('pilot');await a.$('pilot-example').onclick();await pilotFile(a,'pilot-observations-file','time,available_at,asset_id,measurement,value,unit\n2026-07-01T10:00:00+03:00,2026-07-01T10:01:00+03:00,unit-demo,production_rate_m3_h,120.01,m3/h\n','small-difference.csv');
  a.route('resilience');a.$('assessment-tab-observed').click();a.$('reconciliation-day').click();a.$('reconciliation-map-production').value='unit-demo';a.$('reconciliation-tolerance-production_rate_m3_h').value='0.001';
  a.$('reconciliation-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));assert.match(a.$('reconciliation-summary').textContent,/\+0\.0100 m³\/h/);assert.match(a.$('reconciliation-verdict').textContent,/1 comparison requires/);
 }finally{a.close();}
});

async function readyBridge(a){
 a.route('pilot');await a.$('pilot-example').onclick();a.route('resilience');a.$('assessment-tab-observed').click();a.$('reconciliation-day').click();
 a.$('reconciliation-map-tank').value='tank-demo';a.$('reconciliation-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
 assert.equal(a.$('reconciliation-export').disabled,false,a.$('reconciliation-error').textContent);
 return [...a.$('reconciliation-ledger').querySelectorAll('button')];
}
async function assessment(a){a.$('resilience-export').click();return JSON.parse(await a.downloads.at(-1).text());}

test('one action carries exact historical mapping and provenance into remaining-plan assessment',async()=>{
 const a=await boot();try{
  const actions=await readyBridge(a);assert.equal(actions.length,4);actions[0].click();
  assert.equal(a.$('assessment-conditions').hidden,false);assert.equal(a.$('assessment-observed').hidden,true);
  assert.equal(a.$('resilience-start').value,'10');assert.equal(a.$('resilience-initial').value,'1800');
  assert.equal(a.$('resilience-manual-reading').hidden,true);assert.equal(a.$('resilience-map').checked,false);
  assert.match(a.$('resilience-horizon').textContent,/01\/07\/2026, 10:00 GMT\+3/);
  const r=await assessment(a);assert.equal(r.selected.start_hour,10);assert.equal(r.selected.rows.length,14);
  assert.equal(r.inputs.scenario.demand_multiplier,1);assert.equal(r.inputs.scenario.production_multiplier,1);assert.equal(r.inputs.scenario.outage.duration_hours,0);
  assert.equal(r.observation.value,1800);assert.equal(r.observation.bridge.kind,'mapped_historical_tank_restart');
  assert.equal(r.observation.available_at,'2026-07-01T10:02:00+03:00');assert.equal(r.observation.bridge.start_hour,10);
  assert.equal(r.observation.bridge.mapping.asset_id,'tank-demo');assert.equal(r.observation.bridge.source.identity.observations.sha256.length,64);
  assert.equal(r.observation.sourceKind,'synthetic_fixture');assert.match(a.$('resilience-reading-status').textContent,/Synthetic historical reading/);
  openDecision(a,'review-decision-editor');a.$('review-note').value='Review consequence from the selected historical reading';a.route('reviews');a.$('download-current-review').click();
  const review=JSON.parse(await a.downloads.at(-1).text());assert.deepEqual(review.fixedPlanAssessment.observation.bridge,r.observation.bridge);
 }finally{a.close();}
});

test('mapping edits revoke the carried proof; an explicit later run records only a scenario value',async()=>{
 const a=await boot();try{
  (await readyBridge(a))[0].click();await assessment(a);
  a.$('assessment-tab-observed').click();a.$('reconciliation-map-tank').value='';a.$('reconciliation-map-tank').dispatchEvent(new a.w.Event('input'));
  openDecision(a,'review-decision-editor');a.$('review-note').value='Changed mapping';a.route('reviews');a.$('download-current-review').click();
  assert.equal(JSON.parse(await a.downloads.at(-1).text()).fixedPlanAssessment,null);
  a.route('resilience');a.$('assessment-tab-conditions').click();assert.equal(a.$('resilience-export').disabled,true);
  assert.match(a.$('resilience-reading-status').textContent,/Historical mapping revoked/);assert.equal(a.$('resilience-manual-reading').hidden,false);
  a.$('resilience-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));const manual=await assessment(a);
  assert.equal(manual.observation,null);assert.equal(manual.inputs.scenario.initial_storage_m3,1800);
  assert.match(a.$('resilience-chart-note').textContent,/Starting inventory is a scenario value/);
 }finally{a.close();}
});

test('changed pilot cutoff invalidates proof before export, even without revisiting observed departures',async()=>{
 const a=await boot();try{
  (await readyBridge(a))[0].click();await assessment(a);
  a.route('pilot');a.$('pilot-as-of').value='2026-07-01T10:01:00+03:00';a.$('pilot-apply-time').click();
  const before=a.downloads.length;a.$('resilience-export').click();assert.equal(a.downloads.length,before);
  assert.equal(a.$('resilience-export').disabled,true);assert.match(a.$('resilience-reading-status').textContent,/revoked/);
 }finally{a.close();}
});

test('explicit comparison cutoff can extend intake review while preserving both and excluding late readings',async()=>{
 const a=await boot();try{
  a.route('pilot');await a.$('pilot-example').onclick();a.$('pilot-as-of').value='2026-07-01T10:01:00+03:00';a.$('pilot-apply-time').click();
  a.route('resilience');a.$('assessment-tab-observed').click();a.$('reconciliation-day').click();a.$('reconciliation-map-tank').value='tank-demo';
  const compare=()=>a.$('reconciliation-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));compare();
  assert.equal(a.$('reconciliation-ledger').querySelectorAll('button').length,0);
  a.$('reconciliation-cutoff').value='2026-07-01T10:02:00+03:00';compare();
  const buttons=a.$('reconciliation-ledger').querySelectorAll('button');assert.equal(buttons.length,1);buttons[0].click();
  const r=await assessment(a);assert.equal(r.observation.bridge.original_intake_cutoff,'2026-07-01T07:01:00.000Z');
  assert.equal(r.observation.bridge.comparison_cutoff,'2026-07-01T07:02:00.000Z');assert.equal(r.observation.bridge.reading.available_at,'2026-07-01T10:02:00+03:00');
  assert.equal(r.observation.bridge.source.kind,'synthetic_fixture');assert.equal(r.selected.start_hour,10);
 }finally{a.close();}
});

test('selected plan change discards historical proof and restores nominal initial inventory',async()=>{
 const a=await boot();try{
  (await readyBridge(a))[0].click();a.change('tank','8000');const r=await assessment(a);
  assert.equal(r.observation,null);assert.equal(r.inputs.scenario.initial_storage_m3,4000);assert.equal(r.selected.start_hour,0);
 }finally{a.close();}
});

test('identical remapping and recomparison cannot revive a revoked carried proof',async()=>{
 const a=await boot();try{
  (await readyBridge(a))[0].click();await assessment(a);a.$('assessment-tab-observed').click();
  a.$('reconciliation-map-tank').value='';a.$('reconciliation-map-tank').dispatchEvent(new a.w.Event('input'));
  a.$('reconciliation-map-tank').value='tank-demo';a.$('reconciliation-map-tank').dispatchEvent(new a.w.Event('input'));
  a.$('reconciliation-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
  openDecision(a,'review-decision-editor');a.$('review-note').value='Mapping was revoked and recreated';a.route('reviews');a.$('download-current-review').click();
  assert.equal(JSON.parse(await a.downloads.at(-1).text()).fixedPlanAssessment,null);
  a.route('resilience');a.$('reconciliation-ledger').querySelector('button').click();
  assert.equal((await assessment(a)).observation.value,1800);
 }finally{a.close();}
});

test('restoring the original pilot cutoff without visiting assessment cannot revive historical proof',async()=>{
 const a=await boot();try{
  (await readyBridge(a))[0].click();const original=(await assessment(a)).observation.bridge.original_intake_cutoff;
  a.route('pilot');a.$('pilot-as-of').value='2026-07-01T10:01:00+03:00';a.$('pilot-apply-time').click();
  a.$('pilot-as-of').value=original;a.$('pilot-apply-time').click();
  openDecision(a,'review-decision-editor');a.$('review-note').value='Pilot cutoff changed and restored';a.route('reviews');a.$('download-current-review').click();
  assert.equal(JSON.parse(await a.downloads.at(-1).text()).fixedPlanAssessment,null);
 }finally{a.close();}
});

test('restoring the original selected tank away from assessment cannot revive carried proof',async()=>{
 const a=await boot();try{
  (await readyBridge(a))[0].click();await assessment(a);a.route('operations');
  a.change('tank','8000');a.change('tank','4000');openDecision(a,'review-decision-editor');a.$('review-note').value='Plan context changed and restored';a.route('reviews');
  a.$('download-current-review').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).fixedPlanAssessment,null);
 }finally{a.close();}
});


test('tab navigation cannot silently recalculate revoked historical evidence as a scenario',async()=>{
 const a=await boot();try{
  (await readyBridge(a))[0].click();a.$('assessment-tab-observed').click();
  a.$('reconciliation-map-tank').value='';a.$('reconciliation-map-tank').dispatchEvent(new a.w.Event('input'));
  a.$('assessment-tab-conditions').click();assert.equal(a.$('resilience-export').disabled,true);
  a.$('assessment-tab-observed').click();a.$('reconciliation-map-tank').value='tank-demo';
  a.$('reconciliation-map-tank').dispatchEvent(new a.w.Event('input'));
  a.$('reconciliation-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
  a.$('assessment-tab-conditions').click();assert.equal(a.$('resilience-export').disabled,true);
  assert.match(a.$('resilience-reading-status').textContent,/revoked/);
  a.route('reviews');openDecision(a,'review-decision-editor');a.$('review-note').value='Navigation must not recalculate revoked evidence';a.$('download-current-review').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).fixedPlanAssessment,null);
  a.route('resilience');assert.equal(a.$('resilience-export').disabled,true);
  a.$('resilience-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
  const r=await assessment(a);assert.equal(r.observation,null);assert.equal(r.inputs.scenario.initial_storage_m3,1800);
 }finally{a.close();}
});
test('condition edits stay uncalculated across tab and route navigation until explicit run',async()=>{
 const a=await boot();try{
  a.route('resilience');a.$('resilience-demand').value='20';a.$('resilience-demand').dispatchEvent(new a.w.Event('input'));
  a.$('assessment-tab-observed').click();a.$('assessment-tab-conditions').click();assert.equal(a.$('resilience-export').disabled,true);
  a.route('reviews');a.route('resilience');assert.equal(a.$('resilience-export').disabled,true);
  a.$('resilience-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
  assert.equal((await assessment(a)).inputs.scenario.demand_multiplier,1.2);
 }finally{a.close();}
});

const wait=()=>new Promise(r=>setTimeout(r,5));
function openDecision(a,id){if(!a.$(id).open)a.$(id).querySelector('summary').click();}
const input=(a,id,value)=>{if(['revision-note','revision-decision'].includes(id))openDecision(a,'revision-decision-panel');a.$(id).value=value;a.$(id).dispatchEvent(new a.w.Event('input'));};
async function currentCase(a){
 a.route('resilience');input(a,'resilience-demand','0');input(a,'resilience-initial','700');input(a,'resilience-start','10');a.$('resilience-form').onsubmit({preventDefault(){}});
 a.route('reviews');a.$('review-tab-revision').click();if(!a.$('revision-inputs').open)a.$('revision-inputs').querySelector('summary').click();await a.$('revision-current').onclick();assert.equal(a.$('revision-case-export').disabled,false,a.$('revision-case-status').textContent);
 a.$('revision-assumptions').open=true;a.$('revision-case-export').click();a.$('revision-assumptions').open=false;const raw=await a.downloads.at(-1).text();a.$('revision-template').click();const template=await a.downloads.at(-1).text();return{raw,template};
}
const proposalText=(a,template)=>{const rows=a.w.Papa.parse(template,{skipEmptyLines:true}).data;rows[1][2]='220';return a.w.Papa.unparse(rows);};
const submit=a=>{openDecision(a,'revision-decision-panel');a.$('revision-review-form').onsubmit({preventDefault(){}});};
test('complete revision task freezes exact bytes, accepts added water, exports and reopens reproducibly',async()=>{
 const a=await boot();try{
  const {raw,template}=await currentCase(a),hash=createHash('sha256').update(raw).digest('hex');assert.equal(a.w.Papa.parse(template).data[1][0],hash);
  await a.importRevision('revision-proposal-file',proposalText(a,template),'Stefanos-return.csv');assert.equal(a.$('revision-result').hidden,false,a.$('revision-proposal-status').textContent);
  assert.match(a.$('revision-comparison').textContent,/\+340\.00 kWh/);assert.match(a.$('revision-water-balance').textContent,/1,900\.00 m³2,000\.00 m³\+100\.00 m³/);
  input(a,'revision-author','Stefanos (declared)');input(a,'revision-note','Extra 100 m³ restores the target with 340 modeled kWh; discuss the initial reserve deficit.');submit(a);
  const reviewRaw=await a.downloads.at(-1).text(),review=JSON.parse(reviewRaw);assert.equal(review.case_file.text,raw);assert.equal(review.case_file.sha256,hash);assert.equal(review.comparison.revised.result.totals.final_storage_m3,2000);
  review.comparison.revised.result.totals.final_storage_m3=999999;
  await a.importRevision('revision-case-file',JSON.stringify(review),'saved-review.json');assert.match(a.$('revision-review-status').textContent,/Saved review recalculated/);assert.doesNotMatch(a.$('revision-comparison').textContent,/999/);assert.equal(a.$('revision-author').value,'Stefanos (declared)');
  // Global selected day does not silently change the deliberately frozen historical case.
  a.change('date','2026-07-16');assert.match(a.$('revision-case-status').textContent,/2026-07-15/);assert.match(a.$('revision-horizon').textContent,/15 Jul 2026/);
 }finally{a.close();}
});
test('case or assumptions edits clear comparison and identical restored values do not revive it',async()=>{
 const a=await boot();try{
  const {raw,template}=await currentCase(a);await a.importRevision('revision-proposal-file',proposalText(a,template),'proposal.csv');
  input(a,'revision-note','Old accepted rationale');input(a,'revision-decision','Ready for next simulation');input(a,'revision-author','Old author');input(a,'revision-unit','499');input(a,'revision-unit','500');assert.equal(a.$('revision-note').value,'');assert.equal(a.$('revision-decision').value,'Needs team review');assert.equal(a.$('revision-author').value,'');a.route('operations');a.route('reviews');assert.equal(a.$('revision-result').hidden,true);assert.equal(a.$('revision-review-export').disabled,true);
  await a.$('revision-freeze').onclick();assert.equal(a.$('revision-review-export').disabled,true);assert.equal(a.$('revision-result').hidden,true);
  await a.importRevision('revision-proposal-file',proposalText(a,template),'proposal.csv');assert.equal(a.$('revision-result').hidden,false);
  const bad=JSON.parse(raw);bad.assessment.identity.data_sha256='0'.repeat(64);await a.importRevision('revision-case-file',JSON.stringify(bad),'wrong-source.json');assert.match(a.$('revision-case-status').textContent,/source-data hash does not match/);assert.equal(a.$('revision-result').hidden,true);assert.equal(a.$('revision-template').disabled,true);
 }finally{a.close();}
});
test('unknown energy, empty reason, wrong CSV case and byte-tampered reopened review fail safely',async()=>{
 const a=await boot();try{
  const {template}=await currentCase(a);input(a,'revision-sec','');await a.$('revision-freeze').onclick();a.$('revision-template').click();const changed=await a.downloads.at(-1).text();
  await a.importRevision('revision-proposal-file',template,'old-case.csv');assert.match(a.$('revision-proposal-status').textContent,/different case/);assert.equal(a.$('revision-review-export').disabled,true);
  await a.importRevision('revision-proposal-file',changed,'unknown-energy.csv');assert.match(a.$('revision-comparison').textContent,/Modeled production energyUnknownUnknownUnknown/);
  input(a,'revision-note','   ');submit(a);assert.match(a.$('revision-review-status').textContent,/valid reason/);
  input(a,'revision-note','Inspect before the next simulation.');submit(a);const record=JSON.parse(await a.downloads.at(-1).text());record.proposal_file.text+='\n';await a.importRevision('revision-case-file',JSON.stringify(record),'altered-review.json');assert.match(a.$('revision-case-status').textContent,/hash does not match its bytes/);assert.equal(a.$('revision-result').hidden,true);
 }finally{a.close();}
});
test('pending old case cannot overwrite newer case; pending CSV cannot survive a changed assumption',async()=>{
 const a=await boot();try{
  const {raw,template}=await currentCase(a);let resolveOld;
  Object.defineProperty(a.$('revision-case-file'),'files',{value:[{name:'slow.json',size:raw.length,arrayBuffer:()=>new Promise(r=>resolveOld=r)}],configurable:true});const pending=a.$('revision-case-file').onchange();
  const newer=JSON.parse(raw);newer.assessment.inputs.scenario.initial_storage_m3=900;await a.importRevision('revision-case-file',JSON.stringify(newer),'newer.json');resolveOld(new TextEncoder().encode(raw).buffer);await pending;assert.match(a.$('revision-identity').textContent,/newer.json/);assert.match(a.$('revision-identity').textContent,/900\.00 m³/);
  let resolveCSV;Object.defineProperty(a.$('revision-proposal-file'),'files',{value:[{name:'slow.csv',size:template.length,arrayBuffer:()=>new Promise(r=>resolveCSV=r)}],configurable:true});const csvPending=a.$('revision-proposal-file').onchange();input(a,'revision-sec','4');resolveCSV(new TextEncoder().encode(template).buffer);await csvPending;assert.equal(a.$('revision-result').hidden,true);assert.equal(a.$('revision-review-export').disabled,true);assert.match(a.$('revision-case-status').textContent,/Assumptions changed/);
 }finally{a.close();}
});
test('legacy assessment requires an explicit freeze and revision tabs work by keyboard',async()=>{
 const a=await boot();try{
  const {raw}=await currentCase(a);await a.importRevision('revision-case-file',JSON.stringify(JSON.parse(raw).assessment),'old-consequence.json');assert.equal(a.$('revision-case-export').disabled,true);assert.equal(a.$('revision-freeze').disabled,false);
  await a.$('revision-freeze').onclick();assert.equal(a.$('revision-template').disabled,false);
  a.$('review-tab-revision').dispatchEvent(new a.w.KeyboardEvent('keydown',{key:'Home',bubbles:true}));assert.equal(a.$('review-current').hidden,false);assert.equal(a.w.document.activeElement.id,'review-tab-current');
  a.$('review-tab-current').dispatchEvent(new a.w.KeyboardEvent('keydown',{key:'End',bubbles:true}));assert.equal(a.$('review-revision').hidden,false);assert.equal(a.w.document.activeElement.id,'review-tab-revision');
 }finally{a.close();}
});
test('historical proof is retained only when its observed start and complete nominal plan agree',async()=>{
 const a=await boot();try{
  a.route('pilot');await a.$('pilot-example').onclick();a.route('resilience');a.$('assessment-tab-observed').click();a.$('reconciliation-day').click();a.$('reconciliation-map-tank').value='tank-demo';a.$('reconciliation-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));a.$('reconciliation-ledger').querySelector('button').click();
  a.route('reviews');a.$('review-tab-revision').click();if(!a.$('revision-inputs').open)a.$('revision-inputs').querySelector('summary').click();await a.$('revision-current').onclick();assert.equal(a.$('revision-case-export').disabled,false,a.$('revision-case-status').textContent);
  a.$('revision-assumptions').open=true;a.$('revision-case-export').click();a.$('revision-assumptions').open=false;const raw=await a.downloads.at(-1).text();assert.match(a.$('revision-identity').textContent,/Historical mapped reading retained/);
  for(const mutate of [c=>c.assessment.inputs.scenario.initial_storage_m3++,c=>c.assessment.inputs.startHour++,c=>c.assessment.inputs.production[0]++,c=>c.assessment.observation.bridge.plan.storage[0]++,c=>c.assessment.identity.plan='changed',c=>c.assessment.date='2026-07-15',c=>c.assessment.observation={value:1},c=>c.assessment.observation.bridge.comparison_cutoff='2026-07-01T10:01:00+03:00']){
   const c=JSON.parse(raw);mutate(c);await a.importRevision('revision-case-file',JSON.stringify(c),'inconsistent.json');assert.equal(a.$('revision-case-export').disabled,true,a.$('revision-case-status').textContent);assert.doesNotMatch(a.$('revision-identity').textContent,/Historical mapped/);
  }
  await a.importRevision('revision-case-file',raw,'original.json');assert.equal(a.$('revision-case-export').disabled,false,a.$('revision-case-status').textContent);
 }finally{a.close();}
});
test('returned-review context hides unrelated selectors and restores current-plan status',async()=>{
 const a=await boot();try{
  await currentCase(a);assert.equal(a.w.document.querySelector('.context').hidden,true);assert.match(a.$('status').textContent,/Frozen returned-plan review/);
  a.route('operations');assert.equal(a.w.document.querySelector('.context').hidden,false);a.route('reviews');assert.equal(a.w.document.querySelector('.context').hidden,true);assert.match(a.$('status').textContent,/Frozen returned-plan review/);
  a.$('review-tab-current').click();assert.equal(a.w.document.querySelector('.context').hidden,false);assert.match(a.$('review-case-title').textContent,/15 Jul 2026/);
 }finally{a.close();}
});


test('returned comparison foregrounds results, retains editable inputs and shows Cyprus time',async()=>{
 const a=await boot();try{
  const {template}=await currentCase(a);assert.equal(a.$('revision-inputs').open,true);assert.equal(a.w.document.activeElement.id,'revision-proposal-file');
  await a.importRevision('revision-proposal-file',proposalText(a,template),'illustrative-return.csv');
  assert.equal(a.$('revision-inputs').open,false);assert.equal(a.$('revision-result').hidden,false);assert.equal(a.w.document.activeElement.id,'revision-result');
  assert.match(a.$('revision-horizon').textContent,/15 Jul 2026, 10:00 GMT\+3/);
  a.$('revision-inputs').querySelector('summary').click();assert.equal(a.$('revision-inputs').open,true);
  input(a,'revision-sec','');assert.equal(a.$('revision-result').hidden,true);assert.equal(a.$('revision-review-export').disabled,true);
 }finally{a.close();}
});


test('compact navigation supports selection and Escape with focus recovery',async()=>{
 const a=await boot();try{
  a.w.innerWidth=390;a.w.dispatchEvent(new a.w.Event('resize'));
  a.$('workspace-toggle').click();assert.equal(a.$('workspace-toggle').getAttribute('aria-expanded'),'true');
  a.$('workspace-toggle').dispatchEvent(new a.w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  assert.equal(a.$('workspace-toggle').getAttribute('aria-expanded'),'false');assert.equal(a.w.document.activeElement.id,'workspace-toggle');
  a.$('workspace-toggle').click();a.w.document.querySelector('[data-view=reviews]').focus();a.route('reviews');assert.equal(a.w.document.activeElement.id,'views');assert.equal(a.$('workspace-toggle').getAttribute('aria-expanded'),'false');
  assert.equal(a.$('view-reviews').hidden,false);
 }finally{a.close();}
});
test('review distinguishes unassessed conditions and recovers a hidden missing reviewer',async()=>{
 const a=await boot();try{
  a.route('reviews');assert.doesNotMatch(a.$('review-outcomes').textContent,/Not assessed/);assert.match(a.$('review-assessment-state').textContent,/not assessed/);
  assert.equal(a.$('review-history-summary').parentElement.open,false);
  a.$('reviewer').value='';openDecision(a,'review-decision-editor');a.$('review-note').value='Check the water reserve.';
  a.$('review-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
  assert.equal(a.w.document.querySelector('.review-record-details').open,true);assert.equal(a.w.document.activeElement.id,'reviewer');
  assert.equal(a.w.localStorage.getItem('aquashift.review.v1'),null);
  const {template}=await currentCase(a);await a.importRevision('revision-proposal-file',proposalText(a,template),'return.csv');
  a.$('revision-reviewer').value='';openDecision(a,'revision-decision-panel');a.$('revision-note').value='Check the reserve.';a.$('revision-review-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
  assert.equal(a.$('revision-assumptions').open,true);assert.equal(a.w.document.activeElement.id,'revision-reviewer');
 }finally{a.close();}
});


test('current review retains a nonzero shortfall smaller than one cubic metre',async()=>{
 const a=await boot();try{
  a.route('resilience');input(a,'resilience-initial','1999.9');input(a,'resilience-demand','0');
  a.$('resilience-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));a.route('reviews');
  assert.match(a.$('review-outcomes').textContent,/0\.1 m³/);assert.match(a.$('review-outcomes').textContent,/-0\.1 m³/);
  assert.match(a.$('review-assessment-state').textContent,/1,999\.9 m³/);
 }finally{a.close();}
});


test('returned-plan demand margin preserves final target, exports bounds and recalculates on reopen',async()=>{
 const a=await boot();try{
  const fixture=JSON.parse(fs.readFileSync(new URL('fixtures/returned-demand-margin.json',import.meta.url)));
  a.route('reviews');a.$('review-tab-revision').click();
  await a.importRevision('revision-case-file',fixture.case_file.text,fixture.case_file.name);
  await a.importRevision('revision-proposal-file',fixture.proposal_file.text,fixture.proposal_file.name);
  assert.equal(a.$('revision-demand-margin').open,false);
  assert.match(a.$('revision-margin-table').textContent,/At current demand/);assert.match(a.$('revision-margin-table').textContent,/7\.14% above current demand/);
  assert.match(a.$('revision-margin-table').textContent,/Final tank target/);
  openDecision(a,'revision-decision-panel');a.$('revision-note').value='The extra 100 cubic metres buys limited demand margin with 340 additional modeled kWh.';
  a.$('revision-review-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
  const saved=JSON.parse(await a.downloads.at(-1).text());
  assert.ok(Math.abs(saved.comparison.revised.result.margins.joint_maximum_demand_multiplier-15/14)<1e-10);
  saved.comparison.revised.result.margins.joint_maximum_demand_multiplier=100;
  await a.importRevision('revision-case-file',JSON.stringify(saved),'saved.json');
  assert.match(a.$('revision-margin-table').textContent,/7\.14% above current demand/);assert.doesNotMatch(a.$('revision-margin-table').textContent,/9,900/);
  input(a,'revision-unit','499');assert.equal(a.$('revision-result').hidden,true);assert.equal(a.$('revision-margin-table').textContent,'');
 }finally{a.close();}
});

test('review plan selection moves without duplicating controls or changing context',async()=>{
 const a=await boot();try{
  a.route('reviews');const context=a.w.document.querySelector('.context');
  assert.equal(context.parentElement.id,'review-plan-selection');assert.equal(a.$('review-plan-selection').open,false);
  assert.equal(a.$('review-decision-editor').open,false);assert.equal(a.$('review-outcomes').querySelectorAll('thead th').length,2);
  a.$('review-plan-selection').open=true;a.change('date','2026-08-01');a.change('tank','2000');
  assert.match(a.$('review-case-title').textContent,/1 Aug 2026, 2,000 m³ tank/);
  a.$('review-tab-revision').click();assert.equal(context.hidden,true);a.$('review-tab-current').click();assert.equal(context.hidden,false);
  a.route('operations');assert.equal(context.parentElement.id,'workspace-case-row');assert.equal(context.hidden,false);
  assert.equal(a.$('date').value,'2026-08-01');assert.equal(a.$('tank').value,'2000');assert.equal(a.w.document.querySelectorAll('#date').length,1);
  a.route('reviews');openDecision(a,'review-decision-editor');a.$('review-note').value='';a.$('download-current-review').click();
  assert.equal(a.$('review-decision-editor').open,true);assert.equal(a.w.document.activeElement.id,'review-note');assert.equal(a.downloads.length,0);
 }finally{a.close();}
});
test('returned review keeps complete outcomes and template access behind the simplified sheet',async()=>{
 const a=await boot();try{
  const {template}=await currentCase(a);assert.equal(a.$('revision-template').closest('#revision-assumptions'),null);
  await a.importRevision('revision-proposal-file',proposalText(a,template),'returned.csv');
  assert.equal(a.$('revision-comparison').querySelectorAll('tbody tr').length,4);
  assert.equal(a.$('revision-water-balance').querySelectorAll('tbody tr').length,4);
  assert.equal(a.$('revision-decision-panel').open,false);openDecision(a,'revision-decision-panel');
  a.$('revision-review-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
  assert.equal(a.$('revision-decision-panel').open,true);assert.equal(a.w.document.activeElement.id,'revision-note');
  input(a,'revision-unit','499');assert.equal(a.$('revision-water-balance').textContent,'');assert.equal(a.$('revision-result').hidden,true);
 }finally{a.close();}
});

test('hour inspection reads retained boundary inventory without changing the reviewed plan',async()=>{
 const a=await boot();try{
  a.route('reviews');input(a,'review-inspect-hour','0');assert.match(a.$('review-boundary-values').textContent,/Plan at 00:002,000m³/);
  input(a,'review-inspect-hour','13');assert.match(a.$('review-boundary-values').textContent,/Plan at 13:001,320m³/);
  input(a,'review-inspect-hour','24');assert.match(a.$('review-boundary-values').textContent,/Plan at 24:002,000m³/);
  openDecision(a,'review-decision-editor');a.$('review-note').value='Boundary inspection only.';a.$('download-current-review').click();const reviewed=JSON.parse(await a.downloads.at(-1).text());
  assert.equal(reviewed.totals.water_produced_m3,2880);assert.equal(reviewed.totals.energy_kwh,9792);assert.equal(reviewed.fixedPlanAssessment,null);
 }finally{a.close();}
});
test('returned boundary inspection preserves matched case and reflects both retained trajectories',async()=>{
 const a=await boot();try{
  const {raw,template}=await currentCase(a);await a.importRevision('revision-proposal-file',proposalText(a,template),'returned.csv');
  assert.equal(a.$('revision-inspect-hour').max,'14');assert.match(a.$('revision-inspect-time').textContent,/10:00 GMT\+3/);
  assert.match(a.$('revision-boundary-values').textContent,/Original700m³Returned700m³Difference0m³/);
  input(a,'revision-inspect-hour','14');assert.match(a.$('revision-inspect-time').textContent,/00:00 GMT\+3/);
  assert.match(a.$('revision-inspect-time').title,/16 Jul 2026/);
  assert.match(a.$('revision-boundary-values').textContent,/Original1,900m³Returned2,000m³Difference100m³/);
  input(a,'revision-note','Checked hourly boundaries.');submit(a);const record=JSON.parse(await a.downloads.at(-1).text());assert.equal(record.case_file.text,raw);assert.equal(record.comparison.revised.modeled_production_energy_kwh-record.comparison.original.modeled_production_energy_kwh,340);
 }finally{a.close();}
});

async function solarDraft(a){
 const {template}=await currentCase(a);await a.importRevision('revision-proposal-file',proposalText(a,template),'test-return.csv');a.$('revision-solar').open=true;a.$('revision-solar-profile').open=true;a.$('revision-solar-template').click();a.$('revision-solar-profile').open=false;a.$('revision-solar').open=false;
 const p=JSON.parse(await a.downloads.at(-1).text());Object.assign(p,{source_kind:'illustrative_scenario',source_label:'QA solar allocation',plant_mapping:'One modeled unit'});p.intervals.forEach(r=>r.power_kw=1000);return p;
}
test('solar allocation task preserves exact bytes and recalculates both energy and source on reopen',async()=>{
 const a=await boot();try{
  const p=await solarDraft(a);assert.equal(a.$('revision-solar').open,false);const raw='\uFEFF'+JSON.stringify(p);await a.importRevision('revision-solar-file',raw,'solar.json');
  assert.match(a.$('revision-solar-status').textContent,/Complete profile: 14/);assert.match(a.$('revision-solar-table').textContent,/\+340\.00 kWh/);assert.match(a.$('revision-solar-source').textContent,/Illustrative scenario/);
  input(a,'revision-note','Conditional solar result; retain water deficits.');submit(a);const r=JSON.parse(await a.downloads.at(-1).text());assert.equal(r.solar_file.text,raw);assert.equal(r.solar_file.sha256,createHash('sha256').update(raw).digest('hex'));assert.equal(r.solar_comparison.totals.delta_solar_kwh,340);assert.equal(r.comparison.changes.modeled_production_energy_kwh,340);
  r.solar_comparison.totals.delta_solar_kwh=999999;await a.importRevision('revision-case-file',JSON.stringify(r),'solar-review.json');assert.match(a.$('revision-review-status').textContent,/recalculated/);assert.doesNotMatch(a.$('revision-solar-table').textContent,/999/);assert.match(a.$('revision-solar-table').textContent,/\+340\.00 kWh/);
  r.solar_file.text+='\n';await a.importRevision('revision-case-file',JSON.stringify(r),'tampered.json');assert.equal(a.$('revision-result').hidden,true);assert.match(a.$('revision-case-status').textContent,/hash does not match/);
 }finally{a.close();}
});
test('partial solar coverage cannot masquerade as a full result and labels cannot inject markup',async()=>{
 const a=await boot();try{
  const p=await solarDraft(a);p.source_label='<img src=x onerror=alert(1)>';p.plant_mapping='<svg onload=alert(1)>';p.intervals=p.intervals.slice(0,1);await a.importRevision('revision-solar-file',JSON.stringify(p),'<img>.json');
  assert.match(a.$('revision-solar-status').textContent,/Partial profile: 1\.00 of 14\.00/);assert.match(a.$('revision-solar-table').textContent,/Solar useUnknownUnknown/);assert.match(a.$('revision-solar-source').textContent,/<img/);assert.equal(a.w.document.querySelectorAll('#revision-solar img,#revision-solar svg,#revision-solar script').length,0);
  input(a,'revision-note','Partial profile only.');submit(a);const r=JSON.parse(await a.downloads.at(-1).text());assert.equal(r.solar_comparison.totals,null);assert.equal(r.solar_comparison.coverage.unknown_hours,13);
  p.intervals=[];await a.importRevision('revision-solar-file',JSON.stringify(p),'empty.json');assert.match(a.$('revision-solar-table').textContent,/Solar useUnknownUnknown0\.00 to \+340\.00 kWh/);assert.match(a.$('revision-solar-status').textContent,/0\.00 of 14\.00/);
 }finally{a.close();}
});
test('solar removal, invalid replacement and assumption changes clear evidence and decisions',async()=>{
 const a=await boot();try{
  const p=await solarDraft(a);await a.importRevision('revision-solar-file',JSON.stringify(p),'valid.json');input(a,'revision-note','Old solar decision');input(a,'revision-decision','Ready for next simulation');a.$('revision-solar-remove').click();
  assert.equal(a.$('revision-solar-table').textContent,'');assert.equal(a.$('revision-note').value,'');assert.equal(a.$('revision-decision').value,'Needs team review');assert.match(a.$('revision-solar-status').textContent,/Solar use unknown/);
  input(a,'revision-note','No solar evidence.');submit(a);assert.equal(Object.hasOwn(JSON.parse(await a.downloads.at(-1).text()),'solar_file'),false);
  await a.importRevision('revision-solar-file',JSON.stringify(p),'valid.json');const bad={...p,interval_semantics:'average_power'};await a.importRevision('revision-solar-file',JSON.stringify(bad),'wrong.json');assert.equal(a.$('revision-solar-table').textContent,'');assert.match(a.$('revision-solar-status').textContent,/constant within/);
  await a.importRevision('revision-solar-file',JSON.stringify(p),'valid.json');input(a,'revision-sec','4');assert.equal(a.$('revision-result').hidden,true);assert.equal(a.$('revision-solar-table').textContent,'');
 }finally{a.close();}
});
test('pending solar cannot revive after removal, newer import or case invalidation',async()=>{
 const a=await boot();try{
  const p=await solarDraft(a),raw=JSON.stringify(p);let release;
  const slow=()=>{Object.defineProperty(a.$('revision-solar-file'),'files',{value:[{name:'slow.json',size:raw.length,arrayBuffer:()=>new Promise(r=>release=r)}],configurable:true});return a.$('revision-solar-file').onchange();};
  let pending=slow();assert.equal(a.$('revision-review-export').disabled,true);a.$('revision-solar-remove').click();release(new TextEncoder().encode(raw).buffer);await pending;assert.equal(a.$('revision-solar-table').textContent,'');assert.equal(a.$('revision-review-export').disabled,false);
  pending=slow();const zero=structuredClone(p);zero.source_label='New zero allocation';zero.intervals.forEach(r=>r.power_kw=0);await a.importRevision('revision-solar-file',JSON.stringify(zero),'new.json');release(new TextEncoder().encode(raw).buffer);await pending;assert.match(a.$('revision-solar-source').textContent,/New zero allocation/);assert.doesNotMatch(a.$('revision-solar-source').textContent,/slow.json/);
  pending=slow();input(a,'revision-sec','4');release(new TextEncoder().encode(raw).buffer);await pending;assert.equal(a.$('revision-result').hidden,true);assert.equal(a.$('revision-solar-table').textContent,'');assert.equal(a.$('revision-review-export').disabled,true);
 }finally{a.close();}
});
test('energy template, joint ranges, exact-file export and reopened recomputation complete the review task',async()=>{
 const a=await boot();try{
  await solarDraft(a);a.$('revision-solar-format').value='interval_energy';a.$('revision-solar-template').click();
  const p=JSON.parse(await a.downloads.at(-1).text());assert.equal(p.interval_semantics,'interval_energy');assert.equal(p.intervals[0].power_cap_kw,null);
  Object.assign(p,{source_kind:'illustrative_scenario',source_label:'Energy intervals for review',plant_mapping:'One unit'});p.intervals.forEach(r=>{r.energy_kwh=1000;r.power_cap_kw=1000;});
  const raw=JSON.stringify(p);await a.importRevision('revision-solar-file',raw,'energy-profile.json');assert.match(a.$('revision-solar-table').textContent,/Possible energy range/);assert.match(a.$('revision-solar-table').textContent,/\+340\.00 kWh/);assert.match(a.$('revision-solar-timing').textContent,/every timing pattern/);
  input(a,'revision-note','Conditional ranges, water outcomes retained.');submit(a);const review=JSON.parse(await a.downloads.at(-1).text());assert.equal(review.solar_file.text,raw);assert.equal(review.solar_comparison.totals,null);assert.equal(review.solar_comparison.bounds.delta_solar_kwh.lower,340);
  review.solar_comparison.bounds.delta_solar_kwh.lower=999999;await a.importRevision('revision-case-file',JSON.stringify(review),'energy-review.json');assert.doesNotMatch(a.$('revision-solar-table').textContent,/999/);assert.match(a.$('revision-solar-table').textContent,/\+340\.00 kWh/);assert.equal(a.$('revision-solar-format').value,'interval_energy');
  p.intervals=p.intervals.slice(0,1);await a.importRevision('revision-solar-file',JSON.stringify(p),'partial-energy.json');assert.match(a.$('revision-solar-status').textContent,/absolute totals unknown/);assert.match(a.$('revision-solar-timing').textContent,/More solar use for every timing pattern/);
  a.$('revision-solar-remove').click();assert.equal(a.$('revision-solar-timing').hidden,true);assert.equal(a.$('revision-note').value,'');
 }finally{a.close();}
});
test('cancellation dust cannot create a categorical solar superiority claim',async()=>{
 const a=await boot();try{
  const {raw}=await currentCase(a),c=JSON.parse(raw);c.specific_energy_kwh_m3=1;c.assessment.inputs.production=Array(24).fill(0);c.assessment.inputs.production[10]=.1;c.assessment.inputs.production[11]=.2;
  await a.importRevision('revision-case-file',JSON.stringify(c),'fractional-case.json');a.$('revision-template').click();const rows=a.w.Papa.parse(await a.downloads.at(-1).text(),{skipEmptyLines:true}).data;rows[1][2]='.3';rows[2][2]='0';
  await a.importRevision('revision-proposal-file',a.w.Papa.unparse(rows),'fractional-return.csv');a.$('revision-solar-format').value='interval_energy';a.$('revision-solar-template').click();const p=JSON.parse(await a.downloads.at(-1).text());Object.assign(p,{source_label:'Roundoff example',plant_mapping:'Illustrative unit'});p.intervals.forEach(r=>{r.energy_kwh=1;r.power_cap_kw=1;});
  await a.importRevision('revision-solar-file',JSON.stringify(p),'roundoff-energy.json');assert.match(a.$('revision-solar-timing').textContent,/No solar-use change at calculation precision/);assert.doesNotMatch(a.$('revision-solar-timing').textContent,/Less solar use for every/);
 }finally{a.close();}
});

test('maximum interval profile exports and reopens above the raw-source size limit',async()=>{
 const a=await boot();try{
  const p=await solarDraft(a),start=Date.parse(p.intervals[0].start),seconds=(Date.parse(p.intervals.at(-1).end)-start)/1000;
  p.interval_semantics='interval_energy';p.intervals=Array.from({length:4096},(_,i)=>({start:new Date(start+Math.floor(seconds*i/4096)*1000).toISOString(),end:new Date(start+Math.floor(seconds*(i+1)/4096)*1000).toISOString(),available_at:p.review_as_of,energy_kwh:1,power_cap_kw:1000}));
  const raw=JSON.stringify(p);assert.ok(Buffer.byteLength(raw)<2*1024*1024);await a.importRevision('revision-solar-file',raw,'dense-energy.json');assert.match(a.$('revision-solar-status').textContent,/Complete profile/);
  input(a,'revision-note','4096 declared intervals; conditional review.');submit(a);const exported=await a.downloads.at(-1).text();assert.ok(Buffer.byteLength(exported)>2*1024*1024);assert.ok(Buffer.byteLength(exported)<32*1024*1024);
  const r=JSON.parse(exported);assert.equal(r.solar_file.text,raw);assert.equal(r.solar_comparison.rows.length,4096);assert.equal(r.solar_comparison.difference_envelope.contributions,undefined);a.$('revision-evidence-export').click();const request=JSON.parse(await a.downloads.at(-1).text());assert.equal(request.difference_envelope.contributions.length,4096);assert.ok(Buffer.byteLength(JSON.stringify(request))<32*1024*1024);const bounds=JSON.stringify(r.solar_comparison.bounds);
  r.solar_comparison.bounds.delta_solar_kwh.lower=999999;await a.importRevision('revision-case-file',JSON.stringify(r),'dense-review.json');assert.match(a.$('revision-review-status').textContent,/recalculated/);submit(a);const reopened=JSON.parse(await a.downloads.at(-1).text());assert.equal(JSON.stringify(reopened.solar_comparison.bounds),bounds);assert.equal(reopened.solar_file.text,raw);
 }finally{a.close();}
});
test('larger review allowance preserves raw and embedded UTF-8 source limits',async()=>{
 const a=await boot();try{
  const p=await solarDraft(a);await a.importRevision('revision-solar-file',JSON.stringify(p),'solar.json');input(a,'revision-note','Size checks.');submit(a);const review=JSON.parse(await a.downloads.at(-1).text());
  const padded=review.case_file.text+' '.repeat(2*1024*1024);await a.importRevision('revision-case-file',padded,'large-raw-case.json');assert.equal(a.$('revision-result').hidden,true);assert.match(a.$('revision-case-status').textContent,/raw case or assessment.*2 MiB/);
  review.solar_file.text+='\u2003'.repeat(700000);assert.ok(review.solar_file.text.length<2*1024*1024);assert.ok(Buffer.byteLength(review.solar_file.text)>2*1024*1024);review.solar_file.sha256=createHash('sha256').update(review.solar_file.text).digest('hex');await a.importRevision('revision-case-file',JSON.stringify(review),'oversized-source-review.json');assert.equal(a.$('revision-result').hidden,true);assert.match(a.$('revision-case-status').textContent,/retained source file.*2 MiB/);
  Object.defineProperty(a.$('revision-case-file'),'files',{value:[{name:'oversized-review.json',size:32*1024*1024+1,arrayBuffer:async()=>{throw Error('must not read');}}],configurable:true});await a.$('revision-case-file').onchange();assert.match(a.$('revision-case-status').textContent,/32 MiB/);
 }finally{a.close();}
});


function visibleReviewControls(root){
 return [...root.querySelectorAll('button,input,select,textarea,summary')].filter(el=>{
  if(el.closest('[hidden]'))return false;
  for(let parent=el.parentElement;parent&&parent!==root;parent=parent.parentElement)
   if(parent.tagName==='DETAILS'&&!parent.open&&!parent.querySelector(':scope > summary')?.contains(el))return false;
  return true;
 });
}
test('simplified review defaults to one result surface and on-demand decisions',async()=>{
 const a=await boot();try{
  a.route('reviews');const current=a.w.document.querySelector('.current-review-workbench');
  assert.equal(current.querySelectorAll('aside').length,1);assert.equal(current.querySelector('aside').getAttribute('aria-label'),'Selected inventory boundary');assert.equal(current.querySelector('aside').querySelector('input,button,textarea'),null);assert.equal(a.$('review-decision-editor').open,false);
  assert.equal(a.$('review-actions').parentElement,a.w.document.querySelector('.workspace-header-tools'));assert.deepEqual([...a.$('review-actions').querySelectorAll('[data-review-tool]')].map(button=>button.dataset.reviewTool),['evidence','decision','history']);
  assert.equal(current.querySelectorAll('.chart').length,2);assert.equal(visibleReviewControls(current).includes(a.$('review-note')),false);assert.equal(visibleReviewControls(current).includes(a.$('execution-file')),false);assert.match(a.$('review-evidence-summary').textContent,/Conditions untested \/ No observations/);
  openDecision(a,'review-decision-editor');assert.equal(a.$('review-decision-editor').open,true);
  a.$('review-note').value='One clear next step.';a.$('download-current-review').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).note,'One clear next step.');
  a.$('review-tab-revision').click();assert.equal(a.$('revision-inputs').open,true);assert.equal(a.$('revision-inputs-summary').hidden,false);
  assert.deepEqual(visibleReviewControls(a.w.document.querySelector('.revision-workbench')).map(el=>el.id),['revision-inputs-summary','revision-case-file','revision-example','revision-test-plan']);
  const {template}=await currentCase(a);await a.importRevision('revision-proposal-file',proposalText(a,template),'returned.csv');
  const returned=a.w.document.querySelector('.revision-workbench');assert.equal(returned.querySelector('aside'),null);
  assert.equal(a.$('revision-inputs').open,false);assert.equal(a.$('revision-decision-panel').open,false);
  assert.equal(a.$('revision-decision-label').getAttribute('aria-live'),'polite');assert.equal(a.$('revision-decision-label').hasAttribute('role'),false);
  assert.equal(visibleReviewControls(returned).includes(a.$('revision-inspect-hour')),false);a.$('revision-inspect').open=true;assert.ok(visibleReviewControls(returned).includes(a.$('revision-inspect-hour')));assert.equal(visibleReviewControls(returned).includes(a.$('revision-note')),false);assert.equal(visibleReviewControls(returned).includes(a.$('revision-solar-file')),false);assert.match(a.$('revision-impact').getAttribute('aria-label'),/Modeled changes/);
  input(a,'revision-note','Ready to discuss the result.');submit(a);const raw=await a.downloads.at(-1).text();
  await a.importRevision('revision-case-file',raw,'reopened.json');assert.equal(a.$('revision-decision-panel').open,false);assert.equal(a.$('revision-note').value,'Ready to discuss the result.');
 }finally{a.close();}
});
test('expanded solar results keep profile tools closed and source kind visible',async()=>{
 const a=await boot();try{
  const p=await solarDraft(a);await a.importRevision('revision-solar-file',JSON.stringify(p),'profile.json');
  assert.equal(a.$('revision-solar').open,true);assert.equal(a.$('revision-solar-profile').open,false);
  assert.equal(a.$('revision-solar-template').closest('details').id,'revision-solar-profile');
  assert.equal(a.$('revision-solar-file').closest('details').id,'revision-solar-profile');
  assert.equal(a.$('revision-solar-source').closest('details').id,'revision-solar-profile');
  assert.match(a.$('revision-solar-status').textContent,/Illustrative scenario/);assert.match(a.$('revision-solar-timing').textContent,/More solar use for every timing pattern/);
  assert.equal(visibleReviewControls(a.w.document.querySelector('.revision-workbench')).includes(a.$('revision-solar-file')),false);assert.equal(visibleReviewControls(a.w.document.querySelector('.revision-workbench')).includes(a.$('revision-inspect-hour')),false);
  p.source_kind='reviewer_supplied';await a.importRevision('revision-solar-file',JSON.stringify(p),'declared.json');
  assert.equal(a.$('revision-solar-profile').open,false);assert.match(a.$('revision-solar-status').textContent,/Reviewer-supplied profile/);
  p.interval_semantics='invalid';await a.importRevision('revision-solar-file',JSON.stringify(p),'invalid.json');
  assert.equal(a.$('revision-solar-profile').open,true);assert.equal(a.$('revision-solar').open,true);
  assert.equal(a.$('revision-solar-table').textContent,'');assert.equal(a.$('revision-note').value,'');
 }finally{a.close();}
});


test('closed decisions still disclose invalidation and solar import restores visible focus',async()=>{
 const a=await boot();try{
  const p=await solarDraft(a);await a.importRevision('revision-solar-file',JSON.stringify(p),'solar.json');
  input(a,'revision-note','Checked this profile.');submit(a);const saved=await a.downloads.at(-1).text();
  await a.importRevision('revision-case-file',saved,'review.json');assert.equal(a.$('revision-decision-panel').open,false);
  p.intervals[0].power_kw=900;await a.importRevision('revision-solar-file',JSON.stringify(p),'changed.json');
  assert.equal(a.$('revision-decision-panel').open,false);assert.equal(a.$('revision-note').value,'');
  assert.match(a.$('revision-decision-label').textContent,/Record new decision \(solar profile changed\)/);
  assert.equal(a.w.document.activeElement,a.$('revision-solar-profile').querySelector('summary'));
  input(a,'revision-note','Checked the changed profile.');submit(a);assert.equal(a.$('revision-decision-label').textContent,'Record decision');
  a.$('revision-decision-panel').open=false;a.$('revision-solar-profile').open=true;a.$('revision-solar-remove').click();
  assert.equal(a.$('revision-decision-panel').open,false);assert.match(a.$('revision-decision-label').textContent,/Record new decision/);
  assert.equal(a.$('revision-note').value,'');assert.equal(a.$('revision-solar-table').textContent,'');
 }finally{a.close();}
});
test('unreadable saved state remains visible without opening the decision form',async()=>{
 const a=await boot({'aquashift.review.v1':'invalid json'});try{
  a.route('reviews');assert.equal(a.$('review-decision-editor').open,false);
  assert.equal(a.$('review-storage-status').hidden,false);assert.match(a.$('review-storage-status').textContent,/Saved state could not be read/);
  assert.equal(a.$('review-storage-status').closest('details'),null);
 }finally{a.close();}
});

async function sequenceReview(a,through='2026-07-07'){
 a.route('resilience');a.$('assessment-tab-sequence').click();input(a,'sequence-through',through);await a.$('sequence-form').onsubmit({preventDefault(){}});
 assert.equal(a.$('sequence-result').hidden,false,a.$('sequence-error').textContent);a.$('sequence-export').click();return JSON.parse(await a.downloads.at(-1).text());
}
async function sequenceFile(a,raw,name='sequence.json'){
 Object.defineProperty(a.$('sequence-file'),'files',{value:[{name,size:Buffer.byteLength(raw),arrayBuffer:async()=>new TextEncoder().encode(raw).buffer}],configurable:true});await a.$('sequence-file').onchange();
}
test('continuous review carries seven days and exposes the first service failure without adding panels',async()=>{
 const a=await boot();try{
  const r=await sequenceReview(a);assert.equal(a.w.document.querySelector('.context').hidden,true);assert.equal(a.$('sequence-inputs').open,false);assert.equal(a.$('sequence-decision').open,false);assert.equal(a.w.document.querySelectorAll('#assessment-sequence .chart').length,1);assert.equal(a.$('sequence-day').value,'3');
  assert.equal(r.results.selected.blocks.length,7);assert.equal(r.results.selected.rows.length,168);assert.equal(r.results.selected.totals.initial_storage_m3,2000);assert.ok(r.results.selected.totals.unmet_m3>0);assert.equal(r.results.selected.events.find(e=>e.type==='stockout').time,'2026-07-04T05:36:21.818Z');assert.equal(r.results.control.events.find(e=>e.type==='stockout').time,'2026-07-07T19:40:00.000Z');
  for(let i=1;i<7;i++)assert.equal(r.results.selected.blocks[i].initial_storage_m3,r.results.selected.blocks[i-1].totals.final_storage_m3);
  assert.match(a.$('sequence-failure').textContent,/04 Jul 2026, 08:36:21 GMT\+3/);assert.match(a.$('sequence-failure').textContent,/07 Jul 2026, 22:40:00 GMT\+3/);assert.equal(r.reference_files.data.text,read('data.json'));assert.equal(r.reference_files.manifest.text,read('manifest.json'));assert.equal(createHash('sha256').update(r.source_file.text).digest('hex'),r.source_file.sha256);
  a.$('assessment-tab-sequence').dispatchEvent(new a.w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));assert.equal(a.$('assessment-tab-conditions').getAttribute('aria-selected'),'true');assert.equal(a.w.document.querySelector('.context').hidden,false);a.$('assessment-tab-conditions').dispatchEvent(new a.w.KeyboardEvent('keydown',{key:'End',bubbles:true}));assert.equal(a.$('assessment-tab-sequence').getAttribute('aria-selected'),'true');
 }finally{a.close();}
});
test('continuous 92-day review reopens from exact sources, recalculates forged outcomes and clears old decisions',async()=>{
 const a=await boot();try{
  const r=await sequenceReview(a,'2026-09-30');assert.equal(r.results.selected.rows.length,2208);assert.equal(r.results.selected.blocks.length,92);assert.equal(r.results.selected.totals.unmet_m3,25540);assert.equal(r.results.control.totals.unmet_m3,24496);assert.equal(r.results.selected.totals.final_storage_m3,1044);
  input(a,'sequence-reason','Persistent demand exposes the daily reset assumption.');a.$('sequence-decision-value').value='Request revised sequence';a.$('sequence-export').click();const saved=JSON.parse(await a.downloads.at(-1).text());saved.results.selected.totals.unmet_m3=0;saved.results.selected.blocks[3].initial_storage_m3=99999;
  await sequenceFile(a,JSON.stringify(saved),'saved-review.json');assert.equal(a.$('sequence-result').hidden,false,a.$('sequence-error').textContent);assert.match(a.$('sequence-status').textContent,/recalculated/);assert.equal(a.$('sequence-reason').value,'');assert.equal(a.$('sequence-decision-value').value,'Needs team review');a.$('sequence-export').click();const opened=JSON.parse(await a.downloads.at(-1).text());assert.equal(opened.results.selected.totals.unmet_m3,25540);assert.equal(opened.results.selected.blocks[3].initial_storage_m3,1136);assert.equal(opened.source_file.text,r.source_file.text);assert.equal(opened.reference_files.data.text,r.reference_files.data.text);
 }finally{a.close();}
});
test('continuous failing day enters returned-plan review with unchanged production and exact carried conditions',async()=>{
 const a=await boot();try{
  const r=await sequenceReview(a);const keptRaw=await a.downloads.at(-1).text();await a.$('sequence-review-day').onclick();assert.equal(a.$('view-reviews').hidden,false,a.$('sequence-error').textContent);assert.equal(a.$('review-revision').hidden,false);a.$('revision-case-export').click();const raw=await a.downloads.at(-1).text(),c=JSON.parse(raw),block=r.results.selected.blocks[3];
  assert.equal(c.assessment.inputs.initial,1136);assert.equal(c.assessment.inputs.scenario.initial_storage_m3,1136);assert.equal(c.assessment.inputs.scenario.demand_multiplier,1.1);assert.deepEqual(c.assessment.inputs.production,fixture.days[3].schedules['4000'].production);assert.deepEqual(c.assessment.inputs.times,block.inputs.times);assert.equal(c.assessment.identity.sequence_block,3);assert.equal(c.assessment.identity.continuous_review_sha256,createHash('sha256').update(keptRaw).digest('hex'));assert.equal(c.assessment.observation,null);
  a.$('revision-template').click();const template=await a.downloads.at(-1).text();await a.importRevision('revision-proposal-file',template,'unchanged-return.csv');assert.equal(a.$('revision-result').hidden,false,a.$('revision-proposal-status').textContent);input(a,'revision-note','Unchanged return reproduces the carried service deficit.');submit(a);const review=JSON.parse(await a.downloads.at(-1).text());assert.equal(review.comparison.original.result.totals.unmet_m3,block.totals.unmet_m3);assert.equal(review.comparison.revised.result.totals.unmet_m3,block.totals.unmet_m3);await a.importRevision('revision-case-file',JSON.stringify(review),'reopened.json');assert.equal(a.$('revision-result').hidden,false);assert.match(a.$('revision-review-status').textContent,/recalculated/);
 }finally{a.close();}
});
test('continuous supplied source preserves BOM and CRLF, keeps external day separate and recomputes its prefix on reopen',async()=>{
 const a=await boot();try{
  const retained=await sequenceReview(a),source=JSON.parse(retained.source_file.text);source.label='<img src=x onerror=alert(1)>';source.inputs.scenario.demand_multiplier=1.1;const raw='\uFEFF'+JSON.stringify(source,null,2).replaceAll('\n','\r\n');await sequenceFile(a,raw,'outside.json');assert.equal(a.$('sequence-result').hidden,false,a.$('sequence-error').textContent);assert.equal(a.$('sequence-review-day').disabled,true);assert.equal(a.w.document.querySelectorAll('#assessment-sequence img').length,0);assert.equal(a.$('sequence-import-label').textContent.includes('<img'),true);assert.equal(a.$('sequence-inputs').open,false);
  a.$('sequence-export-day').click();const day=JSON.parse(await a.downloads.at(-1).text());assert.equal(day.block_index,3);assert.equal(day.day.inputs.initial,1136);assert.equal(day.review.source_file.text,raw);assert.equal(day.review.source_file.sha256,createHash('sha256').update(raw).digest('hex'));day.review.results.selected.blocks[3].initial_storage_m3=99999;day.day.totals.unmet_m3=99999;await sequenceFile(a,JSON.stringify(day),'day-case.json');assert.equal(a.$('sequence-day').value,'3');a.$('sequence-export-day').click();const opened=JSON.parse(await a.downloads.at(-1).text());assert.equal(opened.day.inputs.initial,1136);assert.equal(opened.day.carried_from,1136);assert.equal(opened.review.source_file.text,raw);assert.notEqual(opened.day.totals.unmet_m3,99999);day.day.inputs.initial=99999;await sequenceFile(a,JSON.stringify(day),'altered-day.json');assert.equal(a.$('sequence-result').hidden,true);assert.match(a.$('sequence-error').textContent,/Day inputs disagree/);
 }finally{a.close();}
});
test('continuous errors reveal controls and clear old results for gaps, tampered bytes, mismatched proof and conditions',async()=>{
 const a=await boot();try{
  const r=await sequenceReview(a),source=JSON.parse(r.source_file.text),badGap=structuredClone(source);badGap.inputs.blocks.splice(2,1);
  const badHash=structuredClone(r);badHash.source_file.text+='\n';const badProof=structuredClone(r);const changedSource=JSON.parse(badProof.source_file.text);changedSource.inputs.blocks[0].production[0]=1;badProof.source_file.text=JSON.stringify(changedSource);badProof.source_file.sha256=createHash('sha256').update(badProof.source_file.text).digest('hex');const badConditions=structuredClone(r);delete badConditions.conditions.demand_multiplier;
  for(const [value,pattern]of [[badGap,/consecutive/],[badHash,/hash does not match/],[badProof,/differs from its retained reference/],[badConditions,/complete finite conditions/]]){await sequenceFile(a,JSON.stringify(value));assert.equal(a.$('sequence-result').hidden,true);assert.equal(a.$('sequence-export').disabled,true);assert.equal(a.$('sequence-inputs').open,true);assert.match(a.$('sequence-error').textContent,pattern);assert.equal(a.w.document.activeElement.id,'sequence-file');}
  await sequenceFile(a,JSON.stringify(r));assert.equal(a.$('sequence-result').hidden,false);input(a,'sequence-demand','20');assert.equal(a.$('sequence-result').hidden,true);assert.equal(a.$('sequence-export').disabled,true);input(a,'sequence-demand','10');assert.equal(a.$('sequence-result').hidden,true);await a.$('sequence-form').onsubmit({preventDefault(){}});assert.equal(a.$('sequence-result').hidden,false);
 }finally{a.close();}
});
test('continuous pending older file cannot overwrite a newer accepted sequence or revive results after input changes',async()=>{
 const a=await boot();try{
  const r=await sequenceReview(a),old=JSON.stringify(r);let release;Object.defineProperty(a.$('sequence-file'),'files',{value:[{name:'slow.json',size:old.length,arrayBuffer:()=>new Promise(resolve=>release=resolve)}],configurable:true});const pending=a.$('sequence-file').onchange();const source=JSON.parse(r.source_file.text);source.label='Newer external sequence';await sequenceFile(a,JSON.stringify(source),'newer.json');release(new TextEncoder().encode(old).buffer);await pending;assert.match(a.$('sequence-status').textContent,/Newer external sequence/);a.$('sequence-export').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).source_file.name,'newer.json');
  Object.defineProperty(a.$('sequence-file'),'files',{value:[{name:'slow.json',size:old.length,arrayBuffer:()=>new Promise(resolve=>release=resolve)}],configurable:true});const pendingAgain=a.$('sequence-file').onchange();input(a,'sequence-demand','20');release(new TextEncoder().encode(old).buffer);await pendingAgain;assert.equal(a.$('sequence-result').hidden,true);assert.equal(a.$('sequence-export').disabled,true);
 }finally{a.close();}
});
test('continuous repeated interruption and imported cross-midnight interruption remain identical in both plans and day cases',async()=>{
 const a=await boot();try{
  await sequenceReview(a);input(a,'sequence-outage-start','12');input(a,'sequence-outage-duration','2');await a.$('sequence-form').onsubmit({preventDefault(){}});a.$('sequence-export').click();const r=JSON.parse(await a.downloads.at(-1).text());assert.equal(r.conditions.outages.length,7);assert.deepEqual(r.results.selected.outages,r.results.control.outages);for(const block of r.results.selected.blocks)assert.deepEqual(block.scenario.outage,{start_hour:12,duration_hours:2});
  const source=JSON.parse(r.source_file.text);source.inputs.outages=[{start:'2026-07-01T23:30:00+03:00',end:'2026-07-02T00:30:00+03:00'}];await sequenceFile(a,JSON.stringify(source));a.$('sequence-day').value='1';a.$('sequence-day').onchange();a.$('sequence-export-day').click();const day=JSON.parse(await a.downloads.at(-1).text());assert.deepEqual(day.day.inputs.scenario.outage,{start_hour:0,duration_hours:.5});assert.equal(day.day.inputs.initial,day.review.results.selected.blocks[0].totals.final_storage_m3);assert.equal(a.$('sequence-recurring-outage').hidden,true);
 }finally{a.close();}
});
test('continuous missing next-step note focuses decision controls and retains the valid result',async()=>{
 const a=await boot();try{await sequenceReview(a);const status=a.$('sequence-status').textContent;a.$('sequence-decision-value').value='Request revised sequence';a.$('sequence-export').click();assert.equal(a.$('sequence-result').hidden,false);assert.equal(a.$('sequence-inputs').open,false);assert.equal(a.$('sequence-status').textContent,status);assert.equal(a.$('sequence-decision').open,true);assert.equal(a.w.document.activeElement.id,'sequence-reason');assert.match(a.$('sequence-error').textContent,/review reason/);a.$('sequence-reason').value='Ask for revised fixed plans.';a.$('sequence-reviewer').value='';a.$('sequence-export').click();assert.equal(a.w.document.activeElement.id,'sequence-reviewer');assert.match(a.$('sequence-accounting').textContent,/Production m³/);assert.match(a.$('sequence-accounting').textContent,/Spill m³/);}finally{a.close();}
});
test('continuous canonical cross-midnight day handoff retains its exact prefix, clipped outage and source hash',async()=>{
 const a=await boot();try{const r=await sequenceReview(a);r.conditions.outages=[{start:'2026-07-01T23:30:00+03:00',end:'2026-07-02T00:30:00+03:00'}];r.selected_block=1;await sequenceFile(a,JSON.stringify(r));assert.equal(a.$('sequence-result').hidden,false,a.$('sequence-error').textContent);assert.match(a.$('sequence-condition-summary').textContent,/1 interruption/);a.$('sequence-export').click();const recomputed=JSON.parse(await a.downloads.at(-1).text());await a.$('sequence-review-day').onclick();a.$('revision-case-export').click();const c=JSON.parse(await a.downloads.at(-1).text());assert.equal(c.assessment.identity.sequence_sha256,r.source_file.sha256);assert.equal(c.assessment.inputs.initial,recomputed.results.selected.blocks[0].totals.final_storage_m3);assert.deepEqual(c.assessment.inputs.scenario.outage,{start_hour:0,duration_hours:.5});}finally{a.close();}
});
test('continuous import limits count actual UTF-8 bytes and reject invalid encoding and incomplete envelopes',async()=>{
 const a=await boot();try{const r=await sequenceReview(a);for(const file of [{name:'invalid.json',size:1,arrayBuffer:async()=>new Uint8Array([255]).buffer},{name:'oversize.json',size:0,arrayBuffer:async()=>new Uint8Array(32*1024*1024+1).buffer}]){Object.defineProperty(a.$('sequence-file'),'files',{value:[file],configurable:true});await a.$('sequence-file').onchange();assert.equal(a.$('sequence-result').hidden,true);assert.match(a.$('sequence-error').textContent,/encoded data|exceeds 32 MiB/);assert.equal(a.w.document.activeElement.id,'sequence-file');}const bad={...r,ignore_gap:true};await sequenceFile(a,JSON.stringify(bad));assert.match(a.$('sequence-error').textContent,/Unsupported continuous review field/);await sequenceFile(a,JSON.stringify({schema:1,kind:'continuous_plan_day_case',review:r,block_index:3}));assert.match(a.$('sequence-error').textContent,/day payload must be an object/);const invalidSource={...JSON.parse(r.source_file.text),future_optimizer:{}};await sequenceFile(a,JSON.stringify(invalidSource));assert.match(a.$('sequence-error').textContent,/Unsupported sequence source field/);}finally{a.close();}
});
test('continuous maximum supported sequence and 4 MiB raw source round-trip within the review limit',async()=>{
 const a=await boot();try{const r=await sequenceReview(a),source=JSON.parse(r.source_file.text),start=Date.parse('2026-01-01T00:00:00Z');source.label='Full-year supplied control';source.inputs.scenario={demand_multiplier:1,production_multiplier:1};source.inputs.blocks=Array.from({length:366},(_,day)=>({times:Array.from({length:24},(_,hour)=>new Date(start+(day*24+hour)*3600000).toISOString()),production:Array(24).fill(120),demand:120}));const json=JSON.stringify(source),raw=json+'\n'.repeat(4*1024*1024-Buffer.byteLength(json));assert.equal(Buffer.byteLength(raw),4*1024*1024);await sequenceFile(a,raw,'large-source.json');assert.equal(a.$('sequence-result').hidden,false,a.$('sequence-error').textContent);a.$('sequence-export').click();const saved=await a.downloads.at(-1).text();assert.ok(Buffer.byteLength(saved)<32*1024*1024);await sequenceFile(a,saved,'full-review.json');assert.equal(a.$('sequence-result').hidden,false,a.$('sequence-error').textContent);a.$('sequence-export').click();const opened=JSON.parse(await a.downloads.at(-1).text());assert.equal(opened.source_file.text,raw);assert.equal(opened.results.selected.blocks.length,366);assert.equal(opened.results.selected.totals.final_storage_m3,2000);assert.match(a.$('sequence-chart-note').textContent,/2026/);assert.match(a.$('sequence-chart-note').textContent,/2027/);assert.equal(a.w.document.querySelectorAll('#sequence-chart svg text').length,8);assert.ok(a.$('sequence-chart').querySelector('.micro').textContent.length>0);}finally{a.close();}
});
test('continuous small real deficits remain visible without a false served-demand conclusion',async()=>{
 const a=await boot();try{const r=await sequenceReview(a),source=JSON.parse(r.source_file.text);source.inputs.blocks=source.inputs.blocks.slice(0,1);source.inputs.initial=0;source.inputs.reserve=0;source.inputs.target=0;source.inputs.blocks[0].production=Array(24).fill(0);source.inputs.blocks[0].demand=1e-10;source.control_rate_m3_h=0;await sequenceFile(a,JSON.stringify(source));assert.equal(a.$('sequence-result').hidden,false,a.$('sequence-error').textContent);assert.match(a.$('sequence-conclusion').textContent,/Unserved demand/);assert.doesNotMatch(a.$('sequence-conclusion').textContent,/Demand is served/);assert.match(a.$('sequence-outcomes').textContent,/0\.0000000024/);assert.match(a.$('sequence-failure').textContent,/small deficit retained/);}finally{a.close();}
});
test('continuous imported exact multipliers survive unedited percentage controls and explicit edits replace them',async()=>{
 const a=await boot();try{const r=await sequenceReview(a),source=JSON.parse(r.source_file.text);source.inputs.blocks=source.inputs.blocks.slice(0,1);source.inputs.scenario.production_multiplier=1e-20;await sequenceFile(a,JSON.stringify(source));assert.equal(a.$('sequence-loss').value,'100');await a.$('sequence-form').onsubmit({preventDefault(){}});a.$('sequence-export').click();let saved=JSON.parse(await a.downloads.at(-1).text());assert.equal(saved.conditions.production_multiplier,1e-20);assert.ok(saved.results.selected.totals.available_production_m3>0);input(a,'sequence-loss','100');await a.$('sequence-form').onsubmit({preventDefault(){}});a.$('sequence-export').click();saved=JSON.parse(await a.downloads.at(-1).text());assert.equal(saved.conditions.production_multiplier,0);assert.equal(saved.results.selected.totals.available_production_m3,0);source.inputs.capacity=500;source.inputs.reserve=100;source.inputs.initial=250;source.inputs.target=250;await sequenceFile(a,JSON.stringify(source));a.$('sequence-use-reference').click();assert.equal(a.$('sequence-initial').max,'4000');assert.equal(a.$('sequence-initial').value,'2000');}finally{a.close();}
});

function joinedSource(blocks=2){const start=Date.parse('2026-07-01T00:00:00Z');return {schema:1,kind:'fixed_plan_sequence_source',label:'Illustrative supplied plans',control_rate_m3_h:1,specific_energy_kwh_m3:1,inputs:{blocks:Array.from({length:blocks},(_,day)=>({times:Array.from({length:24},(_,hour)=>new Date(start+(day*24+hour)*3600000).toISOString()),production:Array(24).fill(1),demand:1})),capacity:100,reserve:0,initial:10,target:10,unitCapacity:4,scenario:{demand_multiplier:1,production_multiplier:1},outages:[]}};}
async function joinedFile(a,id,raw,name){Object.defineProperty(a.$(id),'files',{value:[{name,size:Buffer.byteLength(raw),arrayBuffer:async()=>new TextEncoder().encode(raw).buffer}],configurable:true});await a.$(id).onchange();}
async function joinedCase(a,source=joinedSource(),block=0,raw){a.route('resilience');a.$('assessment-tab-sequence').click();await sequenceFile(a,raw??JSON.stringify(source),'supplied-source.json');assert.equal(a.$('sequence-result').hidden,false,a.$('sequence-error').textContent);a.$('sequence-day').value=String(block);a.$('sequence-day').onchange();await a.$('sequence-freeze').onclick();assert.equal(a.$('sequence-case-export').disabled,false,a.$('sequence-error').textContent);a.$('sequence-case-export').click();const caseText=await a.downloads.at(-1).text();a.$('sequence-return-template').click();const csvText=await a.downloads.at(-1).text();return {caseText,csvText};}
async function joinedReturn(a,csvText,edits={}){const rows=a.w.Papa.parse(csvText,{skipEmptyLines:'greedy'}).data;for(const [hour,rate]of Object.entries(edits))rows[Number(hour)+1][2]=String(rate);const raw=a.w.Papa.unparse(rows);await joinedFile(a,'sequence-return-file',raw,'supplied-return.csv');assert.match(a.$('sequence-revision-status').textContent,/Returned plan compared/,a.$('sequence-error').textContent);return raw;}
async function joinedExport(a){a.$('sequence-export').click();return JSON.parse(await a.downloads.at(-1).text());}
function joinedProfile(record,{energy=false,intervals}={}){const input=JSON.parse(JSON.parse(record.case_file.text).source_file.text).inputs,start=input.blocks[0].times[0],end=new Date(Date.parse(input.blocks.at(-1).times[23])+3600000).toISOString();return {schema:1,kind:'plant_solar_allocation',case_sha256:record.case_file.sha256,source_kind:'illustrative_scenario',source_label:'Explicit synthetic energy',plant_mapping:'Declared example unit',power_basis:'total_plant_eligible_solar',interval_semantics:energy?'interval_energy':'constant_power',review_as_of:end,intervals:intervals??[{start,end,available_at:start,...(energy?{energy_kwh:48,power_cap_kw:4}:{power_kw:1})}]};}

test('joined continuous return preserves exact source and suffix while comparing full-period carry in one chart',async()=>{
 const a=await boot();try{const source=joinedSource(3),raw='\uFEFF'+JSON.stringify(source,null,2).replaceAll('\n','\r\n'),c=await joinedCase(a,source,1,raw),frozen=JSON.parse(c.caseText),rows=a.w.Papa.parse(c.csvText,{skipEmptyLines:'greedy'}).data;
 assert.equal(frozen.kind,'continuous_plan_revision_case');assert.equal(frozen.source_file.text,raw);assert.equal(frozen.source_file.sha256,createHash('sha256').update(raw).digest('hex'));assert.equal(rows.length,49);assert.equal(rows[1][1],source.inputs.blocks[1].times[0]);assert.equal(rows[1][0],createHash('sha256').update(c.caseText).digest('hex'));assert.match(a.$('sequence-revision-horizon').textContent,/preceding 1 block stay unchanged/);
 const returned=await joinedReturn(a,c.csvText,{0:0}),r=await joinedExport(a);assert.equal(r.kind,'continuous_plan_revision_review');assert.equal(r.results.original.final_storage_m3,10);assert.equal(r.results.returned.final_storage_m3,9);assert.equal(r.results.changes.modeled_production_energy_kwh,-1);a.$('sequence-day').value='2';a.$('sequence-day').onchange();assert.match(a.$('sequence-day-status').textContent,/Original: 10 m³ carried in.*Returned: 9 m³ carried in/);assert.equal(r.proposal_file.text,returned);assert.equal(r.case_file.text,c.caseText);assert.equal(a.w.document.querySelectorAll('#assessment-sequence .chart').length,1);assert.equal(a.$('sequence-revision-files').open,false);assert.equal(a.$('sequence-decision').open,false);assert.equal(a.$('sequence-solar').hidden,false);assert.equal(a.$('sequence-chart').getAttribute('aria-label'),'Continuous tank inventory for original and returned plans');assert.equal(a.w.document.querySelector('#sequence-chart svg').getAttribute('aria-label'),'Continuous tank inventory for original and returned plans');assert.match(a.$('sequence-outcomes').textContent,/Whole period/);assert.match(a.$('sequence-outcomes').textContent,/Unknown/);assert.equal(a.$('sequence-solar').open,false);
 }finally{a.close();}
});

test('joined continuous midnight solar ambiguity survives exact-file reopening while forged outcomes and decisions are cleared',async()=>{
 const a=await boot();try{const c=await joinedCase(a),returned=await joinedReturn(a,c.csvText,{23:2,24:0}),r=await joinedExport(a),start='2026-07-01T00:00:00.000Z',split='2026-07-01T23:00:00.000Z',mid='2026-07-02T01:00:00.000Z',end='2026-07-03T00:00:00.000Z';const p=joinedProfile(r,{energy:true,intervals:[{start,end:split,available_at:start,energy_kwh:0,power_cap_kw:0},{start:split,end:mid,available_at:start,energy_kwh:2,power_cap_kw:2},{start:mid,end,available_at:start,energy_kwh:0,power_cap_kw:0}]});
 const raw='\uFEFF'+JSON.stringify(p,null,2).replaceAll('\n','\r\n');await joinedFile(a,'sequence-solar-file',raw,'midnight-solar.json');const solar=await joinedExport(a);assert.deepEqual(solar.results.solar.bounds.delta_solar_kwh,{lower:-1,upper:1});assert.equal(solar.results.changes.unmet_m3,0);assert.equal(solar.results.changes.final_storage_m3,0);assert.equal(solar.results.changes.modeled_production_energy_kwh,0);assert.match(a.$('sequence-outcomes').textContent,/-1 to \+1/);assert.match(a.$('sequence-solar-status').textContent,/Illustrative \/ 48 of 48 h known/);assert.match(a.$('sequence-solar-conclusion').textContent,/reverse the direction/);assert.equal(a.w.document.activeElement,a.$('sequence-solar-profile').querySelector('summary'));assert.equal(solar.solar_file.text,raw);
 input(a,'sequence-reason','Timing is unresolved.');a.$('sequence-decision-value').value='Request revised sequence';const saved=await joinedExport(a);saved.results.original.final_storage_m3=999999;saved.results.solar.bounds.delta_solar_kwh={lower:100,upper:100};await sequenceFile(a,JSON.stringify(saved),'joined-review.json');assert.equal(a.$('sequence-result').hidden,false,a.$('sequence-error').textContent);assert.equal(a.$('sequence-reason').value,'');assert.equal(a.$('sequence-decision-value').value,'Needs team review');const opened=await joinedExport(a);assert.equal(opened.case_file.text,c.caseText);assert.equal(opened.proposal_file.text,returned);assert.equal(opened.solar_file.text,raw);assert.equal(opened.results.original.final_storage_m3,10);assert.deepEqual(opened.results.solar.bounds.delta_solar_kwh,{lower:-1,upper:1});
 }finally{a.close();}
});

test('joined continuous solar gain retains service, production and inventory tradeoffs',async()=>{
 const a=await boot();try{const source=joinedSource();source.inputs.initial=0;source.inputs.target=0;let c=await joinedCase(a,source);await joinedReturn(a,c.csvText,{23:0,24:2});let r=await joinedExport(a);const p=joinedProfile(r,{intervals:[{start:'2026-07-01T00:00:00.000Z',end:'2026-07-02T00:00:00.000Z',available_at:'2026-07-01T00:00:00.000Z',power_kw:0},{start:'2026-07-02T00:00:00.000Z',end:'2026-07-02T01:00:00.000Z',available_at:'2026-07-01T00:00:00.000Z',power_kw:2},{start:'2026-07-02T01:00:00.000Z',end:'2026-07-03T00:00:00.000Z',available_at:'2026-07-01T00:00:00.000Z',power_kw:0}]});await joinedFile(a,'sequence-solar-file',JSON.stringify(p),'service-tradeoff.json');r=await joinedExport(a);assert.equal(r.results.solar.totals.delta_solar_kwh,1);assert.equal(r.results.changes.unmet_m3,1);assert.equal(r.results.changes.final_storage_m3,1);assert.match(a.$('sequence-conclusion').textContent,/stockout/);assert.match(a.$('sequence-solar-conclusion').textContent,/Water comparison fails on delivery/);assert.doesNotMatch(a.$('sequence-conclusion').textContent,/Demand is served/);
 c=await joinedCase(a);await joinedReturn(a,c.csvText,{23:2});r=await joinedExport(a);await joinedFile(a,'sequence-solar-file',JSON.stringify(joinedProfile(r)),'extra-production.json');assert.match(a.$('sequence-solar-conclusion').textContent,/Production also changes/);
 c=await joinedCase(a);await joinedReturn(a,c.csvText,{23:0});r=await joinedExport(a);await joinedFile(a,'sequence-solar-file',JSON.stringify(joinedProfile(r)),'less-production.json');assert.match(a.$('sequence-solar-conclusion').textContent,/final inventory is lower/);
 }finally{a.close();}
});

test('joined continuous partial, late and unknown-specific-energy profiles never imply whole-period electricity',async()=>{
 const a=await boot();try{const c=await joinedCase(a);await joinedReturn(a,c.csvText,{23:2,24:0});const r=await joinedExport(a),p=joinedProfile(r);p.intervals[0].end='2026-07-02T00:00:00.000Z';await joinedFile(a,'sequence-solar-file',JSON.stringify(p),'partial.json');let out=await joinedExport(a);assert.equal(out.results.solar.status,'partial');assert.equal(out.results.solar.totals,null);assert.match(a.$('sequence-solar-status').textContent,/24 of 48 h known \/ absolute totals unknown/);assert.match(a.$('sequence-outcomes').textContent,/Solar use \(kWh\)UnknownUnknown-1 to 0/);assert.match(a.$('sequence-solar-known').textContent,/Known intervals only/);p.intervals[0].available_at='2026-07-04T00:00:00Z';await joinedFile(a,'sequence-solar-file',JSON.stringify(p),'late.json');out=await joinedExport(a);assert.equal(out.results.solar.coverage.known_hours,0);assert.equal(out.results.solar.coverage.late_hours,24);assert.equal(a.$('sequence-solar-known').textContent,'');
 const source=joinedSource();source.specific_energy_kwh_m3=null;const unknown=await joinedCase(a,source);await joinedReturn(a,unknown.csvText);await joinedFile(a,'sequence-solar-file',JSON.stringify(joinedProfile(await joinedExport(a))),'unknown-energy.json');out=await joinedExport(a);assert.equal(out.results.changes.modeled_production_energy_kwh,null);assert.equal(out.results.solar.status,'unknown_energy');assert.match(a.$('sequence-outcomes').textContent,/Total electricity \(kWh\)UnknownUnknownUnknown/);assert.match(a.$('sequence-solar-status').textContent,/specific energy unknown/);
 }finally{a.close();}
});

test('joined continuous pending files and removed profiles cannot revive invalidated decisions or results',async()=>{
 const a=await boot();try{const c=await joinedCase(a);await joinedReturn(a,c.csvText);let r=await joinedExport(a);const p=JSON.stringify(joinedProfile(r));await joinedFile(a,'sequence-solar-file',p,'accepted.json');input(a,'sequence-reason','Checked both outcomes.');a.$('sequence-decision-value').value='Request revised sequence';let release;Object.defineProperty(a.$('sequence-solar-file'),'files',{value:[{name:'slow.json',size:p.length,arrayBuffer:()=>new Promise(resolve=>release=resolve)}],configurable:true});const pending=a.$('sequence-solar-file').onchange();assert.equal(a.$('sequence-export').disabled,true);assert.equal(a.$('sequence-reason').value,'');assert.match(a.$('sequence-decision-label').textContent,/solar profile changed/);a.$('sequence-solar-remove').click();release(new TextEncoder().encode(p).buffer);await pending;assert.equal(a.$('sequence-solar-status').textContent,'Unknown / no profile');r=await joinedExport(a);assert.equal(r.solar_file,undefined);
 Object.defineProperty(a.$('sequence-return-file'),'files',{value:[{name:'slow.csv',size:c.csvText.length,arrayBuffer:()=>new Promise(resolve=>release=resolve)}],configurable:true});const delayed=a.$('sequence-return-file').onchange();assert.equal(a.$('sequence-export').disabled,true);input(a,'sequence-demand','20');release(new TextEncoder().encode(c.csvText).buffer);await delayed;assert.equal(a.$('sequence-result').hidden,true);assert.equal(a.$('sequence-export').disabled,true);assert.equal(a.$('sequence-case-export').disabled,true);assert.equal(a.$('sequence-solar').hidden,true);
 }finally{a.close();}
});

test('joined continuous identity, case mismatch and envelope errors focus their visible controls',async()=>{
 const a=await boot();try{const c=await joinedCase(a);await joinedReturn(a,c.csvText);const r=await joinedExport(a),bad=structuredClone(r);bad.proposal_file.text+='\n';await sequenceFile(a,JSON.stringify(bad));assert.equal(a.$('sequence-result').hidden,true);assert.match(a.$('sequence-error').textContent,/hash does not match/);assert.equal(a.w.document.activeElement.id,'sequence-file');await sequenceFile(a,c.caseText,'external-case.json');assert.equal(a.$('sequence-return-file').disabled,false);assert.equal(a.$('sequence-review-day').disabled,true);await joinedFile(a,'sequence-return-file',c.csvText.replaceAll(r.case_file.sha256,'0'.repeat(64)),'wrong.csv');assert.match(a.$('sequence-error').textContent,/different frozen case/);assert.equal(a.w.document.activeElement.id,'sequence-return-file');assert.equal(a.$('sequence-revision-files').open,true);assert.equal(a.$('sequence-solar').hidden,true);await sequenceFile(a,JSON.stringify({...r,proposal_file:undefined}));assert.equal(a.$('sequence-result').hidden,true);assert.match(a.$('sequence-error').textContent,/retained file must be an object/);
 await sequenceFile(a,c.caseText,'case.json');await joinedReturn(a,c.csvText);const profile=joinedProfile(await joinedExport(a));profile.case_sha256='f'.repeat(64);await joinedFile(a,'sequence-solar-file',JSON.stringify(profile),'wrong-solar.json');assert.equal(a.$('sequence-solar-profile').open,true);assert.equal(a.w.document.activeElement.id,'sequence-solar-file');assert.match(a.$('sequence-error').textContent,/different case/);assert.match(a.$('sequence-solar-status').textContent,/Unknown/);
 }finally{a.close();}
});

test('joined continuous maximum 366-block return and 8784-interval profile reopen below 32 MiB',async()=>{
 const a=await boot();try{const source=joinedSource(366),json=JSON.stringify(source),raw=json+'\n'.repeat(4*1024*1024-Buffer.byteLength(json)),c=await joinedCase(a,source,0,raw);await joinedReturn(a,c.csvText,{0:2});a.$('sequence-solar-format').value='interval_energy';a.$('sequence-solar-template').click();const p=JSON.parse(await a.downloads.at(-1).text());assert.equal(p.intervals.length,8784);p.source_kind='illustrative_scenario';p.source_label='Maximum hourly QA profile';p.plant_mapping='Declared example unit';for(const r of p.intervals){r.energy_kwh=1;r.power_cap_kw=2;}const solar=JSON.stringify(p);await joinedFile(a,'sequence-solar-file',solar,'full-year.json');assert.match(a.$('sequence-solar-status').textContent,/8,784 of 8,784 h known/);const r=await joinedExport(a),saved=JSON.stringify(r);assert.equal(r.kind,'continuous_plan_revision_review',a.$('sequence-error').textContent);assert.ok(Buffer.byteLength(saved)<32*1024*1024);assert.equal(r.results.solar.difference_envelope.contributions,undefined);a.$('sequence-evidence-export').click();const request=JSON.parse(await a.downloads.at(-1).text());assert.equal(request.difference_envelope.contributions.length,8784);assert.ok(Buffer.byteLength(JSON.stringify(request))<32*1024*1024);await sequenceFile(a,saved,'full-year-review.json');assert.equal(a.$('sequence-result').hidden,false,a.$('sequence-error').textContent);const reopened=await joinedExport(a);assert.equal(JSON.parse(reopened.case_file.text).source_file.text,raw);assert.equal(reopened.solar_file.text,solar);assert.equal(reopened.results.changes.unmet_m3,0);assert.equal(reopened.results.solar.coverage.horizon_hours,8784);assert.deepEqual(reopened.results.solar.bounds.delta_solar_kwh,{lower:0,upper:.5});
 }finally{a.close();}
});

test('joined continuous solar direction treats scale-sized roundoff as unchanged without altering exported values',async()=>{
 const a=await boot();try{
  for(const middle of [.3,1.1]){const source=joinedSource();source.specific_energy_kwh_m3=3.4;Object.assign(source.inputs,{capacity:1000000,reserve:0,initial:0,target:0,unitCapacity:500});for(const block of source.inputs.blocks){block.production.fill(middle);block.demand=0;}source.inputs.blocks[0].production[0]=.1;source.inputs.blocks[1].production[23]=.2;
   const c=await joinedCase(a,source);await joinedReturn(a,c.csvText,{0:.2,47:.1});const p=joinedProfile(await joinedExport(a));p.intervals[0].power_kw=2000;await joinedFile(a,'sequence-solar-file',JSON.stringify(p),'roundoff.json');const r=await joinedExport(a),delta=r.results.solar.totals.delta_solar_kwh,tolerance=64*Number.EPSILON*Math.max(r.results.solar.full_load_totals.original_load_kwh,r.results.solar.full_load_totals.revised_load_kwh);assert.ok(Math.abs(delta)<=tolerance);assert.match(a.$('sequence-solar-conclusion').textContent,/No solar-use change at calculation precision/);assert.doesNotMatch(a.$('sequence-solar-conclusion').textContent,/uses more|uses less|reverse the direction/);
  }
 }finally{a.close();}
});

test('joined continuous original-day handoff labels and exports original production and carry while a return is displayed',async()=>{
 const a=await boot();try{const source=joinedSource(3),c=await joinedCase(a,source,1);await joinedReturn(a,c.csvText,{0:0});a.$('sequence-day').value='2';a.$('sequence-day').onchange();assert.match(a.$('sequence-day-status').textContent,/Original: 10 m³ carried in.*Returned: 9 m³ carried in/);assert.equal(a.$('sequence-review-day').textContent,'Review original day');assert.equal(a.$('sequence-export-day').textContent,'Export original day case');const details=a.w.document.querySelector('.sequence-day-handoff');assert.match(details.querySelector('summary').textContent,/Original day/);assert.match(details.textContent,/original production and original carried water/);input(a,'sequence-reason','Revise the returned plan after checking downstream inventory.');a.$('sequence-decision-value').value='Request revised sequence';a.$('sequence-export-day').click();const day=JSON.parse(await a.downloads.at(-1).text());assert.equal(day.kind,'continuous_plan_day_case');assert.equal(day.day.inputs.initial,10);assert.deepEqual(day.day.inputs.production,source.inputs.blocks[2].production);assert.equal(day.review.kind,'continuous_plan_review');assert.equal(day.review.proposal_file,undefined);assert.equal(day.review.reason,'');assert.equal(day.review.decision,'Needs team review');assert.equal(a.$('sequence-reason').value,'Revise the returned plan after checking downstream inventory.');assert.equal(a.$('sequence-decision-value').value,'Request revised sequence');const continuous=await joinedExport(a);assert.equal(continuous.reason,'Revise the returned plan after checking downstream inventory.');assert.equal(continuous.decision,'Request revised sequence');
 }finally{a.close();}
});

test('solar evidence request completes continuous ambiguous-to-changed-evidence review without inventing absolute totals',async()=>{
 const a=await boot();try{
  const c=await joinedCase(a);await joinedReturn(a,c.csvText,{23:2,24:0});const record=await joinedExport(a),start='2026-07-01T23:00:00.000Z',mid='2026-07-02T00:00:00.000Z',end='2026-07-02T01:00:00.000Z';
  const p=joinedProfile(record,{energy:true,intervals:[{start,end,available_at:start,energy_kwh:2,power_cap_kw:2}]}),raw='\uFEFF'+JSON.stringify(p,null,2).replaceAll('\n','\r\n');await joinedFile(a,'sequence-solar-file',raw,'ambiguous.json');
  assert.match(a.$('sequence-outcomes').textContent,/Solar use \(kWh\)UnknownUnknown-1 to \+1/);assert.equal(a.$('sequence-solar-evidence').open,false);assert.equal(a.$('sequence-solar-known').closest('details').id,'sequence-solar-profile');assert.equal(a.$('sequence-evidence-intervals').querySelectorAll('tbody tr').length,1);
  a.$('sequence-evidence-export').click();const request=JSON.parse(await a.downloads.at(-1).text());assert.equal(request.kind,'solar_evidence_request');assert.equal(request.case_file.sha256,record.case_file.sha256);assert.equal(request.proposal_file.sha256,record.proposal_file.sha256);assert.equal(request.solar_file.sha256,createHash('sha256').update(raw).digest('hex'));assert.equal(request.profile.plant_mapping,p.plant_mapping);assert.equal(request.profile.review_as_of,p.review_as_of);assert.deepEqual(request.horizon,{start:'2026-07-01T00:00:00.000Z',end:'2026-07-03T00:00:00.000Z'});assert.equal(request.difference_envelope.contributions.length,3);const uncertain=request.difference_envelope.contributions.find(row=>row.width_kwh>0);assert.equal(uncertain.start,start);assert.equal(uncertain.end,end);assert.deepEqual(uncertain.constraints,{energy_kwh:2,power_cap_kw:2});assert.equal(uncertain.available_at,start);assert.match(request.request,/finer intervals alone need not resolve/);
  input(a,'sequence-reason','Await the plant interval record.');a.$('sequence-decision-value').value='Request revised sequence';p.intervals=[{start,end:mid,available_at:start,energy_kwh:2,power_cap_kw:2},{start:mid,end,available_at:start,energy_kwh:0,power_cap_kw:2}];await joinedFile(a,'sequence-solar-file',JSON.stringify(p),'changed.json');assert.match(a.$('sequence-solar-status').textContent,/Changed evidence.*absolute totals unknown/);assert.equal(a.$('sequence-reason').value,'');assert.equal(a.$('sequence-decision-value').value,'Needs team review');assert.match(a.$('sequence-outcomes').textContent,/Solar use \(kWh\)UnknownUnknown\+1/);assert.equal(a.$('sequence-solar-evidence').open,false);assert.equal(a.$('sequence-evidence-export').hidden,true);assert.match(a.$('sequence-evidence-summary').textContent,/No further solar timing evidence/);
  const saved=await joinedExport(a);assert.equal(saved.results.solar.totals,null);assert.equal(saved.results.solar.difference_envelope.contributions,undefined);saved.results.solar.difference_envelope.delta_solar_kwh={lower:999,upper:999};await sequenceFile(a,JSON.stringify(saved),'review.json');assert.match(a.$('sequence-outcomes').textContent,/Solar use \(kWh\)UnknownUnknown\+1/);assert.doesNotMatch(a.$('sequence-outcomes').textContent,/999/);assert.equal(a.$('sequence-solar-evidence').open,false);
 }finally{a.close();}
});

test('solar evidence interval ranking stays bounded while request retains every constraint and ignores late numeric values',async()=>{
 const a=await boot();try{
  const source=joinedSource(1),c=await joinedCase(a,source);await joinedReturn(a,c.csvText,{0:2,1:0,2:2,3:0,4:2,5:0,6:2,7:0,8:4,9:2,10:0,11:2});const time=h=>new Date(Date.parse(source.inputs.blocks[0].times[0])+h*3600000).toISOString(),rows=Array.from({length:9},(_,h)=>({start:time(h),end:time(h+1),available_at:h===8?time(25):time(0),energy_kwh:h===8?100:1,power_cap_kw:h===8?100:2}));rows.push({start:time(11),end:time(12),available_at:time(0),energy_kwh:2,power_cap_kw:2});const profile=joinedProfile(await joinedExport(a),{energy:true,intervals:rows});await joinedFile(a,'sequence-solar-file',JSON.stringify(profile),'ranked.json');
  const visible=[...a.$('sequence-evidence-intervals').querySelectorAll('tbody tr')];assert.equal(visible.length,5);assert.match(visible[0].textContent,/11:00:00.*late evidence/);assert.match(visible[1].textContent,/12:00:00.*missing evidence/);assert.match(visible[2].textContent,/03:00:00.*timing unknown/);assert.match(a.$('sequence-evidence-summary').textContent,/Showing 5 of 10 uncertain intervals/);assert.equal(a.$('sequence-solar-evidence').open,false);
  a.$('sequence-evidence-export').click();const request=JSON.parse(await a.downloads.at(-1).text());assert.equal(request.difference_envelope.contributions.length,12);assert.equal(request.difference_envelope.contributions.filter(row=>row.width_kwh>0).length,10);const late=request.difference_envelope.contributions.find(row=>row.status==='late');assert.deepEqual(late.constraints,{});assert.equal(late.available_at,time(25));assert.ok(request.difference_envelope.contributions.every(row=>row.constraints.energy_kwh!==100&&row.constraints.power_cap_kw!==100));const whole=request.difference_envelope.contributions.find(row=>row.start===time(11));assert.deepEqual(whole.constraints,{energy_kwh:2,power_cap_kw:2});
  input(a,'sequence-demand','10');assert.equal(a.$('sequence-solar-evidence').hidden,true);assert.equal(a.$('sequence-evidence-export').disabled,true);assert.equal(a.$('sequence-evidence-intervals').textContent,'');
 }finally{a.close();}
});

test('solar evidence distinguishes unknown energy from unchanged loads and bounded sparse positive direction',async()=>{
 const a=await boot();try{
  let c=await joinedCase(a);await joinedReturn(a,c.csvText);let p=joinedProfile(await joinedExport(a),{intervals:[]});await joinedFile(a,'sequence-solar-file',JSON.stringify(p),'empty.json');assert.match(a.$('sequence-outcomes').textContent,/Solar use \(kWh\)UnknownUnknown0/);assert.match(a.$('sequence-solar-conclusion').textContent,/No solar-use change/);assert.equal(a.$('sequence-evidence-export').hidden,true);assert.equal(a.$('sequence-evidence-intervals').textContent,'');
  c=await joinedCase(a);await joinedReturn(a,c.csvText,{23:2,24:.5,25:.5});const time=h=>new Date(Date.parse('2026-07-01T00:00:00Z')+h*3600000).toISOString();p=joinedProfile(await joinedExport(a),{intervals:[{start:time(23),end:time(24),available_at:time(0),power_kw:2},{start:time(24),end:time(25),available_at:time(0),power_kw:0}]});await joinedFile(a,'sequence-solar-file',JSON.stringify(p),'sparse.json');assert.match(a.$('sequence-outcomes').textContent,/Solar use \(kWh\)UnknownUnknown\+0.5 to \+1/);assert.match(a.$('sequence-solar-conclusion').textContent,/uses more eligible solar under every allowed timing pattern/);assert.doesNotMatch(a.$('sequence-solar-conclusion').textContent,/Production also changes|inventory is lower|service is worse/);
  const source=joinedSource();source.specific_energy_kwh_m3=null;c=await joinedCase(a,source);await joinedReturn(a,c.csvText);p=joinedProfile(await joinedExport(a),{intervals:[]});await joinedFile(a,'sequence-solar-file',JSON.stringify(p),'unknown-sec.json');assert.match(a.$('sequence-evidence-summary').textContent,/Declare supported plant specific energy/);assert.equal(a.$('sequence-evidence-export').hidden,false);assert.equal(a.$('sequence-evidence-intervals').textContent,'');a.$('sequence-evidence-export').click();const request=JSON.parse(await a.downloads.at(-1).text());assert.equal(request.specific_energy_kwh_m3,null);assert.equal(request.difference_envelope.status,'unknown_energy');assert.equal(request.difference_envelope.delta_solar_kwh,null);assert.match(request.request,/specific energy/);assert.equal(request.difference_envelope.contributions.length,0);
 }finally{a.close();}
});

test('single-day solar evidence keeps partial absolute totals unknown, exports bindings and recomputes after replacement and reopen',async()=>{
 const a=await boot();try{
  const profile=await solarDraft(a);profile.intervals=[];await a.importRevision('revision-solar-file',JSON.stringify(profile),'missing.json');assert.match(a.$('revision-solar-table').textContent,/Solar useUnknownUnknown0\.00 to \+340\.00 kWh/);assert.match(a.$('revision-solar-timing').textContent,/No positive minimum solar-use gain established/);assert.equal(a.$('revision-solar-evidence').open,false);assert.equal(a.$('revision-evidence-export').hidden,false);a.$('revision-evidence-export').click();const request=JSON.parse(await a.downloads.at(-1).text());assert.equal(request.kind,'solar_evidence_request');assert.equal(request.profile.case_sha256,request.case_file.sha256);assert.match(request.proposal_file.sha256,/^[a-f0-9]{64}$/);assert.equal(request.solar_file.sha256,createHash('sha256').update(JSON.stringify(profile)).digest('hex'));assert.equal(request.difference_envelope.contributions.length,1);assert.equal(request.horizon.start,request.difference_envelope.contributions[0].start);assert.match(a.$('revision-evidence-summary').textContent,/Finer intervals alone may not resolve/);
  input(a,'revision-note','Await evidence.');a.$('revision-decision').value='Ready for next simulation';a.$('revision-solar-template').click();const replacement=JSON.parse(await a.downloads.at(-1).text());Object.assign(replacement,{source_kind:'illustrative_scenario',source_label:'Changed evidence',plant_mapping:profile.plant_mapping});replacement.intervals.forEach(row=>row.power_kw=1000);await a.importRevision('revision-solar-file',JSON.stringify(replacement),'new.json');assert.equal(a.$('revision-note').value,'');assert.equal(a.$('revision-decision').value,'Needs team review');assert.match(a.$('revision-solar-status').textContent,/Changed evidence/);assert.equal(a.$('revision-evidence-export').hidden,true);input(a,'revision-note','New evidence reviewed.');submit(a);const saved=JSON.parse(await a.downloads.at(-1).text());assert.equal(saved.solar_comparison.difference_envelope.contributions,undefined);saved.solar_comparison.difference_envelope.delta_solar_kwh={lower:-999,upper:999};await a.importRevision('revision-case-file',JSON.stringify(saved),'review.json');assert.doesNotMatch(a.$('revision-solar-table').textContent,/999/);assert.match(a.$('revision-solar-table').textContent,/Solar use.*\+340\.00 kWh/);assert.equal(a.$('revision-solar-evidence').open,false);
 }finally{a.close();}
});

test('solar difference review preserves small added load before profile import, with a profile and after removal',async()=>{
 const a=await boot();try{
  const readDelta=(id,label)=>{const row=[...a.$(id).querySelectorAll('tbody tr')].find(row=>row.firstElementChild.textContent===label);return Number(row.lastElementChild.textContent.replaceAll(',','').replace(/ (?:kWh|m³)$/,''));};
  const checkContinuous=()=>{assert.ok(Math.abs(readDelta('sequence-outcomes','Total electricity (kWh)')/1e80-1)<1e-15);assert.equal(readDelta('sequence-outcomes','Production (m³)'),1e-20);};
  const source=joinedSource(1);source.specific_energy_kwh_m3=1e100;source.inputs.blocks[0].production.fill(0);source.inputs.blocks[0].production[0]=1;source.inputs.blocks[0].demand=0;const c=await joinedCase(a,source);await joinedReturn(a,c.csvText,{1:1e-20});checkContinuous();await joinedFile(a,'sequence-solar-file',JSON.stringify(joinedProfile(await joinedExport(a),{intervals:[]})),'unknown-solar.json');checkContinuous();const record=await joinedExport(a),change=record.results.solar.full_load_totals.delta_load_kwh;assert.equal(record.results.changes.modeled_production_energy_kwh,change);assert.equal(record.results.solar.difference_envelope.delta_other_kwh.lower,0);assert.equal(record.results.solar.difference_envelope.delta_other_kwh.upper,change);a.$('sequence-solar-remove').click();checkContinuous();
  const checkDay=()=>{assert.ok(Math.abs(readDelta('revision-comparison','Modeled production energy')/1e80-1)<1e-15);assert.equal(readDelta('revision-water-balance','Water produced'),1e-20);};
  const {raw}=await currentCase(a),single=JSON.parse(raw);single.specific_energy_kwh_m3=1e100;single.assessment.inputs.production.fill(0);single.assessment.inputs.production[10]=1;await a.importRevision('revision-case-file',JSON.stringify(single),'mixed-scale.json');a.$('revision-template').click();const rows=a.w.Papa.parse(await a.downloads.at(-1).text(),{skipEmptyLines:true}).data;rows[2][2]='1e-20';await a.importRevision('revision-proposal-file',a.w.Papa.unparse(rows),'mixed-return.csv');checkDay();a.$('revision-solar-template').click();const profile=JSON.parse(await a.downloads.at(-1).text());Object.assign(profile,{source_kind:'illustrative_scenario',source_label:'Mixed-scale arithmetic case',plant_mapping:'Declared example',intervals:[]});await a.importRevision('revision-solar-file',JSON.stringify(profile),'missing-solar.json');checkDay();input(a,'revision-note','Arithmetic check only.');submit(a);const saved=JSON.parse(await a.downloads.at(-1).text()),delta=saved.solar_comparison.full_load_totals.delta_load_kwh;assert.equal(saved.comparison.changes.modeled_production_energy_kwh,delta);assert.equal(saved.comparison.changes.available_production_m3,1e-20);assert.equal(saved.solar_comparison.difference_envelope.delta_other_kwh.lower,0);assert.equal(saved.solar_comparison.difference_envelope.delta_other_kwh.upper,delta);a.$('revision-solar-remove').click();checkDay();
 }finally{a.close();}
});

test('solar evidence focuses only differing unconstrained periods while retaining whole coupled energy intervals',async()=>{
 const a=await boot();try{
  const time=h=>new Date(Date.parse('2026-07-01T00:00:00Z')+h*3600000).toISOString(),c=await joinedCase(a);await joinedReturn(a,c.csvText,{23:2,24:.5,25:.5});let p=joinedProfile(await joinedExport(a),{intervals:[{start:time(23),end:time(24),available_at:time(0),power_kw:2},{start:time(24),end:time(25),available_at:time(0),power_kw:0}]});await joinedFile(a,'sequence-solar-file',JSON.stringify(p),'sparse-focused.json');const visible=a.$('sequence-evidence-intervals').querySelector('tbody tr');assert.match(visible.textContent,/02 Jul 2026, 04:00:00.*02 Jul 2026, 05:00:00/);assert.doesNotMatch(visible.textContent,/03 Jul/);a.$('sequence-evidence-export').click();let request=JSON.parse(await a.downloads.at(-1).text()),gap=request.difference_envelope.contributions.find(row=>row.start===time(25));assert.equal(gap.end,time(48));assert.deepEqual(gap.focus_intervals,[{start:time(25),end:time(26),delta_solar_kwh:{lower:-.5,upper:0},width_kwh:.5}]);assert.match(request.request,/Declare actual availability/);assert.match(request.request,/later cutoff is a changed review/);
  const source=joinedSource(1);source.inputs.blocks[0].production[0]=0;const next=await joinedCase(a,source);await joinedReturn(a,next.csvText,{1:2});p=joinedProfile(await joinedExport(a),{energy:true,intervals:[{start:time(0),end:time(2),available_at:time(0),energy_kwh:2,power_cap_kw:2}]});await joinedFile(a,'sequence-solar-file',JSON.stringify(p),'coupled.json');assert.match(a.$('sequence-evidence-intervals').textContent,/03:00:00.*05:00:00/);assert.equal(a.$('sequence-solar-format').querySelector('option[value="interval_energy"]').textContent,'Interval energy');assert.match(a.$('sequence-solar-source').textContent,/Declared interval energy and any known power limit/);a.$('sequence-evidence-export').click();request=JSON.parse(await a.downloads.at(-1).text());const coupled=request.difference_envelope.contributions[0];assert.equal(coupled.start,time(0));assert.equal(coupled.end,time(2));assert.equal(coupled.focus_intervals,undefined);assert.deepEqual(coupled.constraints,{energy_kwh:2,power_cap_kw:2});
  await solarDraft(a);a.$('revision-solar-format').value='interval_energy';assert.equal(a.$('revision-solar-format').selectedOptions[0].textContent,'Interval energy');a.$('revision-solar-template').click();p=JSON.parse(await a.downloads.at(-1).text());Object.assign(p,{source_kind:'illustrative_scenario',source_label:'Known energy without a cap',plant_mapping:'Declared example'});p.intervals.forEach(row=>{row.energy_kwh=1;row.power_cap_kw=null;});await a.importRevision('revision-solar-file',JSON.stringify(p),'energy-only.json');assert.match(a.$('revision-solar-source').textContent,/Declared interval energy and any known power limit/);assert.match(a.$('revision-solar-profile').textContent,/any known power limit/);assert.doesNotMatch(a.$('revision-solar-profile').textContent,/within the declared power limit/);
 }finally{a.close();}
});

function executionPacket({sourceChange,caseChange}={}){
 const time=h=>new Date(Date.parse('2026-07-01T21:00:00Z')+h*3600000).toISOString();
 const c={schema:1,kind:'fixed_plan_execution_case',input:{times:Array.from({length:24},(_,h)=>time(h)),production:Array(24).fill(10),demand:10,capacity:200,reserve:20,initial:100,target:100,startHour:0},unit_capacity_m3_h:50,specific_energy_kwh_m3:3.4,identity:{declared_plan_sha256:'a'.repeat(64)}};if(caseChange)caseChange(c);
 const file=(name,value)=>{const text=JSON.stringify(value,null,2)+'\n';return {name,text,sha256:createHash('sha256').update(text).digest('hex')};},case_file=file('frozen-24h-case.json',c);
 const source={schema:1,kind:'plant_execution_measurements',case_sha256:case_file.sha256,source_kind:'illustrative_scenario',source_label:'Illustrative stock withdrawal; no field measurements',plant_mapping:'Illustrative whole plant',tank_mapping:'Illustrative tank',electricity_basis:'gross_plant_load',review_as_of:time(24),streams:[['energy','kWh',680],['produced','m3',200],['delivered','m3',240]].map(([role,unit,value])=>({role,unit,semantics:'interval_total',readings:[{start:time(0),end:time(24),available_at:time(24),lower:value,upper:value}]})),declared_zero:['other_inflow','other_outflow','spill'],tank:[{time:time(0),available_at:time(0),lower:100,upper:100},{time:time(24),available_at:time(24),lower:60,upper:60}]};if(sourceChange)sourceChange(source);
 return {schema:1,kind:'measured_run_review',case_file,measurement_file:file('measured-stock-draw.json',source),createdAt:'2026-10-02T21:00:00Z',note:{reviewer:'Prior reviewer',decision:'Hold for correction',reason:'Prior note'},results:{measured:{energy:{lower:999,upper:999}}}};
}
async function openExecution(a,value,name='measured-review.json'){
 const text=typeof value==='string'?value:JSON.stringify(value);Object.defineProperty(a.$('execution-file'),'files',{value:[{name,size:Buffer.byteLength(text),arrayBuffer:async()=>new TextEncoder().encode(text).buffer}],configurable:true});await a.$('execution-file').onchange();
}
test('measured review reopens its own frozen plan, exposes stock draw, exports exact sources and saves independent history',async()=>{
 const a=await boot();let b;try{
  a.route('reviews');const packet=executionPacket();await openExecution(a,packet);assert.match(a.$('execution-summary').textContent,/different.*water|different.*inventory/i);assert.match(a.$('execution-outcomes').textContent,/680/);assert.doesNotMatch(a.$('execution-outcomes').textContent,/999/);assert.match(a.$('review-case-title').textContent,/0?2 Jul 2026.*200 m³.*Frozen measured-run/);assert.match(a.$('review-boundary-values').textContent,/100/);assert.equal(a.$('review-note').value,'');assert.equal(a.$('decision').value,'Needs team review');assert.match(a.$('review-inventory-chart').textContent,/Frozen plan/);assert.doesNotMatch(a.$('review-inventory-chart').textContent,/Measured/);
  a.$('review-note').value='Hold: lower energy accompanies lower produced water and tank stock.';a.$('decision').value='Hold for correction';a.$('download-current-review').click();const exported=JSON.parse(await a.downloads.at(-1).text());assert.equal(a.$('export-status').querySelector('a').download,'aktina-review-2026-07-02-tank-200.json');assert.equal(exported.kind,'measured_run_review');assert.equal(exported.case_file.text,packet.case_file.text);assert.equal(exported.measurement_file.text,packet.measurement_file.text);assert.equal(exported.results.water_balance.residual_m3.lower,0);assert.equal(exported.results.differences.energy.lower,-136);assert.equal(exported.results.differences.final_storage.lower,-40);assert.equal(exported.note.decision,'Hold for correction');
  a.$('review-form').dispatchEvent(new a.w.Event('submit',{bubbles:true,cancelable:true}));const saved=JSON.parse(a.w.localStorage.getItem('aquashift.review.v1')).at(-1);assert.equal(saved.date,'2026-07-02');assert.equal(saved.tankCapacityM3,200);assert.equal(saved.measuredRunReview.case_file.sha256,packet.case_file.sha256);assert.match(a.$('review-history').textContent,/Measured run/);
  b=await boot();b.route('reviews');await openExecution(b,exported);assert.match(b.$('review-case-title').textContent,/0?2 Jul 2026.*200 m³/);assert.match(b.$('execution-summary').textContent,/Recalculated/);assert.equal(b.$('review-note').value,'');assert.equal(b.$('decision').value,'Needs team review');assert.equal(b.$('execution-outcomes').textContent,a.$('execution-outcomes').textContent);
  b.change('date','2026-07-03');assert.equal(b.$('execution-result').hidden,true);assert.equal(b.$('review-note').value,'');assert.match(b.$('review-case-title').textContent,/0?3 Jul 2026.*4,000 m³.*Frozen reference/);
 }finally{b?.close();a.close();}
});
test('measured review preserves the same frozen basis on correction and clears evidence on failed replacement',async()=>{
 const a=await boot();try{
  a.route('reviews');const packet=executionPacket();await openExecution(a,packet);const changed=JSON.parse(packet.measurement_file.text);changed.source_label='Illustrative corrected electricity';changed.streams[0].readings[0].lower=changed.streams[0].readings[0].upper=690;
  a.$('review-note').value='Old decision';await openExecution(a,changed,'corrected-totals.json');assert.match(a.$('execution-outcomes').textContent,/690/);assert.match(a.$('review-case-title').textContent,/0?2 Jul 2026.*200 m³/);assert.equal(a.$('review-note').value,'');
  changed.case_sha256='b'.repeat(64);await openExecution(a,changed,'wrong-case.json');assert.match(a.$('execution-summary').textContent,/not accepted.*different frozen case/i);assert.equal(a.$('execution-result').hidden,true);assert.doesNotMatch(a.$('execution-source').textContent,/corrected-totals/);assert.match(a.$('review-case-title').textContent,/15 Jul 2026.*4,000 m³/);
 }finally{a.close();}
});

test('pending measured import cannot save or export a generic plan review',async()=>{
 const a=await boot();try{
  a.route('reviews');const raw=JSON.stringify(executionPacket());let release;const bytes=new Promise(resolve=>{release=resolve;});
  Object.defineProperty(a.$('execution-file'),'files',{value:[{name:'pending-review.json',size:Buffer.byteLength(raw),arrayBuffer:()=>bytes}],configurable:true});const opening=a.$('execution-file').onchange();
  assert.equal(a.$('review-form').querySelector('button[type="submit"]').disabled,true);assert.equal(a.$('download-current-review').disabled,true);
  a.$('review-note').value='This must not save the unrelated global plan.';a.$('review-form').dispatchEvent(new a.w.Event('submit',{bubbles:true,cancelable:true}));assert.equal(a.w.localStorage.getItem('aquashift.review.v1'),null);assert.match(a.$('review-status').textContent,/Wait for measured-run validation/);assert.equal(a.downloads.length,0);
  release(new TextEncoder().encode(raw).buffer);await opening;assert.equal(a.$('review-form').querySelector('button[type="submit"]').disabled,false);assert.equal(a.$('download-current-review').disabled,false);assert.match(a.$('review-case-title').textContent,/0?2 Jul 2026.*200 m³/);assert.equal(a.$('review-note').value,'');
 }finally{a.close();}
});

test('input task tabs preserve independent imports and expose the actual schedule tank basis',async()=>{
 const a=await boot();try{
  a.route('data');const context=a.w.document.querySelector('.context');
  const check=task=>{
   assert.equal(a.w.document.querySelectorAll('[data-analysis-pane]:not([hidden])').length,1);
   for(const tab of a.w.document.querySelectorAll('[role="tab"][data-analysis-task]')){
    const active=tab.dataset.analysisTask===task,pane=a.$(tab.getAttribute('aria-controls'));
    assert.equal(tab.getAttribute('aria-selected'),String(active));assert.equal(tab.tabIndex,active?0:-1);
    assert.equal(pane.hidden,!active);assert.equal(pane.getAttribute('aria-labelledby'),tab.id);
   }
   assert.equal(context.hidden,task!=='plan');
   if(task==='plan')assert.equal(context.parentElement.id,'data-plan-context');
   for(const id of ['date','tank','plan-source'])assert.equal(a.w.document.querySelectorAll('#'+id).length,1);
  };
  const key=(task,value)=>a.$('analysis-task-'+task).dispatchEvent(new a.w.KeyboardEvent('keydown',{key:value,bubbles:true,cancelable:true}));
  check('forecast');await a.importCSV(oneRow(),'forecast-task.csv');a.$('model-version').value='Retained forecast note';
  key('forecast','ArrowLeft');check('reference');assert.equal(a.w.document.activeElement.id,'analysis-task-reference');
  key('reference','Home');check('forecast');key('forecast','ArrowRight');check('plan');assert.equal(a.w.document.activeElement.id,'analysis-task-plan');
  a.change('date',fixture.days[0].date);a.change('tank','1000');
  const raw=a.w.Papa.unparse([['time','production_m3'],...fixture.days[0].times.map(time=>[time,120])]);
  await a.importPlan(raw,'selected-tank.csv');a.$('plan-method').value='Retained plan note';
  assert.match(a.$('schedule-import-status').textContent,/VALIDATED/);assert.match(a.$('schedule-validation').textContent,/1,000 m³/);
  key('plan','End');check('reference');key('reference','ArrowRight');check('forecast');assert.equal(a.w.document.activeElement.id,'analysis-task-forecast');
  assert.match(a.$('import-status').textContent,/PARTIAL/);assert.equal(a.$('model-version').value,'Retained forecast note');
  a.$('analysis-task-plan').click();check('plan');a.route('evaluation');assert.equal(context.hidden,false);assert.equal(context.parentElement.id,'forecast-context');a.route('data');check('plan');
  assert.equal(a.$('plan-method').value,'Retained plan note');assert.equal(a.$('tank').value,'1000');
  a.$('inspect-candidate').click();assert.equal(a.$('view-operations').hidden,false);assert.equal(a.$('tank').value,'1000');assert.equal(a.$('plan-source').value,'imported');
 }finally{a.close();}
});

test('diagnostic task tabs preserve forecast scope and one active keyboard-accessible result',async()=>{
 const a=await boot();try{
  a.route('data');await a.importCSV(`time,predicted\n${fixture.days[0].times[12]},0\n`,'daylight-task.csv');
  a.route('evaluation');a.change('evaluation-source','imported');a.change('evaluation-hours','daylight');
  const scope=a.$('evaluation-scope').textContent,metrics=a.$('evaluation-kpis').textContent;
  const check=task=>{
   assert.equal(a.w.document.querySelectorAll('[data-diagnostic-pane]:not([hidden])').length,1);
   for(const tab of a.w.document.querySelectorAll('[role="tab"][data-diagnostic-task]')){
    const active=tab.dataset.diagnosticTask===task,pane=a.$(tab.getAttribute('aria-controls'));
    assert.equal(tab.getAttribute('aria-selected'),String(active));assert.equal(tab.tabIndex,active?0:-1);
    assert.equal(pane.hidden,!active);assert.equal(pane.getAttribute('aria-labelledby'),tab.id);
   }
   assert.equal(a.w.document.querySelector('.context').hidden,false);assert.equal(a.w.document.querySelector('.context').parentElement.id,'forecast-context');
   assert.equal(a.$('workspace-hour-control').parentElement.id,'diagnostic-time-control');assert.equal(a.$('workspace-hour-control').hidden,task!=='timing');
   assert.equal(a.$('evaluation-source').value,'imported');assert.equal(a.$('evaluation-hours').value,'daylight');
   assert.equal(a.$('evaluation-scope').textContent,scope);assert.equal(a.$('evaluation-kpis').textContent,metrics);
  };
  const key=(task,value)=>a.$('diagnostic-task-'+task).dispatchEvent(new a.w.KeyboardEvent('keydown',{key:value,bubbles:true,cancelable:true}));
  check('hourly');assert.match(scope,/1 matching daylight hours/);
  key('hourly','ArrowLeft');check('timing');assert.equal(a.w.document.activeElement.id,'diagnostic-task-timing');
  key('timing','Home');check('hourly');key('hourly','ArrowRight');check('monthly');
  key('monthly','ArrowRight');check('conditions');assert.ok(a.$('weather-diagnostics').querySelectorAll('tbody tr').length>0);
  key('conditions','End');check('timing');key('timing','ArrowRight');check('hourly');
  a.$('diagnostic-task-monthly').click();check('monthly');a.route('operations');a.route('evaluation');check('monthly');
  a.change('date',fixture.days[0].date);check('monthly');assert.doesNotMatch(a.$('forecast-chart').textContent,/No matching predictions/);
  a.$('diagnostic-task-timing').click();check('timing');a.$('hour').value='12';a.$('hour').dispatchEvent(new a.w.Event('input'));
  assert.match(a.$('evaluation-timing').textContent,/Present in selected analysis/);check('timing');
  a.$('download-feedback').click();const feedback=await a.downloads.at(-1).text();assert.match(feedback,/Daylight reference > 20 W\/m² paired matching rows/);assert.match(feedback,/daylight-task\.csv/);
 }finally{a.close();}
});

test('workspace parents expose only the active route group and remember its last task',async()=>{
 const a=await boot();try{
  const groups={plans:['reviews','operations','resilience','scenarios'],forecasts:['evaluation','data'],observations:['pilot','alerts'],reference:['overview','evidence']};
  assert.equal(a.w.document.querySelectorAll('[data-workspace]').length,4);
  const check=(group,route)=>{
   assert.equal(a.w.document.body.dataset.workspaceGroup,group);assert.equal(a.w.document.body.dataset.view,route);
   assert.equal(a.w.document.querySelectorAll('[data-navigation-group]:not([hidden])').length,1);
   assert.equal(a.w.document.querySelectorAll('.view:not([hidden])').length,1);
   for(const button of a.w.document.querySelectorAll('[data-workspace]')){
    const active=button.dataset.workspace===group,pane=a.$(button.getAttribute('aria-controls'));
    assert.equal(button.getAttribute('aria-expanded'),String(active));assert.equal(pane.hidden,!active);
    assert.deepEqual([...pane.querySelectorAll('[data-view]')].map(child=>child.dataset.view),groups[button.dataset.workspace]);
   }
   const selected=a.w.document.querySelectorAll('nav [data-view][aria-current="page"]');assert.equal(selected.length,1);assert.equal(selected[0].dataset.view,route);
  };
  check('plans','reviews');
  for(const [group,routes]of Object.entries(groups)){
   a.click(`[data-workspace="${group}"]`);check(group,routes[0]);
   for(const route of routes){a.route(route);check(group,route);}
  }
  for(const [group,routes]of Object.entries(groups)){a.click(`[data-workspace="${group}"]`);check(group,routes.at(-1));}
  a.$('workspace-toggle').click();a.click('[data-workspace="plans"]');check('plans','scenarios');
  assert.equal(a.$('workspace-toggle').getAttribute('aria-expanded'),'true');assert.equal(a.w.document.activeElement.dataset.workspace,'plans');
  a.route('reviews');check('plans','reviews');assert.equal(a.$('workspace-toggle').getAttribute('aria-expanded'),'false');assert.equal(a.w.document.activeElement.id,'views');
  a.w.location.hash='evaluation';a.w.dispatchEvent(new a.w.HashChangeEvent('hashchange'));check('forecasts','evaluation');
 }finally{a.close();}
});

test('review tools stay exclusive and reveal invalid decision fields from a closed panel',async()=>{
 const a=await boot();try{
  a.route('reviews');const tools=[...a.w.document.querySelectorAll('[data-review-tool]')];
  const check=selected=>{for(const button of tools){const active=button.dataset.reviewTool===selected;assert.equal(button.getAttribute('aria-expanded'),String(active));assert.equal(a.$(button.getAttribute('aria-controls')).open,active);}};
  check(null);a.click('[data-review-tool="evidence"]');check('evidence');a.click('[data-review-tool="history"]');check('history');
  a.click('[data-review-tool="decision"]');check('decision');a.$('review-note').value='Keep this draft while inspecting evidence.';
  a.click('[data-review-tool="evidence"]');check('evidence');assert.equal(a.$('review-note').value,'Keep this draft while inspecting evidence.');
  a.click('[data-review-tool="evidence"]');check(null);
  a.$('review-evidence-panel').open=true;await new Promise(resolve=>setTimeout(resolve,0));check('evidence');
  a.$('review-decision-editor').open=true;await new Promise(resolve=>setTimeout(resolve,0));check('decision');
  a.click('[data-review-tool="history"]');check('history');a.$('review-note').value='';a.$('download-current-review').onclick();check('decision');
  assert.equal(a.w.document.activeElement.id,'review-note');assert.equal(a.downloads.length,0);
  a.$('review-note').value='Inspect the supplied plan.';a.$('reviewer').value='';a.click('[data-review-tool="history"]');a.$('download-current-review').onclick();check('decision');
  assert.equal(a.w.document.querySelector('.review-record-details').open,true);assert.equal(a.w.document.activeElement.id,'reviewer');assert.equal(a.downloads.length,0);
  a.$('reviewer').value='Loucas';a.$('download-current-review').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).note,'Inspect the supplied plan.');
 }finally{a.close();}
});

test('completed measured imports reveal evidence and restore focus after switching review tools',async()=>{
 const a=await boot();try{
  a.route('reviews');
  for(const accepted of [true,false]){
   const packet=accepted?executionPacket():executionPacket({sourceChange:source=>{source.case_sha256='b'.repeat(64);}}),raw=JSON.stringify(packet);let release;
   const bytes=new Promise(resolve=>{release=resolve;});if(!a.$('review-evidence-panel').open)a.click('[data-review-tool="evidence"]');
   Object.defineProperty(a.$('execution-file'),'files',{value:[{name:accepted?'pending-valid.json':'pending-wrong-case.json',size:Buffer.byteLength(raw),arrayBuffer:()=>bytes}],configurable:true});
   const opening=a.$('execution-file').onchange();a.click('[data-review-tool="history"]');
   assert.equal(a.$('review-history-panel').open,true);assert.equal(a.$('review-evidence-panel').open,false);assert.equal(a.$('download-current-review').disabled,true);
   release(new TextEncoder().encode(raw).buffer);await opening;
   assert.equal(a.$('review-evidence-panel').open,true);assert.equal(a.$('review-history-panel').open,false);assert.equal(a.$('review-decision-editor').open,false);
   assert.equal(a.w.document.querySelector('[data-review-tool="evidence"]').getAttribute('aria-expanded'),'true');
   const focus=a.w.document.activeElement;assert.equal(focus.id,accepted?'execution-summary':'execution-file');assert.equal(focus.closest('[hidden]'),null);
   for(let parent=focus.parentElement;parent;parent=parent.parentElement)if(parent.tagName==='DETAILS')assert.equal(parent.open,true);
   assert.equal(a.$('execution-result').hidden,!accepted);assert.equal(a.$('download-current-review').disabled,false);
   if(accepted)assert.match(a.$('execution-outcomes').textContent,/680/);else{assert.match(a.$('execution-summary').textContent,/different frozen case/);assert.equal(a.$('execution-source').textContent,'');}
  }
 }finally{a.close();}
});

test('editing assessment conditions keeps stale results blocked until an explicit valid run returns focus',async()=>{
 const a=await boot();try{
  a.route('resilience');const form=a.$('resilience-form'),scrolled=[];
  a.w.HTMLElement.prototype.scrollIntoView=function(){scrolled.push(this.id);};
  a.$('resilience-export').click();const before=JSON.parse(await a.downloads.at(-1).text());
  a.click('[data-assessment-controls]');assert.equal(a.w.document.activeElement,a.$('resilience-demand'));assert.equal(a.$('assessment-workbench').dataset.mode,'conditions');assert.equal(a.$('resilience-edit').getAttribute('aria-pressed'),'true');assert.equal(scrolled.at(-1),'assessment-workbench');
  input(a,'resilience-demand','');assert.equal(a.$('resilience-export').disabled,true);assert.equal(a.$('resilience-chart').children.length,0);
  form.dispatchEvent(new a.w.Event('submit',{cancelable:true}));assert.equal(a.$('resilience-export').disabled,true);assert.notEqual(a.$('resilience-error').textContent,'');assert.notEqual(a.w.document.activeElement.id,'resilience-verdict');
  input(a,'resilience-demand','20');a.route('operations');a.route('resilience');
  assert.equal(a.$('resilience-export').disabled,true);assert.equal(a.$('resilience-chart').children.length,0);assert.match(a.$('resilience-verdict').textContent,/unavailable|recalculation/i);
  a.click('[data-assessment-controls]');scrolled.length=0;form.dispatchEvent(new a.w.Event('submit',{cancelable:true}));
  assert.equal(a.$('resilience-export').disabled,false);assert.equal(a.w.document.activeElement.id,'resilience-verdict');assert.equal(a.$('assessment-workbench').dataset.mode,'result');assert.equal(a.$('resilience-show-result').getAttribute('aria-pressed'),'true');assert.equal(scrolled.at(-1),'assessment-workbench');assert.notEqual(a.$('resilience-chart').children.length,0);
  a.$('resilience-export').click();const after=JSON.parse(await a.downloads.at(-1).text());
  assert.equal(after.inputs.scenario.demand_multiplier,1.2);assert.equal(after.date,before.date);assert.deepEqual(after.identity,before.identity);assert.deepEqual(after.inputs.production,before.inputs.production);assert.deepEqual(after.inputs.times,before.inputs.times);
  assert.deepEqual(after.control.inputs.scenario,after.inputs.scenario);assert.equal(after.control.inputs.initial,after.inputs.initial);
 }finally{a.close();}
});

test('navigation restores the page heading after a long review without breaking drawer continuation',async()=>{
 const a=await boot();try{
  a.route('reviews');a.click('[data-review-tool="evidence"]');assert.equal(a.$('review-evidence-panel').open,true);
  const scrolled=[],heading=a.w.document.querySelector('.topbar');
  a.w.HTMLElement.prototype.scrollIntoView=function(options){scrolled.push({element:this,block:options?.block});};
  const checkTop=()=>{assert.ok(scrolled.length>0);assert.equal(scrolled.at(-1).element,heading);assert.equal(scrolled.at(-1).block,'start');scrolled.length=0;};
  a.$('workspace-toggle').click();a.click('[data-workspace="forecasts"]');checkTop();
  assert.equal(a.$('view-evaluation').hidden,false);assert.equal(a.$('workspace-toggle').getAttribute('aria-expanded'),'true');assert.equal(a.w.document.activeElement.dataset.workspace,'forecasts');
  a.route('data');checkTop();assert.equal(a.$('view-data').hidden,false);assert.equal(a.$('analysis-pane-forecast').hidden,false);
  assert.equal(a.$('workspace-toggle').getAttribute('aria-expanded'),'false');assert.equal(a.w.document.activeElement.id,'views');
  a.w.location.hash='overview';a.w.dispatchEvent(new a.w.HashChangeEvent('hashchange'));checkTop();assert.equal(a.$('view-overview').hidden,false);
 }finally{a.close();}
});


const roadmapExample=()=>fs.readFileSync(new URL('../delivery/AquaShift-Roadmap-Handoff-Example.json',import.meta.url),'utf8');
async function openRoadmapPacket(a,text){
 Object.defineProperty(a.$('roadmap-file'),'files',{value:[{name:'handoff.json',size:Buffer.byteLength(text),arrayBuffer:async()=>new TextEncoder().encode(text).buffer}],configurable:true});
 await a.$('roadmap-file').onchange();
}
test('roadmap handoff joins original files without replacing forecast, plan or ordinary review state',async()=>{
 const a=await boot();try{
  await a.importCSV(oneRow());a.change('evaluation-source','imported');a.$('model-version').value='Retained model note';
  const day=fixture.days[0];await a.importPlan('time,production_m3,tank_capacity_m3\n'+day.times.map(time=>time+',120,4000').join('\n')+'\n');
  a.$('inspect-candidate').click();a.$('review-note').value='Retained ordinary review';a.$('plan-method').value='Retained plan note';
  const date=a.$('date').value,tank=a.$('tank').value;a.route('data');a.$('analysis-task-handoff').click();
  await openRoadmapPacket(a,roadmapExample());assert.equal(a.$('roadmap-result').hidden,false);assert.equal(a.$('roadmap-export').disabled,false);
  assert.equal(a.w.document.querySelectorAll('[data-analysis-pane]:not([hidden])').length,1);assert.equal(a.w.document.querySelector('.context').hidden,true);
  assert.match(a.$('roadmap-comparison').textContent,/480 kWh/);assert.match(a.$('roadmap-comparison').textContent,/-2 €/);assert.equal(a.$('roadmap-day').options.length,2);
  assert.equal(a.$('date').value,date);assert.equal(a.$('tank').value,tank);assert.equal(a.$('evaluation-source').value,'imported');assert.equal(a.$('model-version').value,'Retained model note');assert.equal(a.$('plan-method').value,'Retained plan note');assert.equal(a.$('review-note').value,'Retained ordinary review');
  a.$('roadmap-export').click();const exported=JSON.parse(await a.downloads.at(-1).text()),original=JSON.parse(roadmapExample());
  assert.deepEqual(exported.files,original.files);assert.deepEqual(exported.declaration_file,original.declaration_file);assert.equal(exported.results.demo.support.cost_eur.delta,-2);
  a.route('evaluation');assert.match(a.$('evaluation-scope').textContent,/1 matching hour/);
 }finally{a.close();}
});
test('handoff replacement rejects tampering and its point-power chart does not imply energy',async()=>{
 const a=await boot();try{
  a.route('data');await openRoadmapPacket(a,roadmapExample());
  const point=JSON.parse(roadmapExample()),d=JSON.parse(point.declaration_file.text);d.power_semantics='point_sample';point.declaration_file.text=JSON.stringify(d)+'\n';point.declaration_file.sha256=createHash('sha256').update(point.declaration_file.text).digest('hex');
  await openRoadmapPacket(a,JSON.stringify(point));assert.match(a.$('roadmap-comparison').textContent,/Unknown/);assert.equal(a.$('roadmap-power').querySelectorAll('polyline').length,0);assert.equal(a.$('roadmap-power').querySelectorAll('circle').length,48);assert.deepEqual([...new Set([...a.$('roadmap-power').querySelectorAll('circle')].map(el=>el.getAttribute('fill')))],['#111','#666']);
  const bad=JSON.parse(roadmapExample());bad.files.schedule.text+='tampered';await openRoadmapPacket(a,JSON.stringify(bad));
  assert.equal(a.$('roadmap-result').hidden,true);assert.equal(a.$('roadmap-export').disabled,true);assert.match(a.$('roadmap-status').textContent,/hash does not match/);assert.equal(a.w.document.activeElement.id,'roadmap-file');
 }finally{a.close();}
});

const frozenTemporal=()=>JSON.parse(fs.readFileSync(new URL('../results/temporal-water/independent-inputs-v1.json',import.meta.url),'utf8')).cases.find(row=>row.id==='retained_midpoint_deficit');
const frozenRawHandoff=()=>JSON.parse(fs.readFileSync(new URL('../results/roadmap-handoff/independent-inputs-v1.json',import.meta.url),'utf8')).cases.find(row=>row.id==='nonconsecutive_48h_shifted_equal_energy').input;
async function openRawHandoff(a,files){
 const selected=Object.values(files).reverse().map(file=>({name:file.name,size:Buffer.byteLength(file.text),arrayBuffer:async()=>new TextEncoder().encode(file.text).buffer}));
 Object.defineProperty(a.$('roadmap-file'),'files',{value:selected,configurable:true});await a.$('roadmap-file').onchange();
}
function declareRawHandoff(a,d){
 for(const [key,value]of Object.entries({'source-kind':d.source_kind,'source-label':d.source_label,offset:d.utc_offset,'power-meaning':d.power_semantics,'test-start':d.test_period.start,'test-end':d.test_period.end,threshold:d.surplus_threshold_w_m2,'comparison-rule':d.surplus_comparison,'tank-capacity':d.tank_capacity_m3,'tank-meaning':d.tank_level_semantics}))input(a,'roadmap-'+key,String(value));
 for(const key of ['units','time','links']){a.$('roadmap-confirm-'+key).checked=true;a.$('roadmap-confirm-'+key).dispatchEvent(new a.w.Event('change',{bubbles:true}));}
}
test('temporal finding leads the review and survives exact-source export and fresh recomputation',async()=>{
 const a=await boot();let b;try{
  const frozen=frozenTemporal(),packet={schema:1,kind:'measured_run_review',case_file:frozen.raw_files.case,measurement_file:frozen.raw_files.source,createdAt:'2026-10-03T00:00:00Z',note:{reviewer:'Prior reviewer',decision:'Ready for next simulation',reason:'Stale approval'},results:{temporal_water:{status:'compatible'},water_balance:{status:'inconsistent'}}};
  a.route('reviews');a.$('review-note').value='Earlier ordinary decision';await openExecution(a,packet);
  assert.equal(a.$('review-verdict-label').textContent,'Measured water evidence');assert.equal(a.$('review-verdict-title').textContent,'Water readings conflict over time');assert.match(a.$('review-verdict-detail').textContent,/No tank path within capacity/);assert.equal(a.$('review-verdict-test').hidden,true);assert.equal(a.$('review-verdict-evidence').hidden,false);assert.equal(a.$('review-note').value,'');assert.equal(a.$('decision').value,'Needs team review');
  assert.match(a.$('execution-balance').textContent,/Water residual 0 m³/);assert.match(a.$('execution-summary').textContent,/conflict over time/);
  a.w.document.querySelector('[data-review-tool="evidence"]').click();assert.equal(a.$('review-evidence-panel').open,false);a.$('review-verdict-evidence').click();assert.equal(a.$('review-evidence-panel').open,true);assert.equal(a.w.document.activeElement.id,'review-evidence-panel');
  a.$('review-note').value='Request corrected interval measurements.';a.$('decision').value='Hold for correction';a.$('download-current-review').click();const exported=JSON.parse(await a.downloads.at(-1).text());
  assert.deepEqual(exported.case_file,packet.case_file);assert.deepEqual(exported.measurement_file,packet.measurement_file);assert.equal(exported.results.temporal_water.status,'inconsistent');assert.equal(exported.results.water_balance.status,'compatible');assert.equal(exported.results.volume_stock_comparison.status,'compatible');
  exported.results.temporal_water.status='compatible';exported.results.measured.produced={lower:999999,upper:999999};
  b=await boot();b.route('reviews');b.$('review-note').value='Another stale decision';await openExecution(b,exported);assert.equal(b.$('review-verdict-title').textContent,'Water readings conflict over time');assert.equal(b.$('review-note').value,'');assert.equal(b.$('decision').value,'Needs team review');assert.doesNotMatch(b.$('execution-outcomes').textContent,/999,999/);assert.equal(b.$('execution-outcomes').textContent,a.$('execution-outcomes').textContent);
  b.$('review-note').value='New review after reopening';b.$('download-current-review').click();const reopened=JSON.parse(await b.downloads.at(-1).text());assert.equal(reopened.results.temporal_water.status,'inconsistent');assert.deepEqual(reopened.case_file,packet.case_file);assert.deepEqual(reopened.measurement_file,packet.measurement_file);assert.equal(reopened.note.reason,'New review after reopening');
  b.$('execution-clear').click();assert.equal(b.$('review-verdict-label').textContent,'Modeled water service');assert.equal(b.$('review-verdict-evidence').hidden,true);assert.equal(b.$('review-verdict-test').hidden,false);assert.equal(b.$('review-note').value,'');assert.doesNotMatch(b.$('review-verdict-title').textContent,/readings conflict/);
 }finally{b?.close();a.close();}
});
test('review headline and compact inspection follow the tested period and boundary arrows clamp both endpoints',async()=>{
 const a=await boot();try{
  a.route('resilience');input(a,'resilience-start','10');input(a,'resilience-initial','700');input(a,'resilience-demand','0');input(a,'resilience-loss','100');a.$('resilience-form').onsubmit({preventDefault(){}});const tested=await assessment(a);assert.equal(tested.selected.totals.unmet_m3,980);
  a.route('reviews');assert.equal(a.$('review-verdict-title').textContent,'980 m³ demand unserved');assert.match(a.$('review-verdict-detail').textContent,/Tested period 10:00–24:00\. .*starting water/);assert.match(a.$('review-impact').textContent,/Unserved demand980 m³/);a.$('review-inspect').open=true;
  input(a,'review-inspect-hour','10');assert.ok(a.$('review-energy-chart').querySelector('svg'));assert.match(a.$('review-boundary-values').textContent,/Tested at 10:00700m³/);
  a.$('review-boundary-prev').click();assert.equal(a.$('review-inspect-hour').value,'9');assert.match(a.$('review-boundary-values').textContent,/Tested at 09:00—m³/);
  input(a,'review-inspect-hour','0');assert.equal(a.$('review-boundary-prev').disabled,true);assert.equal(a.$('review-boundary-next').disabled,false);a.$('review-boundary-prev').onclick();assert.equal(a.$('review-inspect-hour').value,'0');a.$('review-boundary-next').click();assert.equal(a.$('review-inspect-hour').value,'1');
  input(a,'review-inspect-hour','24');assert.equal(a.$('review-boundary-next').disabled,true);assert.equal(a.$('review-boundary-prev').disabled,false);a.$('review-boundary-next').onclick();assert.equal(a.$('review-inspect-hour').value,'24');assert.match(a.$('review-boundary-values').textContent,/Tested at 24:000m³/);assert.equal(a.$('review-energy-chart').querySelectorAll('circle').length,0);a.$('review-boundary-prev').click();assert.equal(a.$('review-inspect-hour').value,'23');assert.deepEqual((await assessment(a)).inputs,tested.inputs);
 }finally{a.close();}
});
test('four raw handoff CSVs require explicit meanings and reopen without replacing ordinary contexts',async()=>{
 const a=await boot();let b;try{
  const frozen=frozenRawHandoff();await a.importCSV(oneRow());a.change('evaluation-source','imported');a.$('model-version').value='Ordinary forecast metadata';await a.importPlan(a.w.Papa.unparse(flatPlan(fixture.days[0])));a.$('inspect-candidate').click();a.$('plan-method').value='Ordinary supplied plan';a.$('review-note').value='Ordinary review note';
  const context=()=>Object.fromEntries(['date','tank','evaluation-source','plan-source','model-version','plan-method','review-note'].map(id=>[id,a.$(id).value])),before=context();
  a.route('data');a.$('analysis-task-handoff').click();await openRawHandoff(a,frozen.files);assert.equal(a.$('roadmap-result').hidden,true);assert.equal(a.$('roadmap-export').disabled,true);assert.equal(a.$('roadmap-preparation').open,true);for(const id of ['roadmap-source-kind','roadmap-offset','roadmap-power-meaning','roadmap-threshold'])assert.equal(a.$(id).value,'');
  await a.$('roadmap-form').onsubmit({preventDefault(){}});assert.match(a.$('roadmap-status').textContent,/Complete the declaration/);assert.equal(a.w.document.activeElement.id,'roadmap-source-kind');assert.equal(a.$('roadmap-export').disabled,true);
  declareRawHandoff(a,frozen.declaration);await a.$('roadmap-form').onsubmit({preventDefault(){}});assert.equal(a.$('roadmap-result').hidden,false);assert.equal(a.$('roadmap-export').disabled,false);assert.match(a.$('roadmap-comparison').textContent,/480 kWh/);assert.match(a.$('roadmap-comparison').textContent,/Declared tariff costUnknownUnknownUnknown/);assert.deepEqual(context(),before);
  a.$('roadmap-export').click();const exported=JSON.parse(await a.downloads.at(-1).text()),d=JSON.parse(exported.declaration_file.text);assert.deepEqual(exported.files,frozen.files);assert.equal(d.tariffs,null);assert.equal(d.power_semantics,'interval_mean');assert.equal(d.declared_links.weather_sha256,frozen.files.weather.sha256);assert.equal(d.declared_links.schedule_forecast_sha256,frozen.files.day_forecast.sha256);assert.equal(createHash('sha256').update(exported.declaration_file.text).digest('hex'),exported.declaration_file.sha256);assert.equal(exported.results.demo.support.electricity_kwh.delta,0);assert.equal(exported.results.demo.support.cost_eur,null);assert.equal(exported.note,undefined);
  exported.results.demo.support.electricity_kwh.normal=999999;exported.note={reviewer:'Prior reviewer',decision:'Needs team review',reason:'Old handoff note'};b=await boot();b.$('review-note').value='Fresh ordinary note';const date=b.$('date').value,tank=b.$('tank').value;await openRoadmapPacket(b,JSON.stringify(exported));assert.match(b.$('roadmap-status').textContent,/Prior note cleared/);assert.doesNotMatch(b.$('roadmap-comparison').textContent,/999,999/);assert.equal(b.$('review-note').value,'Fresh ordinary note');assert.equal(b.$('date').value,date);assert.equal(b.$('tank').value,tank);assert.equal(b.$('evaluation-source').value,'frozen');assert.equal(b.$('plan-source').value,'frozen');
  b.$('roadmap-export').click();const reopened=JSON.parse(await b.downloads.at(-1).text());assert.deepEqual(reopened.files,frozen.files);assert.deepEqual(reopened.declaration_file,exported.declaration_file);assert.equal(reopened.results.demo.support.electricity_kwh.normal,480);assert.equal(reopened.note,undefined);
 }finally{b?.close();a.close();}
});
test('self-contained raw handoff intake remains usable when the retained reference manifest fails',async()=>{
 const a=await boot({}, {'manifest.json':JSON.stringify({data_sha256:'bad'})});try{
  const frozen=frozenRawHandoff();assert.equal(a.$('download').disabled,true);assert.equal(a.$('handoff-file').disabled,true);a.route('data');a.$('analysis-task-handoff').click();assert.equal(a.$('roadmap-file').disabled,false);assert.equal(a.$('view-data').querySelector('.unavailable').hidden,true);
  await openRawHandoff(a,frozen.files);declareRawHandoff(a,frozen.declaration);await a.$('roadmap-form').onsubmit({preventDefault(){}});assert.equal(a.$('roadmap-result').hidden,false);assert.equal(a.$('roadmap-export').disabled,false);assert.match(a.$('roadmap-comparison').textContent,/480 kWh/);a.$('roadmap-export').click();assert.equal(JSON.parse(await a.downloads.at(-1).text()).results.demo.support.electricity_kwh.normal,480);assert.equal(a.$('download').disabled,true);assert.equal(a.$('handoff-file').disabled,true);
  a.route('evaluation');assert.equal(a.$('view-evaluation').querySelector('.unavailable').hidden,false);a.route('data');assert.equal(a.$('roadmap-result').hidden,false);assert.equal(a.$('view-data').querySelector('.unavailable').hidden,true);
 }finally{a.close();}
});
test('in-content route actions move keyboard focus to the visible destination',async()=>{
 const a=await boot();try{
  a.route('reviews');const testAction=a.$('review-verdict-test');testAction.focus();testAction.click();assert.equal(a.$('view-resilience').hidden,false);assert.equal(a.w.document.activeElement.id,'resilience-demand');assert.equal(a.$('assessment-workbench').dataset.mode,'conditions');assert.equal(a.w.document.activeElement.closest('[hidden]'),null);
  a.$('resilience-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));assert.equal(a.$('assessment-workbench').dataset.mode,'result');assert.equal(a.w.document.activeElement.id,'resilience-verdict');
  const decisionAction=a.$('view-resilience').querySelector('[data-route="reviews"]');decisionAction.focus();decisionAction.click();assert.equal(a.$('view-reviews').hidden,false);assert.equal(a.w.document.activeElement.id,'views');
  a.route('scenarios');a.$('scenario-tab-imported').click();const fileAction=a.$('view-scenarios').querySelector('[data-route="data"][data-intake="plan"]');fileAction.focus();fileAction.click();assert.equal(a.$('view-data').hidden,false);assert.equal(a.$('analysis-pane-plan').hidden,false);assert.equal(a.w.document.activeElement.id,'views');assert.equal(a.w.document.activeElement.closest('[hidden]'),null);
 }finally{a.close();}
});

function pairedDailyCase({production=[2,0],returned=[0,2],demand=[0,4],capacity=2,reserve=0,initial=0,target=0}={}){
 const values=list=>Array.from({length:24},(_,h)=>list[h]??0),times=Array.from({length:24},(_,h)=>new Date(Date.parse('2026-07-01T00:00:00Z')+h*3600000).toISOString());
 const c={schema:1,kind:'fixed_plan_revision_case',assessment:{schema:1,kind:'fixed_plan_consequence_assessment',identity:{data_sha256:JSON.parse(read('manifest.json')).data_sha256},inputs:{times,production:values(production),demand:values(demand),capacity,reserve,initial,target}},unit_capacity_m3_h:4,specific_energy_kwh_m3:1};
 const raw='\uFEFF'+JSON.stringify(c,null,2).replaceAll('\n','\r\n'),hash=createHash('sha256').update(raw).digest('hex'),csv='case_sha256,time,production_m3\r\n'+times.map((time,h)=>`${hash},${time},${returned[h]??0}`).join('\r\n')+'\r\n';
 return {raw,csv};
}
async function openPairedDaily(a,options){const files=pairedDailyCase(options);a.route('reviews');a.$('review-tab-revision').click();await a.importRevision('revision-case-file',files.raw,'illustrative-case.json');assert.equal(a.$('revision-template').disabled,false,a.$('revision-case-status').textContent);await a.importRevision('revision-proposal-file',files.csv,'supplied-alternative.csv');assert.equal(a.$('revision-result').hidden,false,a.$('revision-proposal-status').textContent);return files;}

test('paired service finds an intra-hour loss despite identical hourly totals and recomputes exact files on reopen',async()=>{
 const a=await boot();try{
  const files=await openPairedDaily(a);assert.match(a.$('revision-service-heading').textContent,/service|shortfall|water/i);assert.equal(a.$('revision-service-inspect').hidden,false);
  a.$('revision-service-inspect').click();assert.equal(a.$('revision-inspect-hour').value,'1');assert.equal(a.w.document.activeElement.id,'revision-inspect');assert.ok(a.$('revision-inspect').open);
  input(a,'revision-note','Review the newly underserved half-hour.');input(a,'revision-decision','Ready for next simulation');submit(a);const saved=JSON.parse(await a.downloads.at(-1).text());
  assert.equal(saved.case_file.text,files.raw);assert.equal(saved.proposal_file.text,files.csv);const s=saved.comparison.water_service;
  assert.equal(s.status,'regression_detected');assert.equal(s.criteria.delivery_no_worse,false);assert.equal(s.delivery.shifted_shortfall_m3.value,1);assert.equal(s.delivery.first.start_hour.value,1);assert.equal(s.delivery.first.end_hour.value,1.5);assert.equal(saved.comparison.changes.unmet_m3,0);
  saved.comparison.water_service={status:'no_modeled_regression'};saved.comparison.revised.result.totals.unmet_m3=0;
  await a.importRevision('revision-case-file',JSON.stringify(saved),'historical-review.json');assert.equal(a.$('revision-note').value,'');assert.equal(a.$('revision-decision').value,'Needs team review');assert.match(a.$('revision-review-status').textContent,/regression|service|recalculated/i);
  input(a,'revision-note','Recomputed from the retained supplied files.');submit(a);const reopened=JSON.parse(await a.downloads.at(-1).text());assert.equal(reopened.case_file.text,files.raw);assert.equal(reopened.proposal_file.text,files.csv);assert.deepEqual(reopened.comparison.water_service,s);
 }finally{a.close();}
});

test('paired reserve hinge leads the return finding even when whole-period reserve and end stock improve',async()=>{
 const a=await boot();try{
  await openPairedDaily(a,{production:[3,0],returned:[1.5,2],demand:[3,3],capacity:6,reserve:1,initial:3});
  assert.match(a.$('revision-service-heading').textContent,/reserve/i);a.$('revision-service-inspect').click();assert.equal(a.$('revision-inspect-hour').value,'1');assert.equal(a.w.document.activeElement.id,'revision-inspect');
  input(a,'revision-note','Inspect the interior reserve deficit.');submit(a);const c=JSON.parse(await a.downloads.at(-1).text()).comparison;assert.equal(c.changes.unmet_m3,0);assert.equal(c.changes.final_storage_m3,.5);assert.equal(c.changes.max_reserve_deficit_m3,-.5);assert.equal(c.water_service.criteria.reserve_no_worse,false);assert.deepEqual(c.water_service.reserve.max_added_deficit_m3.exact,{numerator:'1',denominator:'6'});assert.equal(c.water_service.reserve.maximum.peak_hour.value,5/3);
 }finally{a.close();}
});

test('paired end stock distinguishes a stock-funded energy reduction from preserving modeled service',async()=>{
 const a=await boot();try{
  await openPairedDaily(a,{production:[1],returned:[0],demand:[1],capacity:2,initial:1});assert.match(a.$('revision-service-heading').textContent,/stock|inventory/i);
  input(a,'revision-note','Both meet demand, but the return spends ending stock.');submit(a);const c=JSON.parse(await a.downloads.at(-1).text()).comparison;assert.equal(c.changes.modeled_production_energy_kwh,-1);assert.equal(c.changes.unmet_m3,0);assert.equal(c.revised.result.totals.terminal_deficit_m3,0);assert.equal(c.water_service.criteria.delivery_no_worse,true);assert.equal(c.water_service.criteria.end_stock_no_lower,false);assert.equal(c.water_service.end_stock.delta_m3.value,-1);
 }finally{a.close();}
});

test('continuous paired service routes the subhour witness across midnight and qualifies favorable solar use',async()=>{
 const a=await boot();try{
  const source=joinedSource();Object.assign(source.inputs,{capacity:2,reserve:0,initial:0,target:0});source.inputs.blocks.forEach(b=>{b.production=Array(24).fill(0);b.demand=Array(24).fill(0);});source.inputs.blocks[0].production[23]=2;source.inputs.blocks[1].demand[0]=4;
  const frozen=await joinedCase(a,source),returned=await joinedReturn(a,frozen.csvText,{23:0,24:2});let saved=await joinedExport(a);const s=saved.results.water_service;assert.equal(s.criteria.delivery_no_worse,false);assert.equal(s.delivery.first.start_hour.value,24);assert.equal(s.delivery.first.end_hour.value,24.5);assert.equal(saved.results.changes.unmet_m3,0);
  a.$('sequence-service-inspect').click();assert.equal(a.$('sequence-day').value,'1');assert.equal(a.w.document.activeElement.id,'sequence-service-proof');
  const start='2026-07-01T00:00:00.000Z',mid='2026-07-02T00:00:00.000Z',after='2026-07-02T01:00:00.000Z',end='2026-07-03T00:00:00.000Z';
  const p=joinedProfile(saved,{intervals:[{start,end:mid,available_at:start,power_kw:0},{start:mid,end:after,available_at:start,power_kw:2},{start:after,end,available_at:start,power_kw:0}]});await joinedFile(a,'sequence-solar-file',JSON.stringify(p),'illustrative-solar.json');saved=await joinedExport(a);assert.equal(saved.results.solar.totals.delta_solar_kwh,2);assert.match(a.$('sequence-solar-conclusion').textContent,/Water comparison fails on delivery/);
  saved.results.water_service={status:'no_modeled_regression'};await sequenceFile(a,JSON.stringify(saved),'continuous-review.json');const reopened=await joinedExport(a);assert.equal(reopened.case_file.text,frozen.caseText);assert.equal(reopened.proposal_file.text,returned);assert.deepEqual(reopened.results.water_service,s);
 }finally{a.close();}
});

test('identical undersupplied alternatives distinguish no new loss from adequate water service',async()=>{
 const a=await boot();try{
  await openPairedDaily(a,{production:[0],returned:[0],demand:[1],capacity:2});assert.match(a.$('revision-service-heading').textContent,/no|retained|preserved/i);assert.match(a.$('revision-service-detail').textContent,/unserved|unmet|adequate|absolute/i);
  input(a,'revision-note','Neither alternative supplies the requested water.');submit(a);const c=JSON.parse(await a.downloads.at(-1).text()).comparison;assert.equal(c.water_service.status,'no_modeled_regression');assert.equal(c.original.result.totals.unmet_m3,1);assert.equal(c.revised.result.totals.unmet_m3,1);assert.ok(Object.values(c.water_service.criteria).every(Boolean));
 }finally{a.close();}
});

test('continuous exact service comparison carries a sub-display reserve loss through midnight without rounded reseeding',async()=>{
 const a=await boot();try{
  const source=joinedSource();Object.assign(source.inputs,{capacity:1e10,reserve:1e10,initial:1e10,target:1e10});source.inputs.blocks.forEach(b=>{b.production=Array(24).fill(0);b.demand=Array(24).fill(0);});source.inputs.blocks[0].production[23]=1e-8;source.inputs.blocks[0].demand[23]=1e-8;
  const c=await joinedCase(a,source);await joinedReturn(a,c.csvText,{23:0,24:1e-8});const r=await joinedExport(a),s=r.results.water_service;
  assert.equal(r.results.changes.max_reserve_deficit_m3,0);assert.equal(r.results.changes.final_storage_m3,0);assert.equal(s.criteria.reserve_no_worse,false);assert.equal(s.reserve.max_added_deficit_m3.value,1e-8);assert.equal(s.reserve.first.start_hour.value,23);assert.equal(s.reserve.first.end_hour.value,25);assert.equal(s.reserve.maximum.peak_hour.value,24);assert.equal(s.end_stock.delta_m3.value,0);assert.match(a.$('sequence-service-heading').textContent,/reserve/i);
 }finally{a.close();}
});

test('empty returned review provides a working test path before offering a tested plan',async()=>{
 const a=await boot();try{a.route('reviews');a.$('review-tab-revision').click();assert.equal(a.$('revision-current').hidden,true);assert.equal(a.$('revision-test-plan').hidden,false);a.$('revision-test-plan').click();assert.equal(a.$('view-resilience').hidden,false);assert.equal(a.w.document.activeElement.id,'resilience-demand');assert.equal(a.$('assessment-workbench').dataset.mode,'conditions');a.$('resilience-form').onsubmit({preventDefault(){}});assert.equal(a.$('assessment-workbench').dataset.mode,'result');assert.equal(a.w.document.activeElement.id,'resilience-verdict');a.route('reviews');a.$('review-tab-revision').click();assert.equal(a.$('revision-current').hidden,false);assert.equal(a.$('revision-test-plan').hidden,true);await a.$('revision-current').onclick();assert.equal(a.$('revision-case-export').disabled,false);}finally{a.close();}
});

test('returned chart measures its visible canvas and redraws without resetting inspection',async()=>{
 const a=await boot();try{let width=980;const chart=a.$('revision-inventory-chart');Object.defineProperty(chart,'clientWidth',{configurable:true,get:()=>chart.closest('[hidden]')?0:width});await openPairedDaily(a);assert.equal(Number(chart.querySelector('svg').getAttribute('viewBox').split(' ')[2]),980);input(a,'revision-inspect-hour','13');width=342;a.route('reviews');assert.equal(Number(chart.querySelector('svg').getAttribute('viewBox').split(' ')[2]),342);assert.equal(a.$('revision-inspect-hour').value,'13');assert.equal(a.$('revision-service-heading').textContent,'Water delivery reduced');}finally{a.close();}
});

test('compact system exposes selectable assets and retains keyboard focus after redraw',async()=>{
 const a=await boot();try{Object.defineProperty(a.$('topology'),'clientWidth',{configurable:true,value:354});a.route('overview');assert.equal(a.$('topology').querySelector('svg').getAttribute('viewBox'),'0 0 340 355');assert.equal(a.$('topology').querySelector('svg').getAttribute('role'),'group');for(const asset of ['unit','garden','tank']){const node=a.$('topology').querySelector(`[data-asset="${asset}"]`);node.focus();node.dispatchEvent(new a.w.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));assert.notEqual(a.w.document.activeElement,node);assert.equal(a.w.document.activeElement.dataset.asset,asset);assert.equal(a.w.document.activeElement.isConnected,true);assert.equal(a.w.document.querySelector('.asset-buttons .selected').dataset.asset,asset);}assert.match(a.$('asset-inspector').textContent,/4,000 m³/);}finally{a.close();}
});


test('compact review disclosures preserve case, inspection, draft and exported findings',async()=>{
 const a=await boot();try{
  a.route('reviews');a.$('review-inspect').open=true;input(a,'review-inspect-hour','17');
  a.$('review-actions').open=true;a.click('[data-review-tool="decision"]');assert.equal(a.$('review-actions').open,false);
  a.$('review-note').value='Keep this draft and selected boundary.';a.$('download-current-review').click();const before=JSON.parse(await a.downloads.at(-1).text());
  a.$('review-inspect').open=false;a.$('review-actions').open=true;a.click('[data-review-tool="history"]');
  assert.equal(a.w.document.activeElement.id,'review-history-panel');assert.equal(a.$('review-history-panel').open,true);assert.equal(a.$('review-actions').open,false);
  a.$('review-actions').open=true;a.w.document.dispatchEvent(new a.w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));assert.equal(a.$('review-actions').open,false);assert.equal(a.w.document.activeElement,a.$('review-actions').querySelector('summary'));
  a.$('review-tab-revision').click();assert.equal(a.$('review-plan-selection').hidden,true);a.$('review-tab-current').click();
  a.route('operations');a.route('reviews');a.$('review-inspect').open=true;assert.equal(a.$('review-inspect-hour').value,'17');assert.equal(a.$('review-note').value,'Keep this draft and selected boundary.');
  a.$('download-current-review').click();const after=JSON.parse(await a.downloads.at(-1).text());
  assert.deepEqual(after.hourly,before.hourly);assert.deepEqual(after.totals,before.totals);assert.deepEqual(after.analysis,before.analysis);assert.deepEqual(after.planProvenance,before.planProvenance);assert.equal(after.note,before.note);
 }finally{a.close();}
});

test('hourly electricity integrates a fractional outage and shares inventory time coordinates',async()=>{
 const a=await boot();try{
  a.route('resilience');input(a,'resilience-outage','12');input(a,'resilience-duration','0.25');a.$('resilience-form').onsubmit({preventDefault(){}});const result=await assessment(a),production=result.selected.rows.find(r=>r.hour===12).available_production_m3;
  const requested=result.inputs.production[12];assert.ok(requested>0);assert.equal(production,requested*.75);
  a.route('reviews');const energy=a.$('review-energy-chart').querySelector('svg'),paths=energy.querySelectorAll('polyline'),points=paths[1].getAttribute('points').split(' ').map(p=>p.split(',').map(Number));
  const source=fixture.days.find(d=>d.date===a.$('date').value).schedules[a.$('tank').value].production,max=Math.max(...source.map(v=>v*fixture.kwh_per_m3))*1.08;
  const plot=energy.querySelector('rect'),top=Number(plot.getAttribute('y')),height=Number(plot.getAttribute('height'));assert.ok(Math.abs(points[24][1]-(top+height-production*fixture.kwh_per_m3/max*height))<1e-9);
  const inventory=a.$('review-inventory-chart').querySelector('polyline').getAttribute('points').split(' ').map(p=>p.split(',').map(Number));assert.equal(points[24][0],inventory[12][0]);assert.equal(points.at(-1)[0],inventory.at(-1)[0]);
  a.$('review-inspect').open=true;input(a,'review-inspect-hour','24');assert.equal(a.$('review-energy-chart').querySelectorAll('circle').length,0);assert.equal(a.$('review-inspect-time').textContent,'24:00');
 }finally{a.close();}
});

test('built-in returned example recalculates retained evidence and exposes water loss alongside solar gain',async()=>{
 const a=await boot();try{
  a.route('reviews');a.$('review-note').value='Keep ordinary work.';a.$('review-tab-revision').click();await a.$('revision-example').onclick();
  assert.equal(a.$('revision-result').hidden,false);assert.equal(a.$('revision-service-heading').textContent,'Water delivery reduced');assert.match(a.$('revision-service-detail').textContent,/Added shortfall: 1 m³/);
  assert.match(a.$('revision-impact-shortfall').textContent,/1 m³/);assert.match(a.$('revision-impact-solar').textContent,/\+2 kWh/);assert.match(a.$('revision-solar-timing').textContent,/not a service-preserving energy gain/);
  assert.match(a.$('revision-first-interval').textContent,/13:00.*13:30/);assert.ok(a.$('revision-inventory-chart').querySelector('.finding-window'));assert.ok(a.$('revision-energy-chart').querySelector('svg'));
  assert.equal(a.$('date').value,'2026-07-15');assert.equal(a.$('tank').value,'4000');assert.equal(a.$('review-note').value,'Keep ordinary work.');
  a.$('revision-note').value='Request correction: the solar gain displaces water delivery.';a.$('revision-review-export').click();const exported=JSON.parse(await a.downloads.at(-1).text()),source=JSON.parse(read('data/returned-water-example.json'));
  assert.deepEqual(exported.case_file,source.case_file);assert.deepEqual(exported.proposal_file,source.proposal_file);assert.deepEqual(exported.solar_file,source.solar_file);assert.equal(exported.comparison.water_service.delivery.shifted_shortfall_m3.value,1);assert.equal(exported.solar_comparison.totals.delta_solar_kwh,2);
 }finally{a.close();}
});


test('compact navigation exposes pages on request and restores focus without changing review drafts',async()=>{
 const a=await boot();try{
  a.w.innerWidth=697;a.w.dispatchEvent(new a.w.Event('resize'));
  a.$('review-note').value='Retain the selected review.';const parent=a.w.document.querySelector('[data-workspace="plans"]');
  assert.equal(parent.getAttribute('aria-expanded'),'false');assert.equal(a.$('navigation-plans').hidden,true);
  a.$('workspace-toggle').click();assert.equal(parent.getAttribute('aria-expanded'),'true');assert.equal(a.$('navigation-plans').hidden,false);await new Promise(r=>setTimeout(r,180));assert.equal(a.$('navigation-plans').hidden,false);parent.focus();a.w.document.dispatchEvent(new a.w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  assert.equal(parent.getAttribute('aria-expanded'),'false');assert.equal(a.$('navigation-plans').hidden,true);assert.equal(a.w.document.activeElement,a.$('workspace-toggle'));
  a.$('workspace-toggle').click();a.route('operations');assert.equal(a.w.document.body.classList.contains('navigation-open'),false);assert.equal(a.$('navigation-plans').hidden,true);assert.equal(a.w.document.activeElement.id,'views');
  a.$('workspace-toggle').click();a.route('reviews');assert.equal(a.$('review-note').value,'Retain the selected review.');
  a.$('review-actions').open=true;a.$('workspace-handoff').click();assert.equal(a.$('analysis-pane-handoff').hidden,false);assert.equal(a.w.document.activeElement.id,'views');
 }finally{a.close();}
});

test('late built-in example cannot overwrite a newer returned case and tampered example bytes are rejected',async()=>{
 let release;const pending=new Promise(resolve=>{release=resolve;});const a=await boot({}, {'./data/returned-water-example.json':pending});let b;try{
  a.route('reviews');a.$('review-tab-revision').click();const opening=a.$('revision-example').onclick(),raw=read('data/returned-water-example.json'),packet=JSON.parse(raw);
  await a.importRevision('revision-case-file',packet.case_file.text,'newer-case.json');const caseIdentity=a.$('revision-identity').textContent;
  release(raw);await opening;assert.equal(a.$('revision-result').hidden,true);assert.equal(a.$('revision-identity').textContent,caseIdentity);assert.match(caseIdentity,/newer-case.json/);
  packet.proposal_file.text+='changed';b=await boot({}, {'./data/returned-water-example.json':JSON.stringify(packet)});b.$('review-tab-revision').click();await b.$('revision-example').onclick();
  assert.equal(b.$('revision-result').hidden,true);assert.match(b.$('revision-case-status').textContent,/hash does not match/);assert.equal(b.$('revision-review-export').disabled,true);
 }finally{b?.close();a.close();}
});


test('measured evidence keeps modeled outcomes distinct and large finite energy retains a finite chart scale',async()=>{
 for(const sec of [null,1.7e308]){const a=await boot();try{
  const packet=executionPacket({caseChange:c=>{c.specific_energy_kwh_m3=sec;c.input.production.fill(0);c.input.production[0]=1;c.input.demand=0;}});
  await openExecution(a,packet);assert.equal(a.$('review-verdict-label').textContent,'Measured water evidence');assert.equal(a.$('review-impact').hidden,true);
  if(sec===null){assert.match(a.$('review-energy-chart').textContent,/unknown.*specific energy/i);assert.equal(a.$('review-energy-chart').querySelector('svg'),null);}
  else {const chart=a.$('review-energy-chart');assert.doesNotMatch(chart.innerHTML,/Infinity|NaN/);const points=chart.querySelector('polyline').getAttribute('points').split(' ').map(p=>p.split(',').map(Number));assert.ok(points.flat().every(Number.isFinite));assert.ok(points[0][1]<30);assert.equal(chart.querySelectorAll('circle').length,0);}
  a.$('review-actions').open=true;a.click('[data-review-tool="evidence"]');assert.equal(a.$('review-evidence-panel').open,false);assert.equal(a.w.document.activeElement,a.$('review-actions').querySelector('summary'));
 }finally{a.close();}}
});
test('continuous production-budget review recomputes exact proof and clears it with changed conditions',async()=>{
 const a=await boot();try{
  const saved=await sequenceReview(a,'2026-09-30'),originalSource=saved.source_file.text,b=saved.results.selected.water_budget;
  assert.equal(b.additional_production_required_m3.value,26496);assert.equal(b.unavoidable_unserved_m3.value,24496);assert.equal(saved.results.control.water_budget.additional_production_required_m3.value,26496);
  assert.equal(a.$('sequence-budget-finding').hidden,false);assert.match(a.$('sequence-budget-finding').textContent,/26,496 m³ more starting water/);assert.equal(a.$('sequence-budget-proof').closest('details').id,'sequence-accounting-details');assert.equal(a.$('sequence-accounting-details').open,false);assert.match(a.$('sequence-budget-proof').textContent,/24496/);
  saved.results.selected.water_budget={status:'budget_not_excluded'};saved.results.control.water_budget.additional_production_required_m3={value:0,exact:{numerator:'0',denominator:'1'}};saved.decision='Request revised sequence';saved.reason='Old budget note';saved.reviewer='Loucas';
  await sequenceFile(a,JSON.stringify(saved),'forged-budget-review.json');const reopened=await joinedExport(a);
  assert.deepEqual(reopened.results.selected.water_budget,b);assert.equal(reopened.results.control.water_budget.additional_production_required_m3.value,26496);assert.equal(reopened.source_file.text,originalSource);assert.equal(a.$('sequence-reason').value,'');assert.equal(a.$('sequence-decision-value').value,'Needs team review');
  input(a,'sequence-demand','0');assert.equal(a.$('sequence-budget-finding').hidden,true);assert.equal(a.$('sequence-budget-finding').textContent,'');assert.equal(a.$('sequence-budget-proof').textContent,'');assert.equal(a.$('sequence-export').disabled,true);
  await a.$('sequence-form').onsubmit({preventDefault(){}});assert.equal(a.$('sequence-budget-finding').hidden,false);assert.match(a.$('sequence-budget-finding').textContent,/requirements without spill/);const nominal=await joinedExport(a);assert.equal(nominal.results.selected.water_budget.status,'budget_not_excluded');assert.match(a.$('sequence-accounting-details').textContent,/zero gap does not establish feasible timing/);assert.match(a.$('sequence-accounting-details').textContent,/fixed available output after derating and outages/);assert.match(a.$('sequence-accounting-details').textContent,/different outage exposure can change output and are not ruled out/);
 }finally{a.close();}
});

test('returned continuous plan exports both budgets and never restores a forged production finding',async()=>{
 const a=await boot();try{
  const source=joinedSource(1),c=await joinedCase(a,source),returned=await joinedReturn(a,c.csvText,{0:0}),saved=await joinedExport(a);
  assert.equal(saved.results.water_budget.original.status,'budget_not_excluded');assert.equal(saved.results.water_budget.returned.additional_production_required_m3.value,1);assert.equal(saved.results.water_budget.returned.unavoidable_unserved_m3.value,0);assert.match(a.$('sequence-budget-finding').textContent,/Returned plan:.*1 m³ more starting water/);
  saved.results.water_budget.returned={status:'budget_not_excluded'};saved.decision='Request revised sequence';saved.reason='Stale target conclusion';saved.reviewer='Loucas';await sequenceFile(a,JSON.stringify(saved),'returned-budget.json');const opened=await joinedExport(a);
  assert.equal(opened.results.water_budget.returned.additional_production_required_m3.value,1);assert.equal(opened.case_file.text,c.caseText);assert.equal(opened.proposal_file.text,returned);assert.equal(a.$('sequence-reason').value,'');assert.equal(a.$('sequence-budget-finding').hidden,false);
  a.$('sequence-return-remove').click();assert.equal(a.$('sequence-budget-finding').hidden,false);assert.match(a.$('sequence-budget-finding').textContent,/requirements without spill/);assert.equal((await joinedExport(a)).results.selected.water_budget.status,'budget_not_excluded');
 }finally{a.close();}
});


test('direct chart inspection shares water and electricity boundaries without changing the plan',async()=>{
 const a=await boot();try{
  a.route('reviews');a.$('review-note').value='Retain the plan and draft.';a.$('download-current-review').click();const before=JSON.parse(await a.downloads.at(-1).text());
  for(const id of ['review-inventory-chart','review-energy-chart']){
   const svg=a.$(id).querySelector('svg'),width=Number(svg.getAttribute('viewBox').split(' ')[2]);svg.getBoundingClientRect=()=>({left:100,width:width/2});
   const x=100+(54+(width-54-17)*.5)/2;svg.dispatchEvent(new a.w.MouseEvent('click',{bubbles:true,clientX:x}));
   assert.equal(a.$('review-inspect').open,true);assert.equal(a.$('review-inspect-hour').value,'12');assert.match(a.$('review-boundary-values').textContent,/Plan at 12:00/);
   const origins=['review-inventory-chart','review-energy-chart'].map(chart=>Number(a.$(chart).querySelector('svg line').getAttribute('x1')));assert.equal(origins[0],origins[1]);
  }
  a.$('download-current-review').click();const after=JSON.parse(await a.downloads.at(-1).text());assert.deepEqual(after.hourly,before.hourly);assert.deepEqual(after.totals,before.totals);assert.equal(after.note,before.note);
 }finally{a.close();}
});

test('keyboard chart inspection opens the inspector and clamps to both terminal boundaries',async()=>{
 const a=await boot();try{
  a.route('reviews');const chart=a.$('review-inventory-chart'),key=value=>chart.dispatchEvent(new a.w.KeyboardEvent('keydown',{key:value,bubbles:true,cancelable:true}));
  key('Enter');assert.equal(a.$('review-inspect').open,true);assert.equal(a.$('review-inspect-hour').value,'13');
  for(let i=0;i<30;i++)key('ArrowRight');assert.equal(a.$('review-inspect-hour').value,'24');assert.equal(a.$('review-boundary-next').disabled,true);assert.match(a.$('review-inspect-time').textContent,/24:00/);
  for(let i=0;i<30;i++)key('ArrowLeft');assert.equal(a.$('review-inspect-hour').value,'0');assert.equal(a.$('review-boundary-prev').disabled,true);
  a.$('review-inspect').open=false;key(' ');assert.equal(a.$('review-inspect').open,true);assert.equal(a.$('review-inspect-hour').value,'0');
 }finally{a.close();}
});

test('product home explains the concept and entering or returning preserves the active review draft',async()=>{
 const a=await boot({}, {},webcrypto,'');try{
  assert.equal(a.w.document.body.dataset.view,'home');assert.equal(a.$('product-home').hidden,false);assert.match(a.$('product-home').textContent,/curtail/i);assert.match(a.$('product-home').textContent,/water/i);
  a.click('#product-home [data-route="reviews"]');assert.equal(a.w.location.hash,'#reviews');assert.equal(a.$('product-home').hidden,true);for(let i=0;i<100&&a.w.document.body.dataset.ready!=='true';i++)await new Promise(r=>setTimeout(r,5));assert.equal(a.$('workspace-loader').hidden,true);
  a.change('tank','1000');a.$('review-note').value='Keep this working review while I inspect the product guide.';
  a.w.location.hash='home-workflow';a.w.dispatchEvent(new a.w.HashChangeEvent('hashchange'));assert.equal(a.w.document.body.dataset.view,'home');assert.equal(a.$('product-home').hidden,false);
  a.click('#product-home [data-route="reviews"]');assert.equal(a.$('tank').value,'1000');assert.equal(a.$('review-note').value,'Keep this working review while I inspect the product guide.');assert.equal(a.$('view-reviews').hidden,false);
 }finally{a.close();}
});
test('loading reflects pending reference input and opening the product guide does not cancel its selected task',async()=>{
 let release;const delayed=new Promise(resolve=>{release=resolve;});const a=await boot({}, {'data.json':delayed},webcrypto,'#reviews');try{
  assert.equal(a.w.document.body.dataset.ready,'false');assert.equal(a.$('workspace-loader').hidden,false);assert.equal(a.$('download').disabled,true);
  a.w.location.hash='home';a.w.dispatchEvent(new a.w.HashChangeEvent('hashchange'));assert.equal(a.$('product-home').hidden,false);
  a.click('#product-home [data-route="data"]');assert.equal(a.w.document.body.dataset.view,'data');
  release(read('data.json'));for(let i=0;i<100&&a.w.document.body.dataset.ready!=='true';i++)await new Promise(r=>setTimeout(r,5));
  assert.equal(a.w.document.body.dataset.ready,'true');assert.equal(a.$('workspace-loader').hidden,true);assert.equal(a.w.location.hash,'#data');assert.equal(a.$('view-data').hidden,false);assert.equal(a.$('download').disabled,false);
 }finally{a.close();}
});
test('failed reference identity ends the loading screen and retains an explicit unavailable workspace',async()=>{
 const manifest=JSON.parse(read('manifest.json'));manifest.data_sha256='0'.repeat(64);const a=await boot({}, {'manifest.json':JSON.stringify(manifest)},webcrypto,'#reviews');try{
  assert.equal(a.w.document.body.dataset.ready,'failed');assert.equal(a.$('workspace-loader').hidden,true);assert.match(a.$('status').textContent,/Dataset identity does not match/);assert.equal(a.$('download').disabled,true);assert.equal(a.$('view-reviews').querySelector('.unavailable').hidden,false);
 }finally{a.close();}
});
test('forecast diagnostics redraw at their visible width when a hidden monthly pane opens',async()=>{
 const a=await boot();try{
  const chart=a.$('month-error-chart'),pane=a.$('diagnostic-pane-monthly');chart.getBoundingClientRect=()=>({width:pane.hidden?0:334});
  a.$('forecast-chart').getBoundingClientRect=()=>({width:520});a.route('evaluation');
  assert.equal(a.$('forecast-chart').querySelector('svg').getAttribute('viewBox').split(' ')[2],'520');
  assert.equal(chart.querySelector('svg').getAttribute('viewBox').split(' ')[2],'680');
  a.$('diagnostic-task-monthly').click();assert.equal(pane.hidden,false);assert.equal(chart.querySelector('svg').getAttribute('viewBox').split(' ')[2],'334');
  assert.deepEqual([...chart.querySelectorAll('text')].slice(-3).map(t=>t.textContent),['07','08','09']);assert.ok(chart.querySelectorAll('rect').length>=6);
 }finally{a.close();}
});
test('reference loading preserves an active home answer and the empty-root navigation entry',async()=>{
 let release;const pending=new Promise(resolve=>{release=resolve;});const a=await boot({}, {'data.json':pending},webcrypto,'#reviews');try{
  a.w.location.hash='';a.w.dispatchEvent(new a.w.HashChangeEvent('hashchange'));const answer=a.w.document.querySelector('.home-questions details'),summary=answer.querySelector('summary');answer.open=true;summary.focus();
  assert.equal(a.w.location.hash,'');release(read('data.json'));for(let i=0;i<100&&a.w.document.body.dataset.ready!=='true';i++)await new Promise(r=>setTimeout(r,5));
  assert.equal(a.w.document.body.dataset.ready,'true');assert.equal(a.w.document.activeElement,summary);assert.equal(answer.open,true);assert.equal(a.w.location.hash,'');
  a.click('#product-home [data-route="reviews"]');a.w.location.hash='';a.w.dispatchEvent(new a.w.HashChangeEvent('hashchange'));assert.equal(a.w.document.body.dataset.view,'home');assert.equal(a.w.location.hash,'');
 }finally{a.close();}
});
test('opening a reference chart disclosure redraws labels at the now-visible width',async()=>{
 const a=await boot();try{
  a.route('overview');const chart=a.$('weather-chart'),details=chart.closest('details');chart.getBoundingClientRect=()=>({width:details.open?334:0});
  a.change('date','2026-07-01');assert.equal(chart.querySelector('svg').getAttribute('viewBox').split(' ')[2],'680');
  details.open=true;await new Promise(r=>setTimeout(r,25));assert.equal(chart.querySelector('svg').getAttribute('viewBox').split(' ')[2],'334');
  const labels=[...chart.querySelectorAll('text')].map(t=>t.textContent);assert.ok(labels.includes('00:00'));assert.ok(labels.includes('23:00'));
 }finally{a.close();}
});

test('self-contained handoff and observation intake remain available during pending reference loading',async()=>{
 let release;const pending=new Promise(resolve=>{release=resolve;});const a=await boot({}, {'data.json':pending},webcrypto,'');try{
  assert.equal(a.w.document.body.dataset.ready,'false');assert.equal(a.$('workspace-loader').hidden,true);assert.equal(a.$('date').options.length,0);
  a.click('#product-home [data-route="data"][data-intake="handoff"]');assert.equal(a.w.document.body.dataset.independent,'true');assert.equal(a.$('workspace-loader').hidden,true);assert.equal(a.$('analysis-pane-handoff').hidden,false);assert.equal(a.$('view-data').querySelector('.unavailable').hidden,true);
  a.route('pilot');assert.equal(a.$('workspace-loader').hidden,true);assert.equal(a.$('pilot-example').disabled,false);await a.$('pilot-example').onclick();assert.match(a.$('pilot-kpis').textContent,/15 \/ 16/);
  a.route('reviews');assert.equal(a.$('workspace-loader').hidden,false);assert.equal(a.w.document.body.dataset.independent,'false');release(read('data.json'));for(let i=0;i<100&&a.w.document.body.dataset.ready!=='true';i++)await new Promise(r=>setTimeout(r,5));assert.equal(a.$('workspace-loader').hidden,true);assert.equal(a.w.location.hash,'#reviews');
 }finally{a.close();}
});
test('reference failure retains the active self-contained handoff without a false disabled message',async()=>{
 let release;const pending=new Promise(resolve=>{release=resolve;});const a=await boot({}, {'data.json':pending,'manifest.json':JSON.stringify({data_sha256:'bad'})},webcrypto,'');try{
  a.click('#product-home [data-route="data"][data-intake="handoff"]');release(read('data.json'));for(let i=0;i<100&&a.w.document.body.dataset.ready!=='failed';i++)await new Promise(r=>setTimeout(r,5));
  assert.equal(a.w.document.body.dataset.ready,'failed');assert.equal(a.$('workspace-loader').hidden,true);assert.equal(a.$('view-data').querySelector('.unavailable').hidden,true);assert.match(a.$('status').textContent,/reviewed independently/);assert.equal(a.$('analysis-task-handoff').disabled,false);
  a.route('reviews');assert.equal(a.$('view-reviews').querySelector('.unavailable').hidden,false);assert.equal(a.$('download').disabled,true);
 }finally{a.close();}
});

for(const [name,minimum,final,deficit] of [['original',800,2000,0],['demand',668,1712,132],['outage',700,1000,100]])test(`homepage ${name} scenario opens the same reviewed and exported result`,async()=>{
 const a=await boot({}, {},webcrypto,'#home');try{
  const choice=a.w.document.querySelector(`[name="home-demo-case"][value="${name}"]`);choice.checked=true;choice.dispatchEvent(new a.w.Event('change'));
  a.$('home-demo-open').click();for(let i=0;i<100&&a.$('home-demo-open').disabled;i++)await new Promise(r=>setTimeout(r,5));
  assert.equal(a.$('home-demo-error').hidden,true);assert.equal(a.$('review-current').hidden,false);assert.equal(a.$('date').value,'2026-07-15');assert.equal(a.$('tank').value,'4000');assert.equal(a.$('plan-source').value,'frozen');
  a.$('resilience-export').click();const result=JSON.parse(await a.downloads.at(-1).text());assert.equal(result.selected.totals.min_storage_m3,minimum);assert.equal(result.selected.totals.final_storage_m3,final);assert.equal(result.selected.totals.max_reserve_deficit_m3,deficit);assert.equal(result.observation,null);assert.deepEqual(result.inputs.production,fixture.days.find(d=>d.date==='2026-07-15').schedules['4000'].production);
 }finally{a.close();}
});

test('continuous storage diagnosis catches timing gaps and recomputes forged evidence',async()=>{
 const a=await boot();try{
  const source=joinedSource(1),i=source.inputs;i.capacity=2;i.reserve=1;i.initial=1;i.target=1;i.blocks[0].production=[0,2,...Array(22).fill(0)];i.blocks[0].demand=[1,1,...Array(22).fill(0)];
  a.route('resilience');a.$('assessment-tab-sequence').click();await sequenceFile(a,JSON.stringify(source));
  const saved=await joinedExport(a),r=saved.results.selected.storage_requirements;
  assert.equal(saved.results.selected.water_budget.status,'budget_not_excluded');assert.equal(r.initial_shortfall_m3.value,1);assert.equal(r.with_spill.capacity_shortfall_m3.value,0);assert.match(a.$('sequence-budget-finding').textContent,/1 m³ more starting water.*larger tank alone/);assert.match(a.$('sequence-storage-proof').textContent,/Minimum starting water/);assert.equal(a.$('sequence-accounting-details').open,false);
  const bytes=saved.source_file.text;saved.results.selected.storage_requirements={minimum_initial_m3:{value:0}};saved.reason='Untrusted old finding';saved.decision='Request revised sequence';
  await sequenceFile(a,JSON.stringify(saved),'forged-storage.json');const reopened=await joinedExport(a);assert.deepEqual(reopened.results.selected.storage_requirements,r);assert.equal(reopened.source_file.text,bytes);assert.equal(a.$('sequence-reason').value,'');
  input(a,'sequence-initial','2');assert.equal(a.$('sequence-budget-finding').hidden,true);assert.equal(a.$('sequence-storage-proof').textContent,'');assert.equal(a.$('sequence-export').disabled,true);
  await a.$('sequence-form').onsubmit({preventDefault(){}});assert.equal((await joinedExport(a)).results.selected.storage_requirements.without_spill.feasible,true);
 }finally{a.close();}
});

test('continuous no-spill diagnosis exposes capacity required by an initial-water topup',async()=>{
 const a=await boot();try{
  const source=joinedSource(1),i=source.inputs;i.capacity=1;i.reserve=0;i.initial=0;i.target=1;i.blocks[0].production=[0,2,...Array(22).fill(0)];i.blocks[0].demand=[1,0,...Array(22).fill(0)];
  a.route('resilience');a.$('assessment-tab-sequence').click();await sequenceFile(a,JSON.stringify(source));const saved=await joinedExport(a),r=saved.results.selected.storage_requirements;
  assert.equal(r.initial_shortfall_m3.value,1);assert.equal(r.without_spill.capacity_shortfall_m3.value,0);assert.equal(r.without_spill.capacity_shortfall_after_initial_topup_m3.value,1);assert.equal(r.without_spill.minimum_capacity_after_initial_topup_m3.value,2);assert.match(a.$('sequence-budget-finding').textContent,/1 m³ more starting water.*no-spill capacity requirement is 2 m³/);assert.doesNotMatch(a.$('sequence-budget-finding').textContent,/requirements without spill/);
 }finally{a.close();}
});


test('Test conditions opens the homepage outage assessment after a prior continuous review',async()=>{
 const a=await boot({}, {}, webcrypto, '#resilience');try{
  a.$('assessment-tab-sequence').click();assert.equal(a.w.document.body.dataset.assessmentTab,'sequence');
  a.w.location.hash='home';a.w.dispatchEvent(new a.w.HashChangeEvent('hashchange'));
  const outage=a.w.document.querySelector('[name="home-demo-case"][value="outage"]');outage.checked=true;outage.dispatchEvent(new a.w.Event('change'));
  a.$('home-demo-open').click();for(let i=0;i<100&&a.$('home-demo-open').disabled;i++)await new Promise(r=>setTimeout(r,5));
  assert.equal(a.$('home-demo-error').hidden,true);assert.equal(a.$('review-current').hidden,false);
  a.$('review-verdict-test').click();assert.equal(a.w.location.hash,'#resilience');assert.equal(a.w.document.body.dataset.assessmentTab,'conditions');assert.equal(a.$('assessment-conditions').hidden,false);assert.equal(a.$('assessment-sequence').hidden,true);
  assert.equal(a.$('resilience-demand').value,'0');assert.equal(a.$('resilience-outage').value,'12');assert.equal(a.$('resilience-duration').value,'2');assert.equal(a.$('resilience-initial').value,'2000');
  a.$('resilience-export').click();const r=JSON.parse(await a.downloads.at(-1).text());assert.equal(r.selected.totals.min_storage_m3,700);assert.equal(r.selected.totals.final_storage_m3,1000);assert.equal(r.selected.totals.max_reserve_deficit_m3,100);assert.deepEqual(r.inputs.scenario.outage,{start_hour:12,duration_hours:2});
  assert.equal(a.$('assessment-workbench').dataset.mode,'conditions');assert.equal(a.w.document.activeElement,a.$('resilience-demand'));
 }finally{a.close();}
});

test('mobile navigation Escape restores the visible hamburger after focus moves into a prior group',async()=>{
 const a=await boot();try{
  Object.defineProperty(a.w,'innerWidth',{value:390,configurable:true});
  a.$('workspace-toggle').click();a.click('[data-workspace="forecasts"]');a.click('nav [data-view="evaluation"]');
  a.$('workspace-toggle').click();const group=a.w.document.querySelector('[data-workspace="forecasts"]');group.focus();
  assert.equal(a.w.document.activeElement,group);assert.equal(a.w.document.body.classList.contains('navigation-open'),true);
  group.dispatchEvent(new a.w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  assert.equal(a.w.document.body.classList.contains('navigation-open'),false);assert.equal(a.w.document.activeElement,a.$('workspace-toggle'));assert.equal(a.$('workspace-navigation').contains(a.w.document.activeElement),false);
  Object.defineProperty(a.w,'innerWidth',{value:800,configurable:true});a.click('[data-workspace="forecasts"]');a.w.document.querySelector('nav [data-view="evaluation"]').focus();
  a.w.document.activeElement.dispatchEvent(new a.w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  assert.equal(a.w.document.body.classList.contains('navigation-open'),false);assert.equal(a.w.document.activeElement,group);
 }finally{a.close();}
});

test('selecting a storage reference opens Current plan and preserves the imported candidate',async()=>{
 const a=await boot();try{
  const day=fixture.days.find(d=>d.date===a.$('date').value);a.route('data');a.$('analysis-task-plan').click();await a.importPlan(a.w.Papa.unparse(flatPlan(day)));a.$('inspect-candidate').click();
  assert.equal(a.$('plan-source').value,'imported');a.route('reviews');a.$('review-tab-revision').click();a.route('scenarios');a.$('scenario-tab-daily').click();
  a.w.document.querySelector('#comparison-table button').click();
  assert.equal(a.w.document.body.dataset.view,'reviews');assert.equal(a.w.document.body.dataset.reviewTab,'current');assert.equal(a.$('review-current').hidden,false);assert.equal(a.$('review-revision').hidden,true);assert.equal(a.$('tank').value,'500');assert.equal(a.$('plan-source').value,'frozen');assert.equal(a.$('date').value,day.date);
  a.route('data');a.$('analysis-task-plan').click();a.$('inspect-candidate').click();
  assert.equal(a.w.document.body.dataset.view,'operations');assert.equal(a.$('plan-source').value,'imported');assert.equal(a.$('tank').value,'4000');assert.equal(a.$('date').value,day.date);
 }finally{a.close();}
});
