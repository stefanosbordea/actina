"""Package fixed benchmark results for the offline website."""
import json
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
    for name, value in [('benchmark-results', original), ('experiment-results', report)]:
        (site / (name + '.json')).write_text(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n')
    summary = dict(original, splits=[{k: v for k, v in split.items() if k not in
                   ('daily', 'largest_model_regressions', 'largest_model_improvements')} for split in original['splits']])
    (site / 'benchmark-data.js').write_text('window.ACTINABENCH=' + json.dumps(
        {'original': summary, 'experiment': report}, separators=(',', ':'), allow_nan=False) + ';\n')
    shutil.copyfile(experiment / 'RESULTS.csv', site / 'experiment-results.csv')
    shutil.copyfile(APP / 'handoff/original-model-inspection/feature-importance.csv', site / 'feature-importance.csv')
    (site / 'figures').mkdir(exist_ok=True)
    for source, destination in [('test-classification.svg', 'test-classification.svg'),
                                ('monthly-forecast-error.svg', 'monthly-error.svg'),
                                ('hourly-forecast-error.svg', 'hourly-error.svg')]:
        shutil.copyfile(experiment / source, site / 'figures' / destination)

if __name__ == '__main__':
    main()
