"""Verify and join already-retained SARAH3 history; never fetch, fit or score."""
import argparse
import csv
from datetime import datetime,timedelta,timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SOURCE=HERE.parent/'satellite-reference-001'
PROTOCOL_SHA='1d13f673bc82a8054e143f7ac2fd5e7fc1786f9963d3ed1a8b5e633edafafaf0'
OFFSET=timezone(timedelta(hours=3))

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text())
def rows(path):
    with path.open() as stream:return list(csv.DictReader(stream))
def save(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
def table(path,values,fields):
    with path.open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(values)
def naive(value):
    t=datetime.fromisoformat(value)
    if t.tzinfo or t.minute or t.second or t.microsecond:raise ValueError('Expected naive whole-hour label')
    return t

def spans(values):
    result=[]
    for row in values:
        current=datetime.fromisoformat(row['valid_time_utc'])
        if result and current==datetime.fromisoformat(result[-1]['last_valid_time_utc'])+timedelta(hours=1):
            result[-1]['last_valid_time_utc']=current.isoformat();result[-1]['hours']+=1
        else:result.append(dict(first_valid_time_utc=current.isoformat(),last_valid_time_utc=current.isoformat(),hours=1))
    return result

def prepare(out):
    if sha(HERE/'PROTOCOL.md')!=PROTOCOL_SHA:raise ValueError('Changed protocol')
    pins=load(HERE/'inputs.json')
    for name,expected in pins.items():
        if sha(ROOT/name)!=expected:raise ValueError('Changed source '+name)
    out.mkdir(exist_ok=False)
    request=load(SOURCE/'result/request.json');receipt=load(SOURCE/'result/response-metadata.json');source_protocol=load(SOURCE/'result/protocol.json')
    if receipt['status']!=200 or not request['url']==receipt['url']==source_protocol['url']:raise ValueError('Source request/response identity mismatch')
    finish=datetime.fromisoformat(receipt['finished_at_utc'])
    if datetime.fromisoformat(request['started_at_utc'])>finish:raise ValueError('Reversed acquisition clock')
    spec=importlib.util.spec_from_file_location('satellite_intake',SOURCE/'fetch.py');source=importlib.util.module_from_spec(spec);spec.loader.exec_module(source)
    summary,regenerated=source.inspect((SOURCE/'result/response.json').read_bytes())
    if regenerated!=(SOURCE/'result/reference-full.csv').read_bytes():raise ValueError('Raw response does not reconstruct retained CSV')
    reference=list(csv.DictReader(io.StringIO(regenerated.decode())))
    lookup={datetime.fromisoformat(r['valid_time_utc']):r for r in reference}
    if len(lookup)!=len(reference):raise ValueError('Duplicate source target')
    six=HERE.parent/'f1-006/result';features=rows(six/'features.csv');targets=rows(six/'feature-targets.csv');run=load(six/'report.json')
    if len(features)!=len(targets) or len(targets)!=17832:raise ValueError('Changed006 row membership')
    origins=[r['feature_time'] for r in targets]
    if len(set(origins))!=len(origins) or origins!=[r['feature_time'] for r in features]:raise ValueError('Duplicate/misaligned006 origins')
    membership={}
    for stage in ('validation','test'):
        training=rows(six/f'{stage}-training-origins.csv')
        cutoff=naive(run['splits'][stage]['first_evaluation_origin'])
        expected=[r for r in targets if naive(r['target_time'])<cutoff]
        if [(r['feature_time'],r['target_time']) for r in training]!=[(r['feature_time'],r['target_time']) for r in expected]:raise ValueError('Training purge mismatch '+stage)
        membership[stage]={r['feature_time'] for r in training}
    joined=[]
    for r in targets:
        origin,target=naive(r['feature_time']),naive(r['target_time'])
        valid=target.replace(tzinfo=OFFSET).astimezone(timezone.utc)
        if target!=origin+timedelta(hours=24) or int(valid.timestamp())!=int(r['target_epoch_utc']):raise ValueError('Target join changed')
        if valid>=finish:raise ValueError('Nonhistorical target relative to actual retained capture')
        satellite=lookup.get(valid)
        if satellite is None:raise ValueError('Absent source timestamp '+str(valid))
        if datetime.fromisoformat(satellite['interval_start_utc'])!=valid-timedelta(hours=1):raise ValueError('Wrong radiation interval')
        joined.append({'feature_time':r['feature_time'],'target_time':r['target_time'],'valid_time_utc':valid.isoformat(),
            'interval_start_utc':satellite['interval_start_utc'],'weather_actual_w_m2':r['actual'],
            'satellite_w_m2':satellite['shortwave_radiation_w_m2'],'is_missing':satellite['is_missing'],
            'validation_training':int(r['feature_time'] in membership['validation']),'test_training':int(r['feature_time'] in membership['test'])})
    table(out/'joined-reference.csv',joined,list(joined[0]))
    table(out/'missing-reference.csv',[r for r in joined if r['is_missing']=='1'],list(joined[0]))
    coverage={}
    for name,subset in [('all_feature_targets',joined),*[(stage+'_training',[r for r in joined if r[stage+'_training']]) for stage in membership]]:
        missing=[r for r in subset if r['is_missing']=='1']
        coverage[name]={'hours':len(subset),'available_hours':len(subset)-len(missing),'missing_hours':len(missing),
            'first_valid_time_utc':subset[0]['valid_time_utc'],'last_valid_time_utc':subset[-1]['valid_time_utc'],'missing_spans':spans(missing)}
    for name,expected in pins.items():
        if sha(ROOT/name)!=expected:raise ValueError('Source changed during join '+name)
    provenance={'network_data_requests':0,'source_status':'REUSED_RETAINED_RAW_BYTES','source_url':request['url'],'source_request':request,'source_http_receipt':receipt,
        'attribution':'EUMETSAT CM SAF SARAH3 satellite-derived irradiance, served by Open-Meteo. Not ground-sensor truth.',
        'documentation':'https://open-meteo.com/en/docs/satellite-radiation-api','product_doi':'https://doi.org/10.5676/EUM_SAF_CM/SARAH/V003',
        'source_schema_summary':summary,'input_sha256':pins,'protocol_sha256':PROTOCOL_SHA,'prepare_sha256':sha(Path(__file__))}
    save(out/'provenance.json',provenance)
    report={'status':'VERIFIED_REFERENCE_JOIN','prepared_at_utc':datetime.now(timezone.utc).isoformat(),'network_data_requests':0,'models_fitted':0,'scores_computed':0,
        'source_bytes_unchanged':True,'raw_to_retained_csv_byte_identity':True,'clock':'Fixed UTC+03 source labels; explicit UTC valid endpoints and preceding-hour intervals.',
        'coverage':coverage,'output_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()}}
    save(out/'report.json',report)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(prepare(parser.parse_args().output),indent=2))
