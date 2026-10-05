import {replaySequence} from './plan-sequence.mjs';
import {sequenceRevisionTemplate,compareSequenceRevision} from './sequence-revision.mjs';
import {sequenceSolarAllocationTemplate,evaluateSequenceSolarAllocation} from './solar-allocation.mjs';
import {solarEvidenceRequest,waterServiceDisplay,waterServiceRows} from './plan-revision-ui.mjs';

export const planSequenceTemplate=`
<form id="sequence-form" class="sequence-toolbar" novalidate><div id="sequence-period" class="sequence-period"><label>From<input id="sequence-from" type="date" required></label><label>Through<input id="sequence-through" type="date" required></label><label>Reference plan<select id="sequence-tank"></select></label></div><span id="sequence-import-label" hidden></span><button type="submit">Run continuous review</button></form>
<p id="sequence-status" class="subtle" role="status">Carry water forward across supplied plans. Starting water is added once.</p><p id="sequence-error" role="alert" hidden></p>
<details id="sequence-inputs" class="sequence-inputs"><summary>Conditions and files <span id="sequence-condition-summary" class="review-detail-hint"></span></summary><div class="sequence-condition-fields"><label>Starting water (m³)<input id="sequence-initial" type="number" min="0" step="any" required></label><label>Demand change (%)<input id="sequence-demand" type="number" min="-100" step="any" value="10" required></label><label>Production loss (%)<input id="sequence-loss" type="number" min="0" max="100" step="any" value="0" required></label></div><div id="sequence-recurring-outage" class="sequence-condition-fields"><label>Daily interruption starts (elapsed hour)<input id="sequence-outage-start" type="number" min="0" max="24" step="any" value="12" required></label><label>Daily interruption duration (hours)<input id="sequence-outage-duration" type="number" min="0" max="24" step="any" value="0" required></label></div><p id="sequence-outage-note" class="micro">Demand and production changes persist across every block. Any daily interruption repeats; water never resets.</p><div class="actions"><label class="revision-file-action">Open sequence or review<input id="sequence-file" type="file" accept=".json,application/json"></label><button id="sequence-template" type="button">Export sequence template</button><button id="sequence-use-reference" type="button" hidden>Use retained plans</button></div><details><summary>Source and method</summary><div id="sequence-source"></div><p class="micro">Supplied fixed plans; issue timing is unverified. Complete 24 elapsed-hour blocks only. Uniform hourly flows, one tank and declared unit limit; no water-quality, ramp or pressure model. No plan generation or operating authority.</p></details></details>
<section id="sequence-result" class="sequence-result" tabindex="-1" hidden><div class="sequence-result-heading"><p id="sequence-service-heading" hidden></p><p id="sequence-conclusion"></p><div class="actions"><button id="sequence-service-inspect" type="button" hidden>Inspect difference</button><button id="sequence-export" disabled>Export review</button></div></div><p id="sequence-service-detail" class="micro" hidden></p><div id="sequence-chart" class="chart" role="region" tabindex="0" aria-label="Continuous tank inventory for supplied and flat plans"></div><p id="sequence-chart-note" class="micro"></p><p id="sequence-budget-finding" class="micro" hidden></p><div id="sequence-outcomes" class="table-wrap"></div><p id="sequence-failure" class="sequence-failure"></p><div class="sequence-day-tools"><label>Inspect block<select id="sequence-day"></select></label><button id="sequence-freeze" disabled>Prepare return file</button></div><p id="sequence-day-status" class="micro"></p>
<details id="sequence-revision-files"><summary>Case and return files <span id="sequence-revision-status" class="review-detail-hint" role="status">No returned plan</span></summary><p id="sequence-revision-horizon" class="micro">Prepare the case and unchanged production template for a supplied return.</p><div class="revision-file-tools"><button id="sequence-case-export" disabled>Export case</button><button id="sequence-return-template" disabled>Export return CSV</button><label class="revision-file-action">Import returned plan<input id="sequence-return-file" type="file" accept=".csv,text/csv" disabled></label><button id="sequence-return-remove" disabled>Remove return</button></div><details><summary>Case identity</summary><div id="sequence-case-identity"></div></details><details class="sequence-day-handoff"><summary>Original day handoff</summary><div class="revision-file-tools"><button id="sequence-review-day" disabled>Review original day</button><button id="sequence-export-day" disabled>Export original day case</button></div><p class="micro">This separate handoff contains the original production and original carried water for the selected block, even while a returned plan is displayed. Export the continuous review to retain the returned plan and its downstream effects.</p></details></details>
<details id="sequence-solar" hidden><summary>Solar use <span id="sequence-solar-status" class="review-detail-hint" role="status">Unknown / no profile</span></summary><p id="sequence-solar-conclusion" class="micro">Add a plant-specific allocation to compare eligible solar use.</p><details id="sequence-solar-profile"><summary>Profile and source</summary><div class="revision-file-tools"><select id="sequence-solar-format" aria-label="Continuous solar template format"><option value="constant_power">Constant power</option><option value="interval_energy">Interval energy</option></select><button id="sequence-solar-template" disabled>Export profile template</button><label class="revision-file-action">Import solar profile<input id="sequence-solar-file" type="file" accept=".json,application/json" disabled></label><button id="sequence-solar-remove" disabled>Remove profile</button></div><div id="sequence-solar-source"></div><p class="micro">Declared plant-eligible solar, not regional curtailment. Energy ranges follow supplied energy and any known power limit; they are not confidence intervals or measured recovery.</p><div id="sequence-solar-known" class="table-wrap"></div></details><details id="sequence-solar-evidence" hidden><summary>Evidence needed</summary><p id="sequence-evidence-summary" class="micro"></p><div id="sequence-evidence-intervals" class="table-wrap"></div><button id="sequence-evidence-export" disabled>Export evidence request</button></details></details>
<details id="sequence-decision"><summary id="sequence-decision-label">Record next step</summary><div class="sequence-condition-fields"><label>Reviewer<input id="sequence-reviewer" maxlength="80" value="Loucas"></label><label>Next step<select id="sequence-decision-value"><option>Needs team review</option><option>Request revised sequence</option></select></label></div><label>Reason<textarea id="sequence-reason" maxlength="2000" rows="2"></textarea></label><p class="micro">Export keeps the note with this exact review. Reopening recalculates the results and starts a new note.</p></details><details id="sequence-accounting-details"><summary>Water accounting</summary><div id="sequence-storage-proof" class="table-wrap"></div><p class="micro">Storage requirements hold production, demand, reserve and ending target fixed over the full period. Adding starting water can itself require a larger tank to avoid spill. Clock labels are approximate; the export retains exact elapsed-hour witnesses. These water-balance limits do not establish availability of extra water or physical plant feasibility.</p><div id="sequence-service-proof" class="table-wrap" tabindex="-1" hidden></div><p id="sequence-service-clock-note" class="micro" hidden>Exact witnesses use elapsed hours from the first sequence timestamp. Clocks are approximate. Hourly totals can hide differences within an hour.</p><div id="sequence-service-hours" class="table-wrap" hidden></div><div id="sequence-budget-proof" class="table-wrap"></div><p class="micro">Production budget: exact fractions for fixed available output after derating and outages. Schedules with different outage exposure can change output and are not ruled out; their feasibility is not established. A zero gap does not establish feasible timing, reserve, capacity or plant operation. A positive gap does not establish that extra production is physically available.</p><div id="sequence-accounting" class="table-wrap"></div><div id="sequence-days" class="table-wrap"></div><p class="micro">Daily targets do not reset inventory. Final target shortfall is reported separately from unmet demand; reduced water service is never credited as an energy saving.</p></details></section>`;

const HOUR=3600000,MiB=1024*1024;
const parse=text=>JSON.parse(text.replace(/^\uFEFF/,''));
const finite=value=>typeof value==='number'&&Number.isFinite(value);
const fields=(value,keys,label)=>{if(!value||typeof value!=='object'||Array.isArray(value))throw Error(`${label} must be an object.`);for(const key of Object.keys(value))if(!keys.includes(key))throw Error(`Unsupported ${label} field: ${key}.`);};
const plain=(value,max,label)=>{if(typeof value!=='string'||!value.trim()||value.length>max||/[\u0000-\u001f]/.test(value))throw Error(`Invalid ${label}.`);return value;};
const same=(a,b)=>{if(a===b)return true;if(!a||!b||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b))return false;const keys=Object.keys(a);return keys.length===Object.keys(b).length&&keys.every(key=>Object.hasOwn(b,key)&&same(a[key],b[key]));};
const clone=value=>JSON.parse(JSON.stringify(value));
const positiveQuantity=value=>value.exact.numerator!=='0';
const requirementAmount=value=>value.value===null?'outside the numeric display range':`${value.value!==0&&(value.value<.01||value.value>1e12)?value.value.toExponential(3):value.value.toLocaleString('en-GB',{maximumFractionDigits:2})} m³`;
export function storageRequirementFinding(requirements){
 const initial=positiveQuantity(requirements.initial_shortfall_m3),capacity=positiveQuantity(requirements.without_spill.capacity_shortfall_m3);
 if(initial){
  const gap=requirements.initial_shortfall_m3,minimum=requirements.minimum_initial_m3;
  if(gap.value===null||minimum.value===null||minimum.value-gap.value===minimum.value)return `Starting-water gap: ${requirementAmount(gap)}. This exact arithmetic gap does not establish a physical shortage.`;
  const coupled=positiveQuantity(requirements.without_spill.capacity_shortfall_after_initial_topup_m3);
  const shortage=requirements.initial_shortfall_m3.value===null?'The exact starting-water shortage is outside the numeric display range.':`About ${requirementAmount(requirements.initial_shortfall_m3)} more starting water is needed.`;
  return `${shortage} ${coupled?`With that added, the no-spill capacity requirement is ${requirementAmount(requirements.without_spill.minimum_capacity_after_initial_topup_m3)}.`:'A larger tank alone cannot fix this shortage.'}`;
 }
 if(capacity){
  const gap=requirements.without_spill.capacity_shortfall_m3,minimum=requirements.without_spill.minimum_capacity_m3;
  const precision=gap.value===null||minimum.value===null||minimum.value-gap.value===minimum.value;
  return `${requirements.with_spill.feasible?'Water requirements hold if overflow is allowed.':'Tank capacity limits this fixed plan in the model.'} No-spill capacity gap: ${requirementAmount(gap)}. ${precision?'This exact arithmetic gap does not establish a physical shortage.':`Required capacity: about ${requirementAmount(minimum)}.`}`;
 }
 return 'The fixed plan meets modeled demand, reserve and ending-water requirements without spill.';
}
export function setupPlanSequence({$,fmt,text,facts,table,lineChart,download,csv,sha256,getReference,openDay,Papa}){
 let initialized=false,imported=false,source=null,sourceFile=null,referenceFiles=null,record=null,generation=0,retainedOutages=[],sourceMultipliers={};
 let revisionCase=null,returnedFile=null,comparison=null,returnPending=false,solarFile=null,solarComparison=null,solarGeneration=0,solarPending=false;
 const local=value=>new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Nicosia',year:'numeric',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',second:'2-digit',timeZoneName:'shortOffset'}).format(new Date(value));
 const dayLabel=value=>new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Nicosia',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));
 const water=value=>value.toLocaleString('en-GB',value!==0&&Math.abs(value)<.01?{maximumSignificantDigits:3}:{maximumFractionDigits:2});
 function controls(){
  const pending=returnPending||solarPending;
  $('sequence-export').disabled=!record||pending;$('sequence-freeze').disabled=!record||pending;
  for(const id of ['sequence-case-export','sequence-return-template','sequence-return-file'])$(id).disabled=!revisionCase||returnPending;
  $('sequence-return-remove').disabled=!returnedFile&&!returnPending;$('sequence-solar').hidden=!comparison;
  for(const id of ['sequence-solar-template','sequence-solar-format'])$(id).disabled=!comparison||solarPending;
  $('sequence-solar-file').disabled=!comparison;$('sequence-solar-remove').disabled=!solarFile&&!solarPending;$('sequence-evidence-export').disabled=!solarComparison||pending;
 }
 function resetDecision(message){
  const changed=$('sequence-reason').value.trim()||$('sequence-decision-value').value!=='Needs team review';
  $('sequence-reason').value='';$('sequence-decision-value').value='Needs team review';$('sequence-decision').open=false;
  text('sequence-decision-label',changed&&message?`Record new next step (${message})`:'Record next step');
 }
 function resetSolar(){
  solarGeneration++;solarFile=null;solarComparison=null;solarPending=false;$('sequence-solar-file').value='';$('sequence-solar').open=false;$('sequence-solar-profile').open=false;
  text('sequence-solar-status','Unknown / no profile');text('sequence-solar-conclusion','Add a plant-specific allocation to compare eligible solar use.');$('sequence-solar-source').replaceChildren();$('sequence-solar-known').replaceChildren();$('sequence-solar-evidence').hidden=true;$('sequence-solar-evidence').open=false;$('sequence-evidence-intervals').replaceChildren();text('sequence-evidence-summary','');
 }
 function resetReturn(clearCase=false){
  returnedFile=null;comparison=null;returnPending=false;for(const id of ['sequence-service-heading','sequence-service-detail','sequence-service-inspect','sequence-service-proof','sequence-service-clock-note','sequence-service-hours'])$(id).hidden=true;resetSolar();resetDecision(clearCase?'case changed':'return changed');$('sequence-return-file').value='';
  if(clearCase){revisionCase=null;$('sequence-case-identity').replaceChildren();$('sequence-revision-files').open=false;text('sequence-revision-horizon','Prepare the case and unchanged production template for a supplied return.');}
  text('sequence-revision-status',revisionCase?'Case ready / no return':'No returned plan');controls();
 }
 const identity=file=>({name:file.name,sha256:file.sha256});
 async function readFile(file,limit=4){
  if(!file||file.size>limit*MiB)throw Error(`Choose a UTF-8 file no larger than ${limit} MiB.`);plain(file.name,255,'filename');
  const bytes=await file.arrayBuffer();if(bytes.byteLength>limit*MiB)throw Error(`File exceeds ${limit} MiB.`);
  return {name:file.name,text:new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes),sha256:await sha256(bytes)};
 }
 async function checkedCase(file){
  const value=parse(file.text);fields(value,['schema','kind','source_file','reference_files','conditions','block_index'],'continuous revision case');
  if(value.schema!==1||value.kind!=='continuous_plan_revision_case')throw Error('Use a continuous_plan_revision_case file.');
  const raw=await embedded(value.source_file),item=validateSource(parse(raw.text)),refs=await verifyReference(value.reference_files,item),results=pair(item,value.conditions);
  if(!Number.isInteger(value.block_index)||value.block_index<0||value.block_index>=item.inputs.blocks.length)throw Error('First editable block is outside the sequence.');
  return {file,value,source:item,sourceFile:raw,referenceFiles:refs,results};
 }
 function compareReturn(c,file){return compareSequenceRevision({input:appliedInput(c.source,c.value.conditions),block_index:c.value.block_index,caseIdentity:identity(c.file),csvText:file.text,proposalIdentity:identity(file),specific_energy_kwh_m3:c.source.specific_energy_kwh_m3,Papa});}
 function showCase(){
  const c=revisionCase,blocks=c.source.inputs.blocks,start=c.value.block_index;
  text('sequence-revision-horizon',`Return every hour from ${local(blocks[start].times[0])} through ${local(new Date(Date.parse(blocks.at(-1).times[23])+HOUR).toISOString())}. The preceding ${start} block${start===1?'':'s'} stay unchanged; both alternatives replay the full ${blocks.length}-block period.`);
  facts('sequence-case-identity',[['Case',c.file.name],['Case SHA-256',c.file.sha256],['Sequence SHA-256',c.sourceFile.sha256],['First editable block',start+1],['Source authority','Supplied bytes; authorship and plant permission are not authenticated']]);
  text('sequence-revision-status',comparison?'Returned plan compared':'Case ready / no return');controls();
 }
 async function freezeCase(){
  if(!record)return;const selectedBlock=Number($('sequence-day').value),token=++generation;resetReturn(true);returnPending=true;controls();
  try{
   const value={schema:1,kind:'continuous_plan_revision_case',source_file:sourceFile,...(referenceFiles?{reference_files:referenceFiles}:{}),conditions:clone(record.conditions),block_index:selectedBlock};
   const raw=JSON.stringify(value,null,2)+'\n';if(new TextEncoder().encode(raw).length>32*MiB)throw Error('Case exceeds the 32 MiB reopening limit. Choose a shorter sequence.');
   const file=await fileFromText('aquashift-continuous-case.json',raw);if(token!==generation)return;
   revisionCase={file,value,source:clone(source),sourceFile,referenceFiles,results:record.results};returnPending=false;show(selectedBlock);showCase();$('sequence-revision-files').open=true;$('sequence-case-export').focus();
  }catch(e){if(token===generation){returnPending=false;controls();$('sequence-revision-files').open=true;error(e,false,'sequence-freeze');}}
 }
 const range=(value,delta=false)=>{if(value===null||value===undefined)return 'Unknown';const f=n=>(delta&&n>0?'+':'')+water(n);return typeof value==='number'?f(value):value.lower===value.upper?f(value.lower):`${f(value.lower)} to ${f(value.upper)}`;};
 function energyRows(result,complete=true){
  const bounds=complete?result?.bounds:result?.known_bounds,totals=complete?result?.totals:result?.known_totals;
  return ['solar','other'].map(key=>[key==='solar'?'Solar use (kWh)':'Other electricity (kWh)',...['original','revised','delta'].map((side,i)=>range((complete&&i===2?result?.difference_envelope?.[`delta_${key}_kwh`]:null)??bounds?.[`${side}_${key}_kwh`]??totals?.[`${side}_${key}_kwh`]??null,i===2))]);
 }
 function showOutcomes(){
  const a=comparison.original,b=comparison.revised,rows=[['Unserved water (m³)','unmet_m3'],['Reserve deficit (m³)','max_reserve_deficit_m3'],['Final water (m³)','final_storage_m3'],['Production (m³)','available_production_m3'],['Spill (m³)','spill_m3']].map(([label,key])=>[label,water(a.result.totals[key]),water(b.result.totals[key]),range(comparison.changes[key],true)]);
  rows.push(['Total electricity (kWh)',range(a.modeled_production_energy_kwh),range(b.modeled_production_energy_kwh),range(solarComparison?.full_load_totals?.delta_load_kwh??comparison.changes.modeled_production_energy_kwh,true)],...energyRows(solarComparison));
  table('sequence-outcomes',['Whole period','Original','Returned','Change'],rows);
 }
 function solarSummary(){const {status,coverage,bounds,known_bounds,totals,known_totals,full_load_totals,difference_envelope}=solarComparison;const {contributions,...summary}=difference_envelope;return {status,coverage,bounds,known_bounds,totals,known_totals,full_load_totals,difference_envelope:summary};}
 function showSolar(changed=false){
  if(!solarComparison)return;const r=solarComparison,c=r.coverage,sourceKind=r.allocation.source_kind==='illustrative_scenario'?'Illustrative':'Reviewer supplied';
  text('sequence-solar-status',`${changed?'Changed evidence / ':''}${sourceKind} / ${water(c.known_hours)} of ${water(c.horizon_hours)} h known${r.status==='unknown_energy'?' / specific energy unknown':r.status==='complete'?'':' / absolute totals unknown'}`);
  facts('sequence-solar-source',[['Profile',solarFile.name],['SHA-256',solarFile.sha256],['Source',r.allocation.source_label],['Plant',r.allocation.plant_mapping],['Review cutoff',r.allocation.review_as_of],['Late / unknown hours',`${water(c.late_hours)} / ${water(c.unknown_hours)}`],['Interval meaning',r.allocation.interval_semantics==='interval_energy'?'Declared interval energy and any known power limit; timing unknown':'Declared constant power']]);
  const envelope=r.difference_envelope,delta=envelope.delta_solar_kwh;
  const tolerance=64*Number.EPSILON*Math.max(Number.MIN_VALUE,r.full_load_totals?.original_load_kwh??0,r.full_load_totals?.revised_load_kwh??0);
  let conclusion=r.status==='unknown_energy'?'Specific energy is unknown; electricity use cannot be calculated.':delta.lower<-tolerance&&delta.upper>tolerance?'Allowed solar timing can reverse the direction of the comparison.':delta.lower>tolerance?'Returned production uses more eligible solar under every allowed timing pattern.':delta.upper<-tolerance?'Returned production uses less eligible solar under every allowed timing pattern.':Math.max(Math.abs(delta.lower),Math.abs(delta.upper))<=tolerance?'No solar-use change at calculation precision.':'No positive minimum solar-use gain established.';
  const d=comparison.changes;conclusion+=waterServiceDisplay(comparison.water_service,comparison).qualification;if(d.available_production_m3!==0)conclusion+=' Production also changes.';if(d.final_storage_m3<0)conclusion+=' Returned final inventory is lower.';
  text('sequence-solar-conclusion',conclusion+' Conditional modeled use; no recovered-curtailment claim.');
  const intervals=envelope.contributions.flatMap(row=>row.focus_intervals?.map(focus=>({...row,...focus}))??[row]).filter(row=>row.width_kwh>0).sort((a,b)=>b.width_kwh-a.width_kwh||a.start.localeCompare(b.start)),unknown=envelope.status==='unknown_energy',needs=unknown||envelope.width_kwh>0;
  $('sequence-solar-evidence').hidden=false;$('sequence-solar-evidence').open=false;$('sequence-evidence-export').hidden=!needs;
  text('sequence-evidence-summary',unknown?'Declare supported plant specific energy (kWh/m³) before comparing electricity.':!needs?'No further solar timing evidence is needed for this modeled change at calculation precision.':`${intervals.length>5?`Showing 5 of ${intervals.length} uncertain intervals. `:''}Confirm plant-eligible solar in these intervals. Finer intervals alone may not resolve the range.`);
  if(needs&&!unknown)table('sequence-evidence-intervals',['Interval / Cyprus time','Possible change (kWh)'],intervals.slice(0,5).map(row=>[`${local(row.start)} to ${local(row.end)} / ${{known:'timing unknown',unknown:'incomplete evidence',late:'late evidence',missing:'missing evidence'}[row.status]}`,range(row.delta_solar_kwh,true)]));else $('sequence-evidence-intervals').replaceChildren();
  if(r.status==='partial'&&c.known_hours>0)table('sequence-solar-known',['Known intervals only','Original','Returned','Change'],energyRows(r,false));else $('sequence-solar-known').replaceChildren();
  $('sequence-solar-profile').open=false;showOutcomes();controls();
 }
 async function openRevision(file,value,token){
  let caseFile=file,proposalFile=null,profileFile=null,selectedBlock;
  if(value.kind==='continuous_plan_revision_review'){
   fields(value,['schema','kind','createdAt','scope','case_file','proposal_file','solar_file','selected_block','decision','reason','reviewer','results'],'continuous revision review');
   if(value.schema!==1||!['Needs team review','Request revised sequence'].includes(value.decision)||typeof value.reason!=='string'||value.reason.length>2000||typeof value.reviewer!=='string'||value.reviewer.length>80)throw Error('Unsupported continuous revision review.');
   caseFile=await embedded(value.case_file,32);proposalFile=await embedded(value.proposal_file);if(Object.hasOwn(value,'solar_file'))profileFile=await embedded(value.solar_file);selectedBlock=value.selected_block;
  }
  const checked=await checkedCase(caseFile),compared=proposalFile?compareReturn(checked,proposalFile):null,solar=profileFile?evaluateSequenceSolarAllocation({comparison:compared,allocation:parse(profileFile.text)}):null;
  if(selectedBlock!==undefined&&(!Number.isInteger(selectedBlock)||selectedBlock<0||selectedBlock>=checked.source.inputs.blocks.length))throw Error('Selected block is outside the sequence.');
  if(token!==generation)return;
  imported=true;source=checked.source;sourceFile=checked.sourceFile;referenceFiles=checked.referenceFiles;revisionCase=checked;returnedFile=proposalFile;comparison=compared;solarFile=profileFile;solarComparison=solar;
  record={schema:1,kind:'continuous_plan_review',createdAt:new Date().toISOString(),scope:'Full-period source replay; carried water is modeled, not observed.',source_file:sourceFile,...(referenceFiles?{reference_files:referenceFiles}:{}),conditions:clone(checked.value.conditions),results:checked.results};
  useConditions(record.conditions);sourceDisplay();show(selectedBlock??checked.value.block_index);showCase();if(solar)showSolar();$('sequence-inputs').open=false;$('sequence-revision-files').open=!comparison;
  text('sequence-status',comparison?'Saved return recalculated from retained files. Record a new next step.':'Frozen continuous case opened. Import the supplied production return.');
 }
 function number(id){const value=$(id).value.trim();if(!value||!Number.isFinite(Number(value)))throw Object.assign(Error('Complete every condition with a finite number.'),{field:id});return Number(value);}
 function clear(message='Inputs changed. Run continuous review again.'){
  generation++;record=null;resetReturn(true);$('sequence-result').hidden=true;for(const id of ['sequence-export','sequence-review-day','sequence-export-day'])$(id).disabled=true;
  $('sequence-budget-finding').hidden=true;text('sequence-budget-finding','');$('sequence-budget-proof').replaceChildren();$('sequence-storage-proof').replaceChildren();
  $('sequence-reason').value='';$('sequence-decision-value').value='Needs team review';$('sequence-decision').open=false;text('sequence-status',message);text('sequence-error','');$('sequence-error').hidden=true;text('sequence-condition-summary','Run to apply conditions');
 }
 function error(e,invalid=false,focus){$('sequence-error').hidden=false;text('sequence-error',e.message);if(invalid){$('sequence-inputs').open=true;text('sequence-status','No current continuous result. Correct the input and run again.');}focus??=e.field;if(invalid&&!focus)focus=[...document.querySelectorAll('#sequence-inputs input[type=number]')].find(el=>!el.validity.valid)?.id;if(focus)$(focus).focus();}
 function decisionError(e){$('sequence-decision').open=true;error(e,false,$('sequence-reviewer').value.trim()?'sequence-reason':'sequence-reviewer');}
 function settings(){
  let outages=retainedOutages;
  if(!imported){const from=number('sequence-outage-start'),duration=number('sequence-outage-duration');if(from<0||duration<0||from+duration>24)throw Error('A repeated interruption must fit within each 24-hour block.');outages=duration?source.inputs.blocks.map(block=>({start:new Date(Date.parse(block.times[0])+from*HOUR).toISOString(),end:new Date(Date.parse(block.times[0])+(from+duration)*HOUR).toISOString()})):[];}
  const multiplier=(id,convert)=>sourceMultipliers[id]?.text===$(id).value?sourceMultipliers[id].value:convert(number(id));
  return {initial:number('sequence-initial'),demand_multiplier:multiplier('sequence-demand',value=>1+value/100),production_multiplier:multiplier('sequence-loss',value=>1-value/100),outages:clone(outages)};
 }
 function validateSource(value){
  fields(value,['schema','kind','label','control_rate_m3_h','specific_energy_kwh_m3','inputs'],'sequence source');
  if(value.schema!==1||value.kind!=='fixed_plan_sequence_source')throw Error('Use a fixed_plan_sequence_source file or a saved continuous review.');
  plain(value.label,200,'plan label');if(!finite(value.control_rate_m3_h)||value.control_rate_m3_h<0||value.control_rate_m3_h>value.inputs?.unitCapacity)throw Error('Declare a finite flat-control rate within the unit limit.');
  if(value.specific_energy_kwh_m3!==null&&(!finite(value.specific_energy_kwh_m3)||value.specific_energy_kwh_m3<=0))throw Error('Specific energy must be a positive number or null.');
  replaySequence(value.inputs);return clone(value);
 }
 function appliedInput(value,conditions){return {...value.inputs,initial:conditions.initial,scenario:{demand_multiplier:conditions.demand_multiplier,production_multiplier:conditions.production_multiplier},outages:clone(conditions.outages)};}
 function pair(value,conditions){
  fields(conditions,['initial','demand_multiplier','production_multiplier','outages'],'review conditions');
  if(!['initial','demand_multiplier','production_multiplier'].every(key=>finite(conditions[key]))||!Array.isArray(conditions.outages))throw Error('Review requires complete finite conditions and explicit interruption windows.');
  const input=appliedInput(value,conditions);
  const selected=replaySequence(input),control=replaySequence({...input,blocks:input.blocks.map(block=>({...block,production:Array(24).fill(value.control_rate_m3_h)}))});
  return {selected,control};
 }
 function referenceSource(){
  const {data}=getReference(),capacity=number('sequence-tank'),from=$('sequence-from').value,through=$('sequence-through').value;
  const start=data.days.findIndex(day=>day.date===from),end=data.days.findIndex(day=>day.date===through);
  if(start<0||end<start)throw Error('Choose a complete consecutive period from the retained dates.');
  return {schema:1,kind:'fixed_plan_sequence_source',label:'Retained reference',control_rate_m3_h:data.demand,specific_energy_kwh_m3:data.kwh_per_m3,inputs:{blocks:data.days.slice(start,end+1).map(day=>({times:[...day.times],production:[...day.schedules[String(capacity)].production],demand:data.demand})),capacity,reserve:capacity*.2,initial:capacity*.5,target:capacity*.5,unitCapacity:data.unit_capacity,scenario:{demand_multiplier:1,production_multiplier:1},outages:[]}};
 }
 async function fileFromText(name,value){return {name,text:value,sha256:await sha256(value)};}
 async function embedded(file,limit=4){
  fields(file,['name','text','sha256'],'retained file');plain(file.name,255,'filename');if(typeof file.text!=='string'||new TextEncoder().encode(file.text).length>limit*MiB)throw Error(`Each retained file must be no larger than ${limit} MiB.`);
  if(!/^[a-f0-9]{64}$/.test(file.sha256??'')||await sha256(file.text)!==file.sha256)throw Error('Retained source hash does not match its bytes.');return clone(file);
 }
 async function verifyReference(files,value){
  if(files==null)return null;fields(files,['data','manifest'],'reference files');const checked={data:await embedded(files.data),manifest:await embedded(files.manifest)},data=parse(checked.data.text),manifest=parse(checked.manifest.text);
  if(manifest.data_sha256!==checked.data.sha256)throw Error('Retained data does not match its manifest.');
  const i=value.inputs,start=data.days?.findIndex(day=>same(day.times,i.blocks[0].times)),expected=data.days?.slice(start,start+i.blocks.length);
  if(start<0||expected.length!==i.blocks.length||!data.tanks?.includes(i.capacity)||i.reserve!==i.capacity*.2||i.initial!==i.capacity*.5||i.target!==i.capacity*.5||i.unitCapacity!==data.unit_capacity||value.control_rate_m3_h!==data.demand||value.specific_energy_kwh_m3!==data.kwh_per_m3||!same(i.scenario,{demand_multiplier:1,production_multiplier:1})||i.outages?.length!==0||i.blocks.some((block,index)=>!same(block.times,expected[index].times)||!same(block.production,expected[index].schedules[String(i.capacity)]?.production)||!same(block.demand,data.demand)))throw Error('Sequence differs from its retained reference sources.');
  return checked;
 }
 function useConditions(c){
  $('sequence-initial').max=source.inputs.capacity;$('sequence-initial').value=c.initial;sourceMultipliers={};
  for(const [id,value,percent] of [['sequence-demand',c.demand_multiplier,(c.demand_multiplier-1)*100],['sequence-loss',c.production_multiplier,(1-c.production_multiplier)*100]]){$(id).value=Number.isFinite(percent)?Number(percent.toPrecision(12)):'';$(id).placeholder=Number.isFinite(percent)?'':`${value} × from source`;sourceMultipliers[id]={text:$(id).value,value};}
  retainedOutages=clone(c.outages??[]);
 }
 function sourceDisplay(){
  $('sequence-period').hidden=imported;$('sequence-import-label').hidden=!imported;$('sequence-use-reference').hidden=!imported;$('sequence-recurring-outage').hidden=imported;
  text('sequence-import-label',source?`${source.label} / ${source.inputs.blocks.length} blocks`:'');
  text('sequence-outage-note',imported?`${retainedOutages.length} supplied absolute interruption windows retained. Demand and production changes persist across all blocks; water never resets.`:'Demand and production changes persist across every block. Any daily interruption repeats; water never resets.');
 }
 function conditionSummary(c){text('sequence-condition-summary',`${fmt(c.initial,0)} m³ initially / ${fmt((c.demand_multiplier-1)*100,1)}% demand / ${fmt((1-c.production_multiplier)*100,1)}% production loss${c.outages?.length?` / ${c.outages.length} interruption${c.outages.length===1?'':'s'}`:''}`);}
 async function run(){
  clear('Calculating continuous water balance…');const token=generation;
  try{
   if(!imported){const next=validateSource(referenceSource()),file=await fileFromText('aquashift-retained-sequence.json',JSON.stringify(next,null,2)+'\n');if(token!==generation)return;source=next;sourceFile=file;referenceFiles=getReference().files;}
   if(token!==generation)return;if(!source)throw Error('Choose a period or open a sequence file.');const conditions=settings(),results=pair(source,conditions);
   record={schema:1,kind:'continuous_plan_review',createdAt:new Date().toISOString(),scope:'Fixed historical sequence comparison; carried inventory is modeled, not a measured reading. No generated schedule or plant authorization.',source_file:sourceFile,...(referenceFiles?{reference_files:referenceFiles}:{}),conditions,results};
   show();$('sequence-inputs').open=false;
  }catch(e){if(token===generation)error(e,true);}
 }
 function failure(result){return result.events.find(e=>e.type==='stockout')??result.events.find(e=>e.type==='reserve_breach');}
 function show(selectedBlock){
  const selected=comparison?.original.result??record.results.selected,control=comparison?.revised.result??record.results.control,c=source.inputs,primary=comparison?control:selected,first=failure(primary),left=comparison?'Original':source.label,right=comparison?'Returned':'Flat control';$('sequence-result').hidden=false;controls();conditionSummary(record.conditions);
  text('sequence-status',`${source.label} / ${selected.blocks.length} consecutive 24-hour blocks / supplied fixed plans. Issue timing unverified.`);
  for(const id of ['sequence-service-heading','sequence-service-detail','sequence-service-proof','sequence-service-clock-note','sequence-service-hours'])$(id).hidden=!comparison;$('sequence-conclusion').hidden=!!comparison;$('sequence-service-inspect').hidden=!comparison;
  if(comparison){const service=waterServiceDisplay(comparison.water_service,comparison);text('sequence-service-heading',service.title);text('sequence-service-detail',`Modeled comparison. ${service.summary}`);$('sequence-service-inspect').hidden=!service.inspect;table('sequence-service-proof',['Check','Compared time or basis','Finding'],waterServiceRows(comparison.water_service));}
  text('sequence-conclusion',(comparison?'Returned plan: ':'')+(first?`${first.type==='stockout'?'First stockout':'First reserve crossing'}: ${local(first.time)}.`:primary.totals.unmet_m3>0?`Unserved demand: ${water(primary.totals.unmet_m3)} m³.`:primary.totals.max_reserve_deficit_m3>0?`Reserve deficit: ${water(primary.totals.max_reserve_deficit_m3)} m³.`:'Demand is served and reserve holds under these conditions.'));
  const count=selected.rows.length+1,labels=Array(count).fill(''),mid=Math.floor((count-1)/2),times=[selected.start_time,...selected.rows.map(row=>row.end_time)];for(const index of [0,mid,count-1])labels[index]=local(times[index]).replace(/ \d{4}/,'').replace(/:\d{2} GMT.*$/,'');
  const values=result=>[result.totals.initial_storage_m3,...result.rows.map(row=>row.storage_end_m3)];
  $('sequence-chart').setAttribute('aria-label',comparison?'Continuous tank inventory for original and returned plans':'Continuous tank inventory for supplied and flat plans');
  lineChart('sequence-chart',[{name:left,values:values(selected),dash:'6 4'},{name:comparison?right:`Flat ${fmt(source.control_rate_m3_h,1)} m³/h control`,values:values(control)}],{labels,max:c.capacity*1.06,height:210,left:72,unit:'m³',levels:[{value:c.reserve,label:'Reserve'}]});
  text('sequence-chart-note',`Hourly boundaries from ${local(selected.start_time)} to ${local(selected.end_time)}. Both start with ${fmt(record.conditions.initial,2)} m³ once; each block carries the preceding end inventory.`);
  $('sequence-budget-finding').hidden=false;text('sequence-budget-finding',`${comparison?'Returned plan: ':''}${storageRequirementFinding(primary.storage_requirements)}`);
  const proof=value=>value.exact.denominator==='1'?value.exact.numerator:`${value.exact.numerator}/${value.exact.denominator}`;
  const requirements=primary.storage_requirements;
  const interval=w=>`${local(Date.parse(primary.start_time)+w.start_hour.value*HOUR)} → ${local(Date.parse(primary.start_time)+w.end_hour.value*HOUR)} (${proof(w.start_hour)}–${proof(w.end_hour)} h elapsed)`;
  const bound=(label,quantity,w)=>[label,proof(quantity),w?`${w.constraint==='terminal_target'?'Ending target':w.constraint==='stored_initial'?'Starting stock':w.constraint==='no_spill'?'Peak inventory':'Reserve'}: ${interval(w)}`:'Starting water held or increased to meet the minimum'];
  table('sequence-storage-proof',[comparison?'Returned plan requirement':'Fixed-plan requirement','Exact m³','Limiting time or condition'],[
   bound('Minimum starting water',requirements.minimum_initial_m3,requirements.witnesses.initial),
   bound('Additional starting water',requirements.initial_shortfall_m3),
   bound('Minimum capacity, overflow allowed',requirements.with_spill.minimum_capacity_m3,requirements.witnesses.with_spill),
   bound('Minimum capacity, no spill',requirements.without_spill.minimum_capacity_m3,requirements.witnesses.without_spill),
   bound('Capacity after any necessary starting-water increase, no spill',requirements.without_spill.minimum_capacity_after_initial_topup_m3)
  ]);
  table('sequence-budget-proof',['Exact production budget',left,right],[['Elapsed hours','horizon_duration_hours'],['Starting water m³','starting_storage_m3'],['Ending target m³','terminal_target_m3'],['Available production m³','effective_production_m3'],['Demand m³','demand_m3'],['Unavoidable unserved m³, allowing an empty end','unavoidable_unserved_m3'],['Production needed for demand and ending target m³','production_required_for_demand_and_target_m3'],['Additional production necessary m³','additional_production_required_m3']].map(([label,key])=>[label,proof(selected.water_budget[key]),proof(control.water_budget[key])]));
  if(comparison)showOutcomes();else table('sequence-outcomes',['Water m³',source.label,'Flat control'],[['Unserved','unmet_m3'],['Served','delivered_m3'],['Lowest inventory','min_storage_m3'],['Final inventory','final_storage_m3'],['Final target shortfall','terminal_deficit_m3']].map(([label,key])=>[label,water(selected.totals[key]),water(control.totals[key])]));
  const failureText=(label,result)=>{const e=failure(result);return e?`${label}: first ${e.type==='stockout'?'stockout':'reserve crossing'} ${local(e.time)}.`:result.totals.unmet_m3>0||result.totals.max_reserve_deficit_m3>0?`${label}: small deficit retained; no event timestamp above the calculation threshold.`:`${label}: no stockout or reserve crossing.`;};text('sequence-failure',`${failureText(comparison?'Original':'Supplied',selected)} ${failureText(right,control)}`);
  $('sequence-day').replaceChildren(...selected.blocks.map((block,index)=>new Option(`${dayLabel(block.inputs.times[0])} / block ${index+1}${(comparison?control.blocks[index]:block).totals.unmet_m3>0?comparison?' / returned unmet demand':' / unmet demand':''}`,String(index))));
  $('sequence-day').value=String(Number.isInteger(selectedBlock)?selectedBlock:first?.block_index??0);$('sequence-export-day').disabled=false;dayChanged();
  facts('sequence-source',[['Sequence file',sourceFile.name],['Sequence SHA-256',sourceFile.sha256],['Reference data SHA-256',referenceFiles?.data.sha256??'Supplied sequence; no canonical source proof'],['Control',`${fmt(source.control_rate_m3_h,2)} m³/h, unchanged across all hours`],['Tank / reserve / final target',`${fmt(c.capacity,0)} / ${fmt(c.reserve,0)} / ${fmt(c.target,0)} m³`],['Unit limit',`${fmt(c.unitCapacity,0)} m³/h`],['Demand / production multipliers',`${record.conditions.demand_multiplier} / ${record.conditions.production_multiplier}`],['Starting inventory','Declared once; later starts are calculated carry, not measured observations']]);
  table('sequence-accounting',['Period totals',left,right],[['Production m³','available_production_m3'],['Spill m³','spill_m3'],['Largest accounting residual m³','max_abs_accounting_residual_m3']].map(([label,key])=>[label,fmt(selected.totals[key],6),fmt(control.totals[key],6)]));
  table('sequence-days',['Block begins',`${comparison?'Original':'Supplied'} start m³`,`${comparison?'Original':'Supplied'} end m³`,`${comparison?'Original':'Supplied'} unmet m³`,`${right} unmet m³`],selected.blocks.map((block,index)=>[local(block.inputs.times[0]),fmt(block.initial_storage_m3,2),fmt(block.totals.final_storage_m3,2),fmt(block.totals.unmet_m3,2),fmt(control.blocks[index].totals.unmet_m3,2)]));
 }
 function dayChanged(){
  if(!record)return;const index=Number($('sequence-day').value),day=record.results.selected.blocks[index];$('sequence-freeze').disabled=returnPending||solarPending;$('sequence-review-day').disabled=referenceFiles?.data.sha256!==getReference()?.files?.data.sha256;
  const next=comparison?.revised.result.blocks[index];
  if(next){const original=comparison.original.result.rows.slice(index*24,(index+1)*24),returned=comparison.revised.result.rows.slice(index*24,(index+1)*24);table('sequence-service-hours',['Hour beginning','Original delivered m³','Returned delivered m³','Original unmet m³','Returned unmet m³'],original.map((row,hour)=>[local(row.time),water(row.delivered_m3),water(returned[hour].delivered_m3),water(row.unmet_m3),water(returned[hour].unmet_m3)]));}
  text('sequence-day-status',next?`Original: ${water(day.initial_storage_m3)} m³ carried in, ${water(day.totals.unmet_m3)} m³ unserved. Returned: ${water(next.initial_storage_m3)} m³ carried in, ${water(next.totals.unmet_m3)} m³ unserved.`:`${water(day.initial_storage_m3)} m³ carried into this block; ${water(day.totals.unmet_m3)} m³ unserved. Prepare a return from this block to inspect downstream changes.`);
 }

 function exported(){
  if(!record)throw Error('Run a continuous review first.');if(returnPending||solarPending)throw Error('Wait for the selected file to finish loading.');const reason=$('sequence-reason').value.trim(),reviewer=$('sequence-reviewer').value.trim(),decision=$('sequence-decision-value').value;
  if(!['Needs team review','Request revised sequence'].includes(decision))throw Error('Choose a supported next step.');
  if(reason||decision==='Request revised sequence'){plain(reviewer,80,'reviewer');plain(reason,2000,'review reason');}
  const note={selected_block:Number($('sequence-day').value),decision,reason,reviewer};
  if(comparison)return {schema:1,kind:'continuous_plan_revision_review',createdAt:new Date().toISOString(),scope:'Recomputed full-period comparison of supplied production. No generated schedule, authenticated source or plant authorization.',case_file:revisionCase.file,proposal_file:returnedFile,...(solarFile?{solar_file:solarFile}:{}),...note,results:{original:comparison.original.result.totals,returned:comparison.revised.result.totals,changes:comparison.changes,water_service:comparison.water_service,water_budget:{original:comparison.original.result.water_budget,returned:comparison.revised.result.water_budget},storage_requirements:{original:comparison.original.result.storage_requirements,returned:comparison.revised.result.storage_requirements},...(solarComparison?{solar:solarSummary()}: {})}};
  return {...record,...note};
 }
 function save(name,value){const raw=JSON.stringify(value,null,2)+'\n';if(new TextEncoder().encode(raw).length>32*MiB)throw Error('Review exceeds the 32 MiB reopening limit. Choose a shorter sequence.');download(name,raw,'application/json');text('sequence-error','');$('sequence-error').hidden=true;}
 function dayPayload(value,results,index){
  const block=results.selected.blocks[index],i=value.inputs;
  return {inputs:{...block.inputs,capacity:i.capacity,reserve:i.reserve,initial:block.initial_storage_m3,target:i.target,scenario:clone(block.scenario),startHour:0},source_block:index,carried_from:index?results.selected.blocks[index-1].totals.final_storage_m3:null,events:block.events,totals:block.totals,unit_capacity_m3_h:i.unitCapacity,specific_energy_kwh_m3:value.specific_energy_kwh_m3};
 }
 function dayCase(){const note=exported(),review={...record,selected_block:note.selected_block,decision:comparison?'Needs team review':note.decision,reason:comparison?'':note.reason,reviewer:note.reviewer},index=review.selected_block;return {schema:1,kind:'continuous_plan_day_case',review,block_index:index,day:dayPayload(source,record.results,index)};}
 $('sequence-freeze').onclick=freezeCase;
 $('sequence-case-export').onclick=()=>{if(revisionCase)download(revisionCase.file.name,revisionCase.file.text,'application/json');};
 $('sequence-return-template').onclick=()=>{try{if(!revisionCase)throw Error('Prepare a return case first.');csv('aquashift-continuous-return.csv',sequenceRevisionTemplate({input:appliedInput(source,record.conditions),block_index:revisionCase.value.block_index,case_sha256:revisionCase.file.sha256}));}catch(e){$('sequence-revision-files').open=true;error(e,false,'sequence-return-template');}};
 $('sequence-return-file').onchange=async()=>{
  const file=$('sequence-return-file').files[0],token=++generation,selected=Number($('sequence-day').value);resetReturn();returnPending=true;controls();show(selected);text('sequence-revision-status','Checking returned production…');
  try{if(!revisionCase)throw Error('Prepare a return case first.');const loaded=await readFile(file);if(token!==generation)return;const result=compareReturn(revisionCase,loaded);returnedFile=loaded;comparison=result;returnPending=false;show(selected);showCase();$('sequence-revision-files').open=false;text('sequence-error','');$('sequence-error').hidden=true;$('sequence-result').focus({preventScroll:true});}
  catch(e){if(token===generation){returnPending=false;controls();$('sequence-revision-files').open=true;text('sequence-revision-status','Return rejected / flat control shown');error(e,false,'sequence-return-file');}}
 };
 $('sequence-return-remove').onclick=()=>{generation++;resetReturn();show(Number($('sequence-day').value));showCase();$('sequence-revision-files').open=true;};
 $('sequence-solar-template').onclick=()=>{try{if(!comparison)throw Error('Import a returned plan first.');save('aquashift-continuous-solar.json',sequenceSolarAllocationTemplate(comparison,$('sequence-solar-format').value));}catch(e){$('sequence-solar').open=true;$('sequence-solar-profile').open=true;error(e,false,'sequence-solar-template');}};
 $('sequence-solar-file').onchange=async()=>{
  const file=$('sequence-solar-file').files[0],parent=generation,changed=Boolean(solarFile);resetSolar();resetDecision('solar profile changed');const token=solarGeneration;solarPending=true;controls();showOutcomes();text('sequence-solar-status','Checking profile…');
  try{if(!comparison)throw Error('Import a returned plan first.');const loaded=await readFile(file);if(token!==solarGeneration||parent!==generation)return;const result=evaluateSequenceSolarAllocation({comparison,allocation:parse(loaded.text)});solarFile=loaded;solarComparison=result;solarPending=false;showSolar(changed);text('sequence-error','');$('sequence-error').hidden=true;$('sequence-solar').open=true;$('sequence-solar-profile').querySelector('summary').focus();}
  catch(e){if(token===solarGeneration&&parent===generation){solarPending=false;controls();text('sequence-solar-status','Unknown / profile rejected');$('sequence-solar').open=true;$('sequence-solar-profile').open=true;error(e,false,'sequence-solar-file');}}
 };
 $('sequence-solar-remove').onclick=()=>{resetSolar();resetDecision('solar profile removed');showOutcomes();controls();$('sequence-solar').open=true;$('sequence-solar').querySelector('summary').focus();};
 $('sequence-evidence-export').onclick=()=>{try{if(!solarComparison||solarPending||returnPending)return;save('aquashift-continuous-solar-evidence-request.json',solarEvidenceRequest(solarComparison,{case_file:identity(revisionCase.file),proposal_file:identity(returnedFile),solar_file:identity(solarFile),specific_energy_kwh_m3:comparison.specific_energy_kwh_m3,horizon:{start:comparison.original.result.start_time,end:comparison.original.result.end_time}}));}catch(e){$('sequence-solar').open=true;$('sequence-solar-evidence').open=true;error(e,false,'sequence-evidence-export');}};
 $('sequence-form').onsubmit=e=>{e.preventDefault();return run();};
 $('sequence-day').onchange=dayChanged;
 $('sequence-service-inspect').onclick=()=>{if(!comparison)return;const hour=waterServiceDisplay(comparison.water_service,comparison).hour;$('sequence-day').value=String(Math.max(0,Math.min(comparison.original.result.blocks.length-1,Math.floor(hour/24))));dayChanged();$('sequence-accounting-details').open=true;$('sequence-service-proof').focus();$('sequence-service-proof').scrollIntoView?.({block:'nearest'});};
 $('sequence-export').onclick=()=>{try{save(comparison?'aquashift-continuous-return-review.json':'aquashift-continuous-review.json',exported());}catch(e){decisionError(e);}};
 $('sequence-export-day').onclick=()=>{try{save('aquashift-continuous-day-case.json',dayCase());}catch(e){decisionError(e);}};
 $('sequence-review-day').onclick=async()=>{try{const kept=dayCase(),day=kept.day,index=Number($('sequence-day').value),token=generation;const reviewHash=await sha256(JSON.stringify(kept.review,null,2)+'\n');if(token!==generation)return;if(referenceFiles?.data.sha256!==getReference()?.files?.data.sha256)throw Error('This source requires a self-contained day case.');await openDay({schema:1,kind:'fixed_plan_consequence_assessment',createdAt:new Date().toISOString(),scope:'Unchanged supplied block with modeled carry from a continuous sequence. Starting storage is not a measured observation.',date:dayLabel(day.inputs.times[0]),planLabel:`${source.label} / continuous block ${index+1}`,identity:{data_sha256:referenceFiles.data.sha256,sequence_sha256:sourceFile.sha256,continuous_review_sha256:reviewHash,continuous_review_filename:'aquashift-continuous-review.json',sequence_block:index},observation:null,inputs:day.inputs},{unit_capacity_m3_h:day.unit_capacity_m3_h,specific_energy_kwh_m3:day.specific_energy_kwh_m3});}catch(e){error(e);}};
 $('sequence-template').onclick=async()=>{const token=generation;try{const value=imported?source:referenceSource();if(!value)throw Error('Choose a period first.');const raw=JSON.stringify(value,null,2)+'\n';if(token===generation)download('aquashift-sequence-source.json',raw,'application/json');}catch(e){error(e);}};
 $('sequence-file').onchange=async()=>{
  clear('Checking sequence sources…');const token=generation;source=null;sourceFile=null;referenceFiles=null;
  try{
   const file=$('sequence-file').files[0];if(!file||file.size>32*MiB)throw Error('Choose a UTF-8 sequence or review no larger than 32 MiB.');const bytes=await file.arrayBuffer();if(bytes.byteLength>32*MiB)throw Error('File exceeds 32 MiB.');const raw=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes);let value=parse(raw),conditions,selectedBlock,files=null,sourceData,nextSource,openedDay=null;
   if(['continuous_plan_revision_case','continuous_plan_revision_review'].includes(value.kind)){await openRevision(await fileFromText(file.name,raw),value,token);return;}
   if(value.kind==='continuous_plan_day_case'){fields(value,['schema','kind','review','block_index','day'],'day case');if(value.schema!==1||!Number.isInteger(value.block_index)||value.review?.kind!=='continuous_plan_review')throw Error('Invalid day-case selection or retained review.');openedDay=value.day;fields(openedDay,['inputs','source_block','carried_from','events','totals','unit_capacity_m3_h','specific_energy_kwh_m3'],'day payload');selectedBlock=value.block_index;value=value.review;}
   if(value.kind==='continuous_plan_review'){
    fields(value,['schema','kind','createdAt','scope','source_file','reference_files','conditions','selected_block','decision','reason','reviewer','results'],'continuous review');if(value.schema!==1)throw Error('Unsupported review schema.');sourceData=await embedded(value.source_file);nextSource=validateSource(parse(sourceData.text));files=await verifyReference(value.reference_files,nextSource);conditions=value.conditions;selectedBlock??=value.selected_block;
   }else{if(bytes.byteLength>4*MiB)throw Error('A raw sequence source must be no larger than 4 MiB.');nextSource=validateSource(value);sourceData=await fileFromText(file.name,raw);conditions={initial:nextSource.inputs.initial,demand_multiplier:nextSource.inputs.scenario?.demand_multiplier??1,production_multiplier:nextSource.inputs.scenario?.production_multiplier??1,outages:nextSource.inputs.outages??[]};}
   const results=pair(nextSource,conditions);if(selectedBlock!==undefined&&(!Number.isInteger(selectedBlock)||selectedBlock<0||selectedBlock>=results.selected.blocks.length))throw Error('Selected block is outside the retained sequence.');if(openedDay){const expected=dayPayload(nextSource,results,selectedBlock);for(const key of ['inputs','source_block','carried_from','unit_capacity_m3_h','specific_energy_kwh_m3'])if(!same(openedDay[key],expected[key]))throw Error('Day inputs disagree with the recomputed continuous source and carried water.');}if(token!==generation)return;
   imported=true;source=nextSource;sourceFile=sourceData;referenceFiles=files;useConditions(conditions);sourceDisplay();record={schema:1,kind:'continuous_plan_review',createdAt:new Date().toISOString(),scope:'Recomputed fixed historical sequence comparison. No restored decision, generated schedule or plant authorization.',source_file:sourceFile,...(referenceFiles?{reference_files:referenceFiles}:{}),conditions:clone(conditions),results};show(selectedBlock);$('sequence-inputs').open=false;text('sequence-status',`${source.label} / ${results.selected.blocks.length} blocks recalculated from retained source bytes. Saved decisions are not restored.`);
  }catch(e){if(token===generation){source=null;sourceFile=null;referenceFiles=null;error(e,true,'sequence-file');}}
 };
 $('sequence-use-reference').onclick=()=>{clear('Choose a retained period and run continuous review.');imported=false;source=null;sourceFile=null;referenceFiles=null;retainedOutages=[];sourceMultipliers={};$('sequence-initial').max=number('sequence-tank');$('sequence-initial').value=number('sequence-tank')*.5;sourceDisplay();};
 for(const id of ['sequence-from','sequence-through','sequence-tank','sequence-initial','sequence-demand','sequence-loss','sequence-outage-start','sequence-outage-duration'])for(const event of ['input','change'])$(id).addEventListener(event,()=>{clear();delete sourceMultipliers[id];if(id==='sequence-tank'){$('sequence-initial').max=number(id);$('sequence-initial').value=number(id)*.5;}});
 return {render(){if(initialized)return;const reference=getReference();if(!reference?.data)return;const days=reference.data.days;$('sequence-from').value=days[0].date;$('sequence-through').value=days[Math.min(6,days.length-1)].date;for(const id of ['sequence-from','sequence-through']){$(id).min=days[0].date;$(id).max=days.at(-1).date;}$('sequence-tank').replaceChildren(...reference.data.tanks.map(capacity=>new Option(`${fmt(capacity,0)} m³`,String(capacity))));$('sequence-tank').value='4000';$('sequence-initial').max=number('sequence-tank');$('sequence-initial').value=number('sequence-tank')*.5;conditionSummary({initial:number('sequence-initial'),demand_multiplier:1.1,production_multiplier:1});initialized=true;},snapshot:()=>record?clone(record):null};
}
