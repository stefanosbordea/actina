import {replayPlan,waterServiceModel} from './plan-resilience.mjs';
import {compareWaterService} from './paired-water-service.mjs';
import {pilotTime} from './pilot.mjs';
import {createObservationRestart,sameRestart} from './observation-restart.mjs';
const fail=message=>{throw Error(`Plan revision: ${message}`);};
const finite=value=>typeof value==='number'&&Number.isFinite(value);
const clone=value=>structuredClone(value);
function fields(value,allowed,label){if(!value||typeof value!=='object'||Array.isArray(value))fail(`${label} must be an object.`);for(const key of Object.keys(value))if(!allowed.includes(key))fail(`Unsupported ${label} field: ${key}.`);}
function identity(value,label){if(!value||typeof value.name!=='string'||!value.name||!/^[a-f0-9]{64}$/.test(value.sha256??''))fail(`Missing exact ${label} filename or SHA-256.`);return clone(value);}
function epoch(value){const parsed=pilotTime(value);if(parsed.error)fail(parsed.error);return parsed.epoch;}

/** Paired replay rows retain changes hidden by a much larger common total. */
export function pairedProductionChanges(original,revised,sec){
 let total=0,correction=0;
 for(let index=0;index<original.rows.length;index++){
  const value=revised.rows[index].available_production_m3-original.rows[index].available_production_m3,next=total+value;
  correction+=Math.abs(total)>=Math.abs(value)?(total-next)+value:(value-next)+total;total=next;
 }
 const volume=total+correction,energy=sec===null?null:volume*sec;
 if(!finite(volume)||(sec!==null&&(!finite(energy)||(volume!==0&&energy===0))))fail('Production or modeled energy change exceeds finite numeric range or precision.');
 return {available_production_m3:volume===0?0:volume,modeled_production_energy_kwh:energy===0?0:energy};
}

function checkObservation(a,replay){
 const r=a.observation;if(r==null)return;
 const input=a.inputs,start=replay.start_hour;
 if(!r||typeof r!=='object'||Array.isArray(r)||r.measurement!=='tank_storage_m3'||r.unit!=='m3'||typeof r.asset_id!=='string'||!r.asset_id||!finite(r.value)||r.value!==replay.totals.initial_storage_m3||epoch(r.time)!==epoch(input.times[start])||r.tankCapacityM3!==input.capacity||typeof r.mapping!=='string'||!r.mapping.trim())fail('Retained observation does not match the case start, inventory or explicit tank mapping.');
 const at=epoch(r.available_at),cutoff=epoch(r.reviewAsOf);
 if(at<epoch(r.time)||at>cutoff||!['synthetic_fixture','operator_observations'].includes(r.sourceKind))fail('Retained reading is unavailable at its declared cutoff.');
 for(const key of ['contract','observations'])if(!/^[a-f0-9]{64}$/.test(r.identity?.[key]?.sha256??''))fail(`Missing retained observation ${key} identity.`);
 if(!r.bridge)return;
 const b=r.bridge,p=b.plan;
 if(b.schema!==1||b.kind!=='mapped_historical_tank_restart'||b.start_hour!==start||!p)fail('Malformed historical mapping proof.');
 const keys=['times','production','demand','capacity','reserve','initial','target'];
 if(keys.some(key=>!sameRestart(p[key],input[key]))||!sameRestart(p.identity,{...a.identity,label:a.planLabel}))fail('Historical mapping proof belongs to a different nominal plan.');
 const nominal=replayPlan(Object.fromEntries(keys.map(key=>[key,input[key]])));
 for(const [field,rowField] of [['storage_start','storage_start_m3'],['storage','storage_end_m3']])if(!Array.isArray(p[field])||p[field].length!==24||p[field].some((v,h)=>!finite(v)||Math.abs(v-nominal.rows[h][rowField])>1e-6))fail('Historical proof inventory does not match nominal water balance.');
 if(!sameRestart(b.reading,Object.fromEntries(Object.keys(b.reading??{}).map(key=>[key,r[key]]))))fail('Retained observation and mapping proof disagree.');
 const {label,...contextIdentity}=p.identity;
 const context={day:{times:p.times},plan:{production:p.production,storage_start:p.storage_start,storage:p.storage,totals:{initial_storage_m3:p.initial,final_storage_m3:p.target}},demand:p.demand,capacity:p.capacity,reserve:p.reserve,unitCapacity:p.unit_capacity_m3_h,identity:contextIdentity,label};
 const comparison={schema:1,kind:'AquaShift point observation reconciliation',plan:p,mapping:{tank:b.mapping?.asset_id},rows:[{kind:'tank_storage',time:r.time,plan_hour:start,status:'within_tolerance',observed:r.value,expected:p.storage_start[start],sources:[b.reading]}],source:b.source,review_as_of:b.comparison_cutoff,original_intake_review_as_of:b.original_intake_cutoff};
 const checked=createObservationRestart(comparison,context,r.time),{comparison_revision,...retained}=b;
 if(!sameRestart(checked,retained))fail('Historical mapping proof is internally inconsistent.');
}

export function makeRevisionCase({assessment,unit_capacity_m3_h,specific_energy_kwh_m3}){
 const kept=Object.fromEntries(['schema','kind','createdAt','scope','date','planLabel','identity','observation','inputs'].filter(key=>Object.hasOwn(assessment,key)).map(key=>[key,assessment[key]]));
 return validateRevisionCase({schema:1,kind:'fixed_plan_revision_case',assessment:kept,unit_capacity_m3_h,specific_energy_kwh_m3:specific_energy_kwh_m3??null});
}
export function validateRevisionCase(value){
 fields(value,['schema','kind','assessment','unit_capacity_m3_h','specific_energy_kwh_m3'],'case');
 if(value.schema!==1||value.kind!=='fixed_plan_revision_case')fail('Unsupported case schema.');
 if(!finite(value.unit_capacity_m3_h)||value.unit_capacity_m3_h<=0)fail('Declare a positive finite unit capacity.');
 if(value.specific_energy_kwh_m3!==null&&(!finite(value.specific_energy_kwh_m3)||value.specific_energy_kwh_m3<=0))fail('Specific energy must be positive and finite, or null when unknown.');
 const a=value.assessment;
 fields(a,['schema','kind','createdAt','scope','date','planLabel','identity','observation','inputs'],'assessment');
 if(a.schema!==1||a.kind!=='fixed_plan_consequence_assessment')fail('Use an exported fixed-plan consequence assessment.');
 if(!a.identity||typeof a.identity!=='object'||Array.isArray(a.identity)||!/^[a-f0-9]{64}$/.test(a.identity.data_sha256??''))fail('Missing retained source-data identity.');
 let original;try{original=replayPlan(a.inputs);}catch(error){fail(error.message);}
 if(original.start_hour>=24)fail('This case has no remaining hours.');
 const day=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Nicosia',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(a.inputs.times[0]));
 if(a.date!==undefined&&a.date!==day)fail('Case date does not match its plan day in Cyprus.');
 if(a.planLabel!==undefined&&(typeof a.planLabel!=='string'||!a.planLabel.trim()||a.planLabel.length>200||/[\u0000-\u001f]/.test(a.planLabel)))fail('Invalid declared plan label.');
 checkObservation(a,original);
 if(a.inputs.production.some(rate=>rate>value.unit_capacity_m3_h))fail('Original production exceeds the declared unit limit.');
 const declared=a.observation?.bridge?.plan?.unit_capacity_m3_h;
 if(declared!==undefined&&declared!==value.unit_capacity_m3_h)fail('Unit limit differs from the carried observation case.');
 return clone(value);
}

export function revisionTemplate(revisionCase,caseSHA){
 const c=validateRevisionCase(revisionCase);
 if(!/^[a-f0-9]{64}$/.test(caseSHA))fail('Missing case hash.');
 const start=replayPlan(c.assessment.inputs).start_hour;
 return [['case_sha256','time','production_m3'],...c.assessment.inputs.times.slice(start).map((time,index)=>[caseSHA,time,c.assessment.inputs.production[index+start]])];
}

export function compareRevision({revisionCase,caseIdentity,csvText,proposalIdentity,Papa}){
 const c=validateRevisionCase(revisionCase),caseFile=identity(caseIdentity,'case'),proposalFile=identity(proposalIdentity,'proposal'),input=c.assessment.inputs;
 if(typeof csvText!=='string'||!Papa?.parse)fail('Supply a CSV string and parser.');
 const parsed=Papa.parse(csvText,{delimiter:',',skipEmptyLines:'greedy'});
 if(parsed.errors.length)fail('Malformed CSV.');
 const matrix=parsed.data,header=(matrix.shift()??[]).map(value=>String(value).trim().replace(/^\uFEFF/,'')),expected=['case_sha256','time','production_m3'];
 if(header.length!==3||new Set(header).size!==3||expected.some(key=>!header.includes(key)))fail('Columns must be exactly case_sha256,time,production_m3.');
 const start=replayPlan(input).start_hour,allowed=new Map(input.times.slice(start).map((time,index)=>[epoch(time),index+start]));
 if(matrix.length!==allowed.size)fail(`Supply exactly ${allowed.size} remaining-hour rows.`);
 const production=[...input.production],seen=new Set();
 for(const values of matrix){
  if(values.length!==3)fail('CSV row has the wrong number of fields.');
  const row=Object.fromEntries(header.map((key,index)=>[key,String(values[index]).trim()]));
  if(row.case_sha256!==caseFile.sha256)fail('Proposal is bound to a different case file.');
  const time=epoch(row.time),hour=allowed.get(time);
  if(hour===undefined||seen.has(time))fail('Proposal contains an outside or duplicate remaining-hour instant.');
  seen.add(time);
  const value=/^(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(row.production_m3)?Number(row.production_m3):NaN;
  if(!finite(value)||value<0||value>c.unit_capacity_m3_h)fail('Production must be finite, nonnegative and within the declared unit limit.');
  production[hour]=value;
 }
 const original=replayPlan(input),revisedInputs={...clone(input),production},revised=replayPlan(revisedInputs);
 const energy=result=>c.specific_energy_kwh_m3===null?null:result.totals.available_production_m3*c.specific_energy_kwh_m3;
 if(c.specific_energy_kwh_m3!==null&&(!finite(energy(original))||!finite(energy(revised))))fail('Modeled energy exceeds finite numeric range.');
 const changes=Object.fromEntries(['available_production_m3','delivered_m3','unmet_m3','spill_m3','final_storage_m3','max_reserve_deficit_m3','terminal_deficit_m3','terminal_deviation_m3'].map(key=>[key,revised.totals[key]-original.totals[key]]));
 Object.assign(changes,pairedProductionChanges(original,revised,c.specific_energy_kwh_m3));
 return {schema:1,kind:'fixed_plan_revision_comparison',case_identity:caseFile,proposal_identity:proposalFile,revision_case:c,
  original:{inputs:clone(input),result:original,modeled_production_energy_kwh:energy(original)},revised:{inputs:revisedInputs,result:revised,modeled_production_energy_kwh:energy(revised)},changes,
  water_service:compareWaterService({original:waterServiceModel(input),revised:waterServiceModel(revisedInputs)}),
  scope:['Independent evaluation of supplied production; no schedule generation, model training or dispatch.',
   'Both plans use identical starting water, remaining times, demand, disturbances, capacity, reserve and terminal target. The past prefix is unchanged.',
   'Energy is produced water times the declared constant specific energy, including spilled production. Less service is not credited as savings.',
   'File hashes identify supplied bytes; authorship and source authority remain reviewer declarations. Historical observation provenance is retained, not renewed.',
   'A revision may have different production and end storage. Reserve, unmet demand, spill and target shortfall are reported separately; no operating approval is inferred.']};
}
