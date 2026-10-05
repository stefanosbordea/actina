"""Independent joins, soft labels, cumulative threshold oracle and saved-model replay; no fit."""
import csv
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
ROOT = EXP.parents[2]
OUT = EXP / 'result'
OLD = ROOT / 'app/experiments/f1-006/result'
checks = 0


def require(condition, detail):
    global checks
    checks += 1
    if not condition:
        raise AssertionError(detail)


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return list(csv.DictReader(path.open()))
def js(path): return json.loads(path.read_text())
def dt(text): return datetime.fromisoformat(text.replace('Z', '+00:00'))
def val(text): return None if text == '' else float(text)


def metrics(counts, brier=None):
    tp, fp, fn, tn = counts
    return dict(hours=tp+fp+fn+tn, tp=tp, fp=fp, fn=fn, tn=tn,
                precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None,
                f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None, brier=brier)


def counted(rows, cutoff, basis):
    counts = [0, 0, 0, 0]
    errors = []
    for r in rows:
        if basis != 'weather_full' and r['sat'] is None:
            continue
        truth = (r['sat'] if basis == 'satellite_common' else r['weather']) > 600
        positive = r['p'] > cutoff
        counts[{(True, True): 0, (False, True): 1, (True, False): 2, (False, False): 3}[truth, positive]] += 1
        errors.append((r['p'] - truth)**2)
    return metrics(counts, math.fsum(errors)/len(errors))


def same(got, expected, label):
    for k, e in expected.items():
        g = got[k]
        if g == '' or g is None:
            require(e is None, (label, k, g, e))
        elif isinstance(e, float):
            require(math.isclose(float(g), e, rel_tol=0, abs_tol=2e-15), (label, k, g, e))
        else:
            require(int(g) == e, (label, k, g, e))


def exact(m, key):
    a, b = {'precision': (m['tp'], m['tp']+m['fp']), 'recall': (m['tp'], m['tp']+m['fn']),
            'f1': (2*m['tp'], 2*m['tp']+m['fp']+m['fn'])}[key]
    return Fraction(a, b) if b else Fraction(-1)


def eligible(candidate, control):
    return all(exact(candidate[b], k) >= 0 and exact(control[b], k) >= 0
               and exact(candidate[b], k) >= exact(control[b], k)
               for b in control for k in ('precision', 'recall', 'f1'))


def rank(metrics_):
    f = [exact(m, 'f1') for m in metrics_.values()]
    return (min(f), sum(f)/2, min(exact(m, 'precision') for m in metrics_.values()),
            min(exact(m, 'recall') for m in metrics_.values()))


def threshold_oracle(rows):
    # Sweep upward, removing all ties before measuring a strict p>cutoff decision.
    counts = {}
    for basis in ('weather_full', 'satellite_common'):
        ref = [r for r in rows if basis == 'weather_full' or r['sat'] is not None]
        positives = sum((r['weather'] if basis == 'weather_full' else r['sat']) > 600 for r in ref)
        counts[basis] = [positives, len(ref)-positives, 0, 0]
    by_probability = defaultdict(list)
    for r in rows:
        by_probability[r['p']].append(r)
    result = []
    for cut in sorted({0., 1., *by_probability}):
        for r in by_probability[cut]:
            for basis in counts:
                if basis == 'satellite_common' and r['sat'] is None:
                    continue
                truth = (r['weather'] if basis == 'weather_full' else r['sat']) > 600
                counts[basis][0 if truth else 1] -= 1
                counts[basis][2 if truth else 3] += 1
        result.append({'cutoff': cut, 'metrics': {b: metrics(c) for b, c in counts.items()}})
    return result


def main():
    report = js(OUT/'report.json')
    selection = js(OUT/'validation-selection.json')
    pins = js(EXP/'inputs.json')
    before = {str(p): sha(p) for p in [EXP/'PROTOCOL.md', EXP/'run.py', EXP/'inputs.json', OUT/'report.json',
                                      *[ROOT/name for name in pins], *[OUT/name for name in report['outputs_sha256']]]}
    require(report['status'] == 'COMPLETE', 'incomplete run')
    require(sha(EXP/'PROTOCOL.md') == 'f6950483c4bc3864c4a902d9b1e230681011c634d02bd7474c025cec4aa461fc', 'protocol')
    require(sha(EXP/'run.py') == report['code_sha256'] == selection['code_sha256'], 'runner identity')
    require(sha(OUT/'validation-selection.json') == report['selection_sha256'], 'selection identity')
    require(sha(EXP/'inputs.json') == selection['input_manifest_sha256'], 'input lock identity')
    for name, identity in pins.items(): require(sha(ROOT/name) == identity, name)
    for name, identity in report['outputs_sha256'].items(): require(sha(OUT/name) == identity, name)
    require(dt(report['started_at_utc']) <= dt(selection['frozen_at_utc']) <= dt(report['completed_at_utc']), 'selection time')
    feature_rows = read(ROOT/'data/features.csv')
    feature_key = next(iter(feature_rows[0]))
    original = {r[feature_key]: r for r in feature_rows}
    satellite_rows = read(ROOT/'app/experiments/satellite-reference-001/result/reference-full.csv')
    satellite = {dt(r['valid_time_utc']): val(r['shortwave_radiation_w_m2']) for r in satellite_rows}
    require(len(satellite) == len(satellite_rows), 'duplicate reference keys')
    train_audit, all_rows, best = {}, {}, {}
    metric_count = grid_count = prediction_count = label_count = 0
    comparison = {(r['split'], r['method'], r['mode'], r['basis']): r for r in read(OUT/'comparison.csv')}
    require(len(comparison) == len(read(OUT/'comparison.csv')), 'duplicate comparison rows')
    for stage, filename, n in [('validation', 'cv_predictions.csv', 3566), ('test', 'test_predictions.csv', 3567)]:
        split = read(ROOT/'eval'/filename)
        key = next(iter(split[0]))
        require(len(split) == n and len({r[key] for r in split}) == n, 'split completeness')
        start = dt(split[0][key])
        labels = read(OUT/f'{stage}-training-labels.csv')
        expected_train = [r for r in feature_rows if dt(r[feature_key])+timedelta(hours=24) < start]
        require([r['feature_time'] for r in labels] == [r[feature_key] for r in expected_train], 'purged original training membership')
        require([r['feature_time'] for r in labels] == [r['feature_time'] for r in read(OLD/f'{stage}-training-origins.csv')], 'matched 006 training')
        monthly = defaultdict(Counter)
        total = Counter()
        for label, source in zip(labels, expected_train):
            target = dt(source[feature_key])+timedelta(hours=24)
            valid = target.replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc)
            require(dt(label['target_time']) == target and dt(label['valid_time_utc']) == valid, 'training clock')
            require(valid in satellite, 'missing training reference timestamp')
            w = int(float(source['target']) > 600)
            s = None if satellite[valid] is None else int(satellite[valid] > 600)
            y = w if s is None else (w+s)/2
            require(int(label['weather_event']) == w and val(label['satellite_event']) == s, 'events')
            require(int(label['satellite_missing']) == (s is None) and int(label['source_count']) == (1 if s is None else 2), 'source count')
            require(float(label['soft_target']) == y, 'soft label')
            field = 'missing' if s is None else f'W{w}_S{s}'
            monthly[target.strftime('%Y-%m')][field] += 1
            total[field] += 1
            label_count += 1
        paired = len(labels)-total['missing']
        train_audit[stage] = {'hours': len(labels), 'event_pairs': dict(total), 'months': {m: dict(c) for m,c in monthly.items()},
                              'effective_weather_weight': paired/2+total['missing'], 'effective_satellite_weight': paired/2,
                              'unit_row_weight_total': len(labels)}
        require(sum(total.values()) == len(labels), 'training accounting')
        meta = report['splits'][stage]
        require(meta['training_hours'] == len(labels) and meta['satellite_missing'] == total['missing']
                and meta['paired_disagreements'] == total['W0_S1']+total['W1_S0'], 'reported training summary')
        for method, stages in report['methods'].items():
            saved = read(OUT/'predictions'/f'{stage}-{method}.csv')
            require([r['feature_time'] for r in saved] == [r[key] for r in split], 'full prediction membership')
            rows = []
            for r, source in zip(saved, split):
                target = dt(r['feature_time'])+timedelta(hours=24)
                valid = target.replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc)
                require(dt(r['target_time']) == target and dt(r['valid_time_utc']) == valid, 'prediction clock')
                require(float(r['weather_actual_w_m2']) == float(source['actual']) == float(original[r['feature_time']]['target']), 'unchanged weather truth')
                require(val(r['satellite_w_m2']) == satellite[valid], 'reference join')
                p, cut = float(r['probability']), float(r['cutoff'])
                require(math.isfinite(p) and 0 <= p <= 1, 'probability range')
                require(int(r['predicted_positive']) == (p > cut) and int(r['default_positive']) == (p > .5), 'strict decisions')
                require(cut == stages[stage]['cutoff'], 'reported cutoff')
                rows.append({'p': p, 'weather': float(source['actual']), 'sat': satellite[valid]})
                prediction_count += 1
            all_rows[stage, method] = rows
            if not method.startswith('consensus_'):
                old_name = method.removeprefix('weather_')
                old = read(OLD/'predictions'/f'{stage}-{old_name}.csv')
                require([r['p'] for r in rows] == [float(r['probability']) for r in old], 'unchanged control predictions')
            for mode, bases in stages[stage]['modes'].items():
                cutoff = stages[stage]['cutoff'] if mode == 'selected' else .5 if mode == 'default_0_5' else float(saved[0]['previous_006_cutoff'])
                if mode == 'previous_006':
                    require(cutoff == float(old[0]['cutoff']), 'original 006 cutoff')
                    require(all(int(r['previous_006_positive']) == (float(r['probability']) > cutoff) for r in saved), 'previous decisions')
                for basis, observed in bases.items():
                    expected = counted(rows, cutoff, basis)
                    same(observed, expected, (stage, method, mode, basis))
                    same(comparison[stage, method, mode, basis], expected, 'comparison CSV')
                    metric_count += 1
            if method.startswith(('weather_', 'consensus_')):
                require(stages[stage]['cutoff'] == selection['all_thresholds'][method]['cutoff'], 'frozen validation cutoff')
        if stage == 'validation':
            control = {b: counted(all_rows[stage, 'nwp_day2'], .5, b) for b in ('weather_full', 'satellite_common')}
            for method in selection['all_thresholds']:
                grid = threshold_oracle(all_rows[stage, method])
                saved_grid = js(OUT/f'validation-grid-{method}.json')
                require(len(grid) == len(saved_grid), 'complete cutoff grid')
                for a,b in zip(grid, saved_grid):
                    require(a['cutoff'] == b['cutoff'], 'cutoff enumeration')
                    a['qualifies'] = eligible(a['metrics'], control)
                    require(a['qualifies'] == b['qualifies'], 'joint six-metric gate')
                    for basis in control: same(b['metrics'][basis], a['metrics'][basis], 'cumulative grid oracle')
                    grid_count += 1
                candidates = [r for r in grid if r['qualifies']] or grid
                chosen = max(candidates, key=lambda r: (*rank(r['metrics']), -abs(r['cutoff']-.5), r['cutoff']))
                require(chosen == selection['all_thresholds'][method], 'threshold rank')
                best[method] = chosen
            for family in ('weather', 'consensus'):
                names = [family+'_'+size for size in ('small', 'medium', 'larger')]
                candidates = [name for name in names if best[name]['qualifies']]
                chosen = max(candidates, key=lambda name: (*rank(best[name]['metrics']), -names.index(name))) if candidates else 'nwp_day2'
                require(chosen == selection['families'][family] == report['selected_families'][family], 'family rank')
    gates = {}
    for family, name in selection['families'].items():
        c = {b: counted(all_rows['test', name], report['methods'][name]['test']['cutoff'], b) for b in ('weather_full', 'satellite_common')}
        n = {b: counted(all_rows['test', 'nwp_day2'], .5, b) for b in c}
        changes = [exact(c[b],k)-exact(n[b],k) for b in c for k in ('precision','recall','f1')]
        passes = eligible(c,n) and any(x>0 for x in changes)
        require(passes == report['test_gates'][family]['passes_frozen_gate'], 'promotion gate')
        gates[family] = {'method': name, 'passes': passes, 'candidate': c, 'nwp': n}
    # Replay the stored trees; no training or runner import.
    import lightgbm as lgb
    import numpy as np
    import pandas as pd
    frame = pd.read_csv(OLD/'features.csv', float_precision='round_trip').set_index('feature_time')
    replay_error = 0.
    for stage in ('validation', 'test'):
        for size in ('small', 'medium', 'larger'):
            name = 'consensus_'+size
            pred = read(OUT/'predictions'/f'{stage}-{name}.csv')
            model = lgb.Booster(model_file=str(OUT/'models'/f'{stage}-{name}.txt'))
            require(model.feature_name() == list(frame.columns), 'stored feature order')
            require(model.params['objective'] == 'cross_entropy', 'stored objective')
            actual = model.predict(frame.loc[[r['feature_time'] for r in pred]], num_threads=2)
            expected = np.array([float(r['probability']) for r in pred])
            error = float(np.max(np.abs(actual-expected)))
            replay_error = max(replay_error, error)
            require(error <= 1e-15, 'saved model replay')
    for name, identity in before.items(): require(sha(Path(name)) == identity, 'immutable: '+name)
    result = {'status': 'PASS', 'checks': checks, 'training_labels': label_count, 'prediction_rows': prediction_count,
              'metric_rows': metric_count, 'threshold_rows': grid_count, 'model_replays': 6,
              'maximum_model_probability_error': replay_error, 'training_reference_audit': train_audit,
              'selected_families': selection['families'], 'test_gates': gates,
              'code_sha256': sha(Path(__file__)), 'protocol_sha256': report['protocol_sha256'],
              'runner_sha256': report['code_sha256'], 'report_sha256': sha(OUT/'report.json'),
              'immutable_paths_verified': len(before),
              'scope': 'Independent numerical reconstruction, cumulative threshold oracle, fixed UTC joins and stored-tree replay; no refit. Timestamp availability is not verified provider publication availability. Shared reference errors and inspected-test selection remain unresolved.'}
    (HERE/'result.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('training_reference_audit','test_gates')}, indent=2))


if __name__ == '__main__': main()
