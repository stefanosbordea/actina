"""ActinaBench: compare retained forecasts without training or scheduling."""
import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THRESHOLD = 600.0


def metrics(rows, field):
    if not rows:
        raise ValueError('A comparison requires at least one paired row')
    actual = [r['actual'] for r in rows]
    predicted = [r[field] for r in rows]
    residual = [p - a for a, p in zip(actual, predicted)]
    tp = sum(a > THRESHOLD and p > THRESHOLD for a, p in zip(actual, predicted))
    fp = sum(a <= THRESHOLD < p for a, p in zip(actual, predicted))
    fn = sum(p <= THRESHOLD < a for a, p in zip(actual, predicted))
    tn = len(rows) - tp - fp - fn
    return {
        'hours': len(rows),
        'mae_w_m2': math.fsum(map(abs, residual)) / len(rows),
        'rmse_w_m2': math.sqrt(math.fsum(e * e for e in residual) / len(rows)),
        'bias_w_m2': math.fsum(residual) / len(rows),
        'true_positive': tp, 'false_positive': fp, 'false_negative': fn, 'true_negative': tn,
        'precision': tp / (tp + fp) if tp + fp else None,
        'recall': tp / (tp + fn) if tp + fn else None,
        'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
    }


def read_rows(path):
    rows = []
    with path.open(newline='') as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ['time', 'actual', 'predicted', 'baseline']:
            raise ValueError(f'Unexpected columns: {path.name}')
        previous = None
        for line, row in enumerate(reader, 2):
            stamp = datetime.fromisoformat(row['time'])
            if stamp.tzinfo is not None or stamp.minute or stamp.second or stamp.microsecond:
                raise ValueError(f'Expected local hourly label at {path.name}:{line}')
            if previous is not None and stamp - previous != timedelta(hours=1):
                raise ValueError(f'Nonconsecutive or repeated hour at {path.name}:{line}')
            previous = stamp
            values = {key: float(row[key]) for key in ('actual', 'predicted', 'baseline')}
            if not all(math.isfinite(x) and x >= 0 for x in values.values()):
                raise ValueError(f'Invalid radiation value at {path.name}:{line}')
            rows.append({'feature_time': stamp.isoformat(' '),
                         'target_time': (stamp + timedelta(hours=24)).isoformat(' '), **values})
    if not rows:
        raise ValueError(f'No predictions in {path.name}')
    return rows


def compare(rows):
    model, baseline = metrics(rows, 'predicted'), metrics(rows, 'baseline')
    return {'model': model, 'persistence': baseline,
            'model_minus_persistence_mae_w_m2': model['mae_w_m2'] - baseline['mae_w_m2'],
            'model_mae_reduction_percent': 100 * (1 - model['mae_w_m2'] / baseline['mae_w_m2']) if baseline['mae_w_m2'] else None}


def benchmark(root=ROOT):
    source = {}
    reports = []
    for filename, split in [('cv_predictions.csv', 'validation'), ('test_predictions.csv', 'test')]:
        path = root / 'eval' / filename
        source[f'eval/{filename}'] = hashlib.sha256(path.read_bytes()).hexdigest()
        rows = read_rows(path)
        months, days, hours = defaultdict(list), defaultdict(list), defaultdict(list)
        for row in rows:
            months[row['target_time'][:7]].append(row)
            days[row['target_time'][:10]].append(row)
            hours[row['target_time'][11:13]].append(row)
        daily = []
        for date, group in sorted(days.items()):
            daily.append({'date': date, 'complete_24_hour_day': len(group) == 24, **compare(group)})
        full_days = [day for day in daily if day['complete_24_hour_day']]
        reports.append({
            'split': split, 'file': f'eval/{filename}',
            'target_start': rows[0]['target_time'], 'target_end': rows[-1]['target_time'],
            **compare(rows),
            'monthly': [{'month': month, **compare(group)} for month, group in sorted(months.items())],
            'hourly': [{'hour': hour, **compare(group)} for hour, group in sorted(hours.items())],
            'daily': daily,
            'largest_model_regressions': sorted(full_days, key=lambda day: (-day['model_minus_persistence_mae_w_m2'], day['date']))[:10],
            'largest_model_improvements': sorted(full_days, key=lambda day: (day['model_minus_persistence_mae_w_m2'], day['date']))[:10],
        })
    return {
        'benchmark': 'ActinaBench', 'version': 2,
        'definition': {
            'scope': 'Paired evaluation of every retained row in each original split; no fitting, parameter search or scheduler execution.',
            'positive_class': 'Actual radiation strictly greater than 600 W/m²',
            'positive_prediction': 'Predicted radiation strictly greater than 600 W/m²',
            'threshold_w_m2': THRESHOLD,
            'time_basis': 'Prediction CSV labels identify feature time; target labels shift +24 hours as in the supplied scheduler. Naive local wall-clock labels are preserved, not converted to UTC.',
            'undefined_metrics': 'null when a precision, recall or F1 denominator is zero',
            'validation_limit': 'Validation data was used for early stopping. Its performance is not an untouched test estimate.',
            'test_limit': 'A retained historical seasonal test, not prospective field validation. Future changes selected using these outcomes need a new holdout before a new generalization claim.',
            'interpretation': 'F1 scores radiation-threshold detection, not grid curtailment, water service, operating savings or safety.',
            'daily_selection': 'Every day is reported. Ranked diagnostic examples use complete 24-row days only and do not replace split-level comparisons.',
        },
        'input_sha256': source,
        'evaluator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'splits': reports,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = benchmark()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as output:
        json.dump(result, output, indent=2, allow_nan=False)
        output.write('\n')
    for report in result['splits']:
        m, b = report['model'], report['persistence']
        print(f"{report['split']}: {m['hours']} hours; MAE {m['mae_w_m2']:.4f} vs {b['mae_w_m2']:.4f}; F1 {m['f1']:.4f} vs {b['f1']:.4f}")


if __name__ == '__main__':
    main()
