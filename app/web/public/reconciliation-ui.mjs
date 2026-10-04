import {reconcileObservations} from './observation-reconciliation.mjs';
import {planForObservation,createObservationRestart,sameRestart} from './observation-restart.mjs';

const roles={tank:['Tank','tank_storage_m3'],production:['Production','production_rate_m3_h'],unit_power:['Unit power','unit_load_kw'],available_power:['Reported available power','available_power_kw']};
const kinds={tank_storage:'Tank inventory',production_rate:'Production rate',modeled_power:'Modeled unit power',reported_power_difference:'Unit − reported available power'};
const tolerances={tank_storage_m3:['Tank difference (m³)',10],production_rate_m3_h:['Production difference (m³/h)',5],unit_load_kw:['Modeled power difference (kW)',25],power_difference_kw:['Power excess (kW)',25]};
const units={m3:'m³','m3/h':'m³/h',kW:'kW'};
const reasons={stream_not_mapped:'Stream not mapped',not_available_at_review_time:'Arrived after cutoff',no_observation_supplied:'Reading missing',outside_plan_horizon:'Outside this plan',not_an_exact_plan_boundary:'Between hourly tank boundaries',specific_energy_not_declared:'Specific energy not declared'};

export const reconciliationTemplate=`<div class="assessment-heading"><div><h2>Observed departures</h2><p class="subtle">Compare exact observations with the selected schedule.</p></div><div id="reconciliation-actions" class="actions" hidden><button id="reconciliation-export" disabled>Export departures</button><button data-route="reviews">Record decision</button></div></div>
<div id="reconciliation-workbench" class="assessment-layout" data-state="empty"><div class="assessment-main">
 <section class="assessment-conclusion" aria-live="polite"><p id="reconciliation-verdict">Load observations to begin.</p><p id="reconciliation-explanation" class="subtle">Import a source declaration and readings CSV in Pilot inputs.</p><button id="reconciliation-import" data-route="pilot">Open pilot inputs</button></section>
 <div id="reconciliation-results" hidden>
 <section class="panel"><div class="panel-head"><h2>Largest differences</h2></div><div id="reconciliation-summary" class="table-wrap"></div><p class="micro">Differences use reviewer-set tolerances. Point readings do not establish energy totals or recovered solar.</p></section>
 <section class="panel"><div class="panel-head"><h2>Observation ledger</h2><label>Show<select id="reconciliation-filter"><option value="all">All comparisons</option><option value="requires_explanation">Requires explanation</option><option value="unknown">Unknown</option><option value="within_tolerance">Within tolerance</option></select></label></div><div id="reconciliation-ledger" class="table-wrap"></div><div class="ledger-navigation"><button id="reconciliation-previous" disabled>Previous</button><span id="reconciliation-page" class="micro"></span><button id="reconciliation-next" disabled>Next</button></div></section>
 <details class="panel"><summary>Source and comparison rules</summary><div id="reconciliation-identity"></div><p class="micro">Tank values match exact hourly boundaries. Production and modeled power use the declared constant rate within the hour. Power readings pair only at the same instant. A power excess requires explanation; the unit may also use grid power.</p></details>
 </div>
</div><aside id="reconciliation-mapping" class="assessment-inspector" aria-label="Observation mapping" hidden><h2>Map the observations</h2><p id="reconciliation-source" class="micro">No observations loaded.</p><div class="actions"><button data-route="pilot">Open pilot inputs</button><button id="reconciliation-day" disabled>Use observation day</button></div>
 <form id="reconciliation-form">${Object.entries(roles).map(([role,[name]])=>`<label>${name}<select id="reconciliation-map-${role}"><option value="">Not mapped</option></select></label>`).join('')}
 <label>Review cutoff<input id="reconciliation-cutoff" maxlength="40" placeholder="ISO time with UTC offset" required></label>
 <details><summary>Comparison assumptions</summary><p class="micro">Starting tolerances are examples. Set them for the source; they are not calibrated sensor uncertainty.</p>${Object.entries(tolerances).map(([key,[label,value]])=>`<label>${label}<input id="reconciliation-tolerance-${key}" type="number" min="0" step="any" value="${value}" required></label>`).join('')}<label>Specific energy (kWh/m³)<input id="reconciliation-sec" type="number" min="0.000001" step="any" placeholder="Optional; no assumed value"></label><p class="micro">Specific energy is required only for modeled unit power. The power-to-power comparison uses the readings directly.</p></details>
 <button type="submit" class="assessment-run">Compare observations</button><p id="reconciliation-error" role="alert"></p></form>
</aside></div>`;

export function setupReconciliation({$,fmt,text,facts,table,json,getContext,getRecord,getRecordRevision,selectDay,onTestRemaining}){
 let result=null,inputKey='',sourceKey='',page=0,revision=0;
 const differenceText=row=>{const value=row.difference,precision=row.tolerance>0?Math.max(1,Math.ceil(-Math.log10(row.tolerance))+1):6;let shown=fmt(value,Math.min(6,precision));const rounded=Number(shown.replaceAll(',',''));if(value!==0&&rounded===0||(Math.abs(rounded)>row.tolerance)!==(Math.abs(value)>row.tolerance))shown=String(value);return `${value>0?'+':''}${shown} ${units[row.unit]}`;};
 const time=value=>new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Nicosia',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',timeZoneName:'shortOffset'}).format(new Date(value));
 const signature=()=>JSON.stringify([getContext(),getRecord(),getRecordRevision?.()]);
 function availability(record=getRecord()){
  const ready=Boolean(record&&record.status!=='BLOCKED'&&record.observations?.length);
  $('reconciliation-mapping').hidden=!ready;$('reconciliation-actions').hidden=!ready;$('reconciliation-import').hidden=ready;$('reconciliation-results').hidden=!ready||!result;
  $('reconciliation-workbench').dataset.state=ready?(result?'result':'mapping'):'empty';return ready;
 }
 function clear(message){revision++;result=null;page=0;$('reconciliation-previous').disabled=true;$('reconciliation-next').disabled=true;$('reconciliation-export').disabled=true;availability();text('reconciliation-verdict',message);text('reconciliation-explanation','');for(const id of ['reconciliation-summary','reconciliation-ledger','reconciliation-identity'])$(id).replaceChildren();text('reconciliation-page','');}
 function render(){
  const record=getRecord(),nextSource=JSON.stringify(record&&[record.identity,record.reviewAsOf,record.status,getRecordRevision?.()]);
  if(sourceKey!==nextSource){sourceKey=nextSource;for(const [role,[,measurement]] of Object.entries(roles)){
   const options=(record?.sourceDeclaration.assets??[]).filter(asset=>asset.measurements.some(m=>m.measurement===measurement));
   $(`reconciliation-map-${role}`).replaceChildren(new Option('Not mapped',''),...options.map(asset=>new Option(`${asset.label} / ${asset.asset_id}`,asset.asset_id)));
  }$('reconciliation-cutoff').value=record?.reviewAsOf??'';clear('Source changed. Map the streams and compare.');}
  const source=record?.sourceDeclaration;
  text('reconciliation-source',source?`${source.source_kind==='synthetic_fixture'?'Synthetic example':'Unverified operator source'} / ${source.label}. ${time(source.window.start)} to ${time(source.window.end)}.`:'No observations loaded.');
  $('reconciliation-day').disabled=!source;
  if(!availability(record)){clear(record?.status==='BLOCKED'?'Observation intake is blocked.':'Load observations to begin.');text('reconciliation-explanation',record?.status==='BLOCKED'?'Correct the intake errors in Pilot inputs before comparing readings.':'Import a source declaration and readings CSV in Pilot inputs.');return;}
  if(result&&inputKey!==signature())clear('The selected plan changed. Compare again.');
 }
 function numeric(id,optional=false){const raw=$(id).value.trim();if(!raw&&optional)return undefined;if(!raw)throw Error('Complete the comparison assumptions.');const value=Number(raw);if(!Number.isFinite(value))throw Error('Comparison assumptions must be finite numbers.');return value;}
 function run(){
  clear('Comparing observations…');text('reconciliation-error','');
  try{
   const record=getRecord();if(!record?.observations?.length)throw Error('Load observations in Pilot inputs first.');
   const mapping=Object.fromEntries(Object.keys(roles).map(role=>[role,$(`reconciliation-map-${role}`).value]).filter(([,value])=>value));
   if(!Object.keys(mapping).length)throw Error('Map at least one stream to the selected plan.');
   const c=getContext(),p=c.plan;
   result=reconcileObservations({record,plan:planForObservation(c),mapping,tolerances:Object.fromEntries(Object.keys(tolerances).map(key=>[key,numeric(`reconciliation-tolerance-${key}`)])),review_as_of:$('reconciliation-cutoff').value.trim(),specific_energy_kwh_m3:numeric('reconciliation-sec',true)});
   inputKey=signature();present();$('reconciliation-export').disabled=false;
  }catch(e){clear('Comparison unavailable.');text('reconciliation-error',e.message);}
 }
 function present(){
  availability();
  const count=result.coverage.requires_explanation,comparable=result.rows.filter(row=>row.status!=='unknown').length;
  text('reconciliation-verdict',!comparable?'No readings can be compared with these settings.':count?`${count} ${count===1?'comparison requires':'comparisons require'} explanation.`:'Comparable readings are within the declared tolerances.');
  text('reconciliation-explanation',`${comparable} comparable points; ${result.coverage.unknown_comparisons} unknown comparisons. Review cutoff ${time(result.review_as_of)}. ${result.source.kind==='synthetic_fixture'?'Invented example readings.':'Source identity is reviewer-declared.'}`);
  table('reconciliation-summary',['Check','Largest difference','Observed at'],Object.entries(kinds).map(([kind,label])=>{
   const known=result.rows.filter(row=>row.kind===kind&&row.difference!==null).sort((a,b)=>kind==='reported_power_difference'?b.difference-a.difference:Math.abs(b.difference)-Math.abs(a.difference)),row=known[0];
   return [label,row?differenceText(row):'Unknown',row?time(row.time):'—'];
  }));
  facts('reconciliation-identity',[['Selected plan',getContext().label],['Tank',`${fmt(result.plan.capacity,0)} m³`],['Source',result.source.label],['Declaration SHA-256',result.source.identity.contract.sha256],['Observations SHA-256',result.source.identity.observations.sha256],['Original intake cutoff',result.original_intake_review_as_of],['This comparison cutoff',result.review_as_of],['Mappings',Object.entries(result.mapping).map(([role,asset])=>`${roles[role][0]} → ${asset}`).join('; ')]]);ledger();
 }
 function ledger(){
  if(!result)return;const filter=$('reconciliation-filter').value,rows=result.rows.filter(row=>filter==='all'||row.status===filter);
  page=Math.min(page,Math.max(0,Math.ceil(rows.length/100)-1));const start=page*100;$('reconciliation-previous').disabled=page===0;$('reconciliation-next').disabled=start+100>=rows.length;
  table('reconciliation-ledger',['Cyprus time','Check','Observed','Plan / reported','Difference','Finding','Assess'],rows.slice(start,start+100).map(row=>[time(row.time),kinds[row.kind],row.observed===null?'—':`${fmt(row.observed,1)} ${units[row.unit]}`,row.expected===null?'—':`${fmt(row.expected,1)} ${units[row.unit]}`,row.difference===null?'—':differenceText(row),row.status==='unknown'?(reasons[row.reason]??'Paired reading unavailable'):row.status==='requires_explanation'?'Requires explanation':'Within tolerance',restartAction(row)]));
  text('reconciliation-page',`${rows.length?start+1:0}–${Math.min(start+100,rows.length)} / ${rows.length} comparisons. Export retains exact observation and arrival times.`);
 }
 function restartProof(time){return {...createObservationRestart(snapshot(),getContext(),time),comparison_revision:revision};}
 function restartAction(row){
  if(!onTestRemaining||row.kind!=='tank_storage')return '—';
  try{restartProof(row.time);}catch{return '—';}
  const button=document.createElement('button');button.textContent='Test remaining plan';button.setAttribute('aria-label',`Test remaining plan from ${time(row.time)} tank reading`);
  button.onclick=()=>{try{const proof=restartProof(row.time);onTestRemaining(proof);}catch(error){text('reconciliation-error',error.message);}};
  return button;
 }
 function isRestartCurrent(proof){
  try{return sameRestart(proof,restartProof(proof.reading.time));}catch{return false;}
 }
 $('reconciliation-form').onsubmit=e=>{e.preventDefault();run();};
 for(const control of $('reconciliation-form').querySelectorAll('input,select'))control.addEventListener('input',()=>{clear('Settings changed. Compare observations again.');text('reconciliation-error','');});
 $('reconciliation-filter').onchange=()=>{page=0;ledger();};
 $('reconciliation-previous').onclick=()=>{page--;ledger();};$('reconciliation-next').onclick=()=>{page++;ledger();};
 $('reconciliation-day').onclick=()=>{const source=getRecord()?.sourceDeclaration;if(source){const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Nicosia',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(source.window.start));if(!selectDay(parts))text('reconciliation-error','No retained plan is available for the observation start day.');render();}};
 $('reconciliation-export').onclick=()=>{if(snapshot())json('aktina-observed-departures.json',result);};
 function snapshot(){return result&&inputKey===signature()?JSON.parse(JSON.stringify(result)):null;}
 return {render,snapshot,isRestartCurrent};
}
