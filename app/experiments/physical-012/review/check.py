"""Independent retrieval, scenario, water and cost replay without production imports."""
import csv
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import time
import numpy as np

HERE = Path(__file__).resolve().parent
EXP, ROOT = HERE.parent, HERE.parent.parents[2]
OUT, OLD = EXP / 'result', EXP.parent / 'physical-011/result'
started, checks = time.perf_counter(), 0
METHODS = ['tariff_context', 'raw_point', 'recency_coherent', 'recency_shuffled', 'conditional_coherent', 'conditional_shuffled']
REFS = ['weather', 'satellite']
PRICE = np.array([.101 if 10 <= h < 17 else .183 if 17 <= h < 23 else .130 for h in range(24)])


def check(ok, label):
    global checks
    checks += 1
    if not ok:
        raise AssertionError(label)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p):
    return json.loads(p.read_text())


def rows(p):
    with p.open(newline='') as f:
        return list(csv.DictReader(f))


def flag(v):
    return v in (True, 'True', '1', 1)


def dt(v):
    return datetime.fromisoformat(v)


def equal(a, b, label, tolerance=0.):
    a, b = np.asarray(a), np.asarray(b)
    check(a.shape == b.shape and np.allclose(a, b, rtol=0, atol=tolerance, equal_nan=True), label)


def tail(v):
    v = sorted(map(float, v), reverse=True)
    check(bool(v) and all(map(math.isfinite, v)), 'finite nonempty CVaR')
    whole, remainder = divmod(len(v), 10)
    return (10 * math.fsum(v[:whole]) + remainder * v[whole]) / len(v)


def statistics(v):
    v = list(map(float, v))
    return dict(mean=math.fsum(v) / len(v), cvar90=tail(v), maximum=max(v), minimum=min(v))


def stats_match(a, b, label):
    for name, value in a.items():
        check(abs(value - b[name]) < 1.e-8, label + '/' + name)


def descriptor(v):
    total, result = 0., []
    for x in v:
        total += min(1700., 1.7 * max(float(x), 0.))
        result.append(total / 3.4)
    return np.array(result)


def solar(v):
    return np.minimum(1700., 1.7 * np.maximum(v, 0.))


def distance_left_to_right(a, b):
    total = 0.
    for x, y in zip(a, b):
        total += abs(float(x)-float(y))
    return total / 24


check(tail([-3.] * 64) == -3., 'negative constant tail')
check(abs(tail(range(64)) - 60.28125) < 1.e-12, 'fractional tail fixture')
check(tail([816., 0.]) == 816. and tail([408., 408.]) == 408., 'dependence fixture')
pins, report, outputs = load(EXP / 'inputs.json'), load(OUT / 'report.json'), load(OUT / 'outputs.json')
identities = {ROOT / p: h for p, h in pins.items()} | {OUT / p: h for p, h in outputs.items()}
identities[EXP / 'inputs.json'] = sha(EXP / 'inputs.json')
identities[OUT / 'outputs.json'] = sha(OUT / 'outputs.json')
for p, h in identities.items():
    check(sha(p) == h, 'initial identity ' + str(p))
check(report['input_sha256'] == pins and report['input_lock_sha256'] == sha(EXP / 'inputs.json'), 'source lock')
check(report['protocol_sha256'] == sha(EXP / 'PROTOCOL.md'), 'final protocol identity')
freeze = load(OUT / 'planning-freeze.json')
for p, h in freeze['files_sha256'].items():
    check(sha(OUT / p) == h, 'planning identity ' + p)
check(report['planning_freeze_sha256'] == sha(OUT / 'planning-freeze.json'), 'planning manifest')
check(dt(report['started_at_utc']) < dt(freeze['all_plans_created_at_utc']) < dt(report['completed_at_utc']), 'planning before completion')
source = rows(ROOT / 'app/experiments/f1-008/result/features.csv')
targets = rows(ROOT / 'app/experiments/f1-006/result/feature-targets.csv')
reference = rows(ROOT / 'app/experiments/reference-training-001/result/joined-reference.csv')
check(len(source) == len(targets) == len(reference) == 17832, 'source coverage')
nwp = np.array([float(r['nwp_day2_radiation']) for r in source])
weather = np.array([float(r['actual']) for r in targets])
satellite = np.array([float(r['satellite_w_m2']) if r['satellite_w_m2'] else math.nan for r in reference])
times = [dt(r['target_time']) for r in targets]
origins, days = {}, {}
for i, (s, t, r) in enumerate(zip(source, targets, reference)):
    check(s['feature_time'] == t['feature_time'] == r['feature_time'], 'source origin join')
    check(times[i] == dt(r['target_time']) == dt(s['feature_time']) + timedelta(hours=24), 'target join')
    check(dt(r['valid_time_utc']) == times[i].replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc), 'fixed UTC+03 join')
    check(weather[i] == float(r['weather_actual_w_m2']) and flag(r['is_missing']) == math.isnan(satellite[i]), 'reference identity')
    origins[s['feature_time']] = i
    days.setdefault(times[i].date().isoformat(), []).append(i)
check(len(origins) == 17832 and all(b-a == timedelta(hours=1) for a, b in zip(times, times[1:])), 'unique hourly sources')
solver = {}
for line in (OUT / 'solver-records.jsonl').read_text().splitlines():
    r = json.loads(line)
    key = r['stage'], r['day'], r['method']
    check(key not in solver, 'unique solve record')
    solver[key] = r
check(len(solver) == 1196, '1196 re-solved or new schedules')
water, summaries = [], {}
maximum_water = Fraction(0)
maximum_replay_error = 0.
scenario_count, distance_count, reproduced = 0, 0, 0


def verify_gate(daily, primary, method, control, saved):
    risks, axes = [], []
    for ref in REFS:
        a = [r for r in daily if flag(r['primary']) and r['method'] == method and r['reference'] == ref]
        b = [r for r in daily if flag(r['primary']) and r['method'] == control and r['reference'] == ref]
        check([r['day'] for r in a] == [r['day'] for r in b] == primary, 'gate complete matched days')
        value = tail([float(x['cost_eur']) - float(y['cost_eur']) for x, y in zip(a, b)])
        item = next(r for r in saved['risk'] if r['reference'] == ref)
        check(abs(value - item['cvar90_daily_regret']) < 1.e-8, 'paired regret tail')
        check(item['nonregressing'] == (item['cvar90_daily_regret'] <= 0) and item['strict_gain'] == (item['cvar90_daily_regret'] < 0), 'literal risk flags')
        check(item['below_resolution'] == (abs(item['cvar90_daily_regret']) < 1.e-5), 'risk resolution')
        risks.append(item)
        for metric in ('cost_eur', 'grid_kwh'):
            sa, sb = statistics([r[metric] for r in a]), statistics([r[metric] for r in b])
            for statistic in ('mean', 'cvar90'):
                item = next(r for r in saved['axes'] if r['reference'] == ref and r['metric'] == metric and r['statistic'] == statistic)
                check(abs(sa[statistic] - item['candidate']) < 1.e-8 and abs(sb[statistic] - item['control']) < 1.e-8, 'axis levels')
                check(abs(sa[statistic] - sb[statistic] - item['difference']) < 1.e-8, 'axis difference')
                check(item['nonregressing'] == (item['difference'] <= 0) and item['strict_gain'] == (item['difference'] < 0), 'literal axis flags')
                check(item['below_resolution'] == (abs(item['difference']) < 1.e-5), 'axis resolution')
                axes.append(item)
    check(saved['risk_only_pass'] == (all(r['nonregressing'] for r in risks) and any(r['strict_gain'] for r in risks)), 'risk gate result')
    check(saved['all_axis_pass'] == (all(r['nonregressing'] for r in axes) and any(r['strict_gain'] for r in axes)), 'eight-axis gate result')


for stage, splitfile in [('validation', 'cv_predictions.csv'), ('test', 'test_predictions.csv')]:
    folder = OUT / stage
    split = rows(ROOT / 'eval' / splitfile)
    membership = {origins[r[next(iter(r))]] for r in split}
    check(len(membership) == len(split) == (3566 if stage == 'validation' else 3567), 'unchanged split hours')
    check(all(weather[origins[r[next(iter(r))]]] == float(r['actual']) for r in split), 'original labels unchanged')
    selected_days = sorted({times[i].date().isoformat() for i in membership})
    cutoff = dt(selected_days[0]) - timedelta(days=1)
    check(cutoff == dt('2025-12-04' if stage == 'validation' else '2026-05-02'), 'frozen stage cutoff')
    ledger = rows(folder / 'pool-membership.csv')
    check(len(ledger) == len(days), 'all pool inclusions and exclusions')
    eligible = []
    for row, (day, indices) in zip(ledger, days.items()):
        before = all(times[i] < cutoff for i in indices)
        complete = len(indices) == 24 and all(times[i] == dt(day) + timedelta(hours=h) for h, i in enumerate(indices))
        finite = [bool(np.isfinite(v[indices]).all()) for v in (nwp, weather, satellite)]
        yes = before and complete and all(finite)
        check(row['day'] == day and dt(row['first_endpoint']) == times[indices[0]] and dt(row['last_endpoint']) == times[indices[-1]], 'pool endpoints')
        check([flag(row[k]) for k in ('strictly_before_cutoff', 'complete_24', 'nwp_complete', 'weather_complete', 'satellite_complete', 'eligible')] == [before, complete, *finite, yes], 'pool eligibility')
        if yes:
            eligible.append(day)
    pos = np.array([days[d] for d in eligible])
    bank = np.load(folder / 'bank.npz', allow_pickle=False)
    check(all(not bank[k].dtype.hasobject for k in bank.files), 'pickle-free bank')
    equal(bank['pool_source_positions'], pos, 'all eligible source positions')
    check(bank['pool_source_days'].tolist() == eligible, 'all source days')
    check(bank['pool_source_target_time'].tolist() == [[str(times[i]) for i in p] for p in pos], 'Unicode source clocks')
    for field, data in [('pool_nwp', nwp), ('pool_weather', weather), ('pool_satellite', satellite)]:
        equal(bank[field], data[pos], field)
    residual = np.array([weather[pos] - nwp[pos], satellite[pos] - nwp[pos]])
    equal(bank['pool_residuals'], residual, 'reference residuals')
    descriptors = np.array([descriptor(v) for v in nwp[pos]])
    equal(bank['pool_descriptor'], descriptors, 'historical forecast-only descriptor')
    recency = np.arange(len(eligible)-64, len(eligible))
    equal(bank['recency_pool_indices'], recency, 'recency set')
    old_bank = np.load(OLD / stage / 'bank.npz', allow_pickle=False)
    equal(pos[recency], old_bank['source_positions'], 'prior bank identity')
    equal(residual[:, recency], old_bank['residuals'], 'prior residual identity')
    rng = np.random.default_rng(20261004)
    permutation = np.array([rng.permutation(64) for _ in range(24)])
    equal(bank['permutations'], permutation, 'fixed shuffle')
    equal(old_bank['permutations'], permutation, 'unchanged prior shuffle')
    plans = np.load(folder / 'plans.npz', allow_pickle=False)
    old_plans = np.load(OLD / stage / 'plans.npz', allow_pickle=False)
    replay = np.load(folder / 'scenario-replay.npz', allow_pickle=False)
    old_replay = np.load(OLD / stage / 'scenario-replay.npz', allow_pickle=False)
    q = plans['production']
    check(q.shape == (len(selected_days), 6, 24) and plans['methods'].tolist() == METHODS, 'all six plans')
    positions = np.array([days[d] for d in selected_days])
    equal(plans['target_positions'], positions, 'complete planned horizons')
    equal(plans['raw_forecast_ghi'], nwp[positions], 'issued raw forecast')
    equal(q[:, :4], old_plans['production'], 'all archived anchors and recency controls exactly reproduced')
    reproduced += len(selected_days) * 2
    record_reproduction = rows(folder / 'recency-reproduction.csv')
    check(len(record_reproduction) == len(selected_days)*2 and all(flag(r['exactly_equal']) and float(r['maximum_difference_m3']) == 0. for r in record_reproduction), 'recency reproduction receipt')
    retrieval = rows(folder / 'retrieval.csv')
    check(len(retrieval) == len(selected_days)*len(eligible), 'all retrieval ranks retained')
    expected_scenarios = np.empty((len(selected_days), 2, 2, 2, 64, 24))
    selected_sets, distance_matrix = [], []
    metadata = rows(folder / 'plan-metadata.csv')
    for d, day in enumerate(selected_days):
        target_descriptor = descriptor(nwp[positions[d]])
        distance = np.array([distance_left_to_right(v, target_descriptor) for v in descriptors])
        equal(bank['target_descriptor'][d], target_descriptor, 'target descriptor')
        equal(bank['distance_m3'][d], distance, 'every scalar distance')
        ordered = sorted(range(len(eligible)), key=lambda i: (distance[i], eligible[i]))
        selected = sorted(ordered[:64], key=lambda i: eligible[i])
        rank = {p: r+1 for r, p in enumerate(ordered)}
        equal(bank['conditional_pool_indices'][d], selected, 'exact ties and canonical chronological order')
        canonical = {p: i for i, p in enumerate(selected)}
        for p, source_day in enumerate(eligible):
            row = retrieval[d*len(eligible)+p]
            check(row['day'] == day and row['source_day'] == source_day and float(row['distance_m3']) == distance[p] and int(row['rank']) == rank[p], 'retrieval source and exact rank')
            check(flag(row['selected']) == (p in canonical) and (int(float(row['canonical_scenario_index'])) if row['canonical_scenario_index'] else None) == canonical.get(p), 'selection ledger')
            check(dt(row['source_last_endpoint']) == times[pos[p,-1]] < cutoff, 'historical source ledger cutoff')
        selected_sets.append(selected)
        distance_matrix.append(distance)
        issue = dt(day) - timedelta(days=1)
        r = metadata[d]
        ages = [(issue-times[pos[p,-1]]).total_seconds()/3600 for p in selected]
        totals = descriptors[:, -1]
        check(r['day'] == day and dt(r['issue_time']) == issue and dt(r['issue_utc']) == issue.replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc), 'common issuance clock')
        check(dt(r['interval_start']) == dt(day)-timedelta(hours=1) and dt(r['interval_end']) == dt(day)+timedelta(hours=23), 'physical interval horizon')
        check(dt(r['maximum_selected_source_time']) == max(times[i] for p in selected for i in pos[p]) < cutoff <= issue, 'all selected sources before issue')
        check(dt(r['maximum_nwp_nominal_time']) == dt(day)-timedelta(hours=25) < issue and all(times[i]-timedelta(hours=48) < issue for i in positions[d]), 'nominal forecast before issue')
        for key, value in [('distance_64_m3', max(distance[selected])), ('minimum_selected_age_hours', min(ages)), ('maximum_selected_age_hours', max(ages)), ('target_potential_water_m3', target_descriptor[-1]), ('pool_minimum_potential_water_m3', min(totals)), ('pool_maximum_potential_water_m3', max(totals))]:
            check(float(r[key]) == value, 'support metadata '+key)
        check(flag(r['target_total_outside_pool']) == (target_descriptor[-1] < min(totals) or target_descriptor[-1] > max(totals)), 'support flag')
        check(int(r['conditional_recency_overlap_days']) == len(set(selected) & set(recency)), 'bank overlap')
        for b, chosen in enumerate((recency, selected)):
            intact = residual[:, chosen]
            permuted = np.empty_like(intact)
            for ref in range(2):
                for h in range(24):
                    permuted[ref,:,h] = intact[ref,permutation[h],h]
            expected_scenarios[d,b,0] = nwp[positions[d]][None,None,:] + intact
            expected_scenarios[d,b,1] = nwp[positions[d]][None,None,:] + permuted
    equal(replay['unclipped_ghi'], expected_scenarios, 'every source scenario value')
    equal(expected_scenarios[:,0], old_replay['unclipped_ghi'], 'archived recency scenarios')
    scenario_count += expected_scenarios.size
    distance_count += len(selected_days)*len(eligible)
    pv = solar(expected_scenarios)
    equal(np.sort(pv[:,:,0], axis=3), np.sort(pv[:,:,1], axis=3), 'same clipped hourly marginals')
    costs = np.empty((len(selected_days),2,2,6,2,64))
    energies, unused = np.empty_like(costs), np.empty_like(costs)
    for d, day in enumerate(selected_days):
        for m, method in enumerate(METHODS):
            power = 3.4*q[d,m]
            grid = np.maximum(power[None,None,None,None,:]-pv[d], 0.)
            costs[d,:,:,m] = np.sum(grid*PRICE, axis=-1)
            energies[d,:,:,m] = np.sum(grid, axis=-1)
            unused[d,:,:,m] = np.sum(np.maximum(pv[d]-power,0.), axis=-1)
            equal(energies[d,:,:,m], sum(power)-pv[d].sum(axis=-1)+unused[d,:,:,m], 'energy allocation identity', 1.e-8)
            equal(energies[d,:,:,m], 9792-pv[d].sum(axis=-1)+unused[d,:,:,m], 'fixed plant energy with water tolerance', 4.e-6)
            rates = [Fraction.from_float(float(v)) for v in q[d,m]]
            stock = [Fraction(2000)]
            for rate in rates:
                stock.append(stock[-1]+rate-120)
            violation = max(Fraction(0), -min(rates), max(rates)-500, 800-min(stock), max(stock)-4000, abs(stock[-1]-2000))
            maximum_water = max(maximum_water, violation)
            check(violation <= Fraction.from_float(1.e-6), 'exact-rational water within declared tolerance')
            water.append(dict(stage=stage,day=day,method=method,final_m3=str(stock[-1]),minimum_m3=str(min(stock)),maximum_m3=str(max(stock)),maximum_violation_m3=str(violation)))
            if m >= 2:
                record = solver[stage,day,method]
                b, f = divmod(m-2,2)
                loss = costs[d,b,f,m]-costs[d,b,f,1]
                objective = max(tail(v) for v in loss)
                check(abs(objective-record['final_direct_objective']) < 1.e-8, 'daily scenario regret objective')
                check(all(r['status'] == 0 and r['success'] for r in record['solves']), 'successful LP stages')
                check(abs(record['primary_optimum']-record['primary_direct_audit']) <= 1.e-6, 'primary objective audit')
                check(abs(record['L1_distance']-sum(abs(q[d,m]-q[d,1]))) < 1.e-8, 'distance to raw anchor')
                if record['anchor_returned']:
                    equal(q[d,m], q[d,1], 'exact action-floor anchor')
                    check(not record['primary_cap_applies'] and objective-record['primary_optimum'] <= 1.e-5+1.e-9, 'action-floor exception')
                else:
                    check(record['primary_cap_applies'] and objective <= record['primary_cap']+1.e-6, 'preserved primary objective cap')
    for field, expected in [('cost_eur', costs), ('grid_kwh', energies), ('unused_pv_kwh', unused)]:
        equal(replay[field], expected, 'all six scenario ledgers '+field, 1.e-8)
    maximum_replay_error = max(maximum_replay_error, float(np.max(abs(replay['cost_eur']-costs))))
    equal(costs[:,:,0].mean(axis=-1), costs[:,:,1].mean(axis=-1), 'additive expected-cost shuffle invariance', 1.e-9)
    equal(energies[:,:,0].mean(axis=-1), energies[:,:,1].mean(axis=-1), 'expected energy shuffle invariance', 1.e-8)
    schedule = rows(folder / 'schedules.csv')
    check(len(schedule) == len(selected_days)*6*24, 'every hourly production row')
    for n, row in enumerate(schedule):
        d, m, h = n//144, (n//24)%6, n%24
        endpoint = times[positions[d,h]]
        check(row['day'] == selected_days[d] and row['method'] == METHODS[m] and dt(row['endpoint_time']) == endpoint and dt(row['interval_start']) == endpoint-timedelta(hours=1), 'schedule identity')
        check(float(row['production_m3']) == q[d,m,h] and float(row['demand_m3']) == 120. and float(row['tariff_eur_kwh']) == PRICE[h], 'hourly units and demand')
        check(abs(float(row['inventory_end_m3'])-(2000+math.fsum(float(v)-120 for v in q[d,m,:h+1]))) < 1.e-8, 'hourly tank ledger')
    mask, daily = rows(folder / 'evaluation-membership.csv'), rows(folder / 'daily-outcomes.csv')
    check(mask == rows(OLD / stage / 'evaluation-membership.csv'), 'every original score mask identical')
    primary, weather_days = [], []
    for row, day in zip(mask, selected_days):
        ids = days[day]
        inside, known = all(i in membership for i in ids), bool(np.isfinite(satellite[ids]).all())
        if inside:
            weather_days.append(day)
        if inside and known:
            primary.append(day)
        check(row['day'] == day and flag(row['primary']) == (inside and known) and flag(row['weather_sensitivity']) == inside, 'independent full-day eligibility')
    daily_keys = {(r['day'],r['method'],r['reference']) for r in daily}
    expected_keys = {(day,method,ref) for day in selected_days for method in METHODS for ref in REFS if ref == 'weather' or np.isfinite(satellite[days[day]]).all()}
    check(len(daily_keys) == len(daily) and daily_keys == expected_keys, 'every available outcome and no imputation')
    day_index = {day:i for i,day in enumerate(selected_days)}
    for row in daily:
        d, m = day_index[row['day']], METHODS.index(row['method'])
        actual = weather[positions[d]] if row['reference'] == 'weather' else satellite[positions[d]]
        pv_actual, power = solar(actual), 3.4*q[d,m]
        grid, anchor = np.maximum(power-pv_actual,0.), np.maximum(3.4*q[d,1]-pv_actual,0.)
        cost, basecost = math.fsum(grid*PRICE), math.fsum(anchor*PRICE)
        values = dict(cost_eur=cost, grid_kwh=math.fsum(grid), unused_pv_kwh=math.fsum(np.maximum(pv_actual-power,0.)), peak_grid_kw=max(grid), cost_regret_eur=cost-basecost, grid_regret_kwh=math.fsum(grid)-math.fsum(anchor))
        for key,value in values.items():
            check(abs(float(row[key])-value) < 1.e-8, 'realized accounting '+key)
        check(abs(values['grid_kwh']-(math.fsum(power)-math.fsum(pv_actual)+values['unused_pv_kwh'])) < 1.e-8, 'realized energy identity')
        check(flag(row['primary']) == (row['day'] in primary) and flag(row['weather_sensitivity']) == (row['day'] in weather_days and row['reference'] == 'weather'), 'daily outcome masks')
    for subset in ('primary','weather_sensitivity'):
        grouped = {}
        for row in daily:
            if flag(row[subset]):
                grouped.setdefault(row['method']+'/'+row['reference'],[]).append(row)
        check(set(grouped) == set(report['outcomes'][stage][subset]), 'all summary groups')
        for key, data in grouped.items():
            saved = report['outcomes'][stage][subset][key]
            for metric in ('cost_eur','grid_kwh','unused_pv_kwh','peak_grid_kw','cost_regret_eur','grid_regret_kwh'):
                stats_match(statistics([r[metric] for r in data]), saved[metric], 'summary '+key+'/'+metric)
            regret = [float(r['cost_regret_eur']) for r in data]
            check(saved['days'] == len(data) and saved['worse_days'] == sum(v>0 for v in regret) and saved['better_days'] == sum(v<0 for v in regret) and saved['equal_days'] == sum(v==0 for v in regret), 'reported better and worse days')
    for method in METHODS[2:]:
        verify_gate(daily,primary,method,'raw_point',report['gates'][stage][method])
    for method, control in [('conditional_coherent','recency_coherent'),('conditional_shuffled','recency_shuffled')]:
        verify_gate(daily,primary,method,control,report['matched_gates'][stage][method])
    for a,b in [('conditional_coherent','recency_coherent'),('conditional_shuffled','recency_shuffled'),('conditional_coherent','conditional_shuffled'),('recency_coherent','recency_shuffled')]:
        for ref in REFS:
            left = [r for r in daily if flag(r['primary']) and r['method'] == a and r['reference'] == ref]
            right = [r for r in daily if flag(r['primary']) and r['method'] == b and r['reference'] == ref]
            check([r['day'] for r in left] == [r['day'] for r in right], '2x2 matched comparison')
            for metric in ('cost_eur','grid_kwh'):
                stats_match(statistics([float(x[metric])-float(y[metric]) for x,y in zip(left,right)]),report['comparisons'][stage][a+'_minus_'+b][ref][metric], '2x2 difference')
    check(report['splits'][stage]['eligible_pool_days'] == len(eligible) and report['splits'][stage]['primary_days'] == len(primary) and report['splits'][stage]['weather_sensitivity_days'] == len(weather_days), 'reported cohort sizes')
    summaries[stage] = dict(planned_days=len(selected_days),eligible_pool_days=len(eligible),primary_days=len(primary),weather_sensitivity_days=len(weather_days),gates={m:{k:report['gates'][stage][m][k] for k in ('risk_only_pass','all_axis_pass')} for m in METHODS[4:]},outcomes={m+'/'+r:report['outcomes'][stage]['primary'][m+'/'+r] for m in METHODS[4:] for r in REFS})

for method in METHODS[4:]:
    risk = all(report['gates'][s][method]['risk_only_pass'] for s in ('validation','test'))
    axes = all(report['gates'][s][method]['all_axis_pass'] for s in ('validation','test'))
    check(report['experiment_gate'][method] == dict(risk_both_periods=risk,all_axis_both_periods=axes,overall_no_tradeoff=risk and axes), 'whole experiment admission')
for p,h in identities.items():
    check(sha(p) == h, 'final immutable identity '+str(p))
with (HERE / 'water-exact.csv').open('w',newline='') as f:
    writer = csv.DictWriter(f,fieldnames=water[0])
    writer.writeheader()
    writer.writerows(water)
result = dict(status='PASS',checks=checks,source_endpoints=len(source),retrieval_distances=distance_count,reconstructed_scenario_values=scenario_count,water_plans=len(water),exact_recency_reproductions=reproduced,maximum_scenario_cost_error_eur=maximum_replay_error,maximum_exact_water_violation_m3=str(maximum_water),maximum_water_violation_float_m3=float(maximum_water),immutable_files=len(identities),splits=summaries,
    limitations=['No fitting or LP re-solving. Independently replayed saved scenarios and per-solve objectives, not a new numerical optimality certificate.','All evaluation periods were already inspected. Validation losses remain and test gains cannot establish general superiority.','Binary64 water residuals retained with the frozen1e-6m3 tolerance. Tiny numerical signs are not meaningful plant gains.','Nominal source times do not verify publication availability. References are estimates, not independent ground sensors.','Constant-efficiency illustrative PV and water plant with unlimited grid backup. No field curtailment or operational authorization claim.'],
    code_sha256=sha(Path(__file__)),report_sha256=sha(OUT/'report.json'),protocol_sha256=sha(EXP/'PROTOCOL.md'),completed_at_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-started)
(HERE/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='splits'},allow_nan=False))
