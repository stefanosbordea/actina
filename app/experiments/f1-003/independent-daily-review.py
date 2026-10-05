"""Independent saved-row audit and paired daily bootstrap; no fitting imports."""
import csv
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import random

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = HERE / 'result'
SEED, REPLICATES = 20261004, 20000
OFFSET = timezone(timedelta(hours=3))

def load(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):
    with path.open() as handle: return list(csv.DictReader(handle))
def exact_ratio(m, name):
    tp, fp, fn = (m[k] for k in ('tp', 'fp', 'fn'))
    n,d = {'precision':(tp,tp+fp),'recall':(tp,tp+fn),'f1':(2*tp,2*tp+fp+fn)}[name]
    return Fraction(n,d) if d else Fraction(-1)
def score(values, cutoff, key='score', radiation=True):
    counts = dict(tp=0,fp=0,fn=0,tn=0)
    errors=[]
    for row in values:
        truth=float(row['actual_w_m2'])>600; value=float(row[key]); positive=value>cutoff
        counts[('tp' if positive else 'fn') if truth else ('fp' if positive else 'tn')]+=1
        errors.append(value-float(row['actual_w_m2']))
    return dict(hours=len(values),**counts,**{k:float(exact_ratio(counts,k)) if exact_ratio(counts,k)>=0 else None for k in ('precision','recall','f1')},
                mae=math.fsum(abs(e) for e in errors)/len(errors) if radiation else None,
                rmse=math.sqrt(math.fsum(e*e for e in errors)/len(errors)) if radiation else None)
def compare(got, expected):
    for key,value in got.items():
        other=expected[key]
        assert (value is None and other is None) or (value is not None and other is not None and math.isclose(value,other,rel_tol=1e-12,abs_tol=1e-12)), (key,value,other)
def rank(m,natural):
    return tuple(exact_ratio(m,k) for k in ('f1','precision','recall'))+(-abs(m['cutoff']-natural),-m['alpha'],-m['cutoff'])
def quantile(ordered,p):
    point=(len(ordered)-1)*p;lo=int(point);hi=math.ceil(point)
    return ordered[lo]+(ordered[hi]-ordered[lo])*(point-lo)

def main():
    output=HERE/'independent-daily-review.json'
    if output.exists(): raise FileExistsError('Retained result exists; do not overwrite.')
    protocol={'comparison':'Predeclared fixed nwp_day2 cutoff600 versus fixed persistence600; not the validation-selected method.',
              'purpose':'Post-run uncertainty analysis requested after point estimates were known; not part of the original selection protocol.',
              'seed':SEED,'replicates':REPLICATES,'block':'Supplied target date under recovered fixed UTC+03; resample all149 date blocks with replacement, using identical blocks for both methods.',
              'partial_day':'Retain the initial15-hour block. Observed estimate uses all3567hours; resampled hour counts may vary when this shorter block is drawn.',
              'interval':'Two-sided95% percentile interval, linear interpolation of ordered bootstrap differences.',
              'effects':['f1','precision','recall','mae','rmse'],'direction':'NWP minus persistence; positive classification differences and negative errors favour NWP.',
              'limitations':['Day blocks do not preserve cross-day weather dependence.','Intervals are marginal, not simultaneous or adjusted for comparisons.','No bootstrap fraction is interpreted as a formal hypothesis-test p-value.','This already-inspected test and unverified historical publication availability cannot establish a deployable model.']}
    protocol_file=HERE/'independent-daily-protocol.json'
    if protocol_file.exists(): assert load(protocol_file)==protocol
    else:
        with protocol_file.open('x') as handle: json.dump(protocol,handle,indent=2);handle.write('\n')
    report=load(RUN/'report.json');selection=load(RUN/'validation-selection.json');contract=load(HERE/'selection-contract.json')
    methods=contract['method_order'];counts=defaultdict(int);all_rows={};computed={}
    for name,key in [('PROTOCOL.md','protocol_sha256'),('PROTOCOL-original.md','original_protocol_sha256'),('protocol-amendment.json','amendment_sha256'),('selection-contract.json','selection_contract_sha256'),('run.py','code_sha256')]: assert sha(HERE/name)==report[key],name
    assert sha(RUN/'validation-selection.json')==report['selection_sha256']
    for name,digest in report['input_sha256'].items(): assert sha(ROOT/name)==digest,name
    for name,digest in report['outputs_sha256'].items(): assert sha(RUN/name)==digest,name
    archive_path=HERE.parent/'nwp-archive-001/archive.json';assert sha(archive_path)==report['archive_sha256']
    archive=load(archive_path)['hourly'];lookup={stamp:i for i,stamp in enumerate(archive['time'])}
    source_features={r['time']:r for r in rows(ROOT/'data/features.csv')}
    joined=rows(RUN/'joined-features.csv');assert len(joined)==len(source_features)
    for row in joined:
        origin=datetime.fromisoformat(row['feature_time']);target=origin+timedelta(hours=24);epoch=int(target.replace(tzinfo=OFFSET).timestamp());i=lookup[epoch]
        assert row['target_time']==str(target) and int(row['target_epoch_utc'])==epoch
        for field in report['features']['base']: assert float(row[field])==float(source_features[row['feature_time']][field])
        assert float(row['nwp_day2_radiation'])==archive['shortwave_radiation_previous_day2'][i]
        cloud=archive['cloud_cover_previous_day2'][i];assert int(row['nwp_day2_cloud_missing'])==(cloud is None)
        assert row['nwp_day2_cloud']=='' if cloud is None else float(row['nwp_day2_cloud'])==cloud
        counts['joined_rows']+=1
    for split,original_name in [('validation','cv_predictions.csv'),('test','test_predictions.csv')]:
        original=rows(ROOT/'eval'/original_name);origins=[r['time'] for r in original]
        training=rows(RUN/f'{split}-training-origins.csv');first=datetime.fromisoformat(origins[0])
        expected=[r for r in source_features if datetime.fromisoformat(r)+timedelta(hours=24)<first]
        assert [r['feature_time'] for r in training]==expected
        assert all(datetime.fromisoformat(r['target_time'])==datetime.fromisoformat(r['feature_time'])+timedelta(hours=24)<first for r in training)
        for method in methods:
            values=rows(RUN/'predictions'/f'{split}-{method}.csv');all_rows[split,method]=values
            assert [r['feature_time'] for r in values]==origins
            config=selection['all_configurations'][method];probability=method.startswith('classifier_')
            for row,source in zip(values,original):
                target=datetime.fromisoformat(source['time'])+timedelta(hours=24);epoch=int(target.replace(tzinfo=OFFSET).timestamp());i=lookup[epoch]
                assert row['target_time']==str(target) and int(row['target_epoch_utc'])==epoch
                assert float(row['actual_w_m2'])==float(source['actual']) and float(row['baseline_w_m2'])==float(source['baseline'])
                assert float(row['actual_w_m2'])==float(source_features[source['time']]['target'])
                assert float(row['nwp_day2_w_m2'])==archive['shortwave_radiation_previous_day2'][i]
                assert int(row['cloud_missing'])==(archive['cloud_cover_previous_day2'][i] is None)
                assert float(row['cutoff'])==config['cutoff'] and float(row['alpha'])==config['alpha']
                raw=float(row['raw_prediction']);nwp=float(row['nwp_day2_w_m2']);expected_score=max(0,nwp+config['alpha']*raw) if method=='residual_nwp' else raw
                assert math.isclose(float(row['score']),expected_score,rel_tol=1e-14,abs_tol=1e-12)
                assert int(row['predicted_positive'])==(float(row['score'])>config['cutoff'])
                if method in ('nwp_day2','nwp_calibrated'): assert raw==nwp
                if method=='persistence': assert raw==float(source['baseline'])
                if method=='original': assert math.isclose(raw,float(source['predicted']),rel_tol=1e-14,abs_tol=2e-13)
            counts['prediction_rows']+=len(values);counts['prediction_files']+=1
            natural=.5 if probability else 600
            for basis,key,cutoff in [('selected','score',config['cutoff']),('default','default_score',natural)]:
                m=score(values,cutoff,key,not probability);compare(m,report['methods'][method][split][basis]);computed[split,method,basis]=m;counts['full_scores']+=1
                bymonth=defaultdict(list)
                for row in values:bymonth[row['target_time'][:7]].append(row)
                expected_months=report['methods'][method][split]['monthly' if basis=='selected' else 'default_monthly']
                assert sorted(bymonth)==[m['month'] for m in expected_months]
                for item in expected_months:compare(score(bymonth[item['month']],cutoff,key,not probability),item);counts['monthly_scores']+=1
    refs=[computed['validation',m,'selected'] for m in ('persistence','original')]
    qualifies=lambda m: all(exact_ratio(m,k)>=max(exact_ratio(ref,k) for ref in refs) for k in ('precision','recall'))
    for method in methods:
        cfg=selection['all_configurations'][method];natural=.5 if method.startswith('classifier_') else 600
        grid_file=RUN/f'validation-grid-{method}.json'
        if grid_file.exists():
            grid=load(grid_file);values=all_rows['validation',method];admitted=[]
            for entry in grid:
                rewritten=[dict(row,score=max(0,float(row['nwp_day2_w_m2'])+entry['alpha']*float(row['raw_prediction'])) if method=='residual_nwp' else row['raw_prediction']) for row in values]
                m=score(rewritten,entry['cutoff'],radiation=not method.startswith('classifier_'));compare(m,entry);assert qualifies(m)==entry['qualifies'];counts['validation_grid_scores']+=1
                if entry['qualifies']:admitted.append(entry)
            winner=max(admitted,key=lambda m:rank(m,natural)) if admitted else None
            assert cfg==({k:winner[k] for k in ('alpha','cutoff','qualifies')} if winner else dict(alpha=1,cutoff=natural,qualifies=False))
        else:assert cfg['qualifies']==qualifies(computed['validation',method,'selected'])
    eligible=[m for m in methods if selection['all_configurations'][m]['qualifies']]
    winner=max(eligible,key=lambda m:rank(computed['validation',m,'selected']|selection['all_configurations'][m],.5 if m.startswith('classifier_') else 600)+(-methods.index(m),)) if eligible else 'persistence'
    assert winner==selection['method']==report['recommendation']['method']
    log=(HERE/'run.log').read_text();assert log.index('VALIDATION selection frozen:')<log.index('TEST after frozen validation selection:')<log.index('test persistence')
    dates=defaultdict(lambda:[[0]*7,[0]*7])
    for left,right in zip(all_rows['test','nwp_day2'],all_rows['test','persistence']):
        assert left['target_time']==right['target_time']
        for role,row in enumerate((left,right)):
            total=dates[row['target_time'][:10]][role];truth=float(row['actual_w_m2'])>600;positive=float(row['score'])>600
            total[0 if truth and positive else 1 if positive else 2 if truth else 3]+=1
            error=float(row['score'])-float(row['actual_w_m2']);total[4]+=abs(error);total[5]+=error*error;total[6]+=1
    blocks=list(dates.values());assert len(blocks)==149 and sum(b[0][6] for b in blocks)==3567
    def from_block(b):
        tp,fp,fn,tn,ae,se,n=b
        return {'precision':tp/(tp+fp),'recall':tp/(tp+fn),'f1':2*tp/(2*tp+fp+fn),'mae':ae/n,'rmse':math.sqrt(se/n)}
    rng=random.Random(SEED);effects={k:[] for k in protocol['effects']};sample_hours=[]
    for _ in range(REPLICATES):
        totals=[[0]*7,[0]*7]
        for _ in blocks:
            block=blocks[rng.randrange(len(blocks))]
            for role in (0,1):
                for j,value in enumerate(block[role]):totals[role][j]+=value
        left,right=map(from_block,totals);sample_hours.append(totals[0][6])
        for key in effects:effects[key].append(left[key]-right[key])
    effects_report={}
    for key,values in effects.items():
        ordered=sorted(values);point=computed['test','nwp_day2','selected'][key]-computed['test','persistence','selected'][key]
        effects_report[key]={'difference_nwp_minus_persistence':point,'percentile_95_interval':[quantile(ordered,.025),quantile(ordered,.975)],'bootstrap_fraction_favouring_nwp':sum(v>0 if key in ('precision','recall','f1') else v<0 for v in values)/REPLICATES}
    result={'status':'PASS','checks':dict(counts),'file_sha256':{'checker':sha(Path(__file__)),'protocol':sha(HERE/'PROTOCOL.md'),'report':sha(RUN/'report.json'),'selection':sha(RUN/'validation-selection.json'),'archive':sha(archive_path)},'validation_selected_method':winner,'selected_test_metrics':computed['test',winner,'selected'],'nwp_fixed_test_metrics':computed['test','nwp_day2','selected'],'persistence_test_metrics':computed['test','persistence','selected'],'bootstrap':protocol|{'target_hours':3567,'blocks':len(blocks),'partial_blocks':{k:v[0][6] for k,v in dates.items() if v[0][6]!=24},'resample_hour_count_range':[min(sample_hours),max(sample_hours)],'effects':effects_report},'interpretation':['The validation-selected classifier fails the precision promotion condition. The fixed NWP control cannot be retroactively substituted as the validation winner.','The raw archived forecast supplies a useful retrospective comparison; provider archive access and nominal48hlead do not prove historical publication by the decision origin.','Fixed UTC+03 aligns retained labels; it is not a Cyprus DST clock. Radiation targets retain preceding-hour-mean semantics.','129 missing cloud hours remain in validation; test has none. Native missing handling and its indicator were declared before fitting.']}
    with output.open('x') as handle:json.dump(result,handle,indent=2,allow_nan=False);handle.write('\n')
    print(json.dumps({'status':result['status'],'checks':result['checks'],'selected':winner,'effects':effects_report},indent=2))

if __name__=='__main__':main()
