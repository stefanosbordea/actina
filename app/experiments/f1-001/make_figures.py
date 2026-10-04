"""Rebuild result tables and three figures from retained predictions; never train."""
import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = HERE / 'result-retry1'
NAMES = {
    'persistence': 'Persistence, fixed 600',
    'calibrated_persistence': 'Persistence, cutoff 590',
    'purged_regression': 'Purged regression',
    'direct_classifier': 'Direct classifier',
    'history_classifier': 'History classifier',
    'deep_classifier': 'Neural classifier',
    'original_model': 'Original model',
}


def read_csv(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def errors(actual, prediction):
    residuals = [p - a for a, p in zip(actual, prediction)]
    return {'mae_w_m2': sum(map(abs, residuals)) / len(residuals),
            'rmse_w_m2': math.sqrt(sum(e * e for e in residuals) / len(residuals))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true', help='Also save PNGs for visual inspection')
    args = parser.parse_args()
    report = json.loads((RUN / 'report.json').read_text())
    audit = json.loads((HERE / 'independent-audit.json').read_text())
    if audit['status'] != 'PASS':
        raise ValueError('Independent audit has not passed')
    identities = {ROOT / name: digest for name, digest in report['input_sha256'].items()}
    identities.update({HERE / name: digest for name, digest in audit['prediction_sha256'].items()})
    identities[RUN / 'report.json'] = audit['reported_result_sha256']
    for path, digest in identities.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Input changed: {path}')
    records, breakdown = [], []
    for stage, filename in [('validation', 'cv_predictions.csv'), ('test', 'test_predictions.csv')]:
        original = read_csv(ROOT / 'eval' / filename)
        target_times = [datetime.fromisoformat(row['time']) + timedelta(hours=24) for row in original]
        actual = [float(row['actual']) for row in original]
        for method in [*report['methods'], 'original_model']:
            if method == 'original_model':
                metrics = audit['original_model_reference'][stage]['overall']
                default = metrics
                cutoff = 600
                prediction = [float(row['predicted']) for row in original]
            else:
                metrics = audit['recomputed_results'][stage][method]
                default = report['methods'][method][stage]['default']
                cutoff = metrics['cutoff']
                prediction = [float(row['score']) for row in read_csv(RUN / 'predictions' / f'{stage}-{method}.csv')]
            probability = method.endswith('classifier')
            records.append({
                'split': stage, 'method': method, 'hours': metrics['hours'],
                'target_start': str(target_times[0]), 'target_end': str(target_times[-1]),
                'selected_on_validation': method == report['selected_on_validation'],
                'cutoff': cutoff, 'score_unit': 'probability' if probability else 'W/m2',
                **{key: metrics[key] for key in ('f1', 'precision', 'recall', 'tp', 'fp', 'fn', 'tn')},
                **{f'default_{key}': default[key] for key in ('f1', 'precision', 'recall')},
                **({'mae_w_m2': None, 'rmse_w_m2': None} if probability else errors(actual, prediction)),
            })
        for grouping in ('month', 'hour'):
            groups = defaultdict(list)
            for index, target in enumerate(target_times):
                groups[target.strftime('%Y-%m') if grouping == 'month' else f'{target.hour:02d}'].append(index)
            for value, indices in sorted(groups.items()):
                for method, field in [('original_model', 'predicted'), ('persistence', 'baseline')]:
                    breakdown.append({'split': stage, 'grouping': grouping, 'value': value,
                        'method': method, 'hours': len(indices),
                        **errors([actual[i] for i in indices], [float(original[i][field]) for i in indices])})
    write_csv(HERE / 'RESULTS.csv', records)
    write_csv(HERE / 'forecast-breakdown.csv', breakdown)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'text.color': '#202934',
        'axes.labelcolor': '#465363', 'xtick.color': '#556170', 'ytick.color': '#344150',
        'axes.spines.top': False, 'axes.spines.right': False, 'axes.spines.left': False,
        'axes.edgecolor': '#c6ccd3', 'axes.titleweight': 'normal', 'svg.fonttype': 'none',
        'svg.hashsalt': 'actinabench-f1-001', 'savefig.facecolor': 'white'})

    def save(fig, name, title):
        fig.savefig(HERE / f'{name}.svg', metadata={'Date': None, 'Title': title,
            'Description': 'Retrospective original-split comparison. Sources and reproduction in README.md.'})
        if args.preview:
            fig.savefig(HERE / f'{name}.preview.png', dpi=150)
        plt.close(fig)

    test = {row['method']: row for row in records if row['split'] == 'test'}
    order = ['persistence', 'original_model', 'calibrated_persistence', 'purged_regression',
             'direct_classifier', 'history_classifier', 'deep_classifier']
    fig, axes = plt.subplots(1, 3, figsize=(11.8, 5.3), sharey=True)
    fig.subplots_adjust(left=.25, right=.91, top=.75, bottom=.17, wspace=.55)
    fig.text(.03, .94, 'Surplus-hour detection', fontsize=18)
    fig.text(.03, .88, 'All 3,567 test hours. Actual radiation > 600 W/m². Higher is better.', color='#556170', fontsize=10)
    for axis, metric, title in zip(axes, ['f1', 'precision', 'recall'], ['F1', 'Precision', 'Recall']):
        axis.set_title(title, loc='left', pad=15, fontsize=12)
        for index, name in enumerate(order):
            value = test[name][metric]
            color = '#176fce' if name == report['selected_on_validation'] else '#59697a'
            axis.scatter(value, index, s=40, color=color, zorder=3)
            axis.text(1.04, index, f'{value:.2%}', transform=axis.get_yaxis_transform(),
                      va='center', color=color, fontsize=9)
        axis.set_xlim(.94, 1)
        axis.set_xticks([.94, .96, .98, 1])
        axis.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        axis.set_yticks(range(len(order)), [NAMES[name] for name in order])
        axis.tick_params(axis='both', length=0, pad=9)
        axis.grid(axis='x', color='#e4e8ec', linewidth=.8)
        axis.set_ylim(len(order) - .5, -.5)
    fig.text(.03, .065, 'Blue: selected on validation. Precision matters more in the roadmap; the selected model loses precision.',
             fontsize=9, color='#556170')
    save(fig, 'test-classification', 'F1, precision and recall for every test method')

    for grouping, name, title in [('month', 'monthly-forecast-error', 'Forecast error by month'),
                                  ('hour', 'hourly-forecast-error', 'Forecast error by hour')]:
        fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.8), sharey=True)
        fig.subplots_adjust(left=.08, right=.97, top=.73, bottom=.20, wspace=.12)
        fig.text(.03, .94, title, fontsize=18)
        fig.text(.03, .88, 'Original model and persistence. Every recorded hour is included; dates refer to the prediction target.',
                 color='#556170', fontsize=10)
        subset = [r for r in breakdown if r['grouping'] == grouping]
        maximum = max(r['mae_w_m2'] for r in subset) * 1.12
        for axis, stage in zip(axes, ['validation', 'test']):
            axis.set_title('Validation period' if stage == 'validation' else 'Original test period', loc='left', fontsize=12, pad=13)
            for method, label, color, style in [('original_model', 'Original model', '#176fce', '-'),
                                               ('persistence', 'Persistence', '#59697a', '--')]:
                values = [r for r in subset if r['split'] == stage and r['method'] == method]
                x = list(range(len(values)))
                axis.plot(x, [r['mae_w_m2'] for r in values], color=color, linestyle=style,
                          marker='o', markersize=3.5, linewidth=1.8, label=label)
            if grouping == 'month':
                labels = [datetime.strptime(r['value'], '%Y-%m').strftime('%b\n%Y') for r in values]
                axis.set_xticks(x, labels, fontsize=9)
            else:
                if [r['value'] for r in values] != [f'{h:02d}' for h in range(24)]:
                    raise ValueError('Missing target hour in figure')
                axis.set_xticks([0, 6, 12, 18, 23], ['00:00', '06:00', '12:00', '18:00', '23:00'], fontsize=9)
                axis.set_xlabel('Target hour, Cyprus local time', fontsize=9, labelpad=12)
            axis.set_ylim(0, maximum)
            axis.grid(axis='y', color='#e4e8ec', linewidth=.8)
            axis.tick_params(axis='both', length=0, pad=8)
        axes[0].set_ylabel('Mean absolute error (W/m²)', labelpad=10)
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc='lower left', bbox_to_anchor=(.075, .01), ncol=2, frameon=False, fontsize=10)
        fig.text(.97, .047, 'Retrospective data. Different original fits across the two splits.', ha='right', fontsize=8.5, color='#556170')
        save(fig, name, title)
    print(f'Wrote {len(records)} result rows, {len(breakdown)} forecast breakdown rows and three SVG figures.')


if __name__ == '__main__':
    main()
