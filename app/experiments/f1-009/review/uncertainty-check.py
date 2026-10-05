import csv
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import numpy as np

ROOT = Path('/Users/kixem/Documents/Loucas-Stefanos-Workspace-2026-09-19/AquaShift/source/private/stefanos-2026-10-04/actina')
HERE = ROOT / 'app/experiments/f1-009/review'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
start = time.perf_counter()
saved = json.loads((HERE / 'uncertainty-result.json').read_text())
old_receipt = json.loads((HERE / 'uncertainty-receipt.json').read_text())
paths = [HERE / name for name in ('uncertainty.py','uncertainty-protocol.md','uncertainty-result.json','uncertainty-receipt.json','uncertainty.log')]
for name, digest in old_receipt['sha256'].items(): assert sha(HERE / name) == digest
for name, digest in saved['inputs_sha256'].items():
    path = HERE.parents[1] / name
    assert sha(path) == digest
    paths.append(path)
for number, filename in [('009','test-joint.csv'), ('008','test-consensus_two_source.csv')]:
    directory = HERE.parents[1] / ('f1-' + number) / 'result'
    report = json.loads((directory / 'report.json').read_text())
    assert sha(directory / 'predictions' / filename) == report['outputs_sha256']['predictions/' + filename]
    paths.append(directory / 'report.json')
paths += [HERE.parent / 'README.md']
before = {str(p):sha(p) for p in paths}
with (HERE.parent / 'result/predictions/test-joint.csv').open() as stream: candidate = list(csv.DictReader(stream))
with (HERE.parents[1] / 'f1-008/result/predictions/test-consensus_two_source.csv').open() as stream: prior = list(csv.DictReader(stream))
lookup = {row['target_time']:row for row in prior}
assert len(lookup) == len(prior) == len(candidate) == 3567
assert len({row['feature_time'] for row in candidate}) == 3567
assert len({row['target_time'] for row in candidate}) == 3567
calendar = {}
for row in candidate:
    other = lookup[row['target_time']]
    target, origin = map(datetime.fromisoformat, (row['target_time'],row['feature_time']))
    assert target - origin == timedelta(hours=24)
    assert other['feature_time'] == row['feature_time']
    assert other['satellite_w_m2'] == row['satellite_w_m2']
    assert float(other['weather_actual_w_m2']) == float(row['weather_w_m2'])
    assert other['nwp_positive'] == row['nwp_positive']
    day = target.date()
    if day not in calendar: calendar[day] = (np.zeros((2,3,3), dtype=np.int64), [0,0])
    array, hours = calendar[day]
    decisions = [int(row['predicted_positive']),int(row['nwp_positive']),int(other['predicted_positive'])]
    assert all(v in (0,1) for v in decisions)
    for reference, key in enumerate(('weather_w_m2','satellite_w_m2')):
        if row[key] == '':
            assert reference == 1
            continue
        value = float(row[key])
        assert np.isfinite(value) and value >= 0
        actual = value > 600
        hours[reference] += 1
        for method, call in enumerate(decisions):
            if actual and call: array[reference,method,0] += 1
            elif call: array[reference,method,1] += 1
            elif actual: array[reference,method,2] += 1
ordered = sorted(calendar)
assert all(b-a == timedelta(days=1) for a,b in zip(ordered,ordered[1:]))
rows = [{'day':str(day),'hours_weather_satellite':calendar[day][1], 'counts_reference_method_tp_fp_fn':calendar[day][0].tolist()} for day in ordered]
assert rows == saved['day_counts']
counts = np.stack([calendar[day][0] for day in ordered])
assert len(ordered) == saved['days'] == 149
assert [sum(calendar[d][1][r] for d in ordered) for r in (0,1)] == saved['hours'] == [3567,3517]
assert calendar[ordered[0]][1][0] == 15
assert all(calendar[d][1][0] == 24 for d in ordered[1:])

def metric(values):
    tp,fp,fn = (values[...,i].astype(float) for i in range(3))
    with np.errstate(invalid='ignore', divide='ignore'):
        return np.stack((tp/(tp+fp),tp/(tp+fn),2*tp/(2*tp+fp+fn)), axis=-1)

point = metric(counts.sum(axis=0))
assert np.isnan(metric(np.zeros((1,3), dtype=int))).all()
rng = np.random.default_rng(20261004)
for block in (1,7):
    differences = []
    for _ in range(80):
        origins = rng.integers(149, size=(250,(149+block-1)//block))
        sampled = np.stack([(origins + step) % 149 for step in range(block)],axis=-1).reshape(250,-1)[:,:149]
        pooled = counts[sampled].sum(axis=1)
        value = metric(pooled)
        differences.append(value[:,:,:1] - value[:,:,1:])
    differences = np.concatenate(differences)
    for comparator,name in enumerate(('raw_nwp','frozen_008')):
        output = next(c for c in saved['comparisons'] if c['block_days'] == block and c['control'] == name)
        difference = differences[:,:,comparator]
        assert float(np.mean(np.all(difference > 0,axis=(1,2)))) == output['fraction_all_six_strictly_positive_draws']
        for r,reference in enumerate(('weather_full','satellite_common')):
            for m,name in enumerate(('precision','recall','f1')):
                result = output['references'][reference][name]
                values = difference[:,r,m]
                finite = np.isfinite(values)
                assert result['defined_resamples'] == int(finite.sum()) == 20000
                assert result['undefined_resamples'] == int((~finite).sum()) == 0
                assert result['difference'] == float(point[r,0,m] - point[r,comparator+1,m])
                assert np.array_equal(np.quantile(values[finite],[.025,.975],method='linear'),result['percentile_95'])
                sorted_values = sorted(values[finite])
                for q,expected in zip((.025,.975),result['percentile_95']):
                    position = (len(sorted_values)-1)*q
                    left = int(position)
                    manual = sorted_values[left] + (position-left)*(sorted_values[left+1]-sorted_values[left])
                    assert abs(manual-expected) < 2e-15
spec = importlib.util.spec_from_file_location('uncertainty009', HERE / 'uncertainty.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
rerun = module.main()
assert rerun == saved
readme = (HERE.parent / 'README.md').read_text()
for snippet in ('+0.050 percentage points','−0.101 to +0.207','+0.053 points','−0.100 to +0.219','Both precision intervals also cross zero'):
    assert snippet in readme
seven = next(c for c in saved['comparisons'] if c['block_days']==7 and c['control']=='raw_nwp')
for label in ('weather_full','satellite_common'):
    ci=seven['references'][label]['precision']['percentile_95']
    assert ci[0] < 0 < ci[1]
assert before == {str(p):sha(p) for p in paths}
receipt = {'status':'PASS','recorded_at_utc':datetime.now(timezone.utc).isoformat(), 'source_sha256':before,
 'checker_sha256':sha(Path(__file__)), 'checker_path':str(Path(__file__)),
 'executed_command':'PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /Volumes/CARMIX-WORK/AquaShift-video-2026-10-02/python-reference-environment/bin/python /tmp/aktina-009-uncertainty-independent.py',
 'checks':{'source_reports_and_original_receipt_hashes':True,'joined_target_hours':3567,'satellite_hours':3517,'calendar_days':149,
 'first_partial_day_hours':15,'independent_daily_counts_exact':True,'direct_paired_pooling_resamples_per_block_length':20000,
 'block_lengths_days':[1,7],'circular_block_sampling_and_truncation':True,'same_draws_all_methods_and_references':True,
 'metric_difference_records':24,'all_quantiles_and_undefined_counts_exact':True,'manual_linear_percentile_check_tolerance':2e-15,
 'undefined_fixture_preserved_nan':True,'imported_main_rerun_exactly_equals_saved_json':True,'readme_intervals_and_percentage_point_units':True,
 'source_bytes_unchanged':True,'no_fitting':True,'no_existing_file_overwritten':True},
 'limitations':['Post-inspection marginal sensitivity intervals do not correct adaptive research or multiple comparisons.',
 'Circular seven-day blocks retain local dependence but not longer seasonal structure.',
 'Sampling fractions are not posterior probabilities.'], 'findings':[], 'wall_seconds':time.perf_counter()-start}
with (HERE / 'uncertainty-review.json').open('x') as stream: json.dump(receipt,stream,indent=2)
print(json.dumps({'status':'PASS','seconds':receipt['wall_seconds'],'checker_sha256':receipt['checker_sha256']}))
