import {makeExecutionCase,executionMeasurementTemplate,evaluateExecution} from './execution-review.mjs';

export const executionReviewTemplate=`<div class="execution-review">
<div class="revision-file-tools"><label class="revision-file-action">Open measured run<input id="execution-file" type="file" accept=".json,application/json" aria-label="Open measured run or saved review"></label></div>
<p id="execution-summary" class="micro" role="status" tabindex="-1" hidden></p>
<section id="execution-result" aria-label="Measured run accounting" hidden><div id="execution-outcomes" class="table-wrap"></div><button id="execution-next" type="button">Record next step</button></section>
<details id="execution-files"><summary>Measurement files</summary><div class="revision-file-tools"><button id="execution-case-export" type="button">Export frozen plan</button><button id="execution-template-export" type="button">Export measurement template</button><button id="execution-clear" type="button" hidden>Remove measured run</button></div><div id="execution-source"></div><p class="micro">Supply interval totals or declared cumulative meters. Point power and flow readings cannot establish these totals.</p></details>
<details id="execution-details" hidden><summary>Accounting details</summary><p id="execution-temporal" class="micro"></p><p id="execution-balance" class="micro"></p><div id="execution-coverage" class="table-wrap"></div><div id="execution-findings" class="table-wrap" tabindex="-1"></div><p class="micro">A possible tank path does not establish the actual trajectory, water quality, flow-rate limits or operating permission.</p></details></div>`;

const MiB=1024*1024,RAW_LIMIT=4*MiB,REVIEW_LIMIT=8*MiB;
const clone=value=>JSON.parse(JSON.stringify(value));
const parse=text=>JSON.parse(text.replace(/^\uFEFF/,''));
const names={energy:'Plant electricity',produced:'Produced water',delivered:'Delivered water',other_inflow:'Other inflow',other_outflow:'Other outflow',spill:'Spill',initial_storage:'Initial tank',final_storage:'Final tank'};
const choices=['Needs team review','Hold for correction','Ready for next simulation'];
function fields(value,keys,label){if(!value||typeof value!=='object'||Array.isArray(value))throw Error(`${label} must be an object.`);for(const key of Object.keys(value))if(!keys.includes(key))throw Error(`Unsupported ${label} field: ${key}.`);}
function plain(value,max,label,multiline=false){if(typeof value!=='string'||!value.trim()||value.length>max||(multiline?/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/:/[\u0000-\u001f]/).test(value))throw Error(`Invalid ${label}.`);return value;}
function bytes(text){const raw=new TextEncoder().encode(text);if(new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(raw)!==text)throw Error('Retained text must be valid UTF-8.');return raw;}
function noteValue(note){if(note===undefined)return undefined;fields(note,['reviewer','decision','reason'],'review note');plain(note.reviewer,80,'reviewer');plain(note.reason,2000,'reason',true);if(!choices.includes(note.decision))throw Error('Choose a supported next step.');return clone(note);}
function number(value){return value.toLocaleString('en-GB',value!==0&&Math.abs(value)<.01?{maximumSignificantDigits:3}:{maximumFractionDigits:2});}
function range(value,unit,change=false){if(value===null||value===undefined)return 'Unknown';const show=n=>(change&&n>0?'+':'')+number(n);return (typeof value==='number'?show(value):value.lower===value.upper?show(value.lower):`${show(value.lower)} to ${show(value.upper)}`)+` ${unit}`;}

export function setupExecutionReview({$,text,table,facts,json,sha256,freezeSelectedPlan,openFrozenPlan,invalidateDecision,onResultChange,revealEvidence=()=>{}}){
 let generation=0,pending=false,importing=false,prepared=null,record=null,result=null,status='',firstFinding='';
 const identity=file=>({name:file.name,sha256:file.sha256});
 async function embedded(file){
  fields(file,['name','text','sha256'],'retained file');plain(file.name,255,'retained filename');
  if(typeof file.text!=='string'||!/^[a-f0-9]{64}$/.test(file.sha256??''))throw Error('Missing retained file bytes or SHA-256.');
  if(bytes(file.text).byteLength>RAW_LIMIT)throw Error('Each raw file must be no larger than 4 MiB.');
  if(await sha256(file.text)!==file.sha256)throw Error('Retained file hash does not match its bytes.');
  return {name:file.name,text:file.text,sha256:file.sha256};
 }
 async function read(file){
  if(!file||file.size>REVIEW_LIMIT)throw Error('Choose a UTF-8 measured run or review no larger than 8 MiB.');plain(file.name,255,'filename');
  const raw=await file.arrayBuffer();if(raw.byteLength>REVIEW_LIMIT)throw Error('Maximum review size is 8 MiB.');
  return {name:file.name,text:new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(raw),sha256:await sha256(raw)};
 }
 async function prepare(){
  const file=await embedded(await freezeSelectedPlan());const executionCase=makeExecutionCase(parse(file.text));return {file,executionCase};
 }
 function compact(value){return Object.fromEntries(['modeled','measured','differences','coverage','water_balance','volume_stock_comparison','temporal_water','issues','scope'].map(key=>[key,clone(value[key])]));}
 function render(){
  text('execution-summary',status);$('execution-summary').hidden=!status;$('execution-result').hidden=!result;$('execution-details').hidden=!result;$('execution-clear').hidden=!record;
  for(const id of ['execution-case-export','execution-template-export','execution-next'])$(id).disabled=pending;
  if($('download-current-review'))$('download-current-review').disabled=pending;
  const save=$('review-form')?.querySelector('[type="submit"]');if(save)save.disabled=pending;
  if(!result){$('execution-outcomes').replaceChildren();$('execution-source').replaceChildren();$('execution-findings').replaceChildren();return;}
  table('execution-outcomes',['Same 24 hours','Modeled','Measured','Difference'],['produced','delivered','energy','final_storage'].map(role=>{const unit=role==='energy'?'kWh':'m³';return[names[role],range(result.modeled[role],unit),range(result.measured[role],unit),range(result.differences[role],unit,true)];}));
  const water=result.water_balance;
  const temporal=result.temporal_water;
  text('execution-temporal',temporal.status==='inconsistent'?'No nonnegative tank path within capacity fits all timely water readings.':temporal.status==='compatible'?'The timely water readings permit at least one tank path within capacity.':'Tank path unresolved: water evidence is incomplete.');
  text('execution-balance',water.status==='unknown'?'Water balance unknown: required totals or tank boundaries are unavailable.':water.status==='inconsistent'?`Water balance does not close: residual ${range(water.residual_m3,'m³')}.`:`Water residual ${range(water.residual_m3,'m³')}; the declared ranges permit balance.`);
  const findings=(result.issues??[]).map(issue=>[names[issue.role]??issue.role,issue.message]);
  if(water.status==='inconsistent')findings.unshift(['Water balance','The declared water and tank ranges cannot balance; this does not identify the cause.']);
  if(result.volume_stock_comparison.status==='different')findings.unshift(['Water comparison','Water volumes or tank inventory differ from the modeled plan.']);
  if(temporal.status==='inconsistent')findings.unshift(['Tank path','No nonnegative tank path within capacity fits all timely water readings.']);
  firstFinding=findings[0]?.[1]??'';
  table('execution-findings',['Check','Finding'],findings.length?findings:[['Accounting','No unresolved accounting finding.']]);
  const semantics={interval_total:'Interval totals',cumulative_counter:'Counter endpoints',declared_zero:'Declared zero',tank_boundary:'Tank boundary'};
  table('execution-coverage',['Stream','Evidence','Late / unknown records'],Object.entries(result.coverage).map(([role,c])=>[names[role]??role,`${semantics[c.semantics]??'Missing'} / ${c.status==='declared_zero'?'caller assertion':c.status}${Number.isFinite(c.known_hours)&&c.semantics!=='declared_zero'?` / ${number(c.known_hours)} h`:''}`,`${c.late_records??0} / ${c.unknown_records??0}`]));
  facts('execution-source',[['Frozen plan',record.case_file.name],['Plan SHA-256',record.case_file.sha256],['Measurements',record.measurement_file.name],['Measurement SHA-256',record.measurement_file.sha256],['Source',result.source.source_label],['Source kind',result.source.source_kind]]);
  text('execution-next',firstFinding?'Inspect finding':'Record next step');
 }
 function clear(reason='Measured run removed.',forceReset=false){
  const visible=record||prepared||importing||forceReset,resetDecision=record||importing||forceReset;
  generation++;pending=false;importing=false;prepared=null;record=null;result=null;firstFinding='';status=visible?reason:'';
  $('execution-details').open=false;if(resetDecision)invalidateDecision(reason);render();onResultChange();
 }
 async function open(file){
  const retained=prepared?clone(prepared):null;
  clear('Checking measured run…',true);const token=generation;prepared=retained;pending=true;importing=true;render();
  try{
   const loaded=await read(file);if(token!==generation)return;const value=parse(loaded.text);let caseFile,measurementFile,executionCase,reopened=false;
   if(value?.kind==='measured_run_review'){
    fields(value,['schema','kind','case_file','measurement_file','createdAt','note','results'],'measured review');
    if(value.schema!==1||typeof value.createdAt!=='string'||!Number.isFinite(Date.parse(value.createdAt)))throw Error('Unsupported measured review.');noteValue(value.note);
    caseFile=await embedded(value.case_file);measurementFile=await embedded(value.measurement_file);executionCase=makeExecutionCase(parse(caseFile.text));reopened=true;
   }else{
    if(bytes(loaded.text).byteLength>RAW_LIMIT)throw Error('A raw measured run must be no larger than 4 MiB.');
    const selected=retained??await prepare();caseFile=selected.file;executionCase=selected.executionCase;measurementFile=loaded;
   }
   if(token!==generation)return;
   const evaluated=evaluateExecution({executionCase,caseIdentity:identity(caseFile),source:parse(measurementFile.text),sourceIdentity:identity(measurementFile)});
   const installed={schema:1,kind:'measured_run_review',case_file:caseFile,measurement_file:measurementFile,createdAt:new Date().toISOString(),results:compact(evaluated)};
   if(bytes(JSON.stringify(installed,null,2)+'\n').byteLength>REVIEW_LIMIT)throw Error('This measured run exceeds the 8 MiB complete-review limit.');
   await openFrozenPlan({case_file:clone(caseFile),executionCase:clone(executionCase),isCurrent:()=>token===generation});if(token!==generation)return;
   record=installed;result=evaluated;prepared={file:caseFile,executionCase};pending=false;importing=false;
   const incomplete=Object.values(result.measured).some(value=>value===null),lowerEnergy=result.differences.energy?.upper<0;
   status=result.temporal_water.status==='inconsistent'?'Water measurements conflict over time; no tank path within capacity fits.':lowerEnergy&&result.volume_stock_comparison.status==='different'?'Lower electricity accompanies different water volumes or tank inventory.':result.water_balance.status==='inconsistent'?'Measured water and tank readings do not balance.':incomplete?'Measured run opened; full accounting remains incomplete.':'Measured run opened; full-period totals are available.';
   if(reopened)status+=' Recalculated; record a new next step.';
   invalidateDecision('Measured evidence changed.');render();onResultChange();revealEvidence();$('execution-summary').focus();
  }catch(error){if(token===generation){pending=false;importing=false;prepared=null;record=null;result=null;status=`Measured run not accepted: ${error.message}`;render();onResultChange();revealEvidence();$('execution-file').focus();}}
 }
 $('execution-file').onchange=()=>{const file=$('execution-file').files[0];return file?open(file):undefined;};
 async function exportInput(template){
  const token=generation;try{
   pending=true;render();const candidate=record&&prepared?prepared:await prepare();if(token!==generation)return;prepared=candidate;
   if(template)json('aktina-measurements-template.json',executionMeasurementTemplate({executionCase:candidate.executionCase,case_sha256:candidate.file.sha256}));
   else json(candidate.file.name,candidate.file.text);
  }catch(error){if(token===generation){status=error.message;$('execution-files').open=true;}}
  finally{if(token===generation){pending=false;render();}}
 }
 $('execution-case-export').onclick=()=>exportInput(false);$('execution-template-export').onclick=()=>exportInput(true);
 $('execution-clear').onclick=()=>clear();
 $('execution-next').onclick=()=>{
  if(!result||pending)return;
  if(firstFinding){$('execution-details').open=true;$('execution-findings').focus();}
  else{const editor=$('review-decision-editor'),note=$('review-note');if(editor)editor.open=true;if(note)note.focus();}
 };
 function exportReview(note){
  if(pending)throw Error('Wait for measured-run validation to finish.');if(!record)throw Error('Open a measured run before exporting its review.');
  const value={...clone(record),createdAt:new Date().toISOString()},kept=noteValue(note);if(kept!==undefined)value.note=kept;
  if(bytes(JSON.stringify(value,null,2)+'\n').byteLength>REVIEW_LIMIT)throw Error('Complete measured review exceeds 8 MiB.');return value;
 }
 render();return {render,snapshot:()=>record?clone(record):null,isPending:()=>pending,exportReview,clear};
}
