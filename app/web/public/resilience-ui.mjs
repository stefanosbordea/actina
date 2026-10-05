import {replayPlan} from './plan-resilience.mjs';
import {planForObservation,sameRestart} from './observation-restart.mjs';

export const resilienceTemplate = `
<div id="assessment-workbench" class="assessment-workbench" data-mode="result">
 <header class="assessment-heading"><nav class="assessment-stage-nav" aria-label="Assessment stage"><button type="button" id="resilience-edit" data-assessment-controls aria-controls="resilience-form" aria-pressed="false">Conditions</button><button type="button" id="resilience-show-result" aria-controls="resilience-result" aria-pressed="true" disabled>Result</button></nav></header>
 <div class="assessment-layout">
  <aside class="assessment-inspector" aria-label="Test conditions">
   <form id="resilience-form"><h2>Conditions</h2><p class="micro" id="resilience-plan-name"></p>
    <label>Demand change (%)<input id="resilience-demand" type="number" min="-100" max="200" step="any" value="10" required></label>
    <label>Production loss (%)<input id="resilience-loss" type="number" min="0" max="100" step="any" value="0" required></label>
    <div class="assessment-input-pair"><label>Start hour<select id="resilience-start"></select></label><label>Starting water (m³)<input id="resilience-initial" type="number" min="0" step="any" required></label></div>
    <fieldset><legend>Production interruption</legend><div class="assessment-input-pair"><label>Starts at<select id="resilience-outage"></select></label><label>Duration (hours)<input id="resilience-duration" type="number" min="0" max="24" step="any" value="0" required></label></div></fieldset>
    <button type="submit" class="assessment-run">Run assessment</button><button type="button" id="resilience-reset">Reset to nominal</button><p id="resilience-error" role="alert"></p>
   </form>
   <details id="resilience-reading-panel"><summary>Use a tank reading</summary><p class="micro">Map an observation to this tank. Source and mapping remain reviewer declarations.</p><div id="resilience-manual-reading"><label>Known hourly reading<select id="resilience-reading"></select></label><label class="check"><input id="resilience-map" type="checkbox"> Use this stream as the selected tank</label><button id="resilience-use-reading" disabled>Use reading</button></div><p id="resilience-reading-status" class="micro" role="status"></p><button data-route="pilot">Open pilot inputs</button></details>
  </aside>
  <section id="resilience-result" class="assessment-main" aria-label="Assessment result">
   <header class="assessment-result-heading"><p id="resilience-conditions-summary" class="assessment-condition-summary"></p><p id="resilience-verdict" tabindex="-1" aria-live="polite"></p><p id="resilience-explanation" class="subtle"></p></header>
   <div class="assessment-chart-heading"><h2>Tank inventory</h2><span id="resilience-horizon" class="micro"></span></div><div id="resilience-chart" class="chart" tabindex="0" role="region" aria-label="Tank inventory under the selected disturbance"></div><p id="resilience-chart-note" class="micro"></p>
   <div id="resilience-kpis" class="assessment-accounting"></div>
   <details id="resilience-details" class="assessment-details"><summary>Details</summary><label class="assessment-evidence-select">View<select id="resilience-evidence-view"><option value="accounting">Hourly accounting</option><option value="sensitivity">Sensitivity</option><option value="comparison">Plan comparison</option><option value="source">Source and assumptions</option></select></label>
    <section id="resilience-evidence-accounting" class="assessment-evidence-panel" aria-label="Hourly accounting"><div id="resilience-ledger" class="table-wrap"></div></section>
    <section id="resilience-evidence-sensitivity" class="assessment-evidence-panel" aria-label="Sensitivity" hidden><p class="micro">Select a case. Cells show reserve deficit in m³; starting water and interruption stay fixed.</p><div id="resilience-matrix" class="table-wrap"></div><p id="resilience-matrix-note" class="micro"></p></section>
    <section id="resilience-evidence-comparison" class="assessment-evidence-panel" aria-label="Plan comparison" hidden><div id="resilience-comparison" class="table-wrap"></div><p class="micro">Same demand, starting water, loss and interruption. Reduced water service is not a saving.</p></section>
    <section id="resilience-evidence-source" class="assessment-evidence-panel" aria-label="Source and assumptions" hidden><div id="resilience-identity"></div><p class="micro">Declared hourly flows, continuous within each segment. No replanning, ramp, salinity or water-quality model. This simulation does not authorize plant operation.</p></section>
   </details>
   <div class="actions"><button id="resilience-export" disabled>Export assessment</button><button data-route="reviews">Record decision</button></div>
  </section>
 </div>
</div>`;

export function setupResilience({$,fmt,text,kpis,facts,table,lineChart,json,getContext,getTankReadings,isObservationRestartCurrent}) {
 let contextKey='',record=null,reading=null,readings=[],needsExplicitRun=false;
 const clock=h=>`${String(Math.floor(h)).padStart(2,'0')}:${String(Math.round((h%1)*60)).padStart(2,'0')}`;
 const displayTime=iso=>new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Nicosia',hour:'2-digit',minute:'2-digit'}).format(new Date(iso));
 const key=c=>JSON.stringify(planForObservation(c));
 const bridgeCurrent=proof=>{try{return Boolean(isObservationRestartCurrent?.(proof))&&sameRestart(proof.plan,planForObservation(getContext()));}catch{return false;}};
 const historicalTime=iso=>new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Nicosia',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',timeZoneName:'shortOffset'}).format(new Date(iso));
 function stage(mode,focus=false){
  $('assessment-workbench').dataset.mode=mode;$('resilience-edit').setAttribute('aria-pressed',String(mode==='conditions'));$('resilience-show-result').setAttribute('aria-pressed',String(mode==='result'));$('resilience-show-result').disabled=!record;
  if(focus){const target=$(mode==='conditions'?'resilience-demand':'resilience-verdict');target.focus({preventScroll:true});$('assessment-workbench').scrollIntoView?.({block:'start'});}
 }
 function editConditions(focus=true){stage('conditions',focus);return true;}
 function showResult(focus=true){if(!snapshot()){editConditions(focus);return false;}stage('result');drawInventory(getContext(),record);if(focus)stage('result',true);return true;}
 $('resilience-edit').onclick=()=>editConditions();$('resilience-show-result').onclick=()=>showResult();
 $('resilience-evidence-view').onchange=()=>{for(const name of ['accounting','sensitivity','comparison','source'])$('resilience-evidence-'+name).hidden=name!==$('resilience-evidence-view').value;};
 for(const id of ['resilience-start','resilience-outage'])for(let h=0;h<24;h++)$(id).add(new Option(clock(h),String(h)));
 function value(id){const raw=$(id).value.trim();if(!raw)throw Error('Complete every test condition.');const v=Number(raw);if(!Number.isFinite(v))throw Error('Test conditions must be finite numbers.');return v;}
 function conditions(){return {demand_multiplier:1+value('resilience-demand')/100,production_multiplier:1-value('resilience-loss')/100,initial_storage_m3:value('resilience-initial'),outage:{start_hour:value('resilience-outage'),duration_hours:value('resilience-duration')}};}
 function args(c,scenario,production=c.plan.production){return {times:c.day.times,production,demand:c.demand,capacity:c.capacity,reserve:c.reserve,initial:c.plan.totals.initial_storage_m3,target:c.plan.totals.final_storage_m3,scenario,startHour:value('resilience-start')};}
 function clearProof(){reading=null;$('resilience-manual-reading').hidden=false;text('resilience-reading-status','');}
 function revokeBridge(){clearProof();$('resilience-map').checked=false;invalidate('The mapped observation changed. Compare and select it again, or explicitly run with the scenario value.');text('resilience-reading-status','Historical mapping revoked. Starting water is now an unverified scenario value.');}
 function invalidate(message){needsExplicitRun=true;record=null;$('resilience-export').disabled=true;editConditions(false);text('resilience-error',message);text('resilience-verdict','Assessment needs recalculation.');text('resilience-explanation','Run assessment to update the result.');for(const id of ['resilience-kpis','resilience-chart','resilience-matrix','resilience-comparison','resilience-ledger','resilience-horizon','resilience-chart-note','resilience-matrix-note','resilience-identity','resilience-conditions-summary'])$(id).replaceChildren();}
 const sameReading=(a,b)=>a.time===b.time&&a.asset_id===b.asset_id&&a.value===b.value&&a.reviewAsOf===b.reviewAsOf&&a.identity.observations.sha256===b.identity.observations.sha256&&a.identity.contract.sha256===b.identity.contract.sha256;
 function refreshReadings(c){
  readings=getTankReadings().filter(r=>c.day.times.some(t=>Date.parse(t)===r.epoch)&&r.value<=c.capacity);
  if(reading?.bridge){if(!bridgeCurrent(reading.bridge)){revokeBridge();return false;}}
  else if(reading&&!readings.some(r=>sameReading(r,reading))){clearProof();$('resilience-map').checked=false;invalidate('The selected reading changed. Select it again, or explicitly run with the scenario value.');}
  const previous=$('resilience-reading').value;$('resilience-reading').replaceChildren(new Option('Choose a reading',''),...readings.map((r,i)=>new Option(`${r.assetLabel} / ${displayTime(r.time)} / ${fmt(r.value,0)} m³`,String(i))));
  if(readings[Number(previous)]&&previous!=='')$('resilience-reading').value=previous;
  $('resilience-use-reading').disabled=!readings.length;
  if(!reading&&!needsExplicitRun)text('resilience-reading-status',readings.length?`${readings.length} hourly readings available by their review cutoff.`:'No compatible known hourly tank readings for this day. Import observations in Pilot inputs.');
  return true;
 }
 function render(){
  const c=getContext(),next=key(c);
  if(contextKey!==next){contextKey=next;record=null;needsExplicitRun=false;clearProof();$('resilience-start').value='0';$('resilience-initial').value=c.plan.totals.initial_storage_m3;$('resilience-map').checked=false;}
  $('resilience-initial').max=c.capacity;text('resilience-plan-name',`${c.label} / ${c.day.date} / ${fmt(c.capacity,0)} m³ tank`);if(refreshReadings(c)&&!record&&!needsExplicitRun)run();else if(record)drawInventory(c,record);
 }
 function run(focus=false){
  if(reading?.bridge&&!bridgeCurrent(reading.bridge)){revokeBridge();return;}
  needsExplicitRun=true;record=null;$('resilience-export').disabled=true;text('resilience-error','');
  try{
   const c=getContext(),scenario=conditions(),input=args(c,scenario),selected=replayPlan(input);
   const comparator=c.imported?c.day.schedules[String(c.capacity)].production:Array(24).fill(c.demand),comparatorLabel=c.imported?'Frozen reference':'Flat production';
   const control=replayPlan({...input,production:comparator});
   record={schema:1,kind:'fixed_plan_consequence_assessment',createdAt:new Date().toISOString(),scope:'Declared scenario replay; no new schedule, field outcome or operating authority',date:c.day.date,planLabel:c.label,identity:c.identity,observation:reading,inputs:input,selected,control:{label:comparatorLabel,inputs:{...input,production:comparator},result:control}};
   present(c,record);needsExplicitRun=false;$('resilience-export').disabled=false;showResult(focus);
  }catch(e){invalidate(e.message);text('resilience-verdict','Assessment unavailable');}
 }
 function drawInventory(c,r){
  const inventory=result=>{const values=Array(25).fill(null);values[result.start_hour]=result.totals.initial_storage_m3;for(const row of result.rows)values[row.hour+1]=row.storage_end_m3;return values;};
  lineChart('resilience-chart',[{name:c.label,values:inventory(r.selected)},{name:r.control.label,values:inventory(r.control.result),dash:'6 4'}],{max:c.capacity*1.08,unit:'m³',levels:[{value:c.reserve,label:'Reserve'},{value:c.capacity,label:'Capacity'}]});
 }
 function conditionSummary(){
  const r=snapshot();if(!r)return '';
  const s=r.inputs.scenario,demand=100*(s.demand_multiplier-1),loss=100*(1-s.production_multiplier),parts=[];
  if(demand)parts.push(`demand ${demand>0?'+':''}${fmt(demand,1)}%`);
  if(loss)parts.push(`production loss ${fmt(loss,1)}%`);
  parts.push(`starting water ${fmt(r.selected.totals.initial_storage_m3,1)} m³`);
  if(s.outage.duration_hours)parts.push(`interruption ${clock(s.outage.start_hour)} for ${fmt(s.outage.duration_hours,2)} h`);
  return parts.join(', ');
 }
 function present(c,r){
  const a=r.selected,b=r.control.result,t=a.totals,event=a.events.find(e=>e.type==='reserve_breach');
  const hasLoss=t.unmet_m3>1e-6,hasDeficit=t.max_reserve_deficit_m3>1e-6;
  text('resilience-conditions-summary',`Simulation: ${conditionSummary()}.`);
  text('resilience-verdict',hasLoss?'Water demand unmet':hasDeficit?'Reserve breached':t.terminal_deficit_m3>1e-6?'End-of-day target missed':'Reserve and target hold');
  text('resilience-explanation',`${event?`Reserve crossing at ${displayTime(event.time)}. `:''}${hasDeficit?`Largest reserve deficit: ${fmt(t.max_reserve_deficit_m3,1)} m³. `:''}${hasLoss?`${fmt(t.unmet_m3,1)} m³ of demand cannot be served. `:''}${t.terminal_deficit_m3>1e-6?`The plan ends ${fmt(t.terminal_deficit_m3,1)} m³ below its original target.`:''}`);
  kpis('resilience-kpis',[
   ['Lowest inventory',`${fmt(t.min_storage_m3,0)} m³`,`Reserve ${fmt(c.reserve,0)} m³`],
   ['Reserve deficit',`${fmt(t.max_reserve_deficit_m3,0)} m³`,event?`First crossing ${displayTime(event.time)}`:'No crossing in this case'],
   ['Unserved demand',`${fmt(t.unmet_m3,0)} m³`,`${fmt(t.delivered_m3,0)} m³ served`],
   ['End-of-day shortfall',`${fmt(t.terminal_deficit_m3,0)} m³`,`Target ${fmt(r.inputs.target,0)} m³`]
  ]);
  drawInventory(c,r);
  text('resilience-horizon',`${historicalTime(r.inputs.times[a.start_hour])} to end of plan`);
  text('resilience-chart-note',`Hourly boundaries; the export retains crossing timestamps. ${reading?.bridge?'Starting inventory is the selected historical reading; source and mapping are unverified.':reading?'Starting inventory comes from the explicitly mapped reading.':'Starting inventory is a scenario value.'}`);
  table('resilience-comparison',['Plan','Water made m³','Water served m³','Lowest tank m³','Reserve deficit m³','End shortfall m³'],[[c.label,t],[r.control.label,b.totals]].map(([label,v])=>[label,fmt(v.available_production_m3,1),fmt(v.delivered_m3,1),fmt(v.min_storage_m3,1),fmt(v.max_reserve_deficit_m3,1),fmt(v.terminal_deficit_m3,1)]));
  table('resilience-ledger',['Hour','Start m³','Planned m³','Produced m³','Demand m³','Served m³','Spill m³','Unserved m³','End m³'],a.rows.map(row=>[clock(row.hour),...['storage_start_m3','requested_production_m3','available_production_m3','demand_m3','delivered_m3','spill_m3','unmet_m3','storage_end_m3'].map(field=>fmt(row[field],1))]));
  const demandSteps=[0,5,10,15,20,30],lossSteps=[0,5,10,20,30,50];
  const matrix=document.createElement('table'),head=matrix.createTHead().insertRow();
  for(const label of ['Demand / production loss',...lossSteps.map(v=>`${v}%`)]){const th=document.createElement('th');th.scope='col';th.textContent=label;head.append(th);}
  const body=matrix.createTBody();r.sensitivity=[];
  for(const demand of demandSteps){const tr=body.insertRow(),th=document.createElement('th');th.scope='row';th.textContent=`+${demand}%`;tr.append(th);
   for(const loss of lossSteps){const scenario={...r.inputs.scenario,demand_multiplier:1+demand/100,production_multiplier:1-loss/100},test=replayPlan({...r.inputs,scenario}),v=test.totals,td=tr.insertCell(),button=document.createElement('button');
    r.sensitivity.push({demand_change_percent:demand,production_loss_percent:loss,reserve_deficit_m3:v.max_reserve_deficit_m3,unmet_m3:v.unmet_m3,terminal_deficit_m3:v.terminal_deficit_m3});
    button.textContent=fmt(v.max_reserve_deficit_m3,0);button.className=v.unmet_m3>1e-6?'case-unserved':v.max_reserve_deficit_m3>1e-6?'case-deficit':'case-held';button.setAttribute('aria-label',`Demand +${demand}%, production loss ${loss}%: reserve deficit ${fmt(v.max_reserve_deficit_m3,1)} m³, unserved demand ${fmt(v.unmet_m3,1)} m³`);button.setAttribute('aria-pressed',String(value('resilience-demand')===demand&&value('resilience-loss')===loss));button.onclick=()=>{$('resilience-demand').value=demand;$('resilience-loss').value=loss;run(true);};td.append(button);
   }
  }
  $('resilience-matrix').replaceChildren(matrix);
  const m=a.margins;
  text('resilience-matrix-note',`Light cells hold the reserve; hatched cells cross it; dark cells leave demand unserved. Minimum starting water for this selected case: ${m.minimum_initial_storage_m3===null?'more than this tank can hold':fmt(m.minimum_initial_storage_m3,1)+' m³'}. This boundary protects reserve and service; it excludes the terminal target.`);
  facts('resilience-identity',[['Plan',c.label],['Plan source',c.imported?c.identity.plan?.name??'Imported candidate':'Retained historical fixture'],['Starting water',fmt(t.initial_storage_m3,1)+' m³'],['Reserve',fmt(c.reserve,0)+' m³'],['Source data SHA-256',c.identity.data_sha256],['Balance error',fmt(t.mass_balance_error_m3,8)+' m³']]);
 }
 function acceptObservationRestart(proof){
  if(!bridgeCurrent(proof))throw Error('The observation, cutoff, mapping or selected plan changed. Compare the observations again.');
  const c=getContext();contextKey=key(c);
  for(const id of ['resilience-demand','resilience-loss','resilience-outage','resilience-duration'])$(id).value='0';
  $('resilience-start').value=proof.start_hour;$('resilience-initial').value=proof.reading.value;$('resilience-initial').max=c.capacity;
  reading={...structuredClone(proof.reading),mapping:'Explicit tank mapping carried from Observed departures',tankCapacityM3:c.capacity,bridge:structuredClone(proof)};
  $('resilience-map').checked=false;$('resilience-manual-reading').hidden=true;$('resilience-reading-panel').open=true;
  text('resilience-plan-name',`${c.label} / ${c.day.date} / ${fmt(c.capacity,0)} m³ tank`);
  text('resilience-reading-status',`${reading.sourceKind==='synthetic_fixture'?'Synthetic':'Unverified operator'} historical reading: ${historicalTime(reading.time)}. First available ${historicalTime(reading.available_at)}; comparison cutoff ${historicalTime(proof.comparison_cutoff)}. Mapping is shared with Observed departures.`);
  run(true);
 }
 $('resilience-form').onsubmit=e=>{e.preventDefault();if(!$('resilience-form').checkValidity()){invalidate('Complete the highlighted condition within its allowed range.');$('resilience-form').reportValidity();return;}run(true);};
 for(const id of ['resilience-demand','resilience-loss','resilience-initial','resilience-start','resilience-outage','resilience-duration'])for(const event of ['input','change'])$(id).addEventListener(event,()=>{invalidate('Conditions changed. Run assessment to update the result.');if(id==='resilience-start'||id==='resilience-initial')clearProof();});
 $('resilience-reset').onclick=()=>{const c=getContext();for(const id of ['resilience-demand','resilience-loss','resilience-start','resilience-outage','resilience-duration'])$(id).value='0';$('resilience-initial').value=c.plan.totals.initial_storage_m3;clearProof();run(true);};
 $('resilience-use-reading').onclick=()=>{
  const raw=$('resilience-reading').value,r=raw===''?null:readings[Number(raw)];
  if(!r||!$('resilience-map').checked){text('resilience-reading-status','Select a reading and explicitly map its stream to this tank.');return;}
  const c=getContext(),h=c.day.times.findIndex(t=>Date.parse(t)===r.epoch);if(h<0||r.value>c.capacity){text('resilience-reading-status','The reading does not fit this scenario.');return;}
  $('resilience-start').value=h;$('resilience-initial').value=r.value;reading={...r,mapping:'Reviewer maps this stream to the selected scenario tank',tankCapacityM3:c.capacity};text('resilience-reading-status',`${r.sourceKind==='synthetic_fixture'?'Synthetic':'Unverified operator'} reading at ${displayTime(r.time)}; known by ${displayTime(r.reviewAsOf)}. Only the remaining plan is replayed.`);run(true);
 };
 $('resilience-map').onchange=()=>{if(reading&&!$('resilience-map').checked){clearProof();invalidate('Mapping changed. Run assessment to replace the previous result.');text('resilience-reading-status','Mapping removed. Starting water is now an unverified scenario value.');}};
 $('resilience-reading').onchange=()=>{if(reading){clearProof();invalidate('Reading changed. Recalculate before exporting.');text('resilience-reading-status','Reading selection changed. Apply the selected reading or run with the scenario value.');}};
 function snapshot(){return record&&contextKey===key(getContext())&&(!reading||(reading.bridge?bridgeCurrent(reading.bridge):getTankReadings().some(r=>sameReading(r,reading))))?JSON.parse(JSON.stringify(record)):null;}
 $('resilience-export').onclick=()=>{const current=snapshot();if(current)json(`aktina-${current.date}-plan-assessment.json`,current);else if(reading?.bridge)revokeBridge();};
 function setScenario(scenario){
  const c=getContext();contextKey=key(c);clearProof();
  for(const [id,value] of Object.entries({'resilience-demand':100*((scenario.demand_multiplier??1)-1),'resilience-loss':100*(1-(scenario.production_multiplier??1)),'resilience-start':0,'resilience-initial':c.plan.totals.initial_storage_m3,'resilience-outage':scenario.outage?.start_hour??0,'resilience-duration':scenario.outage?.duration_hours??0}))$(id).value=String(Number(value.toFixed(10)));
  $('resilience-initial').max=c.capacity;run(true);return snapshot();
 }
 return {render,snapshot,acceptObservationRestart,setScenario,editConditions,showResult,conditionSummary};
}
