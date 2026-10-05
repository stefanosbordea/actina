"""Compare supplied forecast versions on declared clocks without fitting or tuning."""
import argparse
import csv
from datetime import datetime, timedelta
import hashlib
import io
import json
import math
from pathlib import Path

from benchmark_predictions import metrics, read_rows

ROOT = Path(__file__).resolve().parents[2]
EVENT_FIELDS = ('hours', 'true_positive', 'false_positive', 'false_negative', 'true_negative', 'precision', 'recall', 'f1')


def snapshot(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return raw.decode('utf-8-sig'), dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def table(text):
    try:
        matrix = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as error:
        raise ValueError('Malformed CSV') from error
    if not matrix or not matrix[0] or len(set(matrix[0])) != len(matrix[0]):
        raise ValueError('Missing or duplicate CSV headers')
    if any(len(row) != len(matrix[0]) for row in matrix[1:]):
        raise ValueError('CSV row has a different field count from its header')
    return matrix


def finite(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError('Radiation must be finite and nonnegative')
    return number


def hour(value):
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is not None or stamp.minute or stamp.second or stamp.microsecond:
        raise ValueError('Use the declared naive hourly source clock without UTC conversion')
    return stamp


class RetainedCSV:
    def __init__(self, text, name):
        self.text, self.name = text, name

    def open(self, newline=''):
        return io.StringIO(self.text, newline=newline)


def predictions(path, basis):
    if basis not in ('feature', 'target'):
        raise ValueError('Declare feature or target timestamp basis explicitly')
    text, identity = snapshot(path)
    matrix = table(text)
    header = matrix[0]
    if header[0] == '':
        header[0] = 'time'
    if header not in (['time', 'actual', 'predicted', 'baseline'], ['time', 'actual', 'predicted', 'baseline', 'forecast']):
        raise ValueError('Expected time,actual,predicted,baseline with optional final forecast column')
    normalized = io.StringIO(newline='')
    writer = csv.writer(normalized)
    writer.writerow(header[:4])
    writer.writerows(row[:4] for row in matrix[1:])
    loaded = read_rows(RetainedCSV(normalized.getvalue(), Path(path).name))
    for row, supplied in zip(loaded, matrix[1:]):
        row['source_time'] = row['feature_time']
        row['target_time'] = str(hour(row['source_time']) + (timedelta(hours=24) if basis == 'feature' else timedelta()))
        if len(header) == 5:
            row['forecast'] = finite(supplied[4])
    identity.update(timestamp_basis=basis, rows=len(loaded), forecast_column=len(header) == 5,
                    target_start=loaded[0]['target_time'], target_end=loaded[-1]['target_time'])
    return {row['target_time']: row for row in loaded}, identity


def score(rows, field):
    if not rows:
        return None
    try:
        result = metrics(rows, field)
    except OverflowError as error:
        raise ValueError('Metric calculation exceeded finite numeric range') from error
    if any(isinstance(v, float) and not math.isfinite(v) for v in result.values()):
        raise ValueError('Metric calculation exceeded finite numeric range')
    return result


def differences(candidate, control):
    values = {name: None if candidate is None or control is None or candidate[name] is None or control[name] is None else candidate[name] - control[name]
              for name in ('precision', 'recall', 'f1')}
    valid = all(value is not None for value in values.values())
    return dict(differences=values, assessable=valid, all_three_nonregressing=valid and all(v >= 0 for v in values.values()),
                any_strict_gain=valid and any(v > 0 for v in values.values()))


def retained_table(path):
    text, identity = snapshot(path)
    matrix = table(text)
    records = [dict(zip(matrix[0], row)) for row in matrix[1:]]
    if not records or not {'feature_time', 'target_time'} <= set(matrix[0]):
        raise ValueError('Retained comparator needs feature_time and target_time')
    by_target = {}
    for row in records:
        feature, target = hour(row['feature_time']), hour(row['target_time'])
        if target != feature + timedelta(hours=24) or str(target) in by_target:
            raise ValueError('Retained comparator has a duplicate or misaligned target')
        by_target[str(target)] = row
    identity['rows'] = len(by_target)
    return by_target, identity


def compare_versions(incoming_path, reference_path, *, model_id, incoming_time_basis, reference_time_basis,
                     raw_control_path=None, classifier_path=None, classifier_policy_path=None):
    if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 200 or any(ord(c) < 32 for c in model_id):
        raise ValueError('Supply a nonempty model identifier of at most 200 characters')
    if bool(classifier_path) != bool(classifier_policy_path) or classifier_path and not raw_control_path:
        raise ValueError('The frozen classifier requires its policy and retained raw-control CSV')
    incoming, incoming_id = predictions(incoming_path, incoming_time_basis)
    reference, reference_id = predictions(reference_path, reference_time_basis)
    shared = sorted(incoming.keys() & reference.keys())
    missing, extra = sorted(reference.keys() - incoming.keys()), sorted(incoming.keys() - reference.keys())
    sources = dict(incoming=incoming_id, retained_original=reference_id)
    for target in shared:
        for name in ('actual', 'baseline'):
            if incoming[target][name] != reference[target][name]:
                raise ValueError(f'Conflicting {name} on shared target {target}')
    matched = [dict(actual=reference[t]['actual'], predicted=incoming[t]['predicted'], original=reference[t]['predicted'],
                    baseline=reference[t]['baseline'], **({'forecast': incoming[t]['forecast']} if incoming_id['forecast_column'] else {})) for t in shared]
    retained_raw = None
    changed_raw = []
    if raw_control_path:
        retained_raw, sources['retained_raw_control'] = retained_table(raw_control_path)
        if not set(reference) <= set(retained_raw):
            raise ValueError('Retained raw control is missing original target hours')
        for target in reference:
            if finite(retained_raw[target]['actual_w_m2']) != reference[target]['actual']:
                raise ValueError('Retained raw control has conflicting actual values')
            finite(retained_raw[target]['point_w_m2'])
        for target, row in zip(shared, matched):
            row['retained_raw'] = finite(retained_raw[target]['point_w_m2'])
            if incoming_id['forecast_column'] and row['forecast'] != row['retained_raw']:
                changed_raw.append(target)
    scores = dict(incoming=score(matched, 'predicted'), retained_original=score(matched, 'original'), persistence=score(matched, 'baseline'))
    if incoming_id['forecast_column']:
        scores['supplied_raw_forecast'] = score(matched, 'forecast')
    if retained_raw is not None:
        scores['retained_raw_forecast'] = score(matched, 'retained_raw')
    classifier_description = None
    if classifier_path:
        classifier, sources['classifier'] = retained_table(classifier_path)
        policy_text, sources['classifier_policy'] = snapshot(classifier_policy_path)
        selection = json.loads(policy_text)
        arm = selection['selected_augmented_arm']
        if arm != 'consensus_two_source':
            raise ValueError('Expected the frozen 008 consensus_two_source comparator, not a new selected arm')
        policy = selection['policies'][arm]['policy']
        if policy != {'kind': 'correction', 'lower': 0.5, 'upper': 0.6}:
            raise ValueError('Expected the unchanged frozen 008 correction policy at 0.50 and 0.60')
        if not set(reference) <= set(classifier):
            raise ValueError('Frozen classifier is missing original target hours')
        calls = {}
        for target in reference:
            row = classifier[target]
            probability = float(row['probability'])
            if not math.isfinite(probability) or not 0 <= probability <= 1 or row['nwp_positive'] not in ('0', '1') or row['predicted_positive'] not in ('0', '1'):
                raise ValueError('Invalid frozen classifier probability or bit')
            raw = finite(retained_raw[target]['point_w_m2']) > 600
            predicted = probability > policy['lower' if raw else 'upper']
            if (row['nwp_positive'] == '1') != raw or (row['predicted_positive'] == '1') != predicted or finite(row['weather_actual_w_m2']) != reference[target]['actual']:
                raise ValueError('Frozen classifier truth, raw bit or selected policy disagrees')
            calls[target] = predicted
        # Numeric surrogates encode saved bits only. Never expose regression errors for them.
        binary = score([dict(actual=reference[t]['actual'], predicted=601. if calls[t] else 0.) for t in shared], 'predicted')
        scores['f1_008_consensus_two_source'] = None if binary is None else {key: binary[key] for key in EVENT_FIELDS}
        classifier_description = dict(model_id='f1-008/consensus_two_source', policy=policy,
            role='Previously selected two-source event correction. Validation-tuned comparator, not an untouched validation estimate.')
    full_rows = list(incoming.values())
    same = not missing and not extra
    return dict(schema=1, kind='prediction_version_comparison', model_id=model_id.strip(), input_files=sources,
        evaluator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        benchmark_evaluator_sha256=hashlib.sha256((Path(__file__).parent / 'benchmark_predictions.py').read_bytes()).hexdigest(),
        threshold=dict(w_m2=600, comparison='strictly_greater_than'),
        clock='Naive source hourly labels. Feature labels add exactly 24 hours. Target labels do not shift. No timezone conversion.',
        coverage=dict(incoming_hours=len(incoming), retained_original_hours=len(reference), matched_hours=len(shared), identical_target_set=same,
                      missing_original_target_times=missing, extra_incoming_target_times=extra, matched_target_times=shared),
        incoming_full_period=dict(scope='Every supplied row, using supplied actual and persistence values. Values outside shared retained hours are not independently verified.',
            model=score(full_rows, 'predicted'), persistence=score(full_rows, 'baseline'),
            **({'supplied_raw_forecast': score(full_rows, 'forecast')} if incoming_id['forecast_column'] else {})),
        matched=dict(scope='Identical complete target sets' if same else 'Shared target hours only. This does not establish full original-period superiority.',
                     metrics=scores, comparisons={name: differences(scores['incoming'], value) for name, value in scores.items() if name != 'incoming'}),
        supplied_raw_changed_from_retained_target_times=changed_raw, classifier=classifier_description,
        limits=['No fitting, threshold tuning or arm selection performed.',
                'Prediction files alone do not verify training cutoffs, feature availability or forecast issuance.',
                'Validation may have been used for model selection. Reused historical periods are not fresh holdout evidence.',
                'Radiation-threshold events are not observed grid curtailment or water savings.',
                'ActinaBench format version 2 is unrelated to Stefanos model v2. The supplied model_id identifies this handoff.'])


def write_report(report, output):
    output = Path(output).resolve()
    protected = [base / name for base in (ROOT, ROOT / 'app') for name in ('model', 'data', 'eval')]
    if any(output == path or path in output.parents for path in protected):
        raise ValueError('Output cannot be inside protected model, data or eval directories')
    text = json.dumps(report, indent=2, allow_nan=False) + '\n'
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        stream.write(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--incoming', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--model-id', required=True)
    parser.add_argument('--incoming-time-basis', choices=('feature', 'target'), required=True)
    parser.add_argument('--reference-time-basis', choices=('feature', 'target'), required=True)
    parser.add_argument('--raw-control', type=Path)
    parser.add_argument('--classifier', type=Path)
    parser.add_argument('--classifier-policy', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare_versions(args.incoming, args.reference, model_id=args.model_id,
        incoming_time_basis=args.incoming_time_basis, reference_time_basis=args.reference_time_basis,
        raw_control_path=args.raw_control, classifier_path=args.classifier, classifier_policy_path=args.classifier_policy)
    write_report(result, args.output)
    print(f"Saved {result['model_id']} comparison on {result['coverage']['matched_hours']} shared hours")


if __name__ == '__main__':
    main()
