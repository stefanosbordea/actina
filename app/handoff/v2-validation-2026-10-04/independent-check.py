"""Portable read-only verification of retained Stefanos v2 validation files."""
import argparse
import ast
import csv
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVISION = '85097a560769ad8a1459ce55f0b3a4c301202405'


def compute():
    inputs = {}
    def read(name):
        body=(ROOT/name).read_bytes()
        inputs[name]=hashlib.sha256(body).hexdigest()
        return body.decode()
    manifest=json.loads(read(str((HERE/'inputs/manifest.json').relative_to(ROOT))))
    if manifest['git_commit'] != REVISION:
        raise AssertionError('Unexpected supplied revision')
    texts={}
    for source,item in manifest['files'].items():
        texts[source]=read(item['local'])
        if inputs[item['local']] != item['sha256'] or len(texts[source].encode()) != item['bytes']:
            raise AssertionError('Changed retained supplied input')
    def table(text, key):
        result={}
        for row in csv.DictReader(io.StringIO(text)):
            stamp=datetime.fromisoformat(row[key])
            if stamp.tzinfo is not None or stamp in result:
                raise AssertionError('Duplicate or timezone-aware identity')
            result[stamp]=row
        if list(result) != sorted(result):raise AssertionError('Unordered source identities')
        return result
    def num(value):
        value=Decimal(value)
        if not value.is_finite():raise AssertionError('Nonfinite value')
        return value
    def ratio(a,b):return dict(numerator=a,denominator=b,value=a/b) if b else None
    def metric(actual,predicted=None,bits=None):
        truth=[v>600 for v in actual]
        bits=[v>600 for v in predicted] if bits is None else bits
        if len(truth)!=len(bits):raise AssertionError('Unmatched metrics')
        tp=sum(t and b for t,b in zip(truth,bits))
        fp=sum(not t and b for t,b in zip(truth,bits))
        fn=sum(t and not b for t,b in zip(truth,bits))
        result=dict(hours=len(bits),tp=tp,fp=fp,fn=fn,tn=len(bits)-tp-fp-fn,positive_calls=tp+fp,
            precision=ratio(tp,tp+fp),recall=ratio(tp,tp+fn),f1=ratio(2*tp,2*tp+fp+fn),mae_w_m2=None)
        if predicted is not None:
            with localcontext() as context:
                context.prec=50
                mae=sum((abs(a-p) for a,p in zip(actual,predicted)),Decimal())/len(actual)
            result.update(mae_w_m2=float(mae),mae_w_m2_decimal=str(mae))
        return result
    new=table(texts['eval/cv_predictions_v2.csv'],'time')
    old=table(read('eval/cv_predictions.csv'),'time')
    raw=table(read('app/experiments/f1-006/result/predictions/validation-nwp_day2.csv'),'feature_time')
    features=table(read('app/experiments/f1-008/result/features.csv'),'feature_time')
    targets=table(read('app/experiments/f1-006/result/feature-targets.csv'),'feature_time')
    selected=table(read('app/experiments/f1-008/result/predictions/validation-consensus_two_source.csv'),'feature_time')
    policy=json.loads(read('app/experiments/f1-008/result/validation-selection.json'))
    archive=json.loads(read('app/experiments/nwp-archive-001/protocol.json'))
    archived_requests=json.loads(read('app/experiments/nwp-archive-001/requests.json'))
    archived_fetch=read('app/experiments/nwp-archive-001/fetch.py')
    old_loader=read('app/experiments/f1-006/run.py')
    new_urls={}
    for node in ast.parse(texts['data/download_nwp.py']).body:
        if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id.endswith('_url'):new_urls[target.id]=node.value.value
    query=parse_qs(urlparse(new_urls['new_url']).query)
    checks={}
    def check(name,value):checks[name]=bool(value)
    check('same_3566_original_validation_origins',len(new)==3566 and list(new)==list(old)==list(raw)==list(selected))
    check('hourly_validation_origins',all(b-a==timedelta(hours=1) for a,b in zip(new,list(new)[1:])))
    check('same_original_actuals_and_persistence',all(num(r['actual'])==num(old[t]['actual']) and num(r['baseline'])==num(old[t]['baseline']) for t,r in new.items()))
    check('exact_plus24h_target_identity',all(t+timedelta(hours=24)==datetime.fromisoformat(raw[t]['target_time'])==datetime.fromisoformat(targets[t]['target_time'])==datetime.fromisoformat(selected[t]['target_time']) for t in new))
    check('same_saved_target_reference',all(num(r['actual'])==num(targets[t]['actual'])==num(raw[t]['actual_w_m2'])==num(selected[t]['weather_actual_w_m2']) for t,r in new.items()))
    check('archived_raw_event_identity',all(int(num(features[t]['nwp_day2_radiation'])>600)==int(raw[t]['predicted_positive'])==int(selected[t]['nwp_positive']) for t in new))
    check('frozen008_selected_arm',policy['selected_augmented_arm']=='consensus_two_source')
    p=policy['policies']['consensus_two_source']['policy']
    check('frozen008_unchanged_cutoffs',p==dict(kind='correction',lower=0.5,upper=0.6))
    check('frozen008_decisions_reconstructed',all(int(r['predicted_positive'])==((int(r['nwp_positive'])==1 and num(r['probability'])>num(str(p['lower']))) or (int(r['nwp_positive'])==0 and num(r['probability'])>num(str(p['upper'])))) for r in selected.values()))
    actual=[num(r['actual']) for r in new.values()]
    methods={name:metric(actual,[num(r[field]) for r in new.values()]) for name,field in (('stefanos_v2','predicted'),('supplied_raw_day1','forecast'),('yesterday','baseline'))}
    methods['original_v1']=metric(actual,[num(old[t]['predicted']) for t in new])
    methods['retained_raw_day2']=metric(actual,[num(features[t]['nwp_day2_radiation']) for t in new])
    methods['f1_008_validation_selected']=metric(actual,bits=[int(selected[t]['predicted_positive'])==1 for t in new])
    source_differences=dict(different_radiation_rows=sum(num(r['forecast'])!=num(features[t]['nwp_day2_radiation']) for t,r in new.items()),
        different_event_rows=sum((num(r['forecast'])>600)!=(num(features[t]['nwp_day2_radiation'])>600) for t,r in new.items()),
        maximum_absolute_radiation_difference=str(max(abs(num(r['forecast'])-num(features[t]['nwp_day2_radiation'])) for t,r in new.items())))
    provenance=dict(raw_source_identity=source_differences['different_radiation_rows']==0,supplied=dict(request_url=new_urls['new_url'],field=query['hourly'][0].split(','),timezone=query.get('timezone'),model_parameter=query.get('models'),
        target_shift='features_v2.py shifts nwp_radiation and target by -24 rows. CSV origins exactly match the existing hourly validation set.',
        publication_time_verified=False),retained=dict(request_url=next(r['url'] for r in archived_requests if r['label']=='archive'),
        selected_field='shortwave_radiation_previous_day2',model=archive['forecast_model'],fixed_source_clock_offset_seconds=archive['recovered_fixed_offset_seconds'],publication_time_verified=False),
        interpretation='Distinct raw forecasts, not interchangeable controls. The supplied request names previous_day1 and timezone=auto without a models parameter. The retained intake pins ECMWF IFS025 and uses UTC epoch joins. Filenames and equal target rows do not prove equal issue times, practical lead times or historical publication availability.',**source_differences)
    if "archive['shortwave_radiation_previous_day2']" not in old_loader or "'models': 'ecmwf_ifs025'" not in archived_fetch:
        raise AssertionError('Retained source provenance changed')
    return dict(status='PASS_WITH_DISTINCT_RAW_FORECASTS' if all(checks.values()) else 'FAILED',revision=REVISION,
        scope='Portable independent weather-reference validation check. Reads retained inputs only, without Git, network, training or comparator imports.',
        first_origin=str(next(iter(new))),last_origin=str(next(reversed(new))),first_target=str(next(iter(new))+timedelta(hours=24)),last_target=str(next(reversed(new))+timedelta(hours=24)),
        threshold='strictly greater than600 W/m2',checks=checks,methods=methods,raw_source_provenance=provenance,
        caveats=['V2 uses this validation interval for early stopping. These are not untouched test metrics.','008 threshold and arm selection used this validation period, so that comparison is selection-conditioned.','008 event bits have no radiation MAE.','The initial Git-blob check additionally verified v2 feature values against the fetched weather and NWP CSVs at origin+24h. That executed evidence is retained separately inside this JSON. The portable rerun checks retained source declarations and exact existing target identities, without requiring those large upstream CSVs.','No test, satellite, live, water, energy or physical-curtailment improvement is established by this check.'],
        source_sha256=inputs,checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def compare_delivered(independent, delivered):
    names = dict(incoming='stefanos_v2', retained_original='original_v1', persistence='yesterday',
        supplied_raw_forecast='supplied_raw_day1', retained_raw_forecast='retained_raw_day2',
        f1_008_consensus_two_source='f1_008_validation_selected')
    if set(delivered) != set(names):raise AssertionError('Delivered method set differs')
    checked=0
    for external, internal in names.items():
        actual, expected = delivered[external], independent[internal]
        for key, short in dict(hours='hours',true_positive='tp',false_positive='fp',false_negative='fn',true_negative='tn').items():
            if actual[key] != expected[short]:raise AssertionError('Delivered count differs: '+external+'/'+key)
            checked+=1
        for name in ('precision','recall','f1'):
            value=expected[name]['value'] if expected[name] is not None else None
            if actual[name] != value:raise AssertionError('Delivered ratio differs: '+external+'/'+name)
            checked+=1
        a,b=actual.get('mae_w_m2'),expected['mae_w_m2']
        if (a is None)!=(b is None) or (a is not None and (not Decimal(str(a)).is_finite() or abs(a-b)>1e-10)):
            raise AssertionError('Delivered MAE differs: '+external)
        checked+=1
    return checked


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true',help='Compare the saved independent result, without modifying any file')
    args=parser.parse_args()
    result=compute()
    if result['status']=='FAILED':raise AssertionError('Independent identity check failed')
    if args.check:
        saved=json.loads((HERE/'independent-check.json').read_text())
        for key,value in result.items():
            if saved.get(key)!=value:raise AssertionError('Saved check differs: '+key)
        report_path=HERE/'comparison-reviewed.json'
        report_bytes=report_path.read_bytes()
        delivered=json.loads(report_bytes)
        comparisons=compare_delivered(result['methods'],delivered['matched']['metrics'])
        print(json.dumps(dict(status='PASS',revision=REVISION,rows=3566,source_hashes=len(result['source_sha256']),delivered_metric_checks=comparisons,delivered_report_sha256=hashlib.sha256(report_bytes).hexdigest(),result='Independent metrics, source identities and delivered report agree. No files changed.')))
    else:
        print(json.dumps(result,indent=2,allow_nan=False))
