"""Independent005 reconstruction from retained source bytes; no fit or network."""
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import statistics
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
ROOT = EXP.parents[2]
OUT = EXP/'result'
METHODS = ['original','persistence','nwp_day2','analogue_raw','guarded']
UPPER = float.fromhex('0x1.2c00000000001p+9')
checks = 0


def require(condition, label):
    global checks
    checks += 1
    if not condition: raise AssertionError(label)


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    raw = path.read_bytes()
    return list(csv.DictReader(io.StringIO((gzip.decompress(raw) if path.suffix == '.gz' else raw).decode())))


def compare(actual, expected, label):
    if isinstance(expected, dict):
        require(set(actual) == set(expected),label+' keys')
        for key in expected: compare(actual[key],expected[key],label+'.'+key)
    elif isinstance(expected, float): require(math.isclose(actual,expected,abs_tol=1e-10,rel_tol=1e-12),label)
    else: require(actual == expected,label)


def metrics(records, name, reference):
    actual = [r[reference] for r in records]; point = [r[name][0] for r in records]; event = [r[name][1] for r in records]
    tp=sum(y>600 and e for y,e in zip(actual,event)); fp=sum(y<=600 and e for y,e in zip(actual,event))
    fn=sum(y>600 and not e for y,e in zip(actual,event)); tn=len(records)-tp-fp-fn
    errors=[p-y for p,y in zip(point,actual)]; n=len(records)
    return {'hours':n,'mae':math.fsum(map(abs,errors))/n if n else None,
        'rmse':math.sqrt(math.fsum(e*e for e in errors)/n) if n else None,
        'mean_error':math.fsum(errors)/n if n else None,'tp':tp,'tn':tn,'fp':fp,'fn':fn,
        'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,
        'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
        'denominators':{'precision':tp+fp,'recall':tp+fn,'f1':2*tp+fp+fn}}


def diagnostics(records, reference):
    adjustments=[r['guarded'][0]-r['analogue_raw'][0] for r in records]
    transitions={'corrected_false_positive':0,'new_false_positive':0,'corrected_false_negative':0,'new_false_negative':0}
    for r in records:
        old,new,truth=r['analogue_raw'][1],r['guarded'][1],r[reference]>600
        if old and not new: transitions['corrected_false_positive' if not truth else 'new_false_negative']+=1
        if not old and new: transitions['corrected_false_negative' if truth else 'new_false_positive']+=1
    return {'hours':len(records),'projected_points':sum(x!=0 for x in adjustments),'upward':sum(x>0 for x in adjustments),'downward':sum(x<0 for x in adjustments),
        'max_absolute_adjustment_w_m2':max(map(abs,adjustments),default=0),
        'raw_median_event_disagreements':sum((r['analogue_raw'][0]>600)!=r['nwp_day2'][1] for r in records),
        'raw_probability_event_disagreements':sum(r['analogue_raw'][1]!=r['nwp_day2'][1] for r in records),
        'raw_probability_to_guarded_event_changes':transitions,
        'threshold_pileups':{m:{'exactly_600':sum(r[m][0]==600 for r in records),'exactly_nextafter_600':sum(r[m][0]==UPPER for r in records)} for m in ['nwp_day2','analogue_raw','guarded']}}


lock=json.loads((EXP/'inputs.json').read_text());report=json.loads((OUT/'report.json').read_text())
require(report['status']=='COMPLETE' and report['exit_code']==0,'completed run')
require(sha(EXP/'PROTOCOL.md')==lock['protocol_sha256']==report['protocol_sha256'],'protocol identity')
require(sha(EXP/'inputs.json')==report['inputs_lock_sha256'],'input lock identity')
for path,identity in lock['inputs'].items():
    require(sha(ROOT/path)==identity['sha256'] and (ROOT/path).stat().st_size==identity['bytes'],'input '+path)
for name,value in report['code_sha256'].items(): require(sha(EXP/name)==value,'code '+name)
for name,value in report['output_sha256'].items(): require(sha(OUT/name)==value,'output '+name)

spec=importlib.util.spec_from_file_location('reviewed_correction',EXP/'correction.py');correction=importlib.util.module_from_spec(spec);spec.loader.exec_module(correction)
fixtures=json.loads((HERE/'analytical-fixtures.json').read_text())
for case in fixtures['projection_cases']:
    got=correction.constrain_correction(case['nwp'],case['analogue'])
    require(got.hex()==float(case['expected']).hex() and (got>600)==case['event'],'projection fixture '+case['id'])
    require(correction.constrain_correction(case['nwp'],got)==got and float(str(got)).hex()==got.hex(),'fixture idempotence/serialization')
for bad in [None,True,'600',-1,float('nan'),float('inf'),-float('inf'),10**400]:
    for slot in range(3):
        values=[600,600,600];values[slot]=bad
        try: correction.constrain_correction(*values)
        except ValueError: require(True,'invalid rejected')
        else: raise AssertionError('Invalid projection accepted')
for case in fixtures['scenario_cases']:
    values=[v for v,count in case['groups'] for _ in range(count)]
    median=statistics.median(values);probability=sum(v>600 for v in values)/len(values)
    require(median==case['expected_median'] and probability==case['expected_probability'],'scenario fixture')
    require((median>600)==case['expected_median_event'] and (probability>.5)==case['expected_probability_event'],'scenario decision fixture')
c=fixtures['metric_case'];cases=[{'y':y,'x':(p,e)} for y,p,e in zip(c['truth'],c['point'],c['positive'])]
for key,value in c['expected'].items(): compare(metrics(cases,'x','y')[key],value,'hand metric '+key)
require(all(metrics([],'x','y')[k] is None for k in ['mae','rmse','mean_error','precision','recall','f1']),'empty metrics')

satrows=read_csv(ROOT/'app/experiments/satellite-reference-001/result/reference-full.csv')
satellite={r['valid_time_utc']:None if r['shortwave_radiation_w_m2']=='' else float(r['shortwave_radiation_w_m2']) for r in satrows}
require(len(satellite)==len(satrows),'satellite unique timestamps')
for r in satrows: require(int(r['is_missing'])==(satellite[r['valid_time_utc']] is None),'satellite null status')
allmetrics=[];coverage={};allpoints=0;scenario_values=0;comparisons={}
for stage,n in [('validation',3566),('test',3567)]:
    prior=ROOT/'app/experiments/f1-004/result'
    source={m:read_csv(prior/'predictions'/f'{stage}-{m}.csv') for m in METHODS[:-1]}
    scenarios=read_csv(prior/'scenarios'/f'{stage}-analogue_raw.csv.gz')
    ledger=read_csv(OUT/f'{stage}-rows.csv')
    membership=read_csv(ROOT/'app/experiments/reference-sensitivity-001/result-amended'/f'{stage}-membership.csv')
    keys=[r['feature_time'] for r in source['nwp_day2']]
    require(len(keys)==n and len(set(keys))==n,'complete original hour count')
    for group in [*source.values(),scenarios,ledger,membership]:require([r['feature_time'] for r in group]==keys,'matched ordered keys')
    rebuilt=[]
    for i,key in enumerate(keys):
        base=source['nwp_day2'][i];written=ledger[i];member=membership[i]
        origin=datetime.fromisoformat(key);target=origin+timedelta(hours=24)
        valid=target.replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc).isoformat()
        require(written['target_time']==str(target)==base['target_time'],'24h target')
        require(written['valid_time_utc']==valid==member['valid_time_utc'],'fixed+03 conversion')
        sat=satellite.get(valid);weather=float(base['actual_w_m2']);row={'weather':weather,'satellite':sat}
        expected_status='absent' if valid not in satellite else 'null' if sat is None else 'available'
        require(written['reference_status']==expected_status,'missingness retained')
        require((None if written['satellite_reference_w_m2']=='' else float(written['satellite_reference_w_m2']))==sat,'satellite value')
        require(float(written['weather_reference_w_m2'])==weather==float(member['weather_reference_w_m2']),'weather value')
        require(int(member['reference_available'])==(sat is not None),'prior common hours')
        require((None if member['satellite_reference_w_m2']=='' else float(member['satellite_reference_w_m2']))==sat,'prior satellite value')
        for method in METHODS[:-1]:
            src=source[method][i];point=float(src['point_w_m2']);prob=float(src['probability']);event=prob>.5
            require(src['target_time']==str(target) and float(src['actual_w_m2'])==weather,'method target')
            require(event==bool(int(src['default_positive'])) and 0<=prob<=1,'source fixed decision')
            require(float(written[method+'_point_w_m2'])==point==float(member[method+'_point_w_m2']),'source point preserved')
            require(bool(int(written[method+'_positive']))==event==bool(int(member[method+'_default_positive'])),'source call preserved')
            if method!='analogue_raw':require(event==(point>600),'control threshold')
            row[method]=(point,event)
        values=[float(scenarios[i][f'scenario_{j}']) for j in range(64)]
        require(statistics.median(values)==row['analogue_raw'][0],'saved median')
        require(sum(v>600 for v in values)/64==float(source['analogue_raw'][i]['probability']),'saved probability')
        scenario_values+=64
        a=row['analogue_raw'][0];positive=row['nwp_day2'][1]
        expected=a if (a>600)==positive else UPPER if positive else 600.0
        guarded=float(written['guarded_point_w_m2'])
        require(guarded.hex()==float(expected).hex()==written['guarded_point_binary64_hex'],'exact guarded point/CSV')
        require((guarded>600)==positive==bool(int(written['guarded_positive'])),'guarded event equals NWP')
        require(int(written['projection_applied'])==(guarded!=a),'changed point count')
        require(correction.constrain_correction(row['nwp_day2'][0],guarded)==guarded,'all-hour idempotence')
        row['guarded']=(guarded,positive);rebuilt.append(row);allpoints+=1
    common=[r for r in rebuilt if r['satellite'] is not None]
    coverage[stage]={'original_hours':n,'satellite_common_hours':len(common),'missing_reference_hours':n-len(common)}
    compare(report['coverage'][stage],coverage[stage],'coverage')
    for basis,subset,reference in [('weather_full',rebuilt,'weather'),('weather_common',common,'weather'),('satellite_common',common,'satellite')]:
        scored={m:metrics(subset,m,reference) for m in METHODS}
        for method,score in scored.items():
            expected={'split':stage,'basis':basis,'method':method,**score}
            actual=next(r for r in report['metrics'] if (r['split'],r['basis'],r['method'])==(stage,basis,method))
            compare(actual,expected,'metrics '+stage+basis+method);allmetrics.append(expected)
        for key in ['tp','tn','fp','fn','precision','recall','f1']: require(scored['guarded'][key]==scored['nwp_day2'][key],'classification invariant')
        differences={m:{key:scored['guarded'][key]-scored[m][key] for key in ['mae','rmse','mean_error']} for m in ['nwp_day2','analogue_raw']}
        expected={'projection':diagnostics(subset,reference),'guarded_minus':differences}
        compare(report['diagnostics'][stage+'_'+basis],expected,'diagnostics '+stage+basis)
        comparisons[stage+'_'+basis]={'guarded':scored['guarded'],'nwp_day2':scored['nwp_day2'],'differences':differences,'projection':expected['projection']}
csvmetrics=read_csv(OUT/'metrics.csv')
require(len(csvmetrics)==len(report['metrics'])==len(allmetrics)==30,'all thirty metrics retained')
for actual,expected in zip(csvmetrics,allmetrics):
    for key,value in expected.items():
        if key=='denominators':continue
        compare(None if actual[key]=='' else float(actual[key]) if isinstance(value,(int,float)) else actual[key],value,'metric CSV '+key)
require(all(sha(ROOT/path)==identity['sha256'] for path,identity in lock['inputs'].items()),'source inputs unchanged')
result={'status':'PASS','checks':checks,'matched_hours':allpoints,'scenario_values':scenario_values,'metric_rows':len(allmetrics),'coverage':coverage,
    'protocol_sha256':sha(EXP/'PROTOCOL.md'),'runner_sha256':sha(EXP/'run.py'),'correction_sha256':sha(EXP/'correction.py'),
    'report_sha256':sha(OUT/'report.json'),'fixture_sha256':sha(HERE/'analytical-fixtures.json'),'checker_sha256':sha(Path(__file__)),
    'comparisons':comparisons,'numeric_tolerance':{'absolute':1e-10,'relative':1e-12,'guarded_points_and_decisions':'exact binary64/boolean; no tolerance'},
    'limits':['Mechanism motivated after observed test outcomes; no independent promotion or novelty claim.','Same event calls guarantee same matched confusion counts, not improved classification.','Scheduler also ranks continuous forecasts; preserved600W/m2 events do not preserve dispatch/cost/water trajectories.','Threshold pileups require full-precision serialization; rounding the positive floor to600 changes its event.','No calibrated guarded probability, interval or live reliability established.']}
(HERE/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:result[k] for k in ['status','checks','matched_hours','scenario_values','metric_rows','coverage']}))
