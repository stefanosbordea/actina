"""Package retained validation predictions for the forecast viewer. No fitting or selection."""
import csv
import hashlib
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HANDOFF = Path('app/handoff/v2-validation-2026-10-04')
CALIBRATION = Path('app/handoff/v2-calibration-2026-10-04/validation-selection.json')
FEATURES = Path('app/experiments/v2-016/inputs/validation-features.csv')
FEATURE_MANIFEST = FEATURES.with_name('manifest.json')
CORRECTION = Path('app/experiments/v2-019')
BASE = Path('app/experiments/v2-016/result')
SOURCES = {
    'incoming': HANDOFF / 'inputs/cv_predictions_v2.csv',
    'retained_original': Path('eval/cv_predictions.csv'),
    'retained_raw_control': Path('app/experiments/f1-004/result/predictions/validation-nwp_day2.csv'),
    'classifier': Path('app/experiments/f1-008/result/predictions/validation-consensus_two_source.csv'),
    'classifier_policy': Path('app/experiments/f1-008/result/validation-selection.json'),
}
OUTPUT = Path('app/site/forecast-data.js')
HOURS = 3566


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value):
    result = float(value)
    require(math.isfinite(result), 'Non-finite radiation or probability')
    return result


def bit(value):
    require(value in ('0', '1'), f'Invalid event bit: {value!r}')
    return int(value)


def load_rows(path, key):
    with path.open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    require(len(rows) == HOURS, f'{path.name}: expected {HOURS} validation hours')
    require(len({row[key] for row in rows}) == HOURS, f'{path.name}: duplicate timestamp')
    return {row[key]: row for row in rows}


def scores(actual, calls, points=None):
    truth = [value > 600 for value in actual]
    tp = sum(t and bool(p) for t, p in zip(truth, calls))
    fp = sum(not t and bool(p) for t, p in zip(truth, calls))
    fn = sum(t and not p for t, p in zip(truth, calls))
    tn = len(truth) - tp - fp - fn
    result = dict(hours=len(truth), tp=tp, fp=fp, fn=fn, tn=tn,
                  precision=tp / (tp + fp) if tp + fp else None,
                  recall=tp / (tp + fn) if tp + fn else None,
                  f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None)
    if points is not None:
        result['mae_w_m2'] = math.fsum(abs(p - a) for a, p in zip(actual, points)) / len(actual)
    return result


def verify_scores(calculated, retained):
    aliases = {'tp': 'true_positive', 'fp': 'false_positive', 'fn': 'false_negative', 'tn': 'true_negative'}
    for key in ('tp', 'fp', 'fn', 'tn', 'precision', 'recall', 'f1'):
        other = retained.get(key, retained.get(aliases.get(key)))
        require(other is not None and math.isclose(calculated[key], other, rel_tol=0, abs_tol=1e-12),
                f'Retained metric mismatch: {key}')
    if 'mae_w_m2' in retained:
        require(math.isclose(calculated['mae_w_m2'], retained['mae_w_m2'], rel_tol=0, abs_tol=1e-9),
                'Retained radiation error mismatch')


def prepare(root=ROOT):
    root = Path(root)
    report_path = HANDOFF / 'comparison-reviewed.json'
    manifest_path = HANDOFF / 'inputs/manifest.json'
    report = json.loads((root / report_path).read_text())
    manifest = json.loads((root / manifest_path).read_text())
    calibration = json.loads((root / CALIBRATION).read_text())
    feature_manifest = json.loads((root / FEATURE_MANIFEST).read_text())
    require(feature_manifest['git_commit'] == manifest['git_commit'], 'v2 feature snapshot differs')
    require(digest(root / FEATURES) == feature_manifest['files'][FEATURES.name] ==
            'bce5dc92e2bc7c99b40c2fea4987ac0c08a7d23a3128b57ea4655c3e5f06c515', 'v2 feature source hash mismatch')
    require(feature_manifest['original_sources']['eval/cv_predictions_v2.csv']['sha256'] ==
            manifest['files']['eval/cv_predictions_v2.csv']['sha256'], 'v2 feature prediction identity mismatch')
    source_records = []
    for name, relative in SOURCES.items():
        actual_hash = digest(root / relative)
        require(actual_hash == report['input_files'][name]['sha256'], f'{relative}: source hash mismatch')
        if str(relative) in calibration['sources']['files']:
            require(actual_hash == calibration['sources']['files'][str(relative)], f'{relative}: calibration hash mismatch')
        source_records.append({'path': str(relative), 'sha256': actual_hash})
    for retained in manifest['files'].values():
        require(digest(root / retained['local']) == retained['sha256'], 'v2 source manifest mismatch')
    require(manifest['files']['eval/cv_predictions_v2.csv']['sha256'] == report['input_files']['incoming']['sha256'],
            'v2 source receipt mismatch')
    for relative in (report_path, manifest_path, CALIBRATION, FEATURES, FEATURE_MANIFEST):
        source_records.append({'path': str(relative), 'sha256': digest(root / relative)})

    audit_path = CORRECTION / 'review/review.json'
    require(digest(root / audit_path) == 'c823b66f6c24b51e076d7d3139bbab41bf83c53fadda944e162bf6a1be6a4f9e',
            'Correction audit hash mismatch')
    require(digest(root / CORRECTION / 'result/completion.json') == '1acb8b4bfb31c9e5882acd4e75a29681bba907c8a35330698ed1ac33f788cc02',
            'Correction completion hash mismatch')
    audit = json.loads((root / audit_path).read_text())
    completion = json.loads((root / CORRECTION / 'result/completion.json').read_text())
    lock = json.loads((root / CORRECTION / 'lock.json').read_text())
    correction = json.loads((root / CORRECTION / 'result/summary.json').read_text())
    freeze = json.loads((root / CORRECTION / 'result/decision-freeze.json').read_text())
    base_freeze = json.loads((root / BASE / 'policy-freeze.json').read_text())
    require(audit['status'] == 'PASS' and completion['status'] == correction['status'] == 'completed',
            'Event correction has not passed its audit')
    require(digest(root / CORRECTION / 'lock.json') == audit['lock_sha256'] ==
            '6980b53364ae337cb9926549f7081e9c829bb629f83272b39c07ed538c8d6330', 'Event correction lock mismatch')
    for name in ('summary.json', 'validation-decisions.csv', 'decision-freeze.json', 'head-freeze.json',
                 'expanded-final.json', 'day-bootstrap.json'):
        relative = CORRECTION / 'result' / name
        require(digest(root / relative) == completion['output_sha256'][name], f'{relative}: correction hash mismatch')
        source_records.append({'path': str(relative), 'sha256': digest(root / relative)})
    require(digest(root / CORRECTION / 'result/validation-decisions.csv') == freeze['validation_decisions_sha256'],
            'Correction decisions differ from pre-scoring freeze')
    for name in ('validation-decisions.csv', 'final-base.txt', 'policy-freeze.json'):
        relative = BASE / name
        require(digest(root / relative) == lock['source_sha256'][str(relative)], f'{relative}: base source hash mismatch')
        if name != 'policy-freeze.json':
            require(digest(root / relative) == base_freeze['frozen_prediction_files_sha256'][name], 'Base prediction freeze mismatch')
        source_records.append({'path': str(relative), 'sha256': digest(root / relative)})
    for relative in (audit_path, CORRECTION / 'lock.json', CORRECTION / 'result/completion.json'):
        source_records.append({'path': str(relative), 'sha256': digest(root / relative)})
    cutoff_019 = correction['selected_training_thresholds']['expanded']['threshold']
    require(cutoff_019 == audit['thresholds']['expanded'] == .49, 'Unexpected event correction threshold')

    selection = json.loads((root / SOURCES['classifier_policy']).read_text())
    require(selection['selected_augmented_arm'] == 'consensus_two_source', 'Unexpected research comparator')
    policy = selection['policies']['consensus_two_source']['policy']
    require(policy == {'kind': 'correction', 'lower': 0.5, 'upper': 0.6}, 'Changed research event policy')
    threshold = calibration['selected']['threshold_w_m2']
    require(threshold == 562 and calibration['original_threshold']['threshold_w_m2'] == 600,
            'Unexpected retained v2 thresholds')
    v2 = load_rows(root / SOURCES['incoming'], 'time')
    v1 = load_rows(root / SOURCES['retained_original'], 'time')
    weather = load_rows(root / SOURCES['retained_raw_control'], 'feature_time')
    research = load_rows(root / SOURCES['classifier'], 'feature_time')
    features = load_rows(root / FEATURES, 'time')
    corrected = load_rows(root / CORRECTION / 'result/validation-decisions.csv', 'origin')
    base = load_rows(root / BASE / 'validation-decisions.csv', 'origin')
    origins = sorted(v2)
    require(all(set(rows) == set(v2) for rows in (v1, weather, research, features, corrected, base)), 'Validation timestamp sets differ')
    require(origins[0] == '2025-12-04 19:00:00' and origins[-1] == '2026-05-02 08:00:00',
            'Unexpected validation boundaries')
    days = {}
    rows = []
    previous = None
    for origin in origins:
        moment = datetime.fromisoformat(origin)
        require(previous is None or moment - previous == timedelta(hours=1), 'Validation hourly gap')
        previous = moment
        target = (moment + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        incoming, original, raw, event = v2[origin], v1[origin], weather[origin], research[origin]
        require(raw['target_time'] == event['target_time'] == target, 'Target timestamp mismatch')
        actual = number(incoming['actual'])
        require(actual == number(original['actual']) == number(raw['actual_w_m2']) == number(event['weather_actual_w_m2']),
                'Actual radiation differs across sources')
        require(number(incoming['baseline']) == number(original['baseline']), 'Persistence values differ')
        require(number(incoming['forecast']) == number(features[origin]['nwp_radiation']), 'v2 weather feature differs from supplied forecast')
        cloud = number(features[origin]['nwp_cloud'])
        require(0 <= cloud <= 100, 'Cloud-cover input outside percent range')
        archived = number(raw['point_w_m2'])
        probability = number(event['probability'])
        require(0 <= probability <= 1, 'Research probability out of range')
        require(bit(event['nwp_positive']) == (archived > 600), 'Research weather control mismatch')
        expected = probability > (policy['lower'] if archived > 600 else policy['upper'])
        require(bit(event['predicted_positive']) == expected, 'Research call differs from frozen policy')
        refit = number(corrected[origin]['base_prediction'])
        require(math.isclose(refit, number(base[origin]['base_prediction']), rel_tol=0, abs_tol=1e-12),
                'Correction curve differs from its frozen v2 refit')
        corrected_probability = number(corrected[origin]['expanded_probability'])
        require(0 <= corrected_probability <= 1, 'Correction probability out of range')
        corrected_call = bit(corrected[origin]['expanded_call'])
        require(corrected_call == (corrected_probability > cutoff_019), 'Correction call differs from frozen threshold')
        row = {'time': target, 'hour': int(target[11:13]), 'actual': actual,
               'v2': number(incoming['predicted']), 'raw_v2': number(incoming['forecast']),
               'v2_refit': refit, 'event_019': corrected_call,
               'v1': number(original['predicted']), 'persistence': number(incoming['baseline']),
               'ecmwf_day2': archived, 'event_008': bit(event['predicted_positive']), 'nwp_cloud': cloud}
        rows.append(row)
        days.setdefault(target[:10], []).append(row)

    actual = [row['actual'] for row in rows]
    methods = [
        ('v2_600', 'Stefanos v2', 'v2', 600, 'Original threshold', 'incoming'),
        ('v2_562', 'Stefanos v2, tuned threshold', 'v2', threshold, 'Threshold selected on this validation period', None),
        ('v1', 'Stefanos v1', 'v1', 600, 'Original forecast', 'retained_original'),
        ('persistence', 'Previous day', 'persistence', 600, 'Same hour on the previous day', 'persistence'),
        ('raw_v2', 'Supplied weather, day 1', 'raw_v2', 600, 'v2 CSV forecast column, weather model unpinned', 'supplied_raw_forecast'),
        ('ecmwf_day2', 'ECMWF, day 2', 'ecmwf_day2', 600, 'Separate model-pinned archive', 'retained_raw_forecast'),
        ('event_008', 'Two-source event model', None, None, 'Separate research comparator, f1-008/consensus_two_source', 'f1_008_consensus_two_source'),
        ('event_019', 'V2 + event correction', 'v2_refit', cutoff_019, '019 expanded, prototype validation', None),
    ]
    metrics = []
    for key, label, field, cutoff, note, report_key in methods:
        points = [row[field] for row in rows] if field else None
        calls = [row[key] for row in rows] if key in ('event_008', 'event_019') else [value > cutoff for value in points]
        result = scores(actual, calls, points)
        if report_key:
            verify_scores(result, report['matched']['metrics'][report_key])
        if key == 'v2_562':
            verify_scores(result, calibration['selected'])
        if key == 'event_019':
            verify_scores(result, correction['metrics']['expanded'])
            verify_scores(result, audit['metrics']['expanded'])
            verify_scores(scores(actual, [value > 600 for value in points], points), correction['metrics']['base_refit'])
        metrics.append(dict(id=key, label=label, threshold=cutoff, note=note, **result))
    verify_scores(metrics[0], calibration['original_threshold'])
    verify_scores(metrics[6], calibration['frozen_classifier'])
    return {
        'schema': 2,
        'coverage': {'hours': len(rows), 'days': len(days), 'first': rows[0]['time'], 'last': rows[-1]['time'],
                     'clock': 'Recovered fixed UTC+03:00 source labels', 'truth_threshold': 600},
        'source': {'branch': manifest['branch'], 'commit': manifest['git_commit'], 'files': source_records,
                   'v2_threshold': threshold, 'research_policy': policy,
                   'correction_threshold': cutoff_019,
                   'upstream_features_sha256': feature_manifest['original_sources']['data/featuresv2.csv']['sha256']},
        'metrics': metrics,
        'days': [{'date': date, 'rows': values} for date, values in days.items()],
    }


def serialize(data):
    return 'window.AKTINA_FORECAST=' + json.dumps(data, separators=(',', ':'), allow_nan=False) + ';\n'


if __name__ == '__main__':
    data = prepare()
    (ROOT / OUTPUT).write_text(serialize(data))
    print(f"Packaged {data['coverage']['hours']} validation hours across {data['coverage']['days']} dates")
