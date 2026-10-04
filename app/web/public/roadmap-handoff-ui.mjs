import {evaluateRoadmapHandoff,parseRoadmapDeclaration} from './roadmap-handoff.mjs';
import {evaluateForecastDecisionReview} from './forecast-decision.mjs';
import {waterServiceDisplay,waterServiceRows} from './plan-revision-ui.mjs';

export const roadmapHandoffTemplate=`<div class="data-intake">
<header class="result-heading"><h2>Handoff intake</h2><div class="revision-file-tools"><label class="revision-file-action">Open files<input id="roadmap-file" type="file" multiple accept=".json,.csv,application/json,text/csv"></label><button id="roadmap-export" type="button" disabled>Export review</button></div></header>
<p id="roadmap-status" class="micro" role="status" tabindex="-1">Open four supplied CSVs, with optional hourly tariffs, or a saved review.</p>
<details id="roadmap-preparation" class="handoff-preparation" hidden><summary>Declaration</summary>
 <form id="roadmap-form" class="handoff-form" novalidate>
  <div class="handoff-fields">
   <label>Source<select id="roadmap-source-kind" required><option value="">Choose source</option><option value="reviewer_supplied">Reviewer supplied</option><option value="illustrative_scenario">Illustrative scenario</option></select></label>
   <label>Source name<input id="roadmap-source-label" required maxlength="300"></label>
   <label>Cyprus UTC offset<select id="roadmap-offset" required><option value="">Choose offset</option><option value="+02:00">+02:00</option><option value="+03:00">+03:00</option></select></label>
   <label>Power values<select id="roadmap-power-meaning" required><option value="">Choose meaning</option><option value="interval_mean">Hourly mean</option><option value="point_sample">Point sample</option></select></label>
   <label>Test start, inclusive<input id="roadmap-test-start" required placeholder="YYYY-MM-DDThh:00:00+03:00" spellcheck="false"></label>
   <label>Test end, exclusive<input id="roadmap-test-end" required placeholder="YYYY-MM-DDThh:00:00+03:00" spellcheck="false"></label>
   <label>Radiation threshold · W/m²<input id="roadmap-threshold" required inputmode="decimal"></label>
   <label>Flag rule<select id="roadmap-comparison-rule" required><option value="">Choose rule</option><option value="greater_than">Above threshold (&gt;)</option><option value="at_or_above">At or above (≥)</option></select></label>
  </div>
  <details class="handoff-optional"><summary>Tank and tariffs</summary><div class="handoff-fields"><label>Tank capacity · m³<input id="roadmap-tank-capacity" inputmode="decimal" placeholder="Unknown"></label><label>Tank values<select id="roadmap-tank-meaning"><option value="unspecified">Unspecified</option><option value="aquashift_interval_end">AquaShift end-of-hour inventory</option></select></label></div><p id="roadmap-tariff-state" class="micro"></p></details>
  <div class="handoff-confirmations">
   <label><input id="roadmap-confirm-units" type="checkbox" required>Weather units are W/m², %, °C and % for radiation, cloud, temperature and humidity.</label>
   <label><input id="roadmap-confirm-time" type="checkbox" required>Radiation timestamps and demo date/hour labels mark interval starts.</label>
   <label><input id="roadmap-confirm-links" type="checkbox" required>I associate these predictions with this weather file and this schedule with this demo forecast.</label>
  </div>
  <button id="roadmap-compare" type="submit">Compare</button>
 </form>
 <details id="roadmap-input-details"><summary>Selected files</summary><div id="roadmap-input-identities" class="table-wrap"></div></details>
</details>
<section id="roadmap-result" aria-label="Supplied handoff comparison" hidden>
 <div id="roadmap-power-result">
 <div class="result-heading"><h2>Supplied power</h2><label>Demo day<select id="roadmap-day"></select></label></div>
 <div id="roadmap-power" class="chart" role="region" aria-label="Supplied normal and AquaShift power by local hour" tabindex="0"></div><p id="roadmap-day-status" class="micro"></p>
 <p id="roadmap-support" class="micro"></p><div id="roadmap-comparison" class="table-wrap"></div>
 <p class="micro">One tank trace cannot establish matched water service. Water benefit and forecast-specific operating value remain unestablished.</p>
 <details><summary>Forecast check <span id="roadmap-forecast-summary" class="review-detail-hint"></span></summary><div id="roadmap-forecast" class="table-wrap"></div><p id="roadmap-forecast-coverage" class="micro"></p></details>
 </div>
 <div id="roadmap-decision-result" hidden><h2 id="roadmap-decision-heading"></h2><p id="roadmap-decision-adequacy" class="micro"></p><div id="roadmap-decision-comparison" class="table-wrap"></div><p id="roadmap-decision-scope" class="micro"></p><details id="roadmap-water-details" tabindex="-1" aria-label="Compared modeled water service"><summary>Water comparison</summary><div id="roadmap-water-proof" class="table-wrap"></div></details></div>
 <button id="roadmap-finding" type="button" hidden></button>
 <details id="roadmap-source-details"><summary>Sources and scope</summary><div id="roadmap-identities" class="table-wrap"></div><div id="roadmap-declaration"></div><div id="roadmap-gaps" class="table-wrap" tabindex="-1"></div><div id="roadmap-scope"></div><button id="roadmap-clear" type="button">Remove handoff</button></details>
</section></div>`;

const RAW_LIMIT=4*1024*1024,PACKET_LIMIT=20*1024*1024,roles=['weather','predictions','day_forecast','schedule'];
const headers={weather:['time','shortwave_radiation','cloud_cover','temperature_2m','relative_humidity_2m'],predictions:['time','actual','predicted','baseline'],day_forecast:['date','hour','predicted_radiation','surplus_flag'],schedule:['date','hour','normal_power_kw','aquashift_power_kw','tank_level_m3','surplus_flag'],tariffs:['date','hour','eur_kwh']};
const clone=value=>JSON.parse(JSON.stringify(value)),parse=value=>JSON.parse(value.replace(/^\uFEFF/,''));
function fields(value,allowed,label){if(!value||typeof value!=='object'||Array.isArray(value))throw Error(`${label} must be an object.`);for(const key of Object.keys(value))if(!allowed.includes(key))throw Error(`Unsupported ${label} field: ${key}.`);}
function plain(value,max,label,multiline=false){if(typeof value!=='string'||!value.trim()||value.length>max||(multiline?/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/:/[\u0000-\u001f]/).test(value))throw Error(`Invalid ${label}.`);}
function bytes(value){const raw=new TextEncoder().encode(value);if(new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(raw)!==value)throw Error('Retained text must be valid UTF-8.');return raw;}
function checkNote(note){if(note===undefined)return;fields(note,['reviewer','decision','reason'],'prior note');plain(note.reviewer,80,'prior reviewer');plain(note.decision,120,'prior decision');plain(note.reason,2000,'prior reason',true);}
const number=value=>value===null||value===undefined?'Unknown':value.toLocaleString('en-GB',value!==0&&Math.abs(value)<.01?{maximumSignificantDigits:3}:{maximumFractionDigits:2});
const amount=(value,unit,change=false)=>value===null||value===undefined?'Unknown':`${change&&value>0?'+':''}${number(value)} ${unit}`;
function numeric(value,label){const s=String(value).trim(),n=Number(s);if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(s)||!Number.isFinite(n)||n<0||(n===0&&/[1-9]/.test(s.split(/[eE]/)[0])))throw Error(`${label} must be a nonnegative finite number within numeric precision.`);return n;}

export function setupRoadmapHandoff({$,text,table,facts,lineChart,json,sha256,Papa,reveal=()=>{}}){
 let generation=0,pending=false,record=null,result=null,draft=null;
 const compact=value=>Object.fromEntries(['forecast','demo','tank','gaps','scope','water_comparability','forecast_attribution','lineage'].map(key=>[key,clone(value[key])]));
 async function retained(file){
  fields(file,['name','text','sha256'],'retained file');plain(file.name,255,'retained filename');
  if(typeof file.text!=='string'||!/^[a-f0-9]{64}$/.test(file.sha256??''))throw Error('Retain exact file text and its SHA-256.');
  if(bytes(file.text).byteLength>RAW_LIMIT)throw Error('Each raw file must be no larger than 4 MiB.');
  if(await sha256(file.text)!==file.sha256)throw Error(`Retained hash does not match ${file.name}.`);
  return {name:file.name,text:file.text,sha256:file.sha256};
 }
 function identify(file){
  const parsed=Papa.parse(file.text,{delimiter:',',skipEmptyLines:'greedy'});
  if(parsed.errors?.length||!Array.isArray(parsed.data?.[0]))throw Error(`${file.name}: invalid CSV.`);
  const keys=parsed.data[0].map(value=>String(value).trim().replace(/^\uFEFF/,''));
  const matches=Object.keys(headers).filter(role=>keys.length===headers[role].length&&new Set(keys).size===keys.length&&keys.every(key=>headers[role].includes(key)));
  if(matches.length!==1)throw Error(`${file.name}: headers do not identify one supported file role.`);
  if(parsed.data.length-1>(['weather','predictions'].includes(matches[0])?30000:8784))throw Error(`${file.name}: too many supplied rows.`);
  const rows=parsed.data.slice(1).map(values=>{if(values.length!==keys.length)throw Error(`${file.name}: CSV field count does not match its header.`);return Object.fromEntries(keys.map((key,i)=>[key,values[i]]));});
  return {role:matches[0],rows};
 }
 function tariffs(file){
  const parsed=identify(file);if(parsed.role!=='tariffs'||parsed.rows.length>8784)throw Error('Tariffs require date,hour,eur_kwh and at most 8,784 rows.');
  return parsed.rows.map(row=>{const hour=String(row.hour).trim();if(!/^\d{1,2}$/.test(hour))throw Error('Tariff hour must be an integer from 0 to 23.');return {date:String(row.date).trim(),hour:Number(hour),eur_kwh:numeric(row.eur_kwh,'Tariff')};});
 }
 function sameTariffs(a,b){const ordered=rows=>Array.isArray(rows)?rows.map(row=>[row.date,row.hour,row.eur_kwh]).sort((x,y)=>x[0].localeCompare(y[0])||x[1]-y[1]):null;return JSON.stringify(ordered(a))===JSON.stringify(ordered(b));}
 function placePreparation(completed=false){
  const panel=$('roadmap-preparation'),active=panel.ownerDocument.activeElement,keepFocus=panel.contains(active);
  const anchor=completed?$('roadmap-source-details').querySelector('summary'):$('roadmap-status');
  if(anchor.nextElementSibling!==panel)anchor.after(panel);panel.hidden=false;panel.open=!completed;
  if(keepFocus&&!completed)active.focus();
 }
 function prepare(value,declaration=null){
  draft=value;$('roadmap-form').reset();placePreparation(!!declaration);
  if(declaration){for(const [id,value]of Object.entries({'source-kind':declaration.source_kind,'source-label':declaration.source_label,offset:declaration.utc_offset,'test-start':declaration.test_period.start,'test-end':declaration.test_period.end,'power-meaning':declaration.power_semantics,threshold:declaration.surplus_threshold_w_m2,'comparison-rule':declaration.surplus_comparison,'tank-capacity':declaration.tank_capacity_m3??'','tank-meaning':declaration.tank_level_semantics}))$('roadmap-'+id).value=value;}
  const files=[...roles.map(role=>[role,value.files[role]]),...(value.tariff_file?[['tariffs',value.tariff_file]]:[])];
  table('roadmap-input-identities',['Role','File','SHA-256'],files.map(([role,file])=>[role,file.name,file.sha256]));
  text('roadmap-tariff-state',value.tariff_file?`Hourly tariffs: ${value.tariff_file.name}`:value.tariffs!==null?'Hourly tariffs retained in the declaration.':'No tariffs supplied. Cost remains unknown.');
 }
 function declarationFromForm(){
  const form=$('roadmap-form'),missing=[...form.querySelectorAll('[required]')].find(input=>input.type==='checkbox'?!input.checked:!input.value.trim());
  if(missing){missing.focus();throw Error('Complete the declaration and all three confirmations.');}
  const value=id=>$('roadmap-'+id).value;
  return {schema:1,kind:'roadmap_handoff_declaration',source_kind:value('source-kind'),source_label:value('source-label'),utc_offset:value('offset'),radiation_time_semantics:'interval_start',date_hour_semantics:'interval_start',weather_units:{shortwave_radiation:'W/m2',cloud_cover:'percent',temperature_2m:'degC',relative_humidity_2m:'percent'},power_semantics:value('power-meaning'),tank_level_semantics:value('tank-meaning'),tank_capacity_m3:value('tank-capacity').trim()?numeric(value('tank-capacity'),'Tank capacity'):null,surplus_threshold_w_m2:numeric(value('threshold'),'Radiation threshold'),surplus_comparison:value('comparison-rule'),test_period:{start:value('test-start'),end:value('test-end')},tariffs:draft.tariffs,declared_links:{weather_sha256:draft.files.weather.sha256,schedule_forecast_sha256:draft.files.day_forecast.sha256}};
 }
 function install(declaration_file,files,tariff_file,priorNote=false){
  const declaration=parseRoadmapDeclaration(declaration_file.text);
  if(tariff_file&&!sameTariffs(tariffs(tariff_file),declaration.tariffs))throw Error('Retained tariff CSV disagrees with the declaration.');
  const evaluated=evaluateRoadmapHandoff({declaration,files,Papa}),next={schema:1,kind:'roadmap_handoff_review',declaration_file,files,...(tariff_file?{tariff_file}:{}),createdAt:new Date().toISOString(),results:compact(evaluated)};
  if(bytes(JSON.stringify(next,null,2)+'\n').byteLength>PACKET_LIMIT)throw Error('Recomputed handoff review exceeds 20 MiB.');
  record=next;result=evaluated;pending=false;prepare({files,tariff_file,tariffs:declaration.tariffs},declaration);render();
  text('roadmap-status',`${declaration.source_kind==='illustrative_scenario'?'Illustrative':'Reviewer-supplied'} handoff opened. Recalculated from retained files.${priorNote?' Prior note cleared.':''}`);reveal();$('roadmap-status').focus();
 }
 function decisionResult(){
  const r=result,service=waterServiceDisplay(r.water_service),adequate=role=>r.adequacy[role].status==='modeled_requirements_met',cost=r.energy.cost_eur;
  text('roadmap-decision-heading',service.inspect?service.title:!adequate('candidate')||!adequate('control')?'Modeled water requirements not met':cost===null?'Modeled cost unknown':r.energy.matched_water_cost_reduction?'Lower cost with no modeled water regression':r.actions.changed_hours===0?'Supplied plans are unchanged':cost.delta>0?'Candidate costs more':'No modeled cost reduction');
  const requirements=role=>adequate(role)?'met':Object.entries(r.adequacy[role].criteria).filter(([,met])=>!met).map(([key])=>({demand_met:'unserved demand',reserve_met:'reserve shortfall',terminal_target_met:'ending-stock shortfall'})[key]).join(', ');
  text('roadmap-decision-adequacy',`Modeled water requirements — control: ${requirements('control')}; candidate: ${requirements('candidate')}.`);
  const display=(value,unit)=>{if(value&&typeof value==='object'){if(value.value===null)return `Exact positive value; see evidence (${unit})`;value=value.value;}return value===null||value===undefined?'Unknown':`${Math.abs(value)>1e12?value.toExponential(3):number(value)} ${unit}`;};
  table('roadmap-decision-comparison',['Same supplied period','Control','Candidate'],[
   ['Forecast MAE',display(r.forecast.control.mae,'W/m²'),display(r.forecast.candidate.mae,'W/m²')],
   ['Unserved water',display(r.adequacy.control.unmet_m3,'m³'),display(r.adequacy.candidate.unmet_m3,'m³')],
   ['Ending stock',display(r.adequacy.control.final_storage_m3,'m³'),display(r.adequacy.candidate.final_storage_m3,'m³')],
   ['Modeled tariff cost',display(cost?.control,'€'),display(cost?.candidate,'€')]
  ]);
  text('roadmap-decision-scope',`${r.actions.changed_hours} changed production hours. Forecast attribution is not established.`);
  table('roadmap-water-proof',['Check','Compared time or basis','Finding'],waterServiceRows(r.water_service).map(row=>row.map(value=>value.replace(/Original/g,'Control').replace(/original/g,'control').replace(/Returned/g,'Candidate').replace(/returned/g,'candidate'))));
  facts('roadmap-declaration',[['Source',r.source_label],['Source kind',r.source_kind==='illustrative_scenario'?'Illustrative scenario':'Reviewer supplied'],['Period',`${r.horizon.start} to ${r.horizon.end} / ${r.horizon.hours} h`],['Method',r.method.status==='same_declared_method'?'Same declared method; execution unverified':'Declarations differ'],['Timing',r.timing.status==='declared_before_cutoff'?'Declared before cutoff; availability unverified':r.timing.status==='late_declared'?'Declared evidence is late':'Timing not established']]);
  table('roadmap-identities',['File','Name','SHA-256'],[['Declaration',record.declaration_file.name,record.declaration_file.sha256],...Object.entries(record.files).map(([role,file])=>[role,file.name,file.sha256])]);
  table('roadmap-gaps',['Review gaps'],[...r.method.gaps,...r.timing.gaps].map(gap=>[gap]));
  const scope=$('roadmap-scope');scope.replaceChildren(...r.scope.map(value=>{const p=scope.ownerDocument.createElement('p');p.className='micro';p.textContent=value;return p;}));
  const proof=scope.ownerDocument.createElement('details'),summary=scope.ownerDocument.createElement('summary'),pre=scope.ownerDocument.createElement('pre'),scroll=scope.ownerDocument.createElement('div');summary.textContent='Exact evidence';pre.textContent=JSON.stringify({water_service:r.water_service,adequacy:r.adequacy,forecast:r.forecast,energy:r.energy,method:r.method,timing:r.timing,forecast_attribution:r.forecast_attribution},null,2);scroll.className='table-wrap';scroll.append(pre);proof.append(summary,scroll);scope.append(proof);
  const gap=r.method.gaps[0]??r.timing.gaps[0];$('roadmap-finding').hidden=!service.inspect&&!gap;text('roadmap-finding',service.inspect?'Inspect water difference':r.method.gaps.length?'Inspect method difference':gap?'Inspect timing gap':'');
 }
 function render(){
  $('roadmap-export').disabled=pending||!record;$('roadmap-result').hidden=!result;$('roadmap-day').disabled=pending||!result;$('roadmap-compare').disabled=pending||!draft;
  const decision=record?.kind==='forecast_decision_review';$('roadmap-power-result').hidden=decision;$('roadmap-decision-result').hidden=!decision;
  if(!result){for(const id of ['roadmap-power','roadmap-comparison','roadmap-forecast','roadmap-identities','roadmap-declaration','roadmap-gaps','roadmap-scope','roadmap-water-proof','roadmap-decision-comparison'])$(id).replaceChildren();$('roadmap-day').replaceChildren();return;}
  if(decision){decisionResult();return;}
  const dates=result.demo.coverage.selected_dates,selected=$('roadmap-day').value;
  $('roadmap-day').replaceChildren(...dates.map(date=>{const option=$('roadmap-day').ownerDocument.createElement('option');option.value=date;option.textContent=date;return option;}));if(dates.includes(selected))$('roadmap-day').value=selected;
  const day=$('roadmap-day').value,rows=new Map(result.demo.rows.filter(row=>row.date===day).map(row=>[row.hour,row])),coverage=result.demo.days.find(row=>row.date===day)?.coverage,mean=result.declaration.power_semantics==='interval_mean';
  if(dates.length){lineChart('roadmap-power',[{name:'Normal',values:Array.from({length:24},(_,h)=>rows.get(h)?.normal_power_kw??null),dash:'6 4'},{name:'AquaShift',values:Array.from({length:24},(_,h)=>rows.get(h)?.aquashift_power_kw??null)}],{labels:Array.from({length:mean?25:24},(_,h)=>h%6===0||h===(mean?24:23)?String(h).padStart(2,'0')+':00':''),unit:mean?'kW / supplied hourly means':'kW / point samples',step:mean,points:!mean});text('roadmap-day-status',`${day} / ${result.declaration.utc_offset}. ${coverage.matched_hours} of 24 forecast and schedule hours joined.${coverage.status==='complete'?'':' Whole-day totals unknown.'}`);}
  else{text('roadmap-power','No supplied demo hours.');text('roadmap-day-status','Whole-day totals unknown.');}
  const support=result.demo.support;
  const suppliedDates=[...new Set(result.demo.rows.filter(row=>row.normal_power_kw!==null&&row.aquashift_power_kw!==null).map(row=>row.date))];
  text('roadmap-support',`All supplied days: ${suppliedDates.join(', ')||'none'}. ${support.hours} supplied schedule hours. ${mean?'Only supplied hours are totalled.':'Point-power samples do not establish electricity or cost totals.'}`);
  table('roadmap-comparison',['All supplied days','Normal','AquaShift','Change'],[['Electricity','electricity_kwh','kWh'],['Declared tariff cost','cost_eur','€'],['Forecast-flagged load','forecast_flagged_electricity_kwh','kWh']].map(([label,key,unit])=>[label,amount(support[key]?.normal,unit),amount(support[key]?.aquashift,unit),amount(support[key]?.delta,unit,true)]));
  const f=result.forecast,c=f.coverage;
  text('roadmap-forecast-summary',`${c.matched_hours} paired hours`);table('roadmap-forecast',['Paired errors / W/m²','Model','Supplied baseline'],['mae','rmse','bias'].map(key=>[key.toUpperCase(),number(f.model[key]),number(f.baseline[key])]));
  text('roadmap-forecast-coverage',`${c.matched_hours} paired of ${c.expected_hours} declared test hours. ${c.status==='complete'?'Complete supplied coverage.':'Missing or unmatched hours remain outside these metrics.'}`);
  table('roadmap-identities',['File','Name','SHA-256'],[['Declaration',record.declaration_file.name,record.declaration_file.sha256],...roles.map(role=>[role,record.files[role].name,record.files[role].sha256]),...(record.tariff_file?[['tariffs',record.tariff_file.name,record.tariff_file.sha256]]:[])]);
  facts('roadmap-declaration',[['Source',result.declaration.source_label],['Source kind',result.declaration.source_kind==='illustrative_scenario'?'Illustrative scenario':'Reviewer supplied'],['Declared test period',`${result.declaration.test_period.start} to ${result.declaration.test_period.end}`],['Power meaning',mean?'Hourly interval mean':'Point sample'],['Tank meaning',result.tank.semantics==='aquashift_interval_end'?'Supplied AquaShift end-of-hour inventory':'Unspecified'],['Supplied tank range',`${amount(result.tank.min_m3,'m³')} to ${amount(result.tank.max_m3,'m³')}`],['Declared capacity',amount(result.tank.capacity_m3,'m³')]]);
  table('roadmap-gaps',['Review gaps'],result.gaps.map(gap=>[gap.message]));const scope=$('roadmap-scope');scope.replaceChildren(...result.scope.map(value=>{const p=scope.ownerDocument.createElement('p');p.className='micro';p.textContent=value;return p;}));
  const finding=['tank_above_declared_capacity','different_supplied_predictions','partial_demo_coverage','partial_test_coverage','missing_weather','missing_tariffs','missing_demo_forecast'].map(code=>result.gaps.find(gap=>gap.code===code)).find(Boolean);$('roadmap-finding').hidden=!finding;text('roadmap-finding',finding?`${finding.message} View details`:'');
 }
 function clear(message='Handoff removed.'){
  generation++;pending=false;record=null;result=null;draft=null;$('roadmap-preparation').hidden=true;$('roadmap-preparation').open=false;$('roadmap-source-details').open=false;$('roadmap-water-details').open=false;$('roadmap-form').reset();text('roadmap-status',message);render();
 }
 function invalidate(){generation++;pending=false;record=null;result=null;if(draft)placePreparation();text('roadmap-status',draft?'Declaration changed. Compare to update the review.':'File selection changed. Open the supplied files again.');render();}
 async function read(file,limit){if(!file||file.size>limit)throw Error(`Choose files no larger than ${limit===RAW_LIMIT?'4':'20'} MiB.`);const raw=await file.arrayBuffer();if(raw.byteLength>limit)throw Error(`File exceeds ${limit===RAW_LIMIT?'4':'20'} MiB.`);return new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(raw);}
 async function open(selected){
  clear('Checking handoff…');pending=true;render();const token=generation;
  try{
   if(!selected.length||selected.length>5)throw Error('Open one saved review, or four CSVs with optional hourly tariffs.');
   const texts=await Promise.all(selected.map(file=>read(file,selected.length===1?PACKET_LIMIT:RAW_LIMIT)));if(token!==generation)return;
   if(selected.length===1&&texts[0].replace(/^\uFEFF/,'').trimStart().startsWith('{')){
    const packet=parse(texts[0]);
    if(packet.kind==='forecast_decision_review'){
     const evaluated=await evaluateForecastDecisionReview(packet,{sha256,Papa});if(token!==generation)return;
     if(bytes(JSON.stringify(evaluated.record,null,2)+'\n').byteLength>PACKET_LIMIT)throw Error('Recomputed handoff review exceeds 20 MiB.');
     record=evaluated.record;result=evaluated.result;pending=false;render();text('roadmap-status',`${result.source_kind==='illustrative_scenario'?'Illustrative':'Reviewer-supplied'} forecast comparison opened. Recalculated from retained files.${packet.note?' Prior note cleared.':''}`);reveal();$('roadmap-status').focus();return;
    }
    fields(packet,['schema','kind','declaration_file','files','tariff_file','createdAt','results','note'],'handoff review');
    if(packet.schema!==1||packet.kind!=='roadmap_handoff_review'||typeof packet.createdAt!=='string'||!Number.isFinite(Date.parse(packet.createdAt)))throw Error('Use a schema-1 roadmap_handoff_review packet.');checkNote(packet.note);fields(packet.files,roles,'handoff files');
    const [declaration_file,...values]=await Promise.all([retained(packet.declaration_file),...roles.map(role=>retained(packet.files[role])),...(packet.tariff_file?[retained(packet.tariff_file)]:[])]);if(token!==generation)return;
    if(Object.hasOwn(packet,'tariff_file')&&!packet.tariff_file)throw Error('Retain a valid tariff_file or omit it.');
    install(declaration_file,Object.fromEntries(roles.map((role,i)=>[role,values[i]])),values[4],!!packet.note);
   }else{
    const files={},values=await Promise.all(selected.map(async(file,i)=>{plain(file.name,255,'filename');if(bytes(texts[i]).byteLength>RAW_LIMIT)throw Error('Each raw file must be no larger than 4 MiB.');return {name:file.name,text:texts[i],sha256:await sha256(texts[i])};}));if(token!==generation)return;
    for(const file of values){const {role}=identify(file);if(files[role])throw Error(`Two files identify the ${role} role. Open one of each required CSV.`);files[role]=file;}
    const missing=roles.filter(role=>!files[role]);if(missing.length)throw Error(`Missing supplied CSVs: ${missing.join(', ')}.`);
    const tariff_file=files.tariffs;delete files.tariffs;prepare({files,tariff_file,tariffs:tariff_file?tariffs(tariff_file):null});pending=false;render();text('roadmap-status','Files checked. Confirm their meanings to compare.');reveal();$('roadmap-source-kind').focus();
   }
  }catch(error){if(token===generation){pending=false;record=null;result=null;draft=null;$('roadmap-preparation').hidden=true;render();text('roadmap-status',`Handoff not accepted: ${error.message}`);reveal();$('roadmap-file').focus();}}
 }
 async function compare(event){
  event.preventDefault();invalidate();const token=generation;
  try{
   if(!draft)throw Error('Open the four supplied CSVs first.');
   const declaration=declarationFromForm(),text=JSON.stringify(declaration,null,2)+'\n',files=draft.files,tariff_file=draft.tariff_file;pending=true;render();
   const declaration_file={name:'browser-declaration.json',text,sha256:await sha256(text)};if(token!==generation)return;install(declaration_file,files,tariff_file);
  }catch(error){if(token===generation){pending=false;record=null;result=null;$('roadmap-preparation').open=true;render();text('roadmap-status',`Handoff not accepted: ${error.message}`);reveal();if(!$('roadmap-form').contains($('roadmap-form').ownerDocument.activeElement))$('roadmap-compare').focus();}}
 }
 function exportReview(){if(pending)throw Error('Wait for handoff validation to finish.');if(!record)throw Error('Open a complete handoff review first.');const packet={...clone(record),createdAt:new Date().toISOString()};if(bytes(JSON.stringify(packet,null,2)+'\n').byteLength>PACKET_LIMIT)throw Error('Complete handoff review exceeds 20 MiB.');return packet;}
 $('roadmap-file').onchange=()=>{const files=Array.from($('roadmap-file').files);$('roadmap-file').value='';return files.length?open(files):undefined;};$('roadmap-day').onchange=render;$('roadmap-clear').onclick=()=>clear();
 $('roadmap-form').oninput=invalidate;$('roadmap-form').onchange=invalidate;$('roadmap-form').onsubmit=compare;
 $('roadmap-finding').onclick=()=>{if(record?.kind==='forecast_decision_review'&&waterServiceDisplay(result.water_service).inspect){$('roadmap-water-details').open=true;$('roadmap-water-details').focus();}else{$('roadmap-source-details').open=true;$('roadmap-gaps').focus();}};
 $('roadmap-export').onclick=()=>{try{json(record?.kind==='forecast_decision_review'?'aquashift-forecast-decision-review.json':'aquashift-handoff-review.json',exportReview());}catch(error){text('roadmap-status',error.message);reveal();$('roadmap-status').focus();}};
 render();return {render,snapshot:()=>record?clone(record):null,isPending:()=>pending,clear,exportReview};
}
