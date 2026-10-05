"""One pinned GFS archive request; no model fitting or performance evaluation."""
import argparse
import csv
from datetime import datetime,timedelta,timezone
import hashlib
import json
import math
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PROTOCOL_SHA='6f3b720391b0c3fcad427ba97748d6a419c5522127d689aae1cdbb6191a6373f'
FIELDS=['shortwave_radiation_previous_day2','cloud_cover_previous_day2']
PARAMS={'latitude':'34.7744','longitude':'32.4229','start_date':'2024-09-15','end_date':'2026-09-28','hourly':','.join(FIELDS),'models':'gfs_global','timezone':'GMT','timeformat':'unixtime'}
URL='https://previous-runs-api.open-meteo.com/v1/forecast?'+urllib.parse.urlencode(PARAMS,safe=',')
LIMIT=2*1024*1024

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def save(path,value):
    if isinstance(value,bytes):
        with path.open('xb') as stream:stream.write(value)
    else:
        with path.open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
def utc(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
def rows(path):
    with path.open() as stream:return list(csv.DictReader(stream))
def table(path,values,fields):
    with path.open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(values)
def spans(times,values):
    result=[]
    for t,v in zip(times,values):
        if v is not None:continue
        if result and t==result[-1]['last_epoch']+3600:
            result[-1]['last_epoch']=t;result[-1]['hours']+=1
        else:result.append({'first_epoch':t,'last_epoch':t,'hours':1})
    return [dict(first_valid_time_utc=utc(r['first_epoch']),last_valid_time_utc=utc(r['last_epoch']),hours=r['hours']) for r in result]

def inspect(data):
    if data.get('utc_offset_seconds')!=0 or data.get('timezone') not in ('GMT','UTC'):raise ValueError('Wrong UTC basis')
    units=data['hourly_units']
    if units['time']!='unixtime' or units[FIELDS[0]]!='W/m²' or units[FIELDS[1]]!='%':raise ValueError('Wrong units')
    start=int(datetime(2024,9,15,tzinfo=timezone.utc).timestamp());end=int(datetime(2026,9,29,tzinfo=timezone.utc).timestamp())
    hourly=data['hourly'];times=hourly['time']
    if times!=list(range(start,end,3600)) or any(type(t) is not int for t in times):raise ValueError('Missing/duplicate/unordered timestamps or wrong interval')
    for field in FIELDS:
        values=hourly[field]
        if not isinstance(values,list) or len(values)!=len(times):raise ValueError('Wrong array length '+field)
        if any(v is not None and (type(v) not in (int,float) or not math.isfinite(v) or v<0 or (field==FIELDS[1] and v>100)) for v in values):raise ValueError('Invalid nonmissing value '+field)
    for key,bound in [('latitude',90),('longitude',180)]:
        v=data[key]
        if type(v) not in (int,float) or not math.isfinite(v) or abs(v)>bound:raise ValueError('Invalid returned coordinates')
    return hourly

def run(out):
    if sha(HERE/'PROTOCOL.md')!=PROTOCOL_SHA:raise ValueError('Changed frozen protocol')
    pins=json.loads((HERE/'inputs.json').read_text())
    for name,digest in pins.items():
        if sha(ROOT/name)!=digest:raise ValueError('Changed pinned input '+name)
    out.mkdir(exist_ok=False)
    started=time.monotonic();success=False
    try:
        save(out/'request.json',{'started_at_utc':now(),'url':URL,'parameters':PARAMS,'protocol_sha256':PROTOCOL_SHA,'fetch_sha256':sha(Path(__file__)),'input_manifest_sha256':sha(HERE/'inputs.json')})
        try:response=urllib.request.urlopen(urllib.request.Request(URL,headers={'User-Agent':'Aktina-research/1.0','Accept':'application/json'}),timeout=50)
        except urllib.error.HTTPError as error:response=error
        with response:
            raw=response.read(LIMIT+1)
            metadata={'status':response.status,'url':response.geturl(),'headers':response.headers.as_string(),'http_date':response.headers.get('Date'),'finished_at_utc':now(),'elapsed_monotonic_seconds':time.monotonic()-started}
        save(out/'response.json',raw);save(out/'response-metadata.json',metadata)
        if len(raw)>LIMIT:raise ValueError('Response exceeded2MiB; retained prefix is incomplete')
        if metadata['status']!=200 or metadata['url']!=URL:raise ValueError('Fixed source did not return HTTP200 at requested URL')
        data=json.loads(raw);hourly=inspect(data);times=hourly['time'];lookup={t:i for i,t in enumerate(times)}
        targets=rows(ROOT/'app/experiments/f1-006/result/feature-targets.csv')
        if len(targets)!=17832 or len(set(r['feature_time'] for r in targets))!=len(targets):raise ValueError('Changed target membership')
        joined=[];indices=[]
        for r in targets:
            origin=datetime.fromisoformat(r['feature_time']);target=datetime.fromisoformat(r['target_time'])
            if origin.tzinfo or target.tzinfo or target!=origin+timedelta(hours=24):raise ValueError('Wrong original clock')
            epoch=int(target.replace(tzinfo=timezone(timedelta(hours=3))).timestamp())
            if epoch!=int(r['target_epoch_utc']) or epoch not in lookup:raise ValueError('Missing exact UTC target join')
            i=lookup[epoch];indices.append(i)
            radiation,cloud=[hourly[field][i] for field in FIELDS]
            joined.append(dict(feature_time=r['feature_time'],target_time=r['target_time'],target_epoch_utc=epoch,
                valid_time_utc=utc(epoch),radiation_interval_start_utc=utc(epoch-3600),
                gfs_day2_radiation_w_m2=radiation,gfs_day2_cloud_percent=cloud,
                radiation_missing=int(radiation is None),cloud_missing=int(cloud is None)))
        if any(b-a!=1 for a,b in zip(indices,indices[1:])):raise ValueError('Nonconsecutive exact target join')
        raw_rows=[dict(valid_time_utc=utc(t),radiation_interval_start_utc=utc(t-3600),shortwave_radiation_previous_day2=hourly[FIELDS[0]][i],cloud_cover_previous_day2=hourly[FIELDS[1]][i]) for i,t in enumerate(times)]
        table(out/'all-hours.csv',raw_rows,list(raw_rows[0]));table(out/'joined-gfs.csv',joined,list(joined[0]))
        table(out/'missing-targets.csv',[r for r in joined if r['radiation_missing'] or r['cloud_missing']],list(joined[0]))
        coverage={field:{'nulls_all_hours':sum(v is None for v in hourly[field]),'nulls_target_hours':sum(hourly[field][i] is None for i in indices),
            'target_missing_spans':spans([times[i] for i in indices],[hourly[field][i] for i in indices])} for field in FIELDS}
        result={'status':'ARCHIVE_AND_JOIN_VERIFIED','model_selector':'gfs_global','source':'NOAA NCEP GFS via Open-Meteo','raw_hours':len(times),'target_hours':len(joined),'padding_hours':len(times)-len(joined),
            'first_target_utc':joined[0]['valid_time_utc'],'last_target_utc':joined[-1]['valid_time_utc'],'coverage':coverage,
            'returned_grid':{k:data.get(k) for k in ('latitude','longitude','elevation')},'returned_timezone':data['timezone'],'source_url':URL,
            'network_data_requests':1,'scores_computed':0,'models_fitted':0,
            'limits':['Nominal48h lead is not verified historical publication/issue availability.','Radiation is preceding-hour mean; cloud is valid-time instantaneous.','Different NOAA model does not prove statistical independence from ECMWF or reference estimates.','Pinned selector does not identify an immutable upstream model revision.'],
            'input_sha256':pins,'output_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()}}
        save(out/'report.json',result);success=True;return result
    except Exception as error:
        save(out/'failure.json',{'status':'FAILED','finished_at_utc':now(),'error':f'{type(error).__name__}: {error}'})
        raise
    finally:
        changed=[name for name,digest in pins.items() if sha(ROOT/name)!=digest]
        save(out/'integrity.json',{'original_files_unchanged':not changed,'changed_files':changed,'input_sha256':pins,'intake_success':success,'finished_at_utc':now()})
        if changed:raise ValueError('Pinned originals changed during intake')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(parser.parse_args().output),indent=2))
