"""Freeze a supplied v2 event threshold using validation only."""
import csv
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'app/tools'))
from benchmark_predictions import metrics
from compare_prediction_versions import predictions, retained_table

GRID = tuple(range(500, 651))


def event_counts(actual, calls):
    if len(actual) != len(calls) or not actual:
        raise ValueError('Require nonempty paired truth and event calls')
    tp = sum(a and p for a, p in zip(actual, calls))
    fp = sum(not a and p for a, p in zip(actual, calls))
    fn = sum(a and not p for a, p in zip(actual, calls))
    tn = len(actual) - tp - fp - fn
    return dict(tp=tp, fp=fp, fn=fn, tn=tn)


def fractions(counts):
    tp, fp, fn = (counts[k] for k in ('tp', 'fp', 'fn'))
    return dict(precision=Fraction(tp, tp + fp) if tp + fp else None,
                recall=Fraction(tp, tp + fn) if tp + fn else None,
                f1=Fraction(2 * tp, 2 * tp + fp + fn) if 2 * tp + fp + fn else None)


def display(counts):
    exact = fractions(counts)
    return dict(counts, **{name: None if value is None else float(value) for name, value in exact.items()},
                f1_exact=None if exact['f1'] is None else str(exact['f1']))


def scan(actual, predicted):
    truth = [value > 600 for value in actual]
    return [dict(threshold_w_m2=threshold, **display(event_counts(truth, [p > threshold for p in predicted])))
            for threshold in GRID]


def select(candidates):
    valid = [row for row in candidates if row['f1_exact'] is not None]
    if not valid:
        raise ValueError('No defined F1 in validation grid')
    return max(valid, key=lambda row: (Fraction(row['f1_exact']), -abs(row['threshold_w_m2'] - 600), row['threshold_w_m2']))


def frozen_sources():
    protocol = HERE / 'PROTOCOL.md'
    text = protocol.read_text()
    pins = json.loads(text.split('```json\n', 1)[1].split('```', 1)[0])
    for name, expected in pins.items():
        actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f'Frozen source changed: {name}')
    return dict(files=pins, protocol_sha256=hashlib.sha256(protocol.read_bytes()).hexdigest())


def run():
    outputs = [HERE / 'validation-selection.json', HERE / 'validation-table.csv']
    if any(path.exists() for path in outputs):
        raise FileExistsError('Preserve existing calibration artifacts')
    started = datetime.now(timezone.utc).isoformat()
    sources = frozen_sources()
    incoming, identity = predictions(ROOT / 'app/handoff/v2-validation-2026-10-04/inputs/cv_predictions_v2.csv', 'feature')
    original, _ = predictions(ROOT / 'eval/cv_predictions.csv', 'feature')
    saved, _ = retained_table(ROOT / 'app/experiments/f1-008/result/predictions/validation-consensus_two_source.csv')
    if set(incoming) != set(original) or set(incoming) != set(saved):
        raise ValueError('Validation comparison requires identical full target sets')
    times = sorted(incoming)
    for target in times:
        if incoming[target]['actual'] != original[target]['actual'] or incoming[target]['baseline'] != original[target]['baseline']:
            raise ValueError('Supplied truth or persistence differs from retained original')
        if float(saved[target]['weather_actual_w_m2']) != incoming[target]['actual'] or saved[target]['predicted_positive'] not in ('0', '1'):
            raise ValueError('Saved classifier truth or event bit is invalid')
    rows = [incoming[target] for target in times]
    actual = [row['actual'] for row in rows]
    predicted = [row['predicted'] for row in rows]
    classifier = display(event_counts([a > 600 for a in actual], [saved[t]['predicted_positive'] == '1' for t in times]))
    if Fraction(classifier['f1_exact']) != Fraction(542, 598):
        raise ValueError('Frozen 008 validation F1 no longer reproduces 0.9063545150501672')
    regression = metrics(rows, 'predicted')
    candidates = scan(actual, predicted)
    for row in candidates:
        row['mae_w_m2_unchanged'] = regression['mae_w_m2']
    best = select(candidates)
    gap = Fraction(best['f1_exact']) - Fraction(classifier['f1_exact'])
    selection = dict(schema=1, purpose='Validation-only supplied v2 event threshold tuning',
        model_id='Stefanos nwp-features model v2', sources=sources, incoming=identity,
        command=sys.argv, started_at_utc=started, completed_at_utc=datetime.now(timezone.utc).isoformat(),
        truth_rule='actual > 600 W/m²', prediction_rule='predicted > selected threshold W/m²',
        grid=dict(start=500, stop=650, step=1, candidates=151),
        tie_rule='Highest exact F1, then closest to 600, then higher threshold',
        validation_hours=len(rows), target_start=times[0], target_end=times[-1],
        selected=best, original_threshold=next(row for row in candidates if row['threshold_w_m2'] == 600),
        frozen_classifier=dict(model_id='f1-008/consensus_two_source', **classifier),
        comparison_with_008=dict(v2_minus_classifier_f1=float(gap), v2_minus_classifier_f1_exact=str(gap)),
        demo_status='Unchanged. This calibration does not select or modify the team demo.',
        regression_unchanged={key: regression[key] for key in ('mae_w_m2', 'rmse_w_m2', 'bias_w_m2')},
        limits=['No model training or test-file reading occurred.',
                'This selects an event threshold on reused validation, not a fresh holdout result.',
                'The radiation curve is unchanged. Event tuning does not improve its MAE.',
                'ActinaBench format v2 is separate from Stefanos model v2.'])
    with outputs[1].open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(candidates[0]))
        writer.writeheader()
        writer.writerows(candidates)
    selection['validation_table_sha256'] = hashlib.sha256(outputs[1].read_bytes()).hexdigest()
    with outputs[0].open('x') as stream:
        json.dump(selection, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(selected=best, classifier=classifier, comparison=selection['comparison_with_008'],
                          demo_status=selection['demo_status']), indent=2))


if __name__ == '__main__':
    run()
