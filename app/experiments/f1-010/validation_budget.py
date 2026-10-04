"""Validation-only hindsight ceiling, never a candidate or selection input."""
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
source = HERE / 'result/predictions/validation-full.csv'
days = defaultdict(list)
for row in csv.DictReader(source.open()): days[row['target_time'][:10]].append(row)
if len(days) != 150 or any(len(rows) != 24 or len({r['target_time'] for r in rows}) != 24 for rows in days.values()):
    raise ValueError('Changed complete validation-day membership')
result = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'scope': 'Validation-only hindsight ceiling. No training, candidate or threshold selection uses this diagnostic.', 'references': {}}
for name, key in [('weather_complete_days', 'weather_actual_w_m2'), ('satellite_complete_available_days', 'satellite_w_m2')]:
    values = []
    for rows in days.values():
        if any(row[key] == '' for row in rows): continue
        k = sum(int(row['nwp_positive']) for row in rows)
        p = sum(float(row[key]) > 600 for row in rows)
        tp = sum(int(row['nwp_positive']) and float(row[key]) > 600 for row in rows)
        values.append((k, p, tp))
    tp = sum(v[2] for v in values)
    fp, fn = (sum(v[i] - v[2] for v in values) for i in (0, 1))
    swappable = sum(k > t and p > t for k, p, t in values)
    result['references'][name] = dict(complete_days=len(values), hours=24 * len(values), positive_calls=tp + fp,
        positive_truth=tp + fn, tp=tp, fp=fp, fn=fn, days_with_both_false_alarm_and_miss=swappable,
        maximum_tp_with_one_perfect_pair_per_day=tp + swappable,
        maximum_tp_with_arbitrary_count_preserving_reordering=sum(min(k, p) for k, p, t in values),
        unavoidable_fn_from_daily_count_budget=sum(max(0, p-k) for k, p, t in values))
(HERE / 'validation-budget-diagnostic.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
