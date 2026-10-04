"""Read-only check of the packaged curves, calls, metrics and source identities."""
import csv
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(path,key):
    with (ROOT/path).open(newline='') as stream:
        rows=list(csv.DictReader(stream))
    result={row[key]:row for row in rows}
    assert len(result)==len(rows)==3566
    return result


def verify():
    raw=(ROOT/'app/site/forecast-data.js').read_text()
    prefix='window.AKTINA_FORECAST='
    assert raw.startswith(prefix)
    data=json.loads(raw[len(prefix):].rstrip().removesuffix(';'))
    assert data['schema']==2
    rows=[row for day in data['days'] for row in day['rows']]
    assert len(rows)==3566 and len(data['days'])==150 and len({row['time'] for row in rows})==3566
    for source in data['source']['files']:
        assert sha(ROOT/source['path'])==source['sha256'],source['path']
    corrected=table('app/experiments/v2-019/result/validation-decisions.csv','origin')
    base=table('app/experiments/v2-016/result/validation-decisions.csv','origin')
    original=table('eval/cv_predictions_v2.csv','time')
    expected_times={str(datetime.fromisoformat(t)+timedelta(hours=24)) for t in corrected}
    assert {row['time'] for row in rows}==expected_times
    max_difference=0
    for row in rows:
        origin=str(datetime.fromisoformat(row['time'])-timedelta(hours=24))
        c,v=corrected[origin],original[origin]
        assert row['v2']==float(v['predicted']) and row['actual']==float(v['actual'])
        assert row['raw_v2']==float(v['forecast']) and row['persistence']==float(v['baseline'])
        assert row['v2_refit']==float(c['base_prediction'])
        assert row['event_019']==int(c['expanded_call'])==int(float(c['expanded_probability'])>.49)
        max_difference=max(max_difference,abs(row['v2_refit']-float(base[origin]['base_prediction'])))
    assert max_difference<=1e-12
    methods=['v2_600','v2_562','v1','persistence','raw_v2','ecmwf_day2','event_008','event_019']
    assert [row['id'] for row in data['metrics']]==methods
    measured={}
    for saved in data['metrics']:
        name=saved['id']
        field='v2' if name in ('v2_600','v2_562') else name
        truth=[row['actual']>600 for row in rows]
        calls=[bool(row[name]) if name.startswith('event_') else row[field]>(562 if name=='v2_562' else 600) for row in rows]
        tp=sum(t and p for t,p in zip(truth,calls))
        fp=sum(not t and p for t,p in zip(truth,calls))
        fn=sum(t and not p for t,p in zip(truth,calls))
        measured[name]=dict(tp=tp,fp=fp,fn=fn,tn=len(rows)-tp-fp-fn,precision=tp/(tp+fp),recall=tp/(tp+fn),f1=2*tp/(2*tp+fp+fn))
        for key,value in measured[name].items():
            assert saved[key]==value,(name,key)
        if 'mae_w_m2' in saved:
            curve='v2_refit' if name=='event_019' else field
            mae=math.fsum(abs(row[curve]-row['actual']) for row in rows)/len(rows)
            assert math.isclose(mae,saved['mae_w_m2'],rel_tol=0,abs_tol=1e-12)
    assert measured['event_019']['tp']==270 and measured['event_019']['fp']==17
    return dict(status='PASS',verifier_sha256=sha(Path(__file__)),viewer_data_sha256=sha(ROOT/'app/site/forecast-data.js'),
        source_pins_checked=len(data['source']['files']),hours=len(rows),methods=len(methods),
        refit_curve_matches_019_exactly=True,original_curve_matches_upstream_exactly=True,all_019_calls_match=True,
        maximum_016_serialization_difference=max_difference,metrics=measured,training_executed=False)


if __name__=='__main__':
    result=verify()
    with (HERE/'viewer-check.json').open('x') as out:
        json.dump(result,out,indent=2)
        out.write('\n')
    print(json.dumps(result))
