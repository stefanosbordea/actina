import {pilotTime} from './pilot.mjs';

const fail=message=>{throw Error(`Observation restart: ${message}`);};
const instant=value=>{const parsed=pilotTime(value);if(parsed.error)fail(parsed.error);return parsed.epoch;};
const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().filter(key=>value[key]!==undefined).map(key=>[key,canonical(value[key])])):value;
export const sameRestart=(a,b)=>JSON.stringify(canonical(a))===JSON.stringify(canonical(b));

export function planForObservation(c){
 const p=c.plan;
 return {times:c.day.times,production:p.production,storage_start:p.storage_start,storage:p.storage,demand:c.demand,capacity:c.capacity,reserve:c.reserve,
  initial:p.totals.initial_storage_m3,target:p.totals.final_storage_m3,unit_capacity_m3_h:c.unitCapacity,identity:{...c.identity,label:c.label}};
}

export function createObservationRestart(comparison,context,time){
 if(comparison?.schema!==1||comparison.kind!=='AquaShift point observation reconciliation')fail('A current observation comparison is required.');
 const plan=planForObservation(context);
 if(!sameRestart(comparison.plan,plan))fail('The selected plan no longer matches this comparison.');
 const epoch=instant(time),hour=plan.times.findIndex(value=>instant(value)===epoch);
 if(hour<0||hour>23)fail('Choose an exact plan boundary with time remaining.');
 const matches=comparison.rows.filter(row=>row.kind==='tank_storage'&&instant(row.time)===epoch);
 if(matches.length!==1)fail('Choose one unambiguous tank comparison.');
 const row=matches[0],asset=comparison.mapping?.tank;
 if(!asset||row.status==='unknown'||!['within_tolerance','requires_explanation'].includes(row.status)||row.plan_hour!==hour||row.sources?.length!==1)fail('The tank reading is unknown or not explicitly mapped.');
 const source=row.sources[0];
 if(source.role!=='tank'||source.asset_id!==asset||source.measurement!=='tank_storage_m3'||source.unit!=='m3'||instant(source.time)!==epoch||!Number.isFinite(row.observed)||source.value!==row.observed||row.observed<0||row.observed>plan.capacity)fail('The reading does not fit the selected tank.');
 if(row.expected!==plan.storage_start[hour])fail('The comparison boundary no longer matches the plan.');
 const available=instant(source.available_at),cutoff=instant(comparison.review_as_of);
 if(available<epoch||available>cutoff)fail('The reading was not available at the comparison cutoff.');
 const declaration=comparison.source?.declaration,declaredAsset=declaration?.assets?.find(candidate=>candidate.asset_id===asset);
 if(!['synthetic_fixture','operator_observations'].includes(comparison.source?.kind)||declaration?.source_kind!==comparison.source.kind||!declaredAsset?.measurements?.some(value=>value.measurement==='tank_storage_m3'&&value.unit==='m3'))fail('The mapped source declaration is unavailable.');
 for(const key of ['contract','observations'])if(!/^[a-f0-9]{64}$/.test(comparison.source.identity?.[key]?.sha256??''))fail('The source identities are unavailable.');
 const original=comparison.original_intake_review_as_of;
 if(original!==null)instant(original);
 return structuredClone({schema:1,kind:'mapped_historical_tank_restart',plan,
  mapping:{asset_id:asset,measurement:'tank_storage_m3',tank_capacity_m3:plan.capacity,authority:'Explicit mapping in Observed departures; no operating authority'},
  reading:{...source,epoch,availableEpoch:available,assetLabel:declaredAsset.label,sourceKind:comparison.source.kind,sourceLabel:comparison.source.label,
   reviewAsOf:comparison.review_as_of,originalIntakeReviewAsOf:original,identity:comparison.source.identity},
  source:comparison.source,start_hour:hour,comparison_cutoff:comparison.review_as_of,original_intake_cutoff:original,
  scope:'Historical point reading, carried from a current explicit tank comparison. Source and mapping are reviewer declarations; this is not verified current storage or plant authorization.'});
}
