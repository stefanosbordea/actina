"""Independent saved-result audit; stdlib only, no fit or runner scoring imports."""
import calendar
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import statistics
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / 'result'
counts = Counter()
failures = []
TOL = 1e-9

def check(value, label):
    counts[label.split(':')[0]] += 1
    if not value:
        failures.append(label)
        if len(failures) <= 12:
            print('FAIL', label, flush=True)

def near(a, b, label, absolute=TOL):
    check(a is None and b is None or a is not None and b is not None and math.isclose(a, b, rel_tol=1e-10, abs_tol=absolute), label)

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p): return json.loads(p.read_text())
def rows(p):
    opener = gzip.open if p.suffix == '.gz' else open
    with opener(p, 'rt', newline='') as stream:
        return list(csv.DictReader(stream))
def dt(value): return datetime.fromisoformat(value)
def quantile(values, fraction):
    ordered = sorted(values); p = (len(ordered)-1)*fraction; lo = math.floor(p)
    return ordered[lo] + (p-lo)*(ordered[min(lo+1,len(ordered)-1)]-ordered[lo])
def solar(t):
    g = 2*math.pi/(366 if calendar.isleap(t.year) else 365)*(t.timetuple().tm_yday-1+(t.hour+t.minute/60+t.second/3600-12)/24)
    eq = 229.18*(.000075+.001868*math.cos(g)-.032077*math.sin(g)-.014615*math.cos(2*g)-.040849*math.sin(2*g))
    dec = .006918-.399912*math.cos(g)+.070257*math.sin(g)-.006758*math.cos(2*g)+.000907*math.sin(2*g)-.002697*math.cos(3*g)+.00148*math.sin(3*g)
    minutes = t.hour*60+t.minute+t.second/60+eq+4*32.4229-180
    lat = math.radians(34.7744); angle = math.radians(minutes/4-180)
    return math.sin(lat)*math.sin(dec)+math.cos(lat)*math.cos(dec)*math.cos(angle), minutes

def geometry(t):
    start = t-timedelta(hours=1)
    values = [solar(start+timedelta(minutes=n))[0] for n in [5,15,25,35,45,55]]
    phase = 2*math.pi*solar(start+timedelta(minutes=30))[1]/1440
    return max(100,1000*math.fsum(max(x,0) for x in values)/6), math.fsum(values)/6, math.sin(phase), math.cos(phase)

def metrics(records, cutoff):
    tp=fp=fn=tn=0
    for r in records:
        truth=r['actual']>600; positive=r['prob']>cutoff
        tp += truth and positive; fp += not truth and positive
        fn += truth and not positive; tn += not truth and not positive
    n=len(records)
    return dict(hours=n,tp=tp,fp=fp,fn=fn,tn=tn,
        precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,
        f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
        mae=math.fsum(abs(r['point']-r['actual']) for r in records)/n if n else None,
        rmse=math.sqrt(math.fsum((r['point']-r['actual'])**2 for r in records)/n) if n else None,
        brier=math.fsum((r['prob']-(r['actual']>600))**2 for r in records)/n if n else None,
        interval_coverage_90=sum(r['low']<=r['actual']<=r['high'] for r in records)/n if n and records[0]['low'] is not None else None,
        interval_width_90=math.fsum(r['high']-r['low'] for r in records)/n if n and records[0]['low'] is not None else None)

def compare_metrics(expected, actual, label):
    for key, value in expected.items(): near(value, actual[key], label+':'+key)
def ratio(m,key):
    a,b={'precision':(m['tp'],m['tp']+m['fp']),'recall':(m['tp'],m['tp']+m['fn']),'f1':(2*m['tp'],2*m['tp']+m['fp']+m['fn'])}[key]
    return Fraction(a,b) if b else Fraction(-1)
def rank(m): return tuple(ratio(m,key) for key in ['f1','precision','recall'])
def gate(m,controls): return all(ratio(m,key)>=0 and all(ratio(m,key)>=ratio(c,key) for c in controls) for key in ['precision','recall'])

report=load(OUT/'report.json'); selection=load(OUT/'validation-selection.json')
check(report['status']=='COMPLETE','status:complete')
for key,p in [('protocol_sha256',HERE/'PROTOCOL.md'),('code_sha256',HERE/'run.py'),('geometry_sha256',HERE/'geometry.py'),('archive_sha256',HERE.parent/'nwp-archive-001/archive.json'),('reference_evaluator_sha256',HERE.parent/'f1-001/run.py')]:
    check(report[key]==sha(p),'hash:'+key)
for name,digest in report['input_sha256'].items():check(sha(ROOT/name)==digest,'hash:source:'+name)
for name,digest in report['outputs_sha256'].items():check(sha(OUT/name)==digest,'hash:output:'+name)
check(sha(OUT/'validation-selection.json')==report['selection_sha256'],'hash:selection')

features=rows(ROOT/'data/features.csv'); feature={r['time']:r for r in features}
weather={r['time']:r for r in rows(ROOT/'data/paphos_weather_data.csv')}
joined=rows(OUT/'joined-inputs.csv'); joins={r['feature_time']:r for r in joined}
check(list(joins)==list(feature),'membership:all-feature-origins')
archive=load(HERE.parent/'nwp-archive-001/archive.json')['hourly']; archive_index={stamp:i for i,stamp in enumerate(archive['time'])}
check(len(archive_index)==len(archive['time']),'membership:unique-archive')
for r in joined:
    origin=r['feature_time']; target=dt(origin)+timedelta(hours=24); epoch=int(target.replace(tzinfo=timezone(timedelta(hours=3))).timestamp())
    check(dt(r['target_time'])==target and int(r['target_epoch_utc'])==epoch,'join:clock')
    i=archive_index[epoch]
    near(float(r['nwp_day2_w_m2']),archive['shortwave_radiation_previous_day2'][i],'join:radiation')
    cloud=archive['cloud_cover_previous_day2'][i]
    check((r['nwp_cloud']=='')==(cloud is None),'join:cloud-missing')
    if cloud is not None:near(float(r['nwp_cloud']),cloud,'join:cloud-value')
    check(int(r['cloud_missing'])==(cloud is None),'join:cloud-indicator')
    for field,expected in zip(['solar_scale','mean_coszen','solar_hour_sin','solar_hour_cos'],geometry(target)):
        near(float(r[field]),expected,'geometry:'+field)
    near(float(feature[origin]['target']),float(weather[str(target)]['shortwave_radiation']),'join:source-target',absolute=0)

spec=importlib.util.spec_from_file_location('review_geometry',HERE/'geometry.py'); module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
for r in load(HERE/'review-geometry-fixtures.json')['fixtures']:
    expected=[r[k] for k in ['scale','mean_coszen','midpoint_solar_clock_sin','midpoint_solar_clock_cos']]
    for a,b in zip(module.solar_features(dt(r['target_local_fixed_utc_plus_03'])),expected):near(a,b,'geometry:prewritten-fixture',absolute=1e-10)

methods=['persistence','original','nwp_day2','median_bias','ridge_bias','global_residual','analogue_raw','analogue_solar']; configs={}; all_records={}; recommendations={}
for stage,source in [('validation','cv_predictions.csv'),('test','test_predictions.csv')]:
    original=rows(ROOT/'eval'/source); expected_origins=[r['time'] for r in original]; original_map={r['time']:r for r in original}
    first=dt(expected_origins[0]); bank=[r['time'] for r in features if dt(r['time'])+timedelta(hours=24)<first]
    membership=rows(OUT/f'{stage}-training-origins.csv')
    check([r['feature_time'] for r in membership]==bank,'membership:'+stage)
    check(all(dt(r['target_time'])==dt(r['feature_time'])+timedelta(hours=24)<first for r in membership),'purge:'+stage)
    params=load(OUT/'parameters'/f'{stage}.json'); cloud_median=statistics.median(float(joins[o]['nwp_cloud']) for o in bank if joins[o]['nwp_cloud']!='')
    near(cloud_median,params['cloud_median'],'scaler:cloud-median')
    def inputs(origin):
        j=joins[origin]
        return [float(j['nwp_day2_w_m2'])/float(j['solar_scale']),float(j['nwp_cloud']) if j['nwp_cloud'] else cloud_median,int(j['cloud_missing']),float(j['mean_coszen']),float(j['solar_hour_sin']),float(j['solar_hour_cos'])]
    matrix=[inputs(o) for o in bank]; columns=list(zip(*matrix)); means=[math.fsum(c)/len(c) for c in columns]; stds=[math.sqrt(math.fsum((v-m)**2 for v in c)/len(c)) or 1 for c,m in zip(columns,means)]
    for a,b in zip(means,params['feature_mean']):near(a,b,'scaler:mean')
    for a,b in zip(stds,params['feature_std']):near(a,b,'scaler:std')
    # Use verified stored scalers for a numerically faithful independent distance check.
    def standardized(origin):return tuple((v-m)/s for v,m,s in zip(inputs(origin),params['feature_mean'],params['feature_std']))
    train=[standardized(o) for o in bank]; bank_index={o:i for i,o in enumerate(bank)}
    residual={o:float(feature[o]['target'])-float(joins[o]['nwp_day2_w_m2']) for o in bank}
    median=statistics.median(residual.values());near(median,params['raw_residual_median'],'residual:median')
    ordered=sorted(bank,key=lambda o:(residual[o],o)); reps=[ordered[(2*j+1)*len(bank)//128] for j in range(64)]
    check(reps==params['global_source_origins'],'representatives:source-order')
    for o,value in zip(reps,params['global_residuals']):near(residual[o],value,'representatives:residual',absolute=0)
    coef=params['ridge']['coef']; intercept=params['ridge']['intercept']
    fit_errors=[residual[o]-intercept-math.fsum(c*x for c,x in zip(coef,row)) for o,row in zip(bank,train)]
    near(math.fsum(fit_errors),0,'ridge:intercept-normal-equation',absolute=1e-6)
    for column,c in zip(zip(*train),coef):near(math.fsum(x*e for x,e in zip(column,fit_errors)),c,'ridge:regularized-normal-equation',absolute=1e-6)
    neighbor_rows=rows(OUT/f'{stage}-analogue-neighbours.csv.gz');check(len(neighbor_rows)==64*len(expected_origins),'neighbors:row-count')
    neighbors={}
    for qi,origin in enumerate(expected_origins):
        block=neighbor_rows[qi*64:(qi+1)*64]; ids=[r['source_feature_time'] for r in block]; distances=[float(r['distance_squared']) for r in block]
        check(all(r['feature_time']==origin and int(r['rank'])==rank for rank,r in enumerate(block)),'neighbors:query-ranks')
        check(len(set(ids))==64 and all(o in bank_index for o in ids),'neighbors:source-membership')
        check(list(zip(distances,ids))==sorted(zip(distances,ids)),'neighbors:distance-tie-order')
        q=standardized(origin)
        for o,distance in zip(ids,distances):near(math.fsum((a-b)**2 for a,b in zip(train[bank_index[o]],q)),distance,'neighbors:saved-distance')
        # Exhaustive omitted-neighbor boundary check; math.dist is a separate C-backed norm.
        chosen=set(ids); boundary=distances[-1]; leeway=TOL+abs(boundary)*1e-10
        for o,row in zip(bank,train):
            if o not in chosen:
                distance=math.dist(row,q)**2
                check_value=distance>=boundary-leeway
                if not check_value:check(False,'neighbors:omitted-nearer:'+stage+':'+origin+':'+o)
                if row==train[bank_index[ids[-1]]] and o<ids[-1]:check(False,'neighbors:omitted-exact-vector-tie')
        counts['neighbors:exhaustive-query']+=1
        neighbors[origin]=ids
        if qi%1000==0:print(stage,'neighbor queries',qi,'of',len(expected_origins),flush=True)
    stage_records={}
    for method in methods:
        prediction=rows(OUT/'predictions'/f'{stage}-{method}.csv');check([r['feature_time'] for r in prediction]==expected_origins,'prediction:identical-hours')
        scenarios=rows(OUT/'scenarios'/f'{stage}-{method}.csv.gz') if method in methods[5:] else None
        if scenarios is not None:check([r['feature_time'] for r in scenarios]==expected_origins,'scenarios:identical-hours')
        records=[]
        for i,r in enumerate(prediction):
            origin=r['feature_time']; j=joins[origin]; actual=float(original_map[origin]['actual']);q=float(j['nwp_day2_w_m2']); scale=float(j['solar_scale'])
            check(r['target_time']==j['target_time'],'prediction:target-time');near(float(r['actual_w_m2']),actual,'prediction:actual',absolute=0)
            near(actual,float(feature[origin]['target']),'prediction:unchanged-source-target',absolute=0)
            if scenarios is not None:
                source_ids=reps if method=='global_residual' else neighbors[origin]
                expected=[max(0,q+residual[o]*(scale/float(joins[o]['solar_scale']) if method=='analogue_solar' else 1)) for o in source_ids]
                retained=[float(scenarios[i][f'scenario_{k}']) for k in range(64)]
                for a,b in zip(expected,retained):near(a,b,'scenarios:reconstruction')
                point=statistics.median(retained);prob=sum(v>600 for v in retained)/64;low=quantile(retained,.05);high=quantile(retained,.95)
            else:
                point={'persistence':float(original_map[origin]['baseline']),'original':float(original_map[origin]['predicted']),'nwp_day2':q,'median_bias':max(0,q+median),'ridge_bias':max(0,q+intercept+math.fsum(a*b for a,b in zip(coef,standardized(origin))))}[method]
                prob=float(point>600);low=high=None
            for expected,field in [(point,'point_w_m2'),(prob,'probability'),(scale,'solar_scale'),(low,'interval_low_w_m2'),(high,'interval_high_w_m2')]:near(expected,float(r[field]) if r[field] else None,'prediction:'+field)
            check(int(r['daytime'])==(scale>100),'prediction:daytime')
            cutoff=float(r['probability_cutoff']);check(int(r['predicted_positive'])==(prob>cutoff) and int(r['default_positive'])==(prob>.5),'prediction:decisions')
            near(cutoff,report['methods'][method][stage]['configuration']['probability_cutoff'],'prediction:frozen-cutoff',absolute=0)
            records.append(dict(actual=actual,point=point,prob=prob,low=low,high=high,month=r['target_time'][:7],daytime=scale>100))
        stage_records[method]=records
        for basis,cutoff in [('selected',float(prediction[0]['probability_cutoff'])),('default',.5)]:
            saved=report['methods'][method][stage][basis]
            for scope,subset in [('full',records),('daytime',[r for r in records if r['daytime']])]:compare_metrics(metrics(subset,cutoff),saved[scope],'metrics:'+stage+':'+method+':'+basis+':'+scope)
            for scope in ['monthly','daytime_monthly']:
                expected_months=sorted({r['month'] for r in records});check([r['month'] for r in saved[scope]]==expected_months,'metrics:month-membership')
                for item in saved[scope]:compare_metrics(metrics([r for r in records if r['month']==item['month'] and (scope=='monthly' or r['daytime'])],cutoff),item,'metrics:'+stage+':'+method+':'+basis+':'+scope+':'+item['month'])
    all_records[stage]=stage_records
    if stage=='validation':
        controls=[metrics(stage_records[n],.5) for n in ['original','persistence','nwp_day2']]
        for method in methods:
            if method in methods[5:]:
                grid=load(OUT/f'validation-grid-{method}.json');check([r['cutoff'] for r in grid]==[i/100 for i in range(30,71,5)],'selection:grid-values')
                eligible=[]
                for row in grid:
                    score=metrics(stage_records[method],row['cutoff']);compare_metrics(score,row,'grid:'+method);qualifies=gate(score,controls);check(qualifies==row['qualifies'],'selection:qualification')
                    if qualifies:eligible.append((row['cutoff'],score))
                best=max(eligible,key=lambda x:(*rank(x[1]),-abs(x[0]-.5),-x[0])) if eligible else None
                configs[method]={'probability_cutoff':best[0] if best else .5,'qualifies':bool(best),'point_cutoff':None}
            else:configs[method]={'probability_cutoff':.5,'qualifies':gate(metrics(stage_records[method],.5),controls),'point_cutoff':600}
            check(configs[method]==selection['all_configurations'][method],'selection:configuration')
        admitted=[n for n in methods if configs[n]['qualifies']]
        winner=max(admitted,key=lambda n:(*rank(metrics(stage_records[n],configs[n]['probability_cutoff'])),-abs(configs[n]['probability_cutoff']-.5),-methods.index(n))) if admitted else 'nwp_day2'
        check(winner==selection['method']==report['recommendation']['method'],'selection:method')
        check(selection['fallback_no_qualifier']==(not admitted),'selection:fallback')
    print(stage,'reconstruction and metrics complete',flush=True)

for row in rows(OUT/'comparison.csv'):
    records=all_records[row['split']][row['method']];subset=records if row['scope']=='full' else [r for r in records if r['daytime']]
    expected=metrics(subset,float(row['probability_cutoff']))
    for key,value in expected.items():near(value,float(row[key]) if row[key] else None,'comparison:'+key)
    check((row['validation_qualifies']=='True')==configs[row['method']]['qualifies'],'comparison:qualification')
empty=metrics([], .5);check(empty['hours']==0 and all(empty[k] is None for k in ['precision','recall','f1','mae','rmse','brier','interval_coverage_90','interval_width_90']),'oracle:empty-semantics')
selected=metrics(all_records['test'][selection['method']],selection['configuration']['probability_cutoff'])
controls={n:metrics(all_records['test'][n],.5) for n in ['original','persistence','nwp_day2']}
promotion=all(ratio(selected,k)>ratio(controls['original'],k) for k in ['f1','precision','recall']) and all(all(ratio(selected,k)>=ratio(controls[n],k) for k in ['f1','precision','recall']) and any(ratio(selected,k)>ratio(controls[n],k) for k in ['f1','precision','recall']) for n in ['persistence','nwp_day2'])
result={'status':'PASS' if not failures else 'FAIL','command':'python3 app/experiments/f1-004/review-check.py','exit_code':int(bool(failures)),'review_script_sha256':sha(Path(__file__)),'protocol_sha256':sha(HERE/'PROTOCOL.md'),'runner_sha256':sha(HERE/'run.py'),'geometry_sha256':sha(HERE/'geometry.py'),'result_sha256':sha(OUT/'report.json'),'geometry_fixture_sha256':sha(HERE/'review-geometry-fixtures.json'),'checks':dict(counts),'failure_count':len(failures),'failures':failures,'selected_method':selection['method'],'promotion_gate_passed':promotion,'selected_test':selected,'control_test':controls,'numerical_tolerance':{'scalar_absolute':TOL,'scalar_relative':1e-10,'ridge_normal_equations_absolute':1e-6,'nearest_boundary':'Every omitted row checked against retained kth distance with absolute 1e-9 plus relative 1e-10; saved distance/tie ordering exact, identical-vector omitted ties checked. Not an exact-real-arithmetic proof.'},'scope':['All saved source joins, training memberships, geometry and six-input scalers; no model fitting.','All 7133 query neighborhoods, 64 saved source rows each, exhaustive omitted-neighbor boundary check.','All six scenario matrices and sixteen prediction files; every selected/default full/daytime/month/daytime-month score, all27 validation grid choices.','Ridge coefficient optimality checked through regularized normal equations, not refit.','Recorded file hashes match; wall-clock ordering comes from static execution path and retained log, not cryptographic attestation.'],'nonblocking_findings':[{'severity':'P3','file':'run.py','lines':'23-24','issue':'Imports f1-001/run.py, whose imports include installed LightGBM/joblib beyond the libraries listed in protocol execution section. No LightGBM fit occurs.','fix':'Disclose the transitive import dependencies in the run README/receipt.'}]}
(HERE/'review-result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':result['status'],'failure_count':len(failures),'selected_method':selection['method'],'promotion_gate_passed':promotion,'checks':dict(counts)}),flush=True)
sys.exit(result['exit_code'])
