import {replaySequence} from './plan-sequence.mjs';
import {pilotTime} from './pilot.mjs';
import {pairedProductionChanges} from './plan-revision.mjs';
import {waterServiceModel} from './plan-resilience.mjs';
import {compareWaterService} from './paired-water-service.mjs';

const fail=message=>{throw Error(`Continuous return: ${message}`);};
const finite=value=>typeof value==='number'&&Number.isFinite(value);
const clone=value=>JSON.parse(JSON.stringify(value));
const same=(a,b)=>a===b||Boolean(a&&b&&typeof a==='object'&&typeof b==='object'&&Array.isArray(a)===Array.isArray(b)&&Object.keys(a).length===Object.keys(b).length&&Object.keys(a).every(key=>Object.hasOwn(b,key)&&same(a[key],b[key])));
function identity(value,label){
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(key=>!['name','sha256'].includes(key))||typeof value.name!=='string'||!value.name.trim()||value.name.length>255||/[\u0000-\u001f]/.test(value.name)||!/^[a-f0-9]{64}$/.test(value.sha256??''))fail(`Declare an exact ${label} filename and SHA-256.`);
 return clone(value);
}
function start(input,index){if(!Number.isInteger(index)||index<0||index>=input.blocks.length)fail('First editable block must lie within the supplied sequence.');return index;}
function energy(sec){if(sec!==null&&(!finite(sec)||sec<=0))fail('Specific energy must be positive and finite, or null when unknown.');return sec;}
function epoch(value){const parsed=pilotTime(value);if(parsed.error)fail(parsed.error);return parsed.epoch;}
export function sequenceWaterServiceModel(input,replay){
 const models=replay.blocks.map(block=>{
  const {initial_storage_m3,restart,...scenario}=block.scenario;
  return waterServiceModel({...block.inputs,capacity:input.capacity,reserve:input.reserve,initial:input.initial,target:input.target,scenario});
 });
 return {...models[0],end_hour:models.length*24,segments:models.flatMap((model,index)=>model.segments.map(segment=>({...segment,from:segment.from+index*24,to:segment.to+index*24})))};
}
function result(input,block_index,case_identity,proposal_identity,sec,original,revisedInput,revised){
 const modeled=value=>{
  if(sec===null)return null;const produced=value.totals.available_production_m3,total=produced*sec;
  if(!finite(total)||(produced>0&&total===0))fail('Modeled energy exceeds finite numeric range or precision.');return total;
 };
 const changes=Object.fromEntries(['available_production_m3','delivered_m3','unmet_m3','spill_m3','final_storage_m3','max_reserve_deficit_m3','terminal_deficit_m3','terminal_deviation_m3'].map(key=>[key,revised.totals[key]-original.totals[key]]));
 Object.assign(changes,pairedProductionChanges(original,revised,sec));
 return {schema:1,kind:'continuous_plan_revision_comparison',case_identity,proposal_identity,block_index,specific_energy_kwh_m3:sec,
  original:{inputs:clone(input),result:original,modeled_production_energy_kwh:modeled(original)},revised:{inputs:clone(revisedInput),result:revised,modeled_production_energy_kwh:modeled(revised)},changes,
  water_service:compareWaterService({original:sequenceWaterServiceModel(input,original),revised:sequenceWaterServiceModel(revisedInput,revised)}),
  scope:['Supplied production changes only from the first editable block onward; no forecast fitting, schedule generation or dispatch.',
   'Both alternatives replay the full period with identical times, demand, one initial inventory, tank, reserve, final target, derating and interruptions. Earlier production is unchanged; later water carries forward without reset.',
   'Modeled electricity is effective production times declared constant specific energy, including spilled production. Less water service or lower final inventory is not an efficiency saving.',
   'File hashes identify supplied bytes, not authorship or operating authority. Water service, reserve, spill, final inventory and production remain separate outcomes.']};
}

export function sequenceRevisionTemplate({input,block_index,case_sha256}){
 replaySequence(input);start(input,block_index);if(!/^[a-f0-9]{64}$/.test(case_sha256??''))fail('Declare the frozen case SHA-256.');
 return [['case_sha256','time','production_m3'],...input.blocks.slice(block_index).flatMap(block=>block.times.map((time,hour)=>[case_sha256,time,block.production[hour]]))];
}

export function compareSequenceRevision({input,block_index,caseIdentity,csvText,proposalIdentity,specific_energy_kwh_m3,Papa}){
 const original=replaySequence(input),first=start(input,block_index),caseFile=identity(caseIdentity,'case'),proposalFile=identity(proposalIdentity,'return'),sec=energy(specific_energy_kwh_m3);
 if(typeof csvText!=='string'||typeof Papa?.parse!=='function')fail('Supply a CSV string and parser.');
 const parsed=Papa.parse(csvText,{delimiter:',',skipEmptyLines:'greedy'});if(parsed.errors.length)fail('Malformed CSV.');
 const matrix=parsed.data,header=(matrix.shift()??[]).map(value=>String(value).trim().replace(/^\uFEFF/,'')),expected=['case_sha256','time','production_m3'];
 if(header.length!==3||new Set(header).size!==3||expected.some(key=>!header.includes(key)))fail('Columns must be exactly case_sha256,time,production_m3.');
 const allowed=new Map(input.blocks.flatMap((block,index)=>index<first?[]:block.times.map((time,hour)=>[epoch(time),[index,hour]])));
 if(matrix.length!==allowed.size)fail(`Supply exactly ${allowed.size} remaining-hour rows.`);
 const revisedInput=clone(input),seen=new Set();
 for(const values of matrix){
  if(values.length!==3)fail('CSV row has the wrong number of fields.');
  const row=Object.fromEntries(header.map((key,index)=>[key,String(values[index]).trim()]));
  if(row.case_sha256!==caseFile.sha256)fail('Return belongs to a different frozen case.');
  const time=epoch(row.time),position=allowed.get(time);if(!position||seen.has(time))fail('Return contains an outside or duplicate remaining-hour instant.');seen.add(time);
  const rate=/^(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(row.production_m3)?Number(row.production_m3):NaN;
  if(!finite(rate)||rate<0||rate>input.unitCapacity||(rate===0&&/[1-9]/.test(row.production_m3.split(/[eE]/)[0])))fail('Production must be finite, nonnegative and within the declared unit limit and numeric precision.');
  revisedInput.blocks[position[0]].production[position[1]]=rate;
 }
 return result(input,first,caseFile,proposalFile,sec,original,revisedInput,replaySequence(revisedInput));
}

/** Reconstruct comparison inputs; cached results never establish solar loads. */
export function validateSequenceRevisionComparison(comparison){
 if(!comparison||comparison.schema!==1||comparison.kind!=='continuous_plan_revision_comparison')fail('Use a continuous returned-plan comparison.');
 const input=comparison.original?.inputs,revisedInput=comparison.revised?.inputs,original=replaySequence(input),revised=replaySequence(revisedInput),first=start(input,comparison.block_index);
 const {blocks:a,...conditionsA}=input,{blocks:b,...conditionsB}=revisedInput;
 if(!same(conditionsA,conditionsB)||a.length!==b.length||a.some((block,index)=>!same(block.times,b[index].times)||!same(block.demand,b[index].demand)||(index<first&&!same(block.production,b[index].production))))fail('Returned sequence changed shared conditions or the frozen prefix.');
 return result(input,first,identity(comparison.case_identity,'case'),identity(comparison.proposal_identity,'return'),energy(comparison.specific_energy_kwh_m3),original,revisedInput,revised);
}
