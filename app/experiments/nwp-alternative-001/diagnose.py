"""Describe a retained failed intake; preserve every raw cloud value and reject model use."""
import csv
from datetime import datetime,timedelta,timezone
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=HERE/'result'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):
    with path.open() as stream:return list(csv.DictReader(stream))
def save(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
def table(path,values,fields):
    with path.open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(values)
def utc(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()

def main():
    raw=(OUT/'response.json').read_bytes();data=json.loads(raw);h=data['hourly'];times=h['time']
    fields=('shortwave_radiation_previous_day2','cloud_cover_previous_day2')
    expected=list(range(int(datetime(2024,9,15,tzinfo=timezone.utc).timestamp()),int(datetime(2026,9,29,tzinfo=timezone.utc).timestamp()),3600))
    assert times==expected and all(type(t) is int for t in times)
    assert data['utc_offset_seconds']==0 and data['timezone']=='GMT'
    assert data['hourly_units']=={'time':'unixtime',fields[0]:'W/m²',fields[1]:'%'}
    assert all(len(h[f])==len(times) for f in fields)
    assert all(v is None or (type(v) in (int,float) and math.isfinite(v) and v>=0) for v in h[fields[0]])
    assert all(v is None or (type(v) in (int,float) and math.isfinite(v)) for v in h[fields[1]])
    lookup={t:i for i,t in enumerate(times)};targets=rows(ROOT/'app/experiments/f1-006/result/feature-targets.csv')
    assert len(targets)==17832 and len(set(r['feature_time'] for r in targets))==17832
    joined=[]
    for r in targets:
        target=datetime.fromisoformat(r['target_time']);origin=datetime.fromisoformat(r['feature_time'])
        assert target==origin+timedelta(hours=24) and target.tzinfo is None and origin.tzinfo is None
        epoch=int(target.replace(tzinfo=timezone(timedelta(hours=3))).timestamp());assert epoch==int(r['target_epoch_utc'])
        i=lookup[epoch];radiation,cloud=(h[f][i] for f in fields)
        joined.append({'feature_time':r['feature_time'],'target_time':r['target_time'],'target_epoch_utc':epoch,'valid_time_utc':utc(epoch),'radiation_interval_start_utc':utc(epoch-3600),
            'gfs_day2_radiation_w_m2':radiation,'gfs_day2_cloud_percent_raw':cloud,'radiation_missing':int(radiation is None),'cloud_missing':int(cloud is None),'cloud_out_of_range':int(cloud is not None and not 0<=cloud<=100)})
    assert all(b['target_epoch_utc']-a['target_epoch_utc']==3600 for a,b in zip(joined,joined[1:]))
    table(OUT/'diagnostic-join.csv',joined,list(joined[0]))
    flagged=[r for r in joined if r['cloud_out_of_range'] or r['cloud_missing'] or r['radiation_missing']]
    table(OUT/'quality-flags.csv',flagged,list(joined[0]))
    pins=json.loads((HERE/'inputs.json').read_text())
    assert all(sha(ROOT/name)==digest for name,digest in pins.items())
    report={'status':'SOURCE_QUALITY_LIMITATION','original_strict_intake_status':'FAILED','raw_response_sha256':hashlib.sha256(raw).hexdigest(),'raw_bytes':len(raw),
        'raw_hours':len(times),'target_hours':len(joined),'padding_hours':len(times)-len(joined),'exact_utc_joins':True,'radiation_schema_valid':True,
        'null_counts_all':{f:h[f].count(None) for f in fields},'null_counts_targets':{'radiation':sum(r['radiation_missing'] for r in joined),'cloud':sum(r['cloud_missing'] for r in joined)},
        'invalid_cloud_all':sum(v is not None and not 0<=v<=100 for v in h[fields[1]]),'invalid_cloud_targets':sum(r['cloud_out_of_range'] for r in joined),
        'invalid_cloud_rows':flagged,'returned_grid':{k:data[k] for k in ('latitude','longitude','elevation')},
        'original_source_hashes_unchanged':True,'scores_computed':0,'models_fitted':0,'additional_data_requests':0,
        'restriction':'This diagnostic join preserves invalid raw cloud values. No imputation/clipping or downstream-use approval. A separate frozen experiment must declare its feature-quality policy before scoring.',
        'artifacts_sha256':{p.name:sha(p) for p in (OUT/'diagnostic-join.csv',OUT/'quality-flags.csv')}}
    save(OUT/'diagnostic.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='invalid_cloud_rows'},indent=2))

if __name__=='__main__':main()
