"""Fixed post-run paired target-day uncertainty analysis; no fitting or selection."""
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE/'result'
SEED, REPLICATES = 20261004, 20000
METHODS = ['analogue_raw','nwp_day2','global_residual']
COMPARISONS = {'analogue_raw_minus_nwp_day2':['mae','rmse','f1','precision','recall'],
               'analogue_raw_minus_global_residual':['brier','interval_width_90','interval_coverage_90']}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path): return json.loads(path.read_text())
def rows(path):
    with path.open(newline='') as handle:return list(csv.DictReader(handle))
def quantile(ordered,p):
    at=(len(ordered)-1)*p; lo=int(at); hi=math.ceil(at)
    return ordered[lo]+(at-lo)*(ordered[hi]-ordered[lo])
def scores(b):
    tp,fp,fn,tn,absolute,squared,n,brier,width,covered=b
    return dict(mae=absolute/n,rmse=math.sqrt(squared/n),precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
                brier=brier/n,interval_width_90=width/n,interval_coverage_90=covered/n)

def main():
    output=HERE/'review-daily-bootstrap.json'
    if output.exists():raise FileExistsError('Retained bootstrap result exists; do not overwrite.')
    audit=load(HERE/'review-result.json');assert audit['status']=='PASS' and audit['failure_count']==0
    assert audit['result_sha256']==sha(RUN/'report.json')
    protocol={'requested_after_results_known':True,'selection_allowed':False,'seed':SEED,'replicates':REPLICATES,
              'comparisons':COMPARISONS,'configuration':'All three methods use their fixed default, not a test-chosen probability threshold. Event cutoff is probability>0.5; truth is actual>600W/m2.',
              'block':'Resample supplied target-date blocks under fixed UTC+03, paired across all three methods. Retain the partial first date; resampled hour counts can vary.',
              'interval':'Marginal two-sided95% percentile interval, linear interpolation; no multiplicity adjustment.',
              'limits':['Already-inspected retrospective test; neither a new holdout nor a promotion decision.','Day blocks retain within-day but not cross-day dependence.','Scenarios and resamples do not create independent ground truth.','Smaller interval width and larger coverage must be interpreted jointly; neither alone proves better uncertainty.','No bootstrap tail fraction is a formal p-value.']}
    protocol_path=HERE/'review-daily-protocol.json'
    if protocol_path.exists():assert load(protocol_path)==protocol
    else:protocol_path.write_text(json.dumps(protocol,indent=2)+'\n')
    data={m:rows(RUN/'predictions'/f'test-{m}.csv') for m in METHODS}
    identity=[(r['feature_time'],r['target_time'],r['actual_w_m2']) for r in data[METHODS[0]]]
    assert len(identity)==3567 and len({x[0] for x in identity})==3567
    days=defaultdict(lambda:[[0.0]*10 for _ in METHODS])
    for mi,method in enumerate(METHODS):
        assert [(r['feature_time'],r['target_time'],r['actual_w_m2']) for r in data[method]]==identity
        for r in data[method]:
            b=days[r['target_time'][:10]][mi];actual=float(r['actual_w_m2']);point=float(r['point_w_m2']);prob=float(r['probability']);positive=prob>.5;truth=actual>600
            assert int(r['default_positive'])==positive
            b[0 if truth and positive else 1 if positive else 2 if truth else 3]+=1
            error=point-actual;b[4]+=abs(error);b[5]+=error*error;b[6]+=1;b[7]+=(prob-truth)**2
            if method!='nwp_day2':
                low=float(r['interval_low_w_m2']);high=float(r['interval_high_w_m2']);assert low<=high
                b[8]+=high-low;b[9]+=low<=actual<=high
            else:assert r['interval_low_w_m2']==r['interval_high_w_m2']==''
    dates=sorted(days);blocks=[days[date] for date in dates];assert len(blocks)==149
    totals=[[math.fsum(block[mi][col] for block in blocks) for col in range(10)] for mi in range(3)]
    observed=[scores(row) for row in totals];assert all(row[6]==3567 for row in totals)
    report=load(RUN/'report.json')
    for i,method in enumerate(METHODS):
        expected=report['methods'][method]['test']['default']['full']
        for key,value in observed[i].items():
            if method=='nwp_day2' and key.startswith('interval_'):continue
            assert math.isclose(value,expected[key],rel_tol=1e-12,abs_tol=1e-10),(method,key,value,expected[key])
    rng=random.Random(SEED);effects={name:{key:[] for key in keys} for name,keys in COMPARISONS.items()};undefined={name:Counter() for name in COMPARISONS};hour_counts=[]
    for replicate in range(REPLICATES):
        frequencies=Counter(rng.randrange(len(blocks)) for _ in blocks)
        aggregate=[[math.fsum(blocks[index][mi][col]*multiplicity for index,multiplicity in frequencies.items()) for col in range(10)] for mi in range(3)]
        sampled=[scores(row) for row in aggregate];hour_counts.append(int(aggregate[0][6]))
        for name,right_index in [('analogue_raw_minus_nwp_day2',1),('analogue_raw_minus_global_residual',2)]:
            for key in COMPARISONS[name]:
                left,right=sampled[0][key],sampled[right_index][key]
                if left is None or right is None:undefined[name][key]+=1
                else:effects[name][key].append(left-right)
        if replicate%5000==0:print('bootstrap',replicate,'of',REPLICATES,flush=True)
    results={}
    for name,right_index in [('analogue_raw_minus_nwp_day2',1),('analogue_raw_minus_global_residual',2)]:
        results[name]={}
        for key,values in effects[name].items():
            ordered=sorted(values)
            results[name][key]={'observed_difference':observed[0][key]-observed[right_index][key],
                               'percentile_95_interval':[quantile(ordered,.025),quantile(ordered,.975)] if ordered else None,
                               'defined_replicates':len(values),'undefined_replicates':undefined[name][key]}
    final={'status':'COMPLETE','protocol':protocol,'protocol_sha256':sha(protocol_path),'script_sha256':sha(Path(__file__)),
           'audit_sha256':sha(HERE/'review-result.json'),'runner_report_sha256':sha(RUN/'report.json'),
           'prediction_sha256':{m:sha(RUN/'predictions'/f'test-{m}.csv') for m in METHODS},
           'target_hours':len(identity),'target_date_blocks':len(blocks),'partial_blocks':{date:int(days[date][0][6]) for date in dates if days[date][0][6]!=24},
           'resample_hour_count_range':[min(hour_counts),max(hour_counts)],'observed':{m:{k:v for k,v in observed[i].items() if m!='nwp_day2' or not k.startswith('interval_')} for i,m in enumerate(METHODS)},'differences':results}
    output.write_text(json.dumps(final,indent=2,allow_nan=False)+'\n');print(json.dumps(results,indent=2))

if __name__=='__main__':main()
