import {validatePilot,validatePilotContract,pilotRecord,pilotCSV,pilotExample,pilotExampleCSV} from './pilot.mjs';
import {builderTemplate,setupPilotBuilder} from './pilot-builder.mjs';

const measurementNames={tank_storage_m3:'Tank storage',unit_load_kw:'Unit power',production_rate_m3_h:'Production rate',delivered_flow_m3_h:'Delivered flow',available_power_kw:'Reported available power'};
const unitName=unit=>unit==='m3'?'m³':unit==='m3/h'?'m³/h':unit;
const measurementName=kind=>measurementNames[kind]??kind;

export const pilotTemplate=`<p class="micro"><strong id="pilot-source-badge">Source not selected</strong>. Files stay in this browser and clear on reload. Reference plans remain separate.</p>
<div class="columns">
<section class="panel"><div class="panel-head"><h2>Source declaration</h2></div>
<label>Declaration JSON<input id="pilot-contract-file" type="file" accept=".json,application/json"></label><p id="pilot-contract-status" role="status">No declaration selected.</p>
<div class="actions"><button id="pilot-example">Load synthetic example</button></div>
<details><summary>File format and example exports</summary>
<p class="micro">Declare assets, numeric bounds, Europe/Nicosia, a 15 or 60 minute cadence, and an inclusive start / exclusive end. Only supported declaration fields are accepted.</p>
<div class="table-wrap"><table><thead><tr><th scope="col">Measurement</th><th scope="col">CSV unit</th></tr></thead><tbody><tr><td>tank_storage_m3</td><td>m3</td></tr><tr><td>unit_load_kw, available_power_kw</td><td>kW</td></tr><tr><td>production_rate_m3_h, delivered_flow_m3_h</td><td>m3/h</td></tr></tbody></table></div>
<p class="micro">CSV columns: time, available_at, asset_id, measurement, value, unit. No extra columns. ISO times require seconds and Z or an explicit offset.</p>
<p class="micro">Rejection means the format or values conflict with this contract; it does not prove a reading is false. Forecasts, cumulative meters and dispatch commands are unsupported.</p>
<div class="actions"><button id="pilot-contract-template">Export example declaration</button><button id="pilot-csv-template">Export example observations</button></div></details></section>
<section class="panel"><div class="panel-head"><h2>Observation review</h2></div>
<label>Observation CSV<input id="pilot-observations-file" type="file" accept=".csv,text/csv" disabled></label>
<div class="inline-controls"><label>Review cutoff (ISO time)<input id="pilot-as-of" placeholder="Blank: latest first-available input" maxlength="40" disabled></label><button id="pilot-apply-time" disabled>Apply review time</button></div>
<p id="pilot-status" role="status">Choose a declaration, then its observation CSV.</p><p class="micro">Checks cover numbers and data coverage. They do not verify the source, water quality, plant safety or operating authority.</p>
<div class="actions"><button id="pilot-review-export" disabled>Export readiness record</button></div><details><summary>Observation exports</summary><div class="actions"><button id="pilot-observations-export" disabled>Export parsed observations</button><button id="pilot-raw-export" disabled>Export original CSV</button></div></details></section>
</div>${builderTemplate}
<div id="pilot-kpis" class="kpis" hidden></div><p id="pilot-review-reasons" class="subtle" role="status" hidden></p><p id="pilot-empty-state" class="subtle">Choose a declaration and its observation CSV to inspect streams, history and gaps.</p>
<section id="pilot-streams-panel" class="panel" hidden><div class="panel-head"><h2>Observation streams</h2></div><div class="table-wrap" id="pilot-streams"><p class="subtle">Declared assets and latest known readings appear here.</p></div></section>
<section id="pilot-history-panel" class="panel" hidden><div class="panel-head"><h2>Stream history</h2></div><div class="inline-controls"><label>Asset and measurement<select id="pilot-stream-select" disabled></select></label><button id="pilot-previous" aria-label="Previous 96 observation slots" disabled>Previous</button><button id="pilot-next" aria-label="Next 96 observation slots" disabled>Next</button><button id="pilot-latest" aria-label="Jump to the latest known reading" disabled>Latest</button><span id="pilot-page" class="micro"></span></div><div class="chart" id="pilot-chart" role="region" tabindex="0" aria-label="Pilot observation stream"></div><p class="micro" id="pilot-chart-scope"></p></section>
<section id="pilot-findings-panel" class="panel" hidden><div class="panel-head"><h2>Gaps and blocking findings</h2></div><div class="table-wrap" id="pilot-findings"></div><p class="micro" id="pilot-findings-scope"></p></section>
<details class="panel"><summary>Source identity and limitations</summary><div id="pilot-identity"></div><p class="micro">Available power is a declared observation, not dispatch permission or proof of recoverable curtailed energy. Tank reserves are declared limits, not certified safety limits. No water balance, meter calibration or drinking-water quality check is performed.</p></details>`;

export function setupPilot({$,fmt,text,kpis,facts,table,lineChart,json,csv,download,sha256}){
 let contract=null,contractIdentity=null,rawCSV=null,observationIdentity=null,report=null,generation=0,chartOffset=0,intakeRevision=0;
 const formatTime=value=>value?new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Nicosia',year:'numeric',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',timeZoneName:'shortOffset'}).format(new Date(value))+' Cyprus':'Unknown';
 function controls(){const valid=Boolean(contract);$('pilot-observations-file').disabled=!valid;for(const key of ['pilot-as-of','pilot-apply-time','pilot-review-export'])$(key).disabled=!report;$('pilot-observations-export').disabled=!report?.rows.length;$('pilot-stream-select').disabled=!report?.streams.length;$('pilot-raw-export').disabled=rawCSV===null;for(const id of ['pilot-kpis','pilot-review-reasons','pilot-findings-panel'])$(id).hidden=!report;for(const id of ['pilot-streams-panel','pilot-history-panel'])$(id).hidden=!report?.streams.length;$('pilot-empty-state').hidden=Boolean(report);text('pilot-empty-state',valid?'Declaration ready. Import its observation CSV to inspect streams, history and gaps.':'Choose a declaration and its observation CSV to inspect streams, history and gaps.');}
 function render(){
  controls();if(!report)return;
  text('pilot-source-badge',contract.source_kind==='synthetic_fixture'?'Synthetic fixture (invented)':'Operator declaration (unverified origin)');
  kpis('pilot-kpis',[['Validation',report.reviewRequired&&report.status!=='BLOCKED'?'NEEDS REVIEW / '+report.status:report.status,contract.source_kind==='synthetic_fixture'?'Synthetic fixture':'Reviewer-declared observations'],['Known slots',`${fmt(report.knownSlots,0)} / ${fmt(report.expectedSlots,0)}`,'Missing and late readings remain unknown'],['Review cutoff',formatTime(report.reviewAsOf),report.reviewTimeBasis||'Not established'],['Blocking findings',fmt(report.issues.length,0),'Blocked values are excluded']]);
  for(const index of [0,2])$('pilot-kpis').children[index].classList.add('pilot-meta-metric');
  const late=report.rows.length-report.knownRows.length,belowReserve=report.streams.reduce((total,stream)=>total+stream.belowDeclaredReserve,0),reasons=[];
  if(report.issues.length)reasons.push(`${report.issues.length} blocking ${report.issues.length===1?'finding':'findings'}; observations are excluded.`);
  else{
   if(!report.rows.length)reasons.push('No observations supplied.');
   if(report.missing.length)reasons.push(`${report.missing.length} declared ${report.missing.length===1?'slot is':'slots are'} unknown.`);
   if(late)reasons.push(`${late} ${late===1?'reading arrived':'readings arrived'} after the review cutoff.`);
   if(belowReserve)reasons.push(`${belowReserve} tank ${belowReserve===1?'reading is':'readings are'} below a declared reserve; inspect the source limits.`);
  }
  text('pilot-review-reasons',reasons.join(' ')||'Every declared slot was available at the review cutoff.');
  table('pilot-streams',['Asset / measurement','Latest known value','Observed / Cyprus time','Known / expected','Unknown slots','Declared reserve'],report.streams.map(s=>[`${s.label} / ${measurementName(s.measurement)}`,s.latest?`${fmt(s.latest.value,2)} ${unitName(s.unit)}`:'Unknown',formatTime(s.latest?.time),`${s.knownSlots} / ${s.expectedSlots}`,s.missingSlots,s.reserve_m3===null?'—':`${fmt(s.reserve_m3,0)} m³ / ${s.belowDeclaredReserve} readings below`]));
  const findings=report.issues.slice(0,100).map(i=>[i.record,i.field,i.code,i.message]);
  if(!findings.length)findings.push(...report.missing.slice(0,100).map(r=>['—',`${r.asset_id} / ${measurementName(r.measurement)}`,r.time,r.reason]));
  table('pilot-findings',['Record','Asset / field','Finding / time','Detail'],findings.length?findings:[['—','—','Complete coverage','Every declared slot was available at the review cutoff.']]);
  text('pilot-findings-scope',`${report.issues.length} blocking ${report.issues.length===1?'finding':'findings'}; ${report.missing.length} unknown slots. Showing up to 100 blocking findings or gaps. The readiness record includes all findings and review warnings.`);
  facts('pilot-identity',[['Source type',contract.source_kind],['Source label',contract.source_label],['Declaration',`${contractIdentity.origin||'Uploaded file'} / ${contractIdentity.name} / SHA-256 ${contractIdentity.sha256}`],['Observations',`${observationIdentity.name} / SHA-256 ${observationIdentity.sha256}`],['Window / exclusive end',`${contract.window.start} → ${contract.window.end}`],['Cadence / display zone',`${contract.cadence_minutes} minutes / Europe/Nicosia`],['Raw file handling','Browser memory only. Reloading clears files; nothing is uploaded or shared.']]);
  const selected=$('pilot-stream-select').value;$('pilot-stream-select').replaceChildren(...report.streams.map(s=>new Option(`${s.label} / ${measurementName(s.measurement)}`,s.asset_id+'|'+s.measurement)));if([...$('pilot-stream-select').options].some(o=>o.value===selected))$('pilot-stream-select').value=selected;
  renderChart();
 }
 function renderChart(){
  const stream=report?.streams.find(s=>s.asset_id+'|'+s.measurement===$('pilot-stream-select').value);
  if(!stream){text('pilot-chart','No validated observations to chart.');text('pilot-chart-scope','');text('pilot-page','');for(const id of ['pilot-previous','pilot-next','pilot-latest'])$(id).disabled=true;return;}
  const start=Date.parse(contract.window.start),step=contract.cadence_minutes*60000,slots=stream.expectedSlots;
  const rows=new Map(report.knownRows.filter(r=>r.asset_id===stream.asset_id&&r.measurement===stream.measurement).map(r=>[r.epoch,r]));
  // A bounded 96-slot viewport preserves individual missing observations.
  chartOffset=Math.max(0,Math.min(chartOffset,Math.floor((slots-1)/96)*96));const shown=Math.min(slots-chartOffset,96),pageStart=start+chartOffset*step,values=Array.from({length:shown},(_,i)=>rows.get(pageStart+i*step)?.value??null);
  $('pilot-previous').disabled=chartOffset===0;$('pilot-next').disabled=chartOffset+shown>=slots;$('pilot-latest').disabled=!stream.latest;text('pilot-page',`Slots ${chartOffset+1}–${chartOffset+shown} / ${slots}`);
  const tickIndices=[0,Math.floor((shown-1)/2),shown-1].filter((v,i,a)=>a.indexOf(v)===i),labels=values.map((_,i)=>tickIndices.includes(i)?new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Nicosia',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(pageStart+i*step)):'');
  lineChart('pilot-chart',[{name:measurementName(stream.measurement),values}],{max:stream.max,labels,unit:unitName(stream.unit),points:true,pointTitles:Array.from({length:shown},(_,i)=>{const r=rows.get(pageStart+i*step);return r?`Observed ${r.time}; first available ${r.available_at}; ${r.value} ${unitName(r.unit)}`:'';}),levels:stream.reserve_m3===null?[]:[{value:stream.reserve_m3,label:'Declared reserve'}]});
  text('pilot-chart-scope',`Slots ${chartOffset+1}–${chartOffset+shown} of ${slots}. Gaps remain unknown; no interpolation. Export includes all readings and gaps. Observations only, no forecast or plan. Display: Europe/Nicosia. Point details retain exact observation and first-available times.`);
 }
 function inspect(){intakeRevision++;report=validatePilot(contract,rawCSV,globalThis.Papa,$('pilot-as-of').value.trim());text('pilot-status',`${report.status} / ${report.knownSlots} known slots / ${report.issues.length} blocking ${report.issues.length===1?'finding':'findings'}. Reference plans unchanged.`);render();}
 function resetObservations(){intakeRevision++;rawCSV=null;observationIdentity=null;report=null;chartOffset=0;$('pilot-as-of').value='';$('pilot-observations-file').value='';for(const id of ['pilot-kpis','pilot-review-reasons','pilot-streams','pilot-stream-select','pilot-chart','pilot-findings','pilot-identity'])$(id).replaceChildren();text('pilot-chart-scope','');text('pilot-page','');for(const id of ['pilot-previous','pilot-next','pilot-latest'])$(id).disabled=true;text('pilot-findings-scope','');text('pilot-source-badge',contract?.source_kind==='synthetic_fixture'?'Synthetic fixture (invented)':'Operator declaration (unverified origin)');controls();}
 $('pilot-contract-file').onchange=async()=>{
  const file=$('pilot-contract-file').files[0],current=++generation;if(!file)return;
  try{if(file.size>256*1024)throw Error('Maximum declaration size is 256 KB.');const bytes=await file.arrayBuffer(),input=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes)),checked=validatePilotContract(input),hash=await sha256(bytes);if(current!==generation)return;
   if(checked.issues.length){text('pilot-contract-status',`BLOCKED / ${checked.issues.map(i=>`${i.field}: ${i.message}`).join(' ')}`);text('pilot-status','Previous accepted intake remains selected.');return;}
   contract=input;contractIdentity={name:file.name,sha256:hash,bytes:bytes.byteLength,origin:'Uploaded file'};resetObservations();text('pilot-contract-status',`${input.label} / ${input.source_kind} / ${checked.streams.length} declared measurements. Source identity is not verified.`);text('pilot-status','Declaration accepted numerically. Choose its observations.');
  }catch(e){if(current===generation)text('pilot-contract-status',`${e.message} Previous accepted intake remains selected.`);}
 };
 $('pilot-observations-file').onchange=async()=>{
  const file=$('pilot-observations-file').files[0],current=++generation;if(!file||!contract)return;
  try{if(file.size>10*1024*1024)throw Error('Maximum observation file size is 10 MB.');const bytes=await file.arrayBuffer(),input=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes),hash=await sha256(bytes);if(current!==generation)return;rawCSV=input;observationIdentity={name:file.name,sha256:hash};inspect();}
  catch(e){if(current===generation)text('pilot-status',`${e.message} Previous accepted intake remains selected.`);}
 };
 $('pilot-example').onclick=async()=>{const current=++generation,input=JSON.stringify(pilotExample,null,2)+'\n',raw=globalThis.Papa.unparse(pilotExampleCSV,{newline:'\n'})+'\n';const hashes=await Promise.all([sha256(input),sha256(raw)]);if(current!==generation)return;contract=JSON.parse(input);resetObservations();contractIdentity={name:'bundled-synthetic-declaration.json',sha256:hashes[0],origin:'Bundled synthetic fixture'};rawCSV=raw;observationIdentity={name:'bundled-synthetic-observations.csv',sha256:hashes[1]};text('pilot-contract-status','Synthetic fixture with invented values. No real plant or meter.');inspect();};
 $('pilot-apply-time').onclick=()=>{if(rawCSV!==null)inspect();};$('pilot-stream-select').onchange=()=>{chartOffset=0;renderChart();};
 $('pilot-previous').onclick=()=>{chartOffset-=96;renderChart();};$('pilot-next').onclick=()=>{chartOffset+=96;renderChart();};$('pilot-latest').onclick=()=>{const stream=report?.streams.find(s=>s.asset_id+'|'+s.measurement===$('pilot-stream-select').value);if(!stream?.latest)return;const slot=Math.floor((stream.latest.epoch-Date.parse(contract.window.start))/(contract.cadence_minutes*60000));chartOffset=Math.floor(slot/96)*96;renderChart();};
 $('pilot-contract-template').onclick=()=>json('aktina-synthetic-source-declaration.json',pilotExample);
 $('pilot-csv-template').onclick=()=>csv('aktina-synthetic-observations.csv',pilotExampleCSV);
 $('pilot-review-export').onclick=()=>{if(report)json('aktina-observation-readiness.json',pilotRecord(contract,report,{contract:contractIdentity,observations:observationIdentity}));};
 $('pilot-observations-export').onclick=()=>{if(report?.rows.length)csv('aktina-parsed-observations.csv',pilotCSV(report));};
 $('pilot-raw-export').onclick=()=>{if(rawCSV!==null)download('aktina-original-observations.csv',rawCSV);};
 setupPilotBuilder({$,download,invalidatePending:()=>{generation++;},onApply:async(input,serialized)=>{const current=++generation;let hash;try{hash=await sha256(serialized);}catch(e){if(current!==generation)return false;throw e;}if(current!==generation)return false;contract=input;contractIdentity={name:'form-generated-source-declaration.json',sha256:hash,bytes:new TextEncoder().encode(serialized).byteLength,origin:'Form-generated declaration'};$('pilot-contract-file').value='';resetObservations();text('pilot-contract-status',`${input.label} / ${input.source_kind} / Form-generated declaration; source identity is unverified.`);text('pilot-status','Declaration accepted numerically. Choose its observations.');return true;}});
 return {render,revision:()=>intakeRevision,snapshot:()=>report?JSON.parse(JSON.stringify(pilotRecord(contract,report,{contract:contractIdentity,observations:observationIdentity}))):null,tankReadings:()=>!report||report.status==='BLOCKED'?[]:report.knownRows.filter(r=>r.measurement==='tank_storage_m3').map(r=>({...r,assetLabel:contract.assets.find(a=>a.asset_id===r.asset_id)?.label??r.asset_id,sourceKind:contract.source_kind,sourceLabel:contract.source_label,reviewAsOf:report.reviewAsOf,identity:{contract:{...contractIdentity},observations:{...observationIdentity}}}))};
}
