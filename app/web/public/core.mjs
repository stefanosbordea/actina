// Pure handoff validation/evaluation. No network, storage, model fitting or plant commands.
export function isoHour(value) {
  const m=String(value).trim().match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?(Z|[+-]\d{2}:\d{2})$/);
  if(!m) return {error:'Use an ISO timestamp with Z or an explicit UTC offset.'};
  const [year,month,day,hour,minute,second]=[m[1],m[2],m[3],m[4],m[5],m[6]||0].map(Number);
  const local=Date.UTC(year,month-1,day,hour,minute,second), d=new Date(local);
  if(d.getUTCFullYear()!==year||d.getUTCMonth()!==month-1||d.getUTCDate()!==day||d.getUTCHours()!==hour||d.getUTCMinutes()!==minute||d.getUTCSeconds()!==second)
    return {error:'Invalid calendar date or clock time.'};
  const zone=m[8], zh=zone==='Z'?0:Number(zone.slice(1,3)), zm=zone==='Z'?0:Number(zone.slice(4,6));
  if(zh>14||zm>59||(zh===14&&zm!==0))return {error:'Invalid UTC offset.'};
  const offset=(zh*60+zm)*(zone.startsWith('-')?-1:1);
  const epoch=local-offset*60000+Number((m[7]||'0').padEnd(3,'0'));
  if(epoch%3600000!==0)return {error:'Timestamp must align to an exact hourly bin.'};
  return {epoch};
}

export function canonicalRows(data) {
  const rows=[];
  for(const day of data.days)for(let hour=0;hour<24;hour++) {
    const time=day.times?.[hour]||`${day.date}T${String(hour).padStart(2,'0')}:00:00+03:00`;
    const parsed=isoHour(time);
    if(parsed.error)throw Error('Invalid canonical timestamp');
    const issue=day.issues?.[hour]||new Date(Date.parse(`${day.date}T18:00:00+03:00`)-86400000).toISOString();
    const cloud=day.cloud_cover?.[hour];
    rows.push({time,epoch:parsed.epoch,date:day.date,hour,issue,baselineSource:day.baseline_sources?.[hour]??null,actual:day.actual[hour],predicted:day.predicted[hour],baseline:day.baseline[hour],climatology:day.climatology[hour],cloudCover:typeof cloud==='number'&&Number.isFinite(cloud)?cloud:null});
  }
  if(new Set(rows.map(r=>r.epoch)).size!==rows.length)throw Error('Duplicate canonical times');
  return rows;
}

function numeric(value,maximum=2000) {
  const s=String(value??'').trim();
  if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(s))return null;
  const number=Number(s);
  return Number.isFinite(number)&&number>=0&&number<=maximum?number:null;
}

export function validateHandoff(text,canonical,Papa) {
  const parsed=Papa.parse(text,{delimiter:',',skipEmptyLines:'greedy'}), issues=[];
  for(const e of parsed.errors)issues.push({record:(e.row??0)+1,field:'CSV',code:e.code,message:e.message});
  const matrix=parsed.data, headers=(matrix.shift()||[]).map(v=>String(v).trim().replace(/^\uFEFF/,''));
  if(new Set(headers).size!==headers.length)issues.push({record:1,field:'header',code:'duplicate_header',message:'Duplicate column names.'});
  for(const required of ['time','predicted'])if(!headers.includes(required))issues.push({record:1,field:required,code:'missing_header',message:`Required column ${required} is missing.`});
  const allowed=['time','predicted','actual','baseline','forecast_issue_time','baseline_source_time','cloud_cover'];
  for(const field of headers)if(!allowed.includes(field))issues.push({record:1,field,code:'unsupported_column',message:`Unsupported forecast column ${field}. Use the declared handoff fields; additional fields require a separate contract.`});
  const lookup=new Map(canonical.map(row=>[row.epoch,row])), seen=new Set(), rows=[];
  if(matrix.length>10000)issues.push({record:1,field:'CSV',code:'too_many_records',message:'Maximum 10,000 input records; the canonical period has 2,208.'});
  if(!issues.length)matrix.forEach((values,index)=>{
    const record=index+2, row=Object.fromEntries(headers.map((key,i)=>[key,values[i]]));
    const fail=(field,code,message)=>issues.push({record,field,code,message});
    if(values.length!==headers.length){fail('CSV','field_count','Number of fields differs from the header.');return;}
    const time=isoHour(row.time);
    if(time.error){fail('time','invalid_time',time.error);return;}
    if(seen.has(time.epoch)){fail('time','duplicate_time','Duplicate instant, including equivalent UTC offsets.');return;}
    seen.add(time.epoch);
    const truth=lookup.get(time.epoch);
    if(!truth){fail('time','out_of_period','Time is outside 1 July–30 September 2026.');return;}
    const predicted=numeric(row.predicted);
    if(predicted===null){fail('predicted','invalid_number','Radiation prediction must be finite and between 0 and 2,000 W/m².');return;}
    let valid=true;
    for(const field of ['actual','baseline'])if(headers.includes(field)) {
      const value=numeric(row[field]);
      if(value===null||Math.abs(value-truth[field])>1e-6){fail(field,'canonical_mismatch',`${field} does not match retained canonical data.`);valid=false;}
    }
    if(headers.includes('forecast_issue_time')) {
      const issue=isoHour(row.forecast_issue_time), expected=isoHour(truth.issue);
      if(issue.error||issue.epoch!==expected.epoch){fail('forecast_issue_time','issue_mismatch','Issue must match the previous-day 18:00 local contract.');valid=false;}
    }
    if(headers.includes('baseline_source_time')) {
      const supplied=isoHour(row.baseline_source_time),expected=truth.baselineSource?isoHour(truth.baselineSource):null;
      if(!expected||expected.error){fail('baseline_source_time','unsupported_provenance','No retained canonical source timestamp is available for this control.');valid=false;}
      else if(supplied.error||supplied.epoch!==expected.epoch){fail('baseline_source_time','baseline_source_mismatch','Control source timestamp must match the retained latest-available persistence timestamp.');valid=false;}
    }
    if(valid)rows.push({...truth,predicted});
  });
  if(!matrix.length)issues.push({record:1,field:'CSV',code:'empty','message':'No prediction records supplied.'});
  rows.sort((a,b)=>a.epoch-b.epoch);
  const matched=new Set(rows.map(r=>r.epoch)), missing=canonical.filter(r=>!matched.has(r.epoch)).map(r=>r.time);
  const status=issues.length?'BLOCKED':missing.length?'PARTIAL':'COMPLETE';
  return {status,issues,rows:issues.length?[]:rows,inputRecords:matrix.length,matchedRows:rows.length,expectedRows:canonical.length,
    missing,headers,issueProvenanceSupplied:headers.includes('forecast_issue_time'),baselineSourceProvenanceSupplied:headers.includes('baseline_source_time'),
    warnings:[...(missing.length?[`${missing.length} canonical hours missing; comparisons use matching rows only.`]:[]),
      ...(headers.includes('cloud_cover')?['Supplied cloud_cover is not used. Diagnostics use retained realized target weather only.']:[]),
      'Numeric validation does not certify model training or feature timing. Review model metadata separately.']};
}

export function regression(rows,column='predicted') {
  if(!rows.length)return {rows:0,mae:null,rmse:null,bias:null};
  const errors=rows.map(r=>r[column]-r.actual);
  return {rows:rows.length,mae:errors.reduce((s,e)=>s+Math.abs(e),0)/rows.length,
    rmse:Math.sqrt(errors.reduce((s,e)=>s+e*e,0)/rows.length),bias:errors.reduce((s,e)=>s+e,0)/rows.length};
}

export function weatherDiagnostics(rows) {
  const daylight=rows.filter(r=>r.actual>20),score=part=>({rows:part.length,days:new Set(part.map(r=>r.date)).size,model:regression(part),baseline:regression(part,'baseline'),climatology:regression(part,'climatology')});
  const known=r=>typeof r.cloudCover==='number'&&Number.isFinite(r.cloudCover)&&r.cloudCover>=0&&r.cloudCover<=100;
  return {daylight:score(daylight),cloudiness:[['low_0_to_20_percent','0 ≤ cloud < 20%',0,20],['medium_20_to_60_percent','20 ≤ cloud < 60%',20,60],['high_60_to_100_percent','60 ≤ cloud ≤ 100%',60,101]].map(([key,label,min,max])=>({key,label,...score(daylight.filter(r=>known(r)&&r.cloudCover>=min&&r.cloudCover<max))})),unknown:score(daylight.filter(r=>!known(r)))};
}

export function evaluateRows(rows,threshold=600) {
  const grouped=field=>{const groups=new Map();for(const row of rows){const key=field==='month'?row.date.slice(0,7):String(row.hour).padStart(2,'0');if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row);}return [...groups].sort(([a],[b])=>a.localeCompare(b)).map(([period,part])=>({period,model:regression(part),baseline:regression(part,'baseline'),climatology:regression(part,'climatology')}));};
  const matrix={tp:0,fp:0,tn:0,fn:0};
  for(const r of rows)matrix[r.predicted>=threshold?(r.actual>=threshold?'tp':'fp'):(r.actual>=threshold?'fn':'tn')]++;
  matrix.precision=matrix.tp+matrix.fp?matrix.tp/(matrix.tp+matrix.fp):null;
  matrix.recall=matrix.tp+matrix.fn?matrix.tp/(matrix.tp+matrix.fn):null;
  return {model:regression(rows),baseline:regression(rows,'baseline'),climatology:regression(rows,'climatology'),
    byHour:grouped('hour'),byMonth:grouped('month'),matrix,days:new Set(rows.map(r=>r.date)).size,
    first:rows[0]?.time??null,last:rows.at(-1)?.time??null,diagnostics:weatherDiagnostics(rows)};
}

export function feedbackRows(evaluation) {
  return [['group','period','rows','model_mae_w_m2','baseline_mae_w_m2','climatology_mae_w_m2','model_rmse_w_m2','baseline_rmse_w_m2','climatology_rmse_w_m2'],
    ['all','matching rows',evaluation.model.rows,evaluation.model.mae,evaluation.baseline.mae,evaluation.climatology.mae,evaluation.model.rmse,evaluation.baseline.rmse,evaluation.climatology.rmse],
    ...[['hour',evaluation.byHour],['month',evaluation.byMonth]].flatMap(([group,items])=>items.map(x=>[group,x.period,x.model.rows,x.model.mae,x.baseline.mae,x.climatology.mae,x.model.rmse,x.baseline.rmse,x.climatology.rmse])),
    ...[['daylight','actual radiation > 20 W/m²',evaluation.diagnostics.daylight],...evaluation.diagnostics.cloudiness.map(x=>['cloud_daylight',x.label,x]),['cloud_daylight','Unknown cloud',evaluation.diagnostics.unknown]].map(([group,label,x])=>[group,label,x.rows,x.model.mae,x.baseline.mae,x.climatology.mae,x.model.rmse,x.baseline.rmse,x.climatology.rmse])];
}

export function safeCSV(rows,Papa) {
  return Papa.unparse(rows,{escapeFormulae:true,newline:'\n'})+'\n';
}

export function validateSchedule(text,data,selectedTank,Papa) {
  const parsed=Papa.parse(text,{delimiter:',',skipEmptyLines:'greedy'}),issues=[],matrix=parsed.data;
  const headers=(matrix.shift()||[]).map(v=>String(v).trim().replace(/^\uFEFF/,''));
  const fail=(record,field,code,message)=>issues.push({record,field,code,message});
  for(const e of parsed.errors)fail((e.row??0)+1,'CSV',e.code,e.message);
  if(new Set(headers).size!==headers.length)fail(1,'header','duplicate_header','Duplicate column names.');
  for(const field of ['time','production_m3'])if(!headers.includes(field))fail(1,field,'missing_header',`Required column ${field} is missing.`);
  const allowed=['time','production_m3','tank_capacity_m3','demand_m3','storage_start_m3','storage_end_m3','storage_m3','assumed_price_eur_mwh','safety_minimum_m3','unit_capacity_m3_hour'];
  for(const field of headers)if(!allowed.includes(field))fail(1,field,'unsupported_column',`Unsupported schedule column ${field}. Additional assumptions or fields require a separate matched contract.`);
  if(matrix.length!==24)fail(1,'CSV','incomplete_day','A matched candidate needs exactly 24 hourly records.');
  const lookup=new Map(canonicalRows(data).map(r=>[r.epoch,r])),seen=new Set(),rows=[];
  if(!issues.length)matrix.forEach((values,index)=>{
    const record=index+2,r=Object.fromEntries(headers.map((k,i)=>[k,values[i]]));
    if(values.length!==headers.length){fail(record,'CSV','field_count','Number of fields differs from header.');return;}
    const parsedTime=isoHour(r.time);
    if(parsedTime.error){fail(record,'time','invalid_time',parsedTime.error);return;}
    if(seen.has(parsedTime.epoch)){fail(record,'time','duplicate_time','Duplicate instant, including equivalent offsets.');return;}
    seen.add(parsedTime.epoch);const truth=lookup.get(parsedTime.epoch);
    if(!truth){fail(record,'time','unsupported_date','Outside the retained comparison period; not supported by this matched fixture.');return;}
    const production=numeric(r.production_m3,Infinity);
    if(production===null){fail(record,'production_m3','invalid_number','Production must be finite and nonnegative.');return;}
    if(production>data.unit_capacity+1e-6){fail(record,'production_m3','unit_capacity','Exceeds the matched 500 m³/h unit capacity.');return;}
    rows.push({...truth,production,raw:r,record});
  });
  rows.sort((a,b)=>a.epoch-b.epoch);
  const dates=new Set(rows.map(r=>r.date));
  if(rows.length===24&&dates.size!==1)fail(1,'time','multiple_days','Use one complete local date, not hours from several dates.');
  let tank=Number(selectedTank);
  if(rows.length&&headers.includes('tank_capacity_m3')){
    const capacities=rows.map(r=>numeric(r.raw.tank_capacity_m3,Infinity));
    if(capacities.some(v=>v===null)||new Set(capacities).size!==1)fail(1,'tank_capacity_m3','inconsistent_capacity','Supply one finite tank capacity on all rows.');
    else tank=capacities[0];
  }
  if(!data.tanks.includes(tank))fail(1,'tank_capacity_m3','unsupported_assumption','Tank volume has no retained matched control. Supported volumes: '+data.tanks.join(', ')+' m³.');
  const day=data.days.find(d=>d.date===rows[0]?.date),production=rows.map(r=>r.production),storage=[],starts=[];
  let inventory=tank*.5;
  if(!issues.length)rows.forEach(r=>{
    starts.push(inventory);inventory+=r.production-data.demand;storage.push(inventory);
    if(inventory<tank*.2-1e-6||inventory>tank+1e-6)fail(r.record,'storage','tank_bound','Derived inventory violates the 20% reserve or tank capacity.');
    const expected={demand_m3:data.demand,storage_start_m3:starts.at(-1),storage_end_m3:inventory,storage_m3:inventory,
      assumed_price_eur_mwh:day.prices[r.hour],safety_minimum_m3:tank*.2,unit_capacity_m3_hour:data.unit_capacity};
    for(const [field,value]of Object.entries(expected))if(headers.includes(field)){
      const supplied=numeric(r.raw[field],Infinity);
      if(supplied===null||Math.abs(supplied-value)>1e-6)fail(r.record,field,
        ['demand_m3','assumed_price_eur_mwh','safety_minimum_m3','unit_capacity_m3_hour'].includes(field)?'unsupported_assumption':'inventory_mismatch',
        `${field} differs from the matched fixture or its derived inventory.`);
    }
  });
  if(!issues.length&&Math.abs(inventory-tank*.5)>1e-6)fail(1,'storage','terminal_balance','Final inventory must equal the 50% initial inventory; daily water must match 2,880 m³.');
  const warnings=['Static matched-fixture validation only: 120 m³/h demand, 500 m³/h unit, 20% reserve, 50% start/end tank and retained illustrative tariffs.',
    'Uniform production and demand within each hour; no ramps, brine constraints, grid permission or method timing certified.',
    ...(!headers.includes('tank_capacity_m3')?['Tank capacity comes from the explicitly selected workspace context.']:[])];
  if(issues.length)return {status:'BLOCKED',issues,warnings,inputRecords:matrix.length,candidate:null,headers};
  const water=production.reduce((s,v)=>s+v,0),energy=water*data.kwh_per_m3,
    cost=production.reduce((s,v,h)=>s+v*data.kwh_per_m3*day.prices[h]/1000,0),flat=day.schedules[String(tank)].totals;
  const totals={water_produced_m3:water,water_demand_m3:2880,unmet_demand_m3:0,energy_kwh:energy,baseline_energy_kwh:flat.baseline_energy_kwh,
    cost_eur:cost,baseline_cost_eur:flat.baseline_cost_eur,cost_saving_eur:flat.baseline_cost_eur-cost,
    cost_saving_percent:(flat.baseline_cost_eur-cost)/flat.baseline_cost_eur*100,safety_violations:0,safety_minimum_m3:tank*.2,
    initial_storage_m3:tank*.5,final_storage_m3:inventory,min_storage_m3:Math.min(tank*.5,...storage),max_storage_m3:Math.max(tank*.5,...storage),
    scheduled_solar_proxy_share_pct:production.reduce((s,v,h)=>s+(day.actual[h]>=data.threshold?v:0),0)/water*100,
    baseline_solar_proxy_share_pct:flat.baseline_solar_proxy_share_pct,co2_saving_kg:0};
  return {status:'VALIDATED',issues:[],warnings,inputRecords:24,headers,candidate:{date:day.date,tankCapacityM3:tank,
    plan:{production,storage,storage_start:starts,totals}}};
}

export function planRecord({day,tank,plan,manifest,reviewer,decision,note,analysis,id,createdAt,
  planSource='Frozen reference radiation; illustrative clock tariffs',planProvenance=null}) {
  if(!reviewer.trim()||!note.trim())throw Error('Add a reviewer and a reason.');
  if(!['Needs team review','Hold for correction','Ready for next simulation'].includes(decision))throw Error('Invalid review decision.');
  return {schema:1,id,createdAt,scope:'Historical simulation review; no plant authorization',reviewer:reviewer.trim().slice(0,80),
    decision,note:note.trim().slice(0,2000),date:day.date,tankCapacityM3:Number(tank),datasetSHA256:manifest.data_sha256,
    planSource,planProvenance,analysis,
    assumptions:{unitCapacityM3Hour:500,demandM3Hour:120,kwhPerM3:3.4,minimumTankFraction:.2,initialFinalTankFraction:.5},
    totals:{...plan.totals},hourly:{times:[...day.times],productionM3:[...plan.production],storageM3:[...plan.storage],pricesEurMWh:[...day.prices]}};
}

export function alertRows(day,plan,tank,modelRows,leak,acknowledged={},sourceId='frozen') {
  const events=[],add=(type,hour,message)=>{const id=`${day.date}:${tank}:${sourceId}:${type}:${hour}`;events.push({id,type,hour,message,reviewed:Boolean(acknowledged[id])});};
  if(plan.totals.min_storage_m3<=plan.totals.safety_minimum_m3+1e-6)add('Reserve reached',null,'Tank reaches its modeled reserve; no bound is violated.');
  for(const row of modelRows.filter(r=>r.date===day.date))if(row.predicted>=600&&row.actual<600)add('Proxy false positive',row.hour,'Forecast high-radiation flag was not observed. This is not a measured surplus event.');
  const meter=day.sites[leak?'leak':'normal'];meter.alerts.forEach((alert,hour)=>{if(alert)add('Synthetic meter',hour,'Injected fixture anomaly; a demonstration, not a field alarm.');});
  return events;
}
