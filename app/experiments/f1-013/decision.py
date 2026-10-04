"""Exact finite-scenario event decisions with two separate reference guards."""
from collections import Counter
from fractions import Fraction as F
from itertools import product
import time
import numpy as np


def events(radiation):
    values = np.asarray(radiation)
    if not np.isfinite(values).all():
        raise ValueError('Radiation scenarios must be finite')
    return values > 600


def inputs(scenarios, raw):
    y, b = np.asarray(scenarios), np.asarray(raw)
    if y.ndim != 3 or y.shape[0] != 2 or y.shape[1] < 1 or not 1 <= y.shape[2] <= 24:
        raise ValueError('Expected two reference arrays with 1 to 24 hours')
    if b.shape != (y.shape[2],) or not np.isin(y, (0, 1)).all() or not np.isin(b, (0, 1)).all():
        raise ValueError('Scenarios and raw calls must be binary with matching hours')
    return y.astype(bool), b.astype(bool)


def direct_scores(scenarios, decision):
    """Independent scenario-by-scenario arithmetic for a selected action."""
    k = sum(bool(v) for v in decision)
    result = []
    for reference in scenarios:
        n, p, r, f, active = len(reference), F(0), F(0), F(0), 0
        for truth in reference:
            s = sum(bool(v) for v in truth)
            tp = sum(bool(a) and bool(b) for a, b in zip(truth, decision))
            if k:
                p += F(tp, k)
            if s:
                r += F(tp, s)
                active += 1
            f += F(2 * tp, s + k) if s + k else F(1)
        result.append(dict(precision=p / n if k else None,
                           recall=r / active if active else None, f1=f / n))
    return result


def coefficients(y):
    tables = []
    for reference in y:
        n, h = reference.shape
        counts = reference.sum(axis=1)
        active = int(np.count_nonzero(counts))
        hist = [Counter(int(s) for s, positive in zip(counts, reference[:, i]) if positive)
                for i in range(h)]
        tables.append(dict(
            scenarios=n, positive_scenarios=active, empty_f1=F(n - active, n),
            probability=[F(sum(v.values()), n) for v in hist],
            recall=[sum((F(count, active * s) for s, count in v.items()), F(0))
                    for v in hist] if active else None,
            f1={k: [sum((F(2 * count, n * (s + k)) for s, count in v.items()), F(0))
                    for v in hist] for k in range(1, h + 1)}))
    return tables


def coefficient_scores(tables, selected):
    k = len(selected)
    return [dict(
        precision=sum((t['probability'][i] for i in selected), F(0)) / k if k else None,
        recall=sum((t['recall'][i] for i in selected), F(0)) if t['recall'] is not None else None,
        f1=sum((t['f1'][k][i] for i in selected), F(0)) if k else t['empty_f1'])
        for t in tables]


def failures(metrics, baseline, k, k0):
    failed = ['zero_call_precision'] if k == 0 and k0 > 0 else []
    for r, (current, previous) in enumerate(zip(metrics, baseline)):
        for name in ('precision', 'recall', 'f1'):
            if previous[name] is not None and (current[name] is None or current[name] < previous[name]):
                failed.append(f'{r}/{name}')
    return failed


def solve(scenarios, raw, deadline=None):
    y, b = inputs(scenarios, raw)
    h, k0 = len(b), int(b.sum())
    tables = coefficients(y)
    baseline = direct_scores(y, b.tolist())
    count = y.sum(axis=(0, 1))
    ones = tuple(int(i) for i in np.flatnonzero(count == y.shape[0] * y.shape[1]))
    zeros = tuple(int(i) for i in np.flatnonzero(count == 0))
    uncertain = tuple(int(i) for i in np.flatnonzero((count > 0) & (count < y.shape[0] * y.shape[1])))
    raw_tuple = tuple(bool(v) for v in b)
    def candidates():
        yield raw_tuple
        for bits in product((False, True), repeat=len(uncertain)):
            action = [False] * h
            for i in ones:
                action[i] = True
            for i, positive in zip(uncertain, bits):
                action[i] = positive
            if tuple(action) != raw_tuple:
                yield tuple(action)
    ledger, best, ranks = [], {}, {}
    for decision in candidates():
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError('Declared decision runtime budget exhausted')
        selected = tuple(i for i, positive in enumerate(decision) if positive)
        k = len(selected)
        changed = sum(a != c for a, c in zip(decision, raw_tuple))
        metrics = coefficient_scores(tables, selected)
        failed = failures(metrics, baseline, k, k0)
        gains = [current['f1'] - previous['f1'] for current, previous in zip(metrics, baseline)]
        objectives = dict(robust=min(gains), pooled=sum(gains, F(0)) / 2)
        record = dict(decision=list(decision), positive_calls=k, changed_bits=changed,
                      metrics=metrics, failed_constraints=failed, objectives=objectives)
        ledger.append(record)
        if failed:
            continue
        for arm, value in objectives.items():
            rank = (value, -changed, -k, tuple(-i for i in selected))
            if arm not in ranks or rank > ranks[arm]:
                ranks[arm] = rank
                best[arm] = dict(decision=list(decision), metrics=metrics, objective=value,
                                 changed_bits=changed, positive_calls=k)
    if set(best) != {'robust', 'pooled'}:
        raise AssertionError('Raw decision must remain feasible')
    for record in best.values():
        direct = direct_scores(y, record['decision'])
        if direct != record['metrics'] or failures(direct, baseline, record['positive_calls'], k0):
            raise AssertionError('Selected exact scores or safeguards disagree')
        if record['objective'] < 0 or (record['objective'] == 0 and record['decision'] != list(raw_tuple)):
            raise AssertionError('No-gain decision did not retain raw calls')
    return dict(raw_metrics=baseline, arms=best, coefficients=tables, candidates=ledger,
                unanimous_positive=list(ones), unanimous_negative=list(zeros),
                uncertain=list(uncertain), canonical_subsets=2 ** len(uncertain))
