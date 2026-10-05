"""Independent stdlib reconstruction of saved006 counts, selection and past-only features."""
from bisect import bisect_right
import csv
from datetime import datetime,timedelta
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=HERE/'result'

def rows(path):
    with path.open() as stream:return list(csv.DictReader(stream))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def ratio(m,k):
    tp,fp,fn=map(int,(m['tp'],m['fp'],m['fn']))
    a,b={'precision':(tp,tp+fp),'recall':(tp,tp+fn),'f1':(2*tp,2*tp+fp+fn)}[k]
    return Fraction(a,b) if b else Fraction(-1)
def rank(m):return tuple(ratio(m,k) for k in ('f1','precision','recall'))
def gate(m,c):return all(ratio(m,k)>=0 and ratio(m,k)>=ratio(c,k) for k in ('precision','recall','f1'))
def counts(truth,positive):
    pairs=list(zip(truth,positive))
    return {'hours':len(pairs),'tp':sum(t and p for t,p in pairs),'fp':sum(not t and p for t,p in pairs),'fn':sum(t and not p for t,p in pairs),'tn':sum(not t and not p for t,p in pairs)}
def check_counts(actual,expected):
    for k in ('hours','tp','fp','fn','tn'):assert actual[k]==int(expected[k]),(k,actual,expected)
    for k in ('precision','recall','f1'):
        if k in expected and expected[k] not in (None,''):assert abs(float(ratio(actual,k))-float(expected[k]))<=1e-15

def main():
    report=json.loads((OUT/'report.json').read_text());selection=json.loads((OUT/'validation-selection.json').read_text())
    pins=json.loads((HERE/'inputs.json').read_text())
    for name,expected in pins.items():assert sha(ROOT/name)==expected,name
    for name,expected in report['outputs_sha256'].items():assert sha(OUT/name)==expected,name
    assert sha(HERE/'run.py')==report['code_sha256'] and sha(OUT/'validation-selection.json')==report['selection_sha256']
    features=rows(OUT/'features.csv');targets=rows(OUT/'feature-targets.csv')
    original=rows(ROOT/'data/features.csv');nwp=rows(ROOT/'app/experiments/f1-004/result/joined-inputs.csv')
    assert len(features)==len(targets)==len(original)==len(nwp)==17832
    residual={datetime.fromisoformat(r['target_time']):float(t['target'])-float(r['nwp_day2_w_m2']) for r,t in zip(nwp,original)}
    max_mean_error=0
    for row,target,raw in zip(features,targets,original):
        origin=datetime.fromisoformat(row['feature_time'])
        assert row['feature_time']==target['feature_time']==raw[next(iter(raw))]
        assert datetime.fromisoformat(target['target_time'])==origin+timedelta(hours=24)
        assert float(target['actual'])==float(raw['target'])
        for window in (24,168):
            values=[residual[origin-timedelta(hours=h)] for h in range(1,window+1) if origin-timedelta(hours=h) in residual]
            assert float(row[f'residual_count_{window}'])==len(values)
            if values:
                error=abs(float(row[f'residual_mean_{window}'])-math.fsum(values)/len(values));max_mean_error=max(max_mean_error,error);assert error<=1e-10
            else:assert row[f'residual_mean_{window}']==''
        prior=residual.get(origin-timedelta(hours=24))
        assert (row['residual_lag24']=='' if prior is None else float(row['residual_lag24'])==prior)
    predictions={};validation_best={};grid_rows=0
    for stage in ('validation','test'):
        split=rows(ROOT/f'eval/{"cv" if stage=="validation" else "test"}_predictions.csv')
        key=next(iter(split[0]));origin_start=datetime.fromisoformat(split[0][key])
        expected_train=[r for r in targets if datetime.fromisoformat(r['target_time'])<origin_start]
        training=rows(OUT/f'{stage}-training-origins.csv')
        assert [(r['feature_time'],r['target_time']) for r in training]==[(r['feature_time'],r['target_time']) for r in expected_train]
        assert len(training)==report['splits'][stage]['training_hours']
        for method in ('original','persistence','nwp_day2','small','medium','larger'):
            pred=rows(OUT/'predictions'/f'{stage}-{method}.csv');predictions[stage,method]=pred
            assert len(pred)==len(split)
            for p,s in zip(pred,split):
                assert p['feature_time']==s[key] and float(p['actual_w_m2'])==float(s['actual'])
                assert datetime.fromisoformat(p['target_time'])==datetime.fromisoformat(p['feature_time'])+timedelta(hours=24)
                assert int(p['predicted_positive'])==(float(p['probability'])>float(p['cutoff']))
                assert int(p['default_positive'])==(float(p['probability'])>.5)
            truth=[float(p['actual_w_m2'])>600 for p in pred];positive=[p['predicted_positive']=='1' for p in pred]
            check_counts(counts(truth,positive),report['methods'][method][stage]['metrics'])
            check_counts(counts(truth,[p['default_positive']=='1' for p in pred]),report['methods'][method][stage]['default_0_5'])
            if stage=='validation' and method in ('small','medium','larger'):
                probs=[float(p['probability']) for p in pred];ordered=sorted(probs);event=sorted(p for p,t in zip(probs,truth) if t)
                grid=json.loads((OUT/f'validation-grid-{method}.json').read_text());grid_rows+=len(grid)
                assert [r['cutoff'] for r in grid]==sorted(set([0.,1.,*probs]))
                for row in grid:
                    n=len(probs)-bisect_right(ordered,row['cutoff']);tp=len(event)-bisect_right(event,row['cutoff']);fp=n-tp;fn=len(event)-tp;tn=len(probs)-tp-fp-fn
                    m=dict(hours=len(probs),tp=tp,fp=fp,fn=fn,tn=tn);check_counts(m,row)
                    assert row['qualifies']==gate(m,selection['fixed_control'])
                admitted=[r for r in grid if r['qualifies']]
                best=max(admitted or grid,key=lambda r:(*rank(r),-abs(r['cutoff']-.5),r['cutoff']))
                assert best==selection['all_thresholds'][method];validation_best[method]=best
    eligible=[m for m,r in validation_best.items() if r['qualifies']]
    chosen=max(eligible,key=lambda m:(*rank(validation_best[m]),-['small','medium','larger'].index(m))) if eligible else 'nwp_day2'
    assert chosen==selection['selected_method']==report['selected_method']
    references={}
    for stage in ('validation','test'):
        member=rows(OUT/f'{stage}-reference-membership.csv');references[stage]=member
        assert len(member)==len(predictions[stage,'nwp_day2'])
        assert sum(r['scored']=='1' for r in member)==report['reference_sensitivity'][stage]['common_hours']
    sat={r['valid_time_utc']:r for r in rows(ROOT/'app/experiments/satellite-reference-001/result/reference-full.csv')}
    for stage,member in references.items():
        for r in member:
            actual=sat[r['target_time_utc']]['shortwave_radiation_w_m2']
            assert (r['satellite_w_m2']=='' if actual=='' else float(r['satellite_w_m2'])==float(actual))
            assert r['scored']==str(int(actual!=''))
    comparisons=rows(OUT/'comparison.csv')
    for row in comparisons:
        pred=predictions[row['split'],row['method']];member=references[row['split']]
        include=list(range(len(pred))) if row['basis']=='weather_full' else [i for i,r in enumerate(member) if r['scored']=='1']
        truth=[float(member[i]['satellite_w_m2'] if row['basis']=='satellite_common' else pred[i]['actual_w_m2'])>600 for i in include]
        positive=[pred[i]['predicted_positive']=='1' for i in include]
        check_counts(counts(truth,positive),row)
        brier=math.fsum((float(pred[i]['probability'])-t)**2 for i,t in zip(include,truth))/len(include)
        assert abs(brier-float(row['brier']))<1e-14
    return dict(status='PASS',feature_rows=len(features),history_values_checked=len(features)*5,maximum_history_mean_abs_error=max_mean_error,
        prediction_rows=sum(map(len,predictions.values())),grid_rows_checked=grid_rows,comparison_rows_checked=len(comparisons),
        selection=chosen,source_hashes_unchanged=True,result_report_sha256=sha(OUT/'report.json'),checker_sha256=sha(Path(__file__)))

if __name__=='__main__':
    result=main()
    with (HERE/'check-result.json').open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))
