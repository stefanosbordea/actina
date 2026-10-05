"""Frozen common-issuance, worst-reference paired exchange experiment."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import resource
import sys
import time

sys.dont_write_bytecode = True
import lightgbm as lgb
import numpy as np
import pandas as pd
from policy import MARGINS, best_pair, apply_pair

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('prior008', HERE.parent / 'f1-008/run.py')
prior = importlib.util.module_from_spec(spec); spec.loader.exec_module(prior)
BASES = prior.BASES
HISTORY = ('residual_mean_24', 'residual_count_24', 'residual_mean_168', 'residual_count_168', 'residual_lag24')
WEATHER = ('temperature_2m', 'shortwave_radiation', 'relative_humidity_2m', 'cloud_cover')
PROTOCOL_SHA = 'ce014afdfca37458c3f3429bbbe07f62befcb3f1c053c2dfae5bf3ef1bd5b1da'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return pd.read_csv(path, float_precision='round_trip')
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
def now(): return datetime.now(timezone.utc).isoformat()


def issue_features(features, targets, weather):
    origin = pd.DatetimeIndex(features.feature_time)
    target = pd.DatetimeIndex(targets.target_time)
    if not origin.is_unique or not target.is_unique or not weather.index.is_unique: raise ValueError('Duplicate source timestamps')
    if not np.all(target == origin + pd.Timedelta(hours=24)) or not np.all(np.diff(target.asi8) == 3600000000000): raise ValueError('Target chronology')
    issue = target.normalize() - pd.Timedelta(days=1)
    if not np.all(pd.Series(target.normalize()).value_counts().to_numpy() == 24): raise ValueError('Incomplete target day')
    state = issue - pd.Timedelta(hours=1)
    lag = issue - pd.Timedelta(hours=24)
    history_rows = origin.get_indexer(issue)
    if np.any(history_rows < 0) or not state.isin(weather.index).all() or not lag.isin(weather.index).all(): raise ValueError('Missing issued source')
    x = features.drop(columns='feature_time').copy()
    rename = {}
    for name in WEATHER:
        x[name] = weather[name].reindex(state).to_numpy(); rename[name] = 'issue_' + name
    x['radiation_yesterday'] = weather.shortwave_radiation.reindex(lag).to_numpy()
    rename.update(radiation_yesterday='issue_radiation_lag24', hour='lead_hours', month='issue_month')
    x['hour'] = ((target - issue) / pd.Timedelta(hours=1)).astype(int)
    x['month'] = issue.month
    for name in HISTORY:
        x[name] = features[name].iloc[history_rows].to_numpy(); rename[name] = 'issue_' + name
    x = x.rename(columns=rename)
    residual = pd.Series(targets.actual.to_numpy() - features.nwp_day2_radiation.to_numpy(), index=target)
    latest = {}
    for issued in issue.unique():
        row = features.iloc[origin.get_loc(issued)]
        available = residual.loc[residual.index < issued]
        latest[issued] = available.index[-1] if len(available) else pd.NaT
        for window in (24, 168):
            values = available.loc[available.index >= issued - pd.Timedelta(hours=window)]
            if row[f'residual_count_{window}'] != len(values): raise ValueError('History count mismatch')
            mean = float(values.mean()) if len(values) else np.nan
            if not np.isclose(mean, row[f'residual_mean_{window}'], rtol=0, atol=1e-9, equal_nan=True): raise ValueError('History mean mismatch')
        if not np.isclose(residual.get(issued - pd.Timedelta(hours=24), np.nan), row.residual_lag24, rtol=0, atol=1e-12, equal_nan=True): raise ValueError('History lag mismatch')
    nominal = target - pd.Timedelta(hours=48)
    if not np.all(nominal <= state) or np.any((x.lead_hours < 24) | (x.lead_hours > 47)): raise ValueError('Issuance leakage')
    if len(x.columns) != 27 or np.isinf(x.to_numpy()).any() or x[['issue_' + n for n in WEATHER]].isna().any().any(): raise ValueError('Feature shape/value')
    meta = pd.DataFrame({'feature_time': features.feature_time, 'target_time': target, 'issue_time': issue,
                         'weather_source_time': state, 'lag24_source_time': lag,
                         'latest_residual_source_time': [latest[t] for t in issue],
                         'nwp_nominal_time': nominal, 'maximum_source_time': state})
    if not np.array_equal(meta.maximum_source_time.to_numpy() < meta.issue_time.to_numpy(), np.ones(len(meta), dtype=bool)): raise ValueError('Source after issue')
    return x, meta


def gate(metrics, control):
    a, b = ({k: value[k] for k in BASES} for value in (metrics, control))
    result = prior.joint.test_gate(a, b)
    if any(prior.fraction(m, key) < 0 for v in (a, b) for m in v.values() for key in ('precision', 'recall', 'f1')):
        result['passes_frozen_gate'] = result['all_six_strictly_improved'] = False
    return result


def main(out):
    wall, cpu = time.perf_counter(), time.process_time()
    if sha(HERE / 'PROTOCOL.md') != PROTOCOL_SHA: raise ValueError('Protocol changed')
    pins = json.loads((HERE / 'inputs.json').read_text())
    for name, expected in pins.items():
        if sha(ROOT / name) != expected: raise ValueError('Pinned input changed: ' + name)
    if HERE not in out.parents: raise ValueError('Output outside experiment')
    out.mkdir(exist_ok=False); (out / 'models').mkdir(); (out / 'predictions').mkdir(); (out / 'pairs').mkdir()
    features = read(HERE.parent / 'f1-008/result/features.csv')
    targets = read(HERE.parent / 'f1-006/result/feature-targets.csv')
    reference = read(HERE.parent / 'reference-training-001/result/joined-reference.csv')
    weather_source = read(ROOT / 'data/paphos_weather_data.csv').set_index('time')
    weather_source.index = pd.to_datetime(weather_source.index)
    if len(features) != 17832 or any(not features.feature_time.equals(v.feature_time) for v in (targets, reference)): raise ValueError('Source membership')
    target = pd.to_datetime(targets.target_time)
    if not target.equals(pd.to_datetime(reference.target_time)) or not np.array_equal(targets.actual, reference.weather_actual_w_m2): raise ValueError('Truth join')
    epoch = target.dt.tz_localize('Etc/GMT-3').dt.tz_convert('UTC')
    if not epoch.equals(pd.to_datetime(reference.valid_time_utc, utc=True)): raise ValueError('Reference clock')
    if not np.array_equal(targets.actual, weather_source.shortwave_radiation.reindex(target).to_numpy()): raise ValueError('Weather truth source')
    satellite = reference.satellite_w_m2.to_numpy()
    if np.isinf(satellite).any() or np.any(satellite < 0) or not np.array_equal(np.isnan(satellite), reference.is_missing.astype(bool)): raise ValueError('Satellite value/missingness')
    x, meta = issue_features(features, targets, weather_source)
    pd.concat([meta[['feature_time']], x], axis=1).to_csv(out / 'features.csv', index=False)
    meta.to_csv(out / 'source-timestamps.csv', index=False)
    report = dict(status='RUNNING', started_at_utc=now(), input_sha256=pins, protocol_sha256=PROTOCOL_SHA,
                  code_sha256=sha(Path(__file__)), policy_sha256=sha(HERE / 'policy.py'), features=list(x.columns),
                  versions=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, lightgbm=lgb.__version__),
                  scope='Retrospective; already-inspected test; common issuance changes horizon; publication times unverified; event count is not operational dispatch.',
                  configuration=prior.joint.CONFIGS['larger'], splits={}, methods={}, raw_head_scores={})
    policies = {}
    for stage, filename in (('validation', 'cv_predictions.csv'), ('test', 'test_predictions.csv')):
        if stage == 'test' and sha(out / 'validation-selection.json') != report['selection_sha256']: raise ValueError('Selection changed')
        split = read(ROOT / 'eval' / filename); names = split.iloc[:, 0]
        positions = pd.Index(features.feature_time).get_indexer(names)
        if len(positions) != {'validation': 3566, 'test': 3567}[stage] or np.any(positions < 0) or not names.is_unique: raise ValueError('Split membership')
        if not np.array_equal(targets.actual.iloc[positions], split.actual): raise ValueError('Split truth')
        days = target.iloc[positions].dt.normalize().unique()
        full = np.flatnonzero(target.dt.normalize().isin(days))
        scored = np.isin(full, positions)
        if not np.array_equal(full[scored], positions) or len(full) != len(days) * 24: raise ValueError('Full-day extension')
        issue_cutoff = meta.issue_time.iloc[full].min()
        train = np.flatnonzero(target < issue_cutoff)
        train_satellite = train[np.isfinite(satellite[train])]
        train_ledger = meta.iloc[train].copy()
        train_ledger['weather_actual_w_m2'] = targets.actual.iloc[train].to_numpy()
        train_ledger['satellite_w_m2'] = satellite[train]
        train_ledger['weather_event'] = (targets.actual.iloc[train].to_numpy() > 600).astype(int)
        train_ledger['satellite_event'] = [None if not np.isfinite(v) else int(v > 600) for v in satellite[train]]
        train_ledger['satellite_training'] = np.isfinite(satellite[train])
        train_ledger['satellite_exclusion'] = np.where(np.isfinite(satellite[train]), '', 'missing_reference')
        train_ledger.to_csv(out / f'{stage}-training.csv', index=False)
        forecast = meta.iloc[full].reset_index(drop=True).copy()
        forecast['weather_actual_w_m2'] = targets.actual.iloc[full].to_numpy()
        forecast['satellite_w_m2'] = satellite[full]
        forecast['original_score_mask'] = scored
        forecast['satellite_score_mask'] = scored & np.isfinite(satellite[full])
        nwp = x.nwp_day2_radiation.iloc[full].to_numpy(); baseline = nwp > 600
        forecast['nwp_day2_w_m2'] = nwp; forecast['nwp_positive'] = baseline.astype(int)
        probability = {}
        for head, indices in (('weather', train), ('satellite', train_satellite)):
            y = (targets.actual.iloc[indices].to_numpy() if head == 'weather' else satellite[indices]) > 600
            model = lgb.LGBMClassifier(**prior.joint.CONFIGS['larger'], objective='binary', learning_rate=.03, reg_lambda=2,
                                      random_state=17, n_jobs=2, deterministic=True, force_col_wise=True, verbosity=-1)
            start = time.perf_counter(); model.fit(x.iloc[indices], y.astype(int))
            model.booster_.save_model(str(out / 'models' / f'{stage}-{head}.txt'))
            p = model.predict_proba(x.iloc[full])[:, 1]
            if not np.isfinite(p).all() or np.any((p < 0) | (p > 1)): raise ValueError('Head probability')
            probability[head] = p; forecast[f'probability_{head}'] = p
            print(stage, head, 'fit_rows', len(indices), 'seconds', time.perf_counter() - start, flush=True)
        w = forecast.weather_actual_w_m2.to_numpy()[scored]; s = satellite[positions]
        control = prior.metrics(baseline[scored], w, s)
        report['splits'][stage] = dict(original_hours=len(positions), full_hours=len(full), padded_hours=int(np.sum(~scored)),
            target_days=len(days), first_issue=str(issue_cutoff), latest_training_target=str(target.iloc[train[-1]]),
            weather_training_rows=len(train), satellite_training_rows=len(train_satellite), satellite_missing_train=int(len(train)-len(train_satellite)),
            satellite_scored_hours=int(np.isfinite(s).sum()))
        for head, p in probability.items():
            report['raw_head_scores'].setdefault(head, {})[stage] = prior.metrics(p[scored] > .5, w, s, p[scored])
        for name in ('original', 'persistence', 'nwp_day2'):
            old = read(HERE.parent / f'f1-006/result/predictions/{stage}-{name}.csv')
            if not np.array_equal(old.feature_time, names): raise ValueError('Control membership')
            decision = old.probability.to_numpy() > .5
            if name == 'nwp_day2' and not np.array_equal(decision, baseline[scored]): raise ValueError('Raw NWP identity')
            report['methods'].setdefault(name, {})[stage] = dict(metrics=prior.metrics(decision, w, s))
        old_selection = json.loads((HERE.parent / 'f1-008/result/validation-selection.json').read_text())
        context_name = old_selection['selected_augmented_arm']
        old_context = read(HERE.parent / f'f1-008/result/predictions/{stage}-{context_name}.csv')
        if not np.array_equal(old_context.feature_time, names): raise ValueError('Context membership')
        report['methods'].setdefault('008_context', {})[stage] = dict(method=context_name, different_issuance=True,
             metrics=prior.metrics(old_context.predicted_positive.to_numpy().astype(bool), w, s))
        for arm in ('min', 'mean'):
            ledgers, candidates, decisions = [], [], {}
            pairs = [best_pair(baseline[i:i+24], probability['weather'][i:i+24], probability['satellite'][i:i+24], arm) for i in range(0, len(full), 24)]
            for margin in MARGINS:
                decision = baseline.copy(); swaps = 0
                for day_no, i in enumerate(range(0, len(full), 24)):
                    pair = pairs[day_no]; after = apply_pair(baseline[i:i+24], pair, margin)
                    acted = bool(np.any(after != baseline[i:i+24])); swaps += acted
                    decision[i:i+24] = after
                    ledger = dict(target_day=str(target.iloc[full[i]].date()), issue_time=str(meta.issue_time.iloc[full[i]]), arm=arm, margin=margin,
                                  acted=acted, positive_count_before=int(np.sum(baseline[i:i+24])), positive_count_after=int(np.sum(after)))
                    if pair:
                        add, remove = i + pair['add'], i + pair['remove']
                        ledger.update(pair)
                        ledger.update(add_target=str(target.iloc[full[add]]), remove_target=str(target.iloc[full[remove]]),
                          add_original_mask=bool(scored[add]), remove_original_mask=bool(scored[remove]),
                          add_satellite_mask=bool(forecast.satellite_score_mask.iloc[add]), remove_satellite_mask=bool(forecast.satellite_score_mask.iloc[remove]))
                    ledgers.append(ledger)
                m = prior.metrics(decision[scored], w, s); checked = gate(m, control)
                item = dict(policy=dict(kind='swap', margin=margin), metrics=m, full_day_swaps=swaps,
                    original_added=int(np.sum(decision[scored] & ~baseline[scored])), original_removed=int(np.sum(~decision[scored] & baseline[scored])), gate=checked)
                candidates.append(item); decisions[margin] = decision
                forecast[f'{arm}_margin_{margin:g}_positive'] = decision.astype(int)
            if stage == 'validation':
                eligible = [c for c in candidates if c['gate']['passes_frozen_gate']]
                chosen = max(eligible, key=lambda c: (*prior.joint.rank(dict(metrics={b:c['metrics'][b] for b in BASES})), -c['full_day_swaps'], c['policy']['margin'])) if eligible else dict(policy=dict(kind='control'), metrics=control, full_day_swaps=0, gate=gate(control, control))
                policies[arm] = chosen['policy']
            policy = policies[arm]
            selected = next(c for c in candidates if c['policy'] == policy) if policy['kind'] == 'swap' else dict(policy=policy, metrics=control, full_day_swaps=0, original_added=0, original_removed=0, gate=gate(control, control))
            forecast[f'{arm}_selected_positive'] = (decisions[policy['margin']] if policy['kind'] == 'swap' else baseline).astype(int)
            report['methods'].setdefault(arm, {})[stage] = selected
            save(out / f'{stage}-grid-{arm}.json', candidates)
            pd.DataFrame(ledgers).to_csv(out / 'pairs' / f'{stage}-{arm}.csv', index=False)
            print(stage, arm, json.dumps(selected), flush=True)
        forecast.to_csv(out / 'predictions' / f'{stage}-full.csv', index=False)
        if stage == 'validation':
            save(out / 'validation-selection.json', dict(policies=policies, frozen_at_utc=now(), protocol_sha256=PROTOCOL_SHA,
                 code_sha256=sha(Path(__file__)), validation_prediction_sha256=sha(out / 'predictions/validation-full.csv')))
            report['selection_sha256'] = sha(out / 'validation-selection.json')
        save(out / 'report.json', report)
    report.update(status='COMPLETE', completed_at_utc=now(), wall_seconds=time.perf_counter()-wall, cpu_seconds=time.process_time()-cpu,
                  peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  verdict='No product replacement. Evaluate both fixed arms independently; gains require all-six admission, and event-count preservation is not dispatch preservation.')
    save(out / 'report.json', report)
    save(out / 'outputs.json', {str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'outputs.json'})
    print('COMPLETE', json.dumps({arm:report['methods'][arm]['test']['gate'] for arm in ('min','mean')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out', type=Path, default=HERE/'result')
    main(parser.parse_args().out.resolve())
