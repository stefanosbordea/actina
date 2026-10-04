"""Fixed retrospective constrained correction; standard library, no fitting or network."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import sys
from correction import constrain_correction

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROTOCOL_SHA = 'a72390b7ad764b40e12b63b898837480502a32a1cff1b4cee8b50cf916c7f37a'
INPUTS_SHA = 'b161df257bb527f4e04ea9cef80fea2c3872370841716c5e3b9eeb3e4971700f'
METHODS = ('original', 'persistence', 'nwp_day2', 'analogue_raw', 'guarded')
ZONE = timezone(timedelta(hours=3))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def rows(raw, compressed=False):
    return list(csv.DictReader(io.StringIO((gzip.decompress(raw) if compressed else raw).decode())))


def finite(text):
    value = float(text)
    if not math.isfinite(value): raise ValueError('Nonfinite input')
    return value


def unique(records, key):
    result = {record[key]: record for record in records}
    if len(result) != len(records): raise ValueError(f'Duplicate {key}')
    return result


def scores(records, method, reference):
    errors = [row[method + '_point_w_m2'] - row[reference] for row in records]
    tp = tn = fp = fn = 0
    for row in records:
        actual, event = row[reference] > 600, row[method + '_positive']
        tp += actual and event; tn += not actual and not event
        fp += not actual and event; fn += actual and not event
    n = len(records)
    return {'hours': n, 'mae': math.fsum(abs(v) for v in errors) / n if n else None,
            'rmse': math.sqrt(math.fsum(v*v for v in errors) / n) if n else None,
            'mean_error': math.fsum(errors) / n if n else None,
            'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
            'precision': tp / (tp+fp) if tp+fp else None,
            'recall': tp / (tp+fn) if tp+fn else None,
            'f1': 2*tp / (2*tp+fp+fn) if 2*tp+fp+fn else None,
            'denominators': {'precision': tp+fp, 'recall': tp+fn, 'f1': 2*tp+fp+fn}}


def diagnostics(records, reference):
    changed = [r for r in records if r['guarded_point_w_m2'] != r['analogue_raw_point_w_m2']]
    transitions = {'corrected_false_positive': 0, 'new_false_positive': 0, 'corrected_false_negative': 0, 'new_false_negative': 0}
    for r in records:
        old, new, actual = r['analogue_raw_positive'], r['guarded_positive'], r[reference] > 600
        if old != new:
            key = ('corrected_false_negative' if actual else 'new_false_positive') if new else ('new_false_negative' if actual else 'corrected_false_positive')
            transitions[key] += 1
    return {'hours': len(records), 'projected_points': len(changed),
            'upward': sum(r['guarded_point_w_m2'] > r['analogue_raw_point_w_m2'] for r in changed),
            'downward': sum(r['guarded_point_w_m2'] < r['analogue_raw_point_w_m2'] for r in changed),
            'max_absolute_adjustment_w_m2': max((abs(r['guarded_point_w_m2']-r['analogue_raw_point_w_m2']) for r in changed), default=0),
            'raw_median_event_disagreements': sum((r['analogue_raw_point_w_m2'] > 600) != r['nwp_day2_positive'] for r in records),
            'raw_probability_event_disagreements': sum(r['analogue_raw_positive'] != r['nwp_day2_positive'] for r in records),
            'raw_probability_to_guarded_event_changes': transitions,
            'threshold_pileups': {method: {'exactly_600': sum(r[method+'_point_w_m2'] == 600 for r in records),
                                        'exactly_nextafter_600': sum(r[method+'_point_w_m2'] == math.nextafter(600, math.inf) for r in records)}
                                  for method in ('nwp_day2', 'analogue_raw', 'guarded')}}


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    report = {'status': 'RUNNING', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'command': [sys.executable, *sys.argv], 'scope': 'Fixed standard constrained postprocessing motivated after test inspection. Retrospective only; no fit, tuning, probability guarantee or live superiority. Only strict >600 events are preserved, not magnitude ranks, dispatch, costs or water paths. No scheduler integration.',
              'code_sha256': {n: digest((HERE/n).read_bytes()) for n in ('run.py','correction.py','MEASUREMENT-NOTE.md')},
              'protocol_sha256': PROTOCOL_SHA, 'inputs_lock_sha256': INPUTS_SHA}
    try:
        if digest((HERE/'PROTOCOL.md').read_bytes()) != PROTOCOL_SHA or digest((HERE/'inputs.json').read_bytes()) != INPUTS_SHA:
            raise ValueError('Frozen protocol/input identities changed')
        lock = json.loads((HERE/'inputs.json').read_bytes()); blobs = {}
        for name, identity in lock['inputs'].items():
            raw = (ROOT/name).read_bytes()
            if digest(raw) != identity['sha256'] or len(raw) != identity['bytes']: raise ValueError('Changed input: '+name)
            blobs[name] = raw
        reference = unique(rows(blobs['app/experiments/satellite-reference-001/result/reference-full.csv']), 'valid_time_utc')
        old_report = json.loads(blobs['app/experiments/f1-004/result/report.json'])
        metrics = []; coverage = {}; details = {}; checks = {'row_memberships': 0, 'scenario_values': 0, 'projection_identities': 0, 'serialized_roundtrips': 0}
        for stage, expected_count in [('validation',3566),('test',3567)]:
            inputs = {}
            for method in METHODS[:-1]:
                name = f'predictions/{stage}-{method}.csv'; raw = blobs['app/experiments/f1-004/result/'+name]
                if digest(raw) != old_report['outputs_sha256'][name]: raise ValueError('004 prediction identity mismatch')
                inputs[method] = rows(raw); unique(inputs[method], 'feature_time')
            base = inputs['nwp_day2']; keys = [r['feature_time'] for r in base]
            if len(keys) != expected_count or any([r['feature_time'] for r in values] != keys for values in inputs.values()): raise ValueError('Original forecast membership changed')
            scenarios = rows(blobs[f'app/experiments/f1-004/result/scenarios/{stage}-analogue_raw.csv.gz'], True)
            if [r['feature_time'] for r in scenarios] != keys: raise ValueError('Scenario membership changed')
            membership = rows(blobs[f'app/experiments/reference-sensitivity-001/result-amended/{stage}-membership.csv'])
            if [r['feature_time'] for r in membership] != keys: raise ValueError('Satellite membership changed')
            ledger = []
            for index, base_row in enumerate(base):
                origin = datetime.fromisoformat(base_row['feature_time']); target = datetime.fromisoformat(base_row['target_time'])
                if origin.tzinfo or target != origin+timedelta(hours=24): raise ValueError('Changed target horizon')
                valid = target.replace(tzinfo=ZONE).astimezone(timezone.utc); key = valid.isoformat()
                source = reference.get(key)
                satellite = None if source is None or source['shortwave_radiation_w_m2']=='' else finite(source['shortwave_radiation_w_m2'])
                if source is not None and int(source['is_missing']) != (satellite is None): raise ValueError('Reference missing flag mismatch')
                row = {'feature_time': base_row['feature_time'], 'target_time': base_row['target_time'], 'valid_time_utc': key,
                       'weather_reference_w_m2': finite(base_row['actual_w_m2']), 'satellite_reference_w_m2': satellite,
                       'reference_status': 'absent' if source is None else 'null' if satellite is None else 'available'}
                prior = membership[index]
                if prior['valid_time_utc'] != key or int(prior['target_epoch_utc']) != int(valid.timestamp()) or int(prior['reference_available']) != (satellite is not None): raise ValueError('Prior reference membership mismatch')
                if finite(prior['weather_reference_w_m2']) != row['weather_reference_w_m2'] or (None if prior['satellite_reference_w_m2']=='' else finite(prior['satellite_reference_w_m2'])) != satellite: raise ValueError('Prior reference value changed')
                for method, source_rows in inputs.items():
                    item = source_rows[index]; point = finite(item['point_w_m2']); probability = finite(item['probability'])
                    if item['target_time'] != base_row['target_time'] or finite(item['actual_w_m2']) != row['weather_reference_w_m2']: raise ValueError('Candidate target mismatch')
                    if not 0 <= probability <= 1 or int(item['default_positive']) != int(probability > .5): raise ValueError('Saved decision rule mismatch')
                    if method != 'analogue_raw' and (probability != int(point > 600)): raise ValueError('Control decision differs from >600')
                    row[method+'_point_w_m2'] = point; row[method+'_positive'] = int(probability > .5)
                    if point != finite(prior[method+'_point_w_m2']) or row[method+'_positive'] != int(prior[method+'_default_positive']): raise ValueError('Prior forecast changed')
                values = [finite(scenarios[index][f'scenario_{i}']) for i in range(64)]
                if any(v < 0 for v in values) or statistics.median(values) != row['analogue_raw_point_w_m2'] or sum(v > 600 for v in values)/64 != finite(inputs['analogue_raw'][index]['probability']): raise ValueError('Analogue scenario reconstruction mismatch')
                guarded = constrain_correction(row['nwp_day2_point_w_m2'], row['analogue_raw_point_w_m2'])
                row.update(guarded_point_w_m2=guarded,guarded_point_binary64_hex=guarded.hex(),guarded_positive=int(guarded > 600),
                           projection_applied=int(guarded != row['analogue_raw_point_w_m2']))
                if row['guarded_positive'] != row['nwp_day2_positive'] or constrain_correction(row['nwp_day2_point_w_m2'],guarded) != guarded: raise ValueError('Projection identity/idempotence failed')
                ledger.append(row); checks['row_memberships'] += 1; checks['scenario_values'] += 64; checks['projection_identities'] += 1
            with (output/f'{stage}-rows.csv').open('x',newline='') as stream:
                writer = csv.DictWriter(stream,fieldnames=list(ledger[0]));writer.writeheader();writer.writerows(ledger)
            reread = rows((output/f'{stage}-rows.csv').read_bytes())
            for old, written in zip(ledger,reread):
                recovered = float(written['guarded_point_w_m2'])
                if recovered.hex()!=old['guarded_point_binary64_hex'] or int(recovered > 600)!=old['guarded_positive']: raise ValueError('CSV lost the strict decision boundary')
                checks['serialized_roundtrips'] += 1
            common = [r for r in ledger if r['satellite_reference_w_m2'] is not None]
            coverage[stage] = {'original_hours':len(ledger),'satellite_common_hours':len(common),'missing_reference_hours':len(ledger)-len(common)}
            for basis, selected, reference_field in [('weather_full',ledger,'weather_reference_w_m2'),('weather_common',common,'weather_reference_w_m2'),('satellite_common',common,'satellite_reference_w_m2')]:
                by_method = {m:scores(selected,m,reference_field) for m in METHODS}
                for key in ('tp','tn','fp','fn','precision','recall','f1'):
                    if by_method['guarded'][key] != by_method['nwp_day2'][key]: raise ValueError('Guarded classification changed')
                for method, score in by_method.items(): metrics.append({'split':stage,'basis':basis,'method':method,**score})
                details[stage+'_'+basis] = {'projection':diagnostics(selected,reference_field),
                    'guarded_minus':{control:{k:by_method['guarded'][k]-by_method[control][k] for k in ('mae','rmse','mean_error')} for control in ('nwp_day2','analogue_raw')}}
        if any(digest((ROOT/name).read_bytes()) != identity['sha256'] for name,identity in lock['inputs'].items()): raise ValueError('Inputs changed during run')
        if any(digest((HERE/name).read_bytes()) != expected for name,expected in report['code_sha256'].items()): raise ValueError('Code changed during run')
        with (output/'metrics.csv').open('x',newline='') as stream:
            fields=[k for k in metrics[0] if k!='denominators'];writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows({k:r[k] for k in fields} for r in metrics)
        report.update(status='COMPLETE',exit_code=0,coverage=coverage,metrics=metrics,diagnostics=details,checks=checks,
                      output_sha256={p.name:digest(p.read_bytes()) for p in sorted(output.iterdir())},
                      finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(output/'report.json',report)
        return report
    except Exception as error:
        report.update(status='FAILED',exit_code=1,error=f'{type(error).__name__}: {error}',finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(output/'failure.json',report)
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    try:
        result=run(args.output);print(json.dumps({k:result[k] for k in ('status','coverage','checks','diagnostics')},indent=2))
    except Exception as error:
        print(f'FAILED: {type(error).__name__}: {error}',file=sys.stderr);sys.exit(1)
