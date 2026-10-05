"""Package fixed benchmark results for the offline website."""
import json
import csv
import hashlib
import shutil
from pathlib import Path

APP = Path(__file__).resolve().parents[1]

def main():
    site = APP / 'site'
    experiment = APP / 'experiments/f1-001'
    original = json.loads((APP / 'handoff/actinabench-v2.json').read_text())
    report = json.loads((experiment / 'result-retry1/report.json').read_text())
    if report['status'] != 'COMPLETE':
        raise ValueError('Only completed experiments can be published')
    research_path = APP / 'experiments/f1-004/result/report.json'
    research = json.loads(research_path.read_text())
    if research['status'] != 'COMPLETE':
        raise ValueError('Research comparison is incomplete')
    comparisons = {}
    for method in ('nwp_day2', 'analogue_raw'):
        comparisons[method] = {}
        for period in ('validation', 'test'):
            scores = research['methods'][method][period]['default']['full']
            baseline = research['methods']['original'][period]['default']['full']
            supplied = next(s['model'] for s in original['splits'] if s['split'] == period)
            if scores['hours'] != supplied['hours'] or any(baseline[k] != supplied[v] for k, v in
                    [('tp', 'true_positive'), ('fp', 'false_positive'), ('fn', 'false_negative'), ('tn', 'true_negative')]):
                raise ValueError('Research comparison does not match original evaluation membership')
            comparisons[method][period] = scores
    research_summary = {'methods': comparisons, 'source_sha256': hashlib.sha256(research_path.read_bytes()).hexdigest(),
                        'scope': 'Retrospective weather-model reference; fixed default rules, no live promotion.'}
    for name, value in [('benchmark-results', original), ('experiment-results', report)]:
        (site / (name + '.json')).write_text(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n')
    summary = dict(original, splits=[{k: v for k, v in split.items() if k not in
                   ('daily', 'largest_model_regressions', 'largest_model_improvements')} for split in original['splits']])
    (site / 'benchmark-data.js').write_text('window.ACTINABENCH=' + json.dumps(
        {'original': summary, 'experiment': report, 'research': research_summary}, separators=(',', ':'), allow_nan=False) + ';\n')
    with (experiment / 'RESULTS.csv').open(newline='') as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    for method, periods in comparisons.items():
        for period, scores in periods.items():
            split = next(s for s in original['splits'] if s['split'] == period)
            rows.append(dict(split=period, method=method, hours=scores['hours'], target_start=split['target_start'],
                target_end=split['target_end'], selected_on_validation='Fixed default',
                cutoff=600 if method == 'nwp_day2' else .5,
                score_unit='W/m2' if method == 'nwp_day2' else 'probability',
                **{k: scores[k] for k in ('f1', 'precision', 'recall', 'tp', 'fp', 'fn', 'tn')},
                **{'default_' + k: scores[k] for k in ('f1', 'precision', 'recall')},
                mae_w_m2=scores['mae'], rmse_w_m2=scores['rmse']))
    with (site / 'experiment-results.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    (site / 'research-results.json').write_text(json.dumps(research_summary, separators=(',', ':'), allow_nan=False) + '\n')
    shutil.copyfile(APP / 'handoff/original-model-inspection/feature-importance.csv', site / 'feature-importance.csv')
    (site / 'figures').mkdir(exist_ok=True)
    for source, destination in [('test-classification.svg', 'test-classification.svg'),
                                ('monthly-forecast-error.svg', 'monthly-error.svg'),
                                ('hourly-forecast-error.svg', 'hourly-error.svg')]:
        shutil.copyfile(experiment / source, site / 'figures' / destination)

if __name__ == '__main__':
    main()
