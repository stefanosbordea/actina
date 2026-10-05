// Observational intake only. No model, planner, network or plant commands.
export const pilotKinds={tank_storage_m3:'m3',unit_load_kw:'kW',production_rate_m3_h:'m3/h',delivered_flow_m3_h:'m3/h',available_power_kw:'kW'};
export const pilotColumns=['time','available_at','asset_id','measurement','value','unit'];
const scope='Local observation review; numeric checks only. No source authentication, water-quality or safety certification, dispatch permission, recovered-energy claim or plan change.';
const finite=v=>typeof v==='number'&&Number.isFinite(v);
const short=v=>typeof v==='string'&&v.trim().length>0&&v.length<=200;
const id=v=>typeof v==='string'&&/^[A-Za-z0-9_-]{1,64}$/.test(v);

export function pilotTime(value){
 const m=typeof value==='string'&&value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?(Z|[+-]\d{2}:\d{2})$/);
 if(!m)return {error:'Use ISO date/time with seconds and Z or an explicit UTC offset.'};
 const [y,mo,d,h,mi,s]=m.slice(1,7).map(Number),local=Date.UTC(y,mo-1,d,h,mi,s),check=new Date(local);
 if(y<1900||y>2100||check.getUTCFullYear()!==y||check.getUTCMonth()!==mo-1||check.getUTCDate()!==d||check.getUTCHours()!==h||check.getUTCMinutes()!==mi||check.getUTCSeconds()!==s)return {error:'Invalid calendar date or clock time.'};
 const zone=m[8],zh=zone==='Z'?0:Number(zone.slice(1,3)),zm=zone==='Z'?0:Number(zone.slice(4,6));
 if(zh>14||zm>59||(zh===14&&zm!==0))return {error:'Invalid UTC offset.'};
 return {epoch:local-(zh*60+zm)*(zone.startsWith('-')?-1:1)*60000+Number((m[7]||'0').padEnd(3,'0'))};
}

export function validatePilotContract(input){
 const issues=[],fail=(field,code,message)=>issues.push({record:0,field,code,message});
 if(!input||typeof input!=='object'||Array.isArray(input))return {issues:[{record:0,field:'contract',code:'invalid_contract',message:'Declaration must be a JSON object.'}],contract:null};
 const allowed=['schema','label','source_kind','source_label','timezone','window','cadence_minutes','assets','review_as_of'];
 for(const key of Object.keys(input))if(!allowed.includes(key))fail(key,'unsupported_field','This declaration field is not supported.');
 if(input.schema!==1)fail('schema','unsupported_schema','Only schema 1 is supported.');
 for(const key of ['label','source_label'])if(!short(input[key]))fail(key,'invalid_label','Provide a nonempty label, up to 200 characters.');
 if(!['synthetic_fixture','operator_observations'].includes(input.source_kind))fail('source_kind','unsupported_source','Declare synthetic_fixture or operator_observations; forecasts are not telemetry.');
 if(input.timezone!=='Europe/Nicosia')fail('timezone','unsupported_timezone','Declare Europe/Nicosia. Explicit timestamp offsets identify absolute instants.');
 if(![15,60].includes(input.cadence_minutes))fail('cadence_minutes','unsupported_cadence','Cadence must be 15 or 60 minutes.');
 const start=pilotTime(input.window?.start),end=pilotTime(input.window?.end),step=input.cadence_minutes*60000;
 if(!input.window||Object.keys(input.window).some(k=>!['start','end'].includes(k)))fail('window','invalid_window','Window declares start and end only.');
 if(start.error)fail('window.start','invalid_time',start.error);
 if(end.error)fail('window.end','invalid_time',end.error);
 if(!start.error&&!end.error&&(end.epoch<=start.epoch||end.epoch-start.epoch>31*86400000||(end.epoch-start.epoch)%step!==0))fail('window','invalid_window','Use a positive window up to 31 days, with a whole number of cadence slots.');
 let declaredReview=null;
 if(input.review_as_of!==undefined){declaredReview=pilotTime(input.review_as_of);if(declaredReview.error)fail('review_as_of','invalid_time',declaredReview.error);}
 const seen=new Set(),streams=[];
 if(!Array.isArray(input.assets)||!input.assets.length||input.assets.length>20)fail('assets','invalid_assets','Declare 1–20 unique assets.');
 else input.assets.forEach((asset,index)=>{
  const field=`assets[${index}]`;
  if(!asset||typeof asset!=='object'||Array.isArray(asset)){fail(field,'invalid_asset','Asset must be an object.');return;}
  if(Object.keys(asset).some(k=>!['asset_id','label','measurements','tank_reserve_m3'].includes(k)))fail(field,'unsupported_field','Unsupported asset field.');
  if(!id(asset.asset_id)||seen.has(asset.asset_id))fail(field+'.asset_id','invalid_asset_id','Use a unique simple asset ID, up to 64 characters.');
  seen.add(asset.asset_id);
  if(!short(asset.label))fail(field+'.label','invalid_label','Provide an asset label, up to 200 characters.');
  const measurements=new Set();
  if(!Array.isArray(asset.measurements)||!asset.measurements.length||asset.measurements.length>5){fail(field+'.measurements','invalid_measurements','Declare 1–5 supported measurements.');return;}
  asset.measurements.forEach((m,i)=>{
   const path=field+`.measurements[${i}]`;
   if(!m||typeof m!=='object'||Array.isArray(m)){fail(path,'invalid_measurement','Measurement must be an object.');return;}
   if(Object.keys(m).some(k=>!['measurement','unit','min','max'].includes(k)))fail(path,'unsupported_field','Unsupported measurement field.');
   if(!Object.hasOwn(pilotKinds,m.measurement)||measurements.has(m.measurement))fail(path+'.measurement','unsupported_measurement','Declare each supported measurement once per asset.');
   measurements.add(m.measurement);
   if(m.unit!==pilotKinds[m.measurement])fail(path+'.unit','wrong_unit','Use the exact unit for this measurement.');
   if(!finite(m.min)||!finite(m.max)||m.min<0||m.max<=m.min)fail(path,'invalid_bounds','Bounds must be finite numbers with 0 ≤ min < max.');
   streams.push({asset_id:asset.asset_id,label:asset.label,...m,reserve_m3:m.measurement==='tank_storage_m3'?(asset.tank_reserve_m3??null):null});
  });
  if(asset.tank_reserve_m3!==undefined){const tank=asset.measurements.find(m=>m?.measurement==='tank_storage_m3');if(!tank||!finite(asset.tank_reserve_m3)||asset.tank_reserve_m3<tank.min||asset.tank_reserve_m3>tank.max)fail(field+'.tank_reserve_m3','invalid_reserve','Optional reserve must lie inside this asset’s declared tank bounds.');}
 });
 const slots=(!start.error&&!end.error&&Number.isFinite(step))?(end.epoch-start.epoch)/step:0;
 if(slots*streams.length>100000)fail('window','too_many_slots','Maximum 100,000 declared measurement slots per intake.');
 return {issues,contract:issues.length?null:input,streams,start:start.epoch,end:end.epoch,step,slots,declaredReview:declaredReview?.epoch??null};
}

export function validatePilot(input,text,Papa,reviewOverride){
 const declaration=validatePilotContract(input),issues=[...declaration.issues],warnings=[scope,'Source labels and numeric limits are supplied by the reviewer, not independently verified. Missing slots stay unknown. Available power is operator-reported information, never dispatch permission.'];
 const empty=()=>({status:'BLOCKED',reviewRequired:true,issues,warnings,rows:[],knownRows:[],streams:[],missing:[],expectedSlots:0,knownSlots:0,reviewAsOf:null,scope});
 if(issues.length)return empty();
 const parsed=Papa.parse(text,{delimiter:',',skipEmptyLines:'greedy'});
 for(const e of parsed.errors)issues.push({record:(e.row??0)+1,field:'CSV',code:e.code,message:e.message});
 const matrix=parsed.data,headers=(matrix.shift()||[]).map(v=>String(v).trim().replace(/^\uFEFF/,''));
 const fail=(record,field,code,message)=>issues.push({record,field,code,message});
 if(new Set(headers).size!==headers.length)fail(1,'header','duplicate_header','Duplicate column names.');
 for(const key of pilotColumns)if(!headers.includes(key))fail(1,key,'missing_header',`Required column ${key} is missing.`);
 for(const key of headers)if(!pilotColumns.includes(key))fail(1,key,'unsupported_column','Only the six observation columns are supported.');
 if(matrix.length>100000)fail(1,'CSV','too_many_records','Maximum 100,000 input records.');
 const lookup=new Map(declaration.streams.map(s=>[s.asset_id+'\0'+s.measurement,s])),seen=new Set(),rows=[];
 if(!issues.length)matrix.forEach((values,index)=>{
  const record=index+2;
  if(values.length!==headers.length){fail(record,'CSV','field_count','Number of fields differs from the header.');return;}
  const raw=Object.fromEntries(headers.map((key,i)=>[key,String(values[i]).trim()])),time=pilotTime(raw.time),available=pilotTime(raw.available_at);
  if(time.error){fail(record,'time','invalid_time',time.error);return;}
  if(available.error){fail(record,'available_at','invalid_time',available.error);return;}
  if(available.epoch<time.epoch){fail(record,'available_at','future_forecast','Telemetry cannot be available before its observation time.');return;}
  if(time.epoch<declaration.start||time.epoch>=declaration.end){fail(record,'time','out_of_window','Observation must lie in the declared [start, end) window.');return;}
  if((time.epoch-declaration.start)%declaration.step!==0){fail(record,'time','off_cadence','Observation must align with the declared cadence grid.');return;}
  const stream=lookup.get(raw.asset_id+'\0'+raw.measurement);
  if(!stream){fail(record,'asset_id / measurement','undeclared_measurement','This asset and measurement pair was not declared.');return;}
  const key=time.epoch+'\0'+raw.asset_id+'\0'+raw.measurement;
  if(seen.has(key)){fail(record,'time','duplicate_observation','Duplicate asset/measurement instant, including equivalent offsets.');return;}seen.add(key);
  if(raw.unit!==stream.unit){fail(record,'unit','wrong_unit',`Expected ${stream.unit}; no unit conversion is applied.`);return;}
  const value=/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(raw.value)?Number(raw.value):NaN;
  if(!Number.isFinite(value)||value<stream.min||value>stream.max){fail(record,'value','out_of_bounds','Value must be finite and inside the declared numeric bounds.');return;}
  rows.push({...raw,value,epoch:time.epoch,availableEpoch:available.epoch});
 });
 if(issues.length)return empty();
 rows.sort((a,b)=>a.epoch-b.epoch||a.asset_id.localeCompare(b.asset_id)||a.measurement.localeCompare(b.measurement));
 const override=reviewOverride===undefined||reviewOverride===''?null:pilotTime(reviewOverride);
 if(override?.error){fail(0,'review_as_of','invalid_time',override.error);return empty();}
 const reviewEpoch=override?.epoch??declaration.declaredReview??(rows.length?rows.reduce((latest,r)=>Math.max(latest,r.availableEpoch),-Infinity):null);
 const knownRows=rows.filter(r=>reviewEpoch!==null&&r.availableEpoch<=reviewEpoch),known=new Map(knownRows.map(r=>[r.epoch+'\0'+r.asset_id+'\0'+r.measurement,r])),provided=new Map(rows.map(r=>[r.epoch+'\0'+r.asset_id+'\0'+r.measurement,r])),missing=[];
 const streams=declaration.streams.map(s=>{
  const accepted=knownRows.filter(r=>r.asset_id===s.asset_id&&r.measurement===s.measurement),all=rows.filter(r=>r.asset_id===s.asset_id&&r.measurement===s.measurement);
  for(let epoch=declaration.start;epoch<declaration.end;epoch+=declaration.step){const key=epoch+'\0'+s.asset_id+'\0'+s.measurement;if(!known.has(key))missing.push({time:new Date(epoch).toISOString(),asset_id:s.asset_id,measurement:s.measurement,reason:provided.has(key)?'Not available at review time':'No observation supplied'});}
  return {...s,expectedSlots:declaration.slots,providedSlots:all.length,knownSlots:accepted.length,missingSlots:declaration.slots-accepted.length,withheldSlots:all.length-accepted.length,coverage:accepted.length/declaration.slots,latest:accepted.at(-1)??null,belowDeclaredReserve:s.reserve_m3===null?0:accepted.filter(r=>r.value<s.reserve_m3).length};
 });
 if(rows.length!==knownRows.length)warnings.push(`${rows.length-knownRows.length} observation(s) were first available after the chosen review time and remain unknown in this review.`);
 const belowReserve=streams.reduce((sum,s)=>sum+s.belowDeclaredReserve,0);
 if(belowReserve)warnings.push(`${belowReserve} tank observation(s) are below a reviewer-declared reserve. Review is required; this is not a plant safety determination.`);
 if(!rows.length)warnings.push('No observations supplied; review time remains unknown unless explicitly declared.');
 return {status:missing.length?'PARTIAL':'COMPLETE',reviewRequired:Boolean(missing.length||belowReserve),issues,warnings,rows,knownRows,streams,missing,expectedSlots:declaration.slots*streams.length,knownSlots:knownRows.length,reviewAsOf:reviewEpoch===null?null:new Date(reviewEpoch).toISOString(),reviewTimeBasis:override?'Reviewer override':declaration.declaredReview!==null?'Declaration':'Latest first-available input',scope};
}

export function pilotRecord(contract,report,identity){
 return {schema:1,kind:'AquaShift observation intake review',scope,sourceDeclaration:contract,identity,reviewAsOf:report.reviewAsOf,reviewTimeBasis:report.reviewTimeBasis,status:report.status,reviewRequired:report.reviewRequired,expectedSlots:report.expectedSlots,knownSlots:report.knownSlots,streams:report.streams,missing:report.missing,issues:report.issues,warnings:report.warnings,observations:report.rows.map(({epoch,availableEpoch,...row})=>row)};
}

export function pilotCSV(report){return [pilotColumns,...report.rows.map(r=>pilotColumns.map(key=>r[key]))];}

export const pilotExample={schema:1,label:'Synthetic observation intake example',source_kind:'synthetic_fixture',source_label:'Bundled invented QA data; no plant meter',timezone:'Europe/Nicosia',window:{start:'2026-07-01T10:00:00+03:00',end:'2026-07-01T14:00:00+03:00'},cadence_minutes:60,assets:[{asset_id:'tank-demo',label:'Illustrative tank',measurements:[{measurement:'tank_storage_m3',unit:'m3',min:0,max:4000}],tank_reserve_m3:800},{asset_id:'unit-demo',label:'Illustrative desalination unit',measurements:[{measurement:'unit_load_kw',unit:'kW',min:0,max:1700},{measurement:'production_rate_m3_h',unit:'m3/h',min:0,max:500}]},{asset_id:'grid-demo',label:'Operator signal example',measurements:[{measurement:'available_power_kw',unit:'kW',min:0,max:1700}]}]};
export const pilotExampleCSV=[pilotColumns,['2026-07-01T10:00:00+03:00','2026-07-01T10:02:00+03:00','tank-demo','tank_storage_m3',1800,'m3'],['2026-07-01T11:00:00+03:00','2026-07-01T11:02:00+03:00','tank-demo','tank_storage_m3',2050,'m3'],['2026-07-01T12:00:00+03:00','2026-07-01T12:02:00+03:00','tank-demo','tank_storage_m3',2300,'m3'],['2026-07-01T13:00:00+03:00','2026-07-01T13:02:00+03:00','tank-demo','tank_storage_m3',2550,'m3'],['2026-07-01T10:00:00+03:00','2026-07-01T10:01:00+03:00','unit-demo','unit_load_kw',1258,'kW'],['2026-07-01T11:00:00+03:00','2026-07-01T11:01:00+03:00','unit-demo','unit_load_kw',1258,'kW'],['2026-07-01T13:00:00+03:00','2026-07-01T13:01:00+03:00','unit-demo','unit_load_kw',1258,'kW'],['2026-07-01T10:00:00+03:00','2026-07-01T10:01:00+03:00','unit-demo','production_rate_m3_h',370,'m3/h'],['2026-07-01T11:00:00+03:00','2026-07-01T11:01:00+03:00','unit-demo','production_rate_m3_h',370,'m3/h'],['2026-07-01T12:00:00+03:00','2026-07-01T12:01:00+03:00','unit-demo','production_rate_m3_h',370,'m3/h'],['2026-07-01T13:00:00+03:00','2026-07-01T13:01:00+03:00','unit-demo','production_rate_m3_h',370,'m3/h'],['2026-07-01T10:00:00+03:00','2026-07-01T10:05:00+03:00','grid-demo','available_power_kw',900,'kW'],['2026-07-01T11:00:00+03:00','2026-07-01T11:05:00+03:00','grid-demo','available_power_kw',1200,'kW'],['2026-07-01T12:00:00+03:00','2026-07-01T12:05:00+03:00','grid-demo','available_power_kw',1350,'kW'],['2026-07-01T13:00:00+03:00','2026-07-01T13:05:00+03:00','grid-demo','available_power_kw',1100,'kW']];
