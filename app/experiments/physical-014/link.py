"""Fixed binary64 event interface and paired physical evidence."""
from fractions import Fraction
import importlib.util
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('physical014_optimizer', HERE.parent / 'physical-011/optimizer.py')
optimizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(optimizer)
CONTROLS = ('tariff_context', 'raw_point', 'recency_coherent', 'recency_shuffled', 'conditional_coherent', 'conditional_shuffled')
CALL_METHODS = ('raw_nwp', 'recency_robust', 'recency_pooled', 'conditional_robust', 'conditional_pooled')
CANDIDATES = tuple('mapped_' + name for name in CALL_METHODS[1:])
METHODS = CONTROLS + CANDIDATES
POSITIVE = np.nextafter(np.float64(600), np.float64(np.inf))


def project(raw, calls):
    f, x = np.asarray(raw, dtype=np.float64), np.asarray(calls)
    if f.shape != (24,) or x.shape != (24,) or not np.isfinite(f).all() or np.any(f < 0):
        raise ValueError('Expected finite nonnegative 24-hour raw GHI and matching calls')
    if x.dtype.kind not in 'biu' or not np.isin(x, (0, 1)).all():
        raise ValueError('Calls must be Boolean or binary integers')
    g = np.where(x.astype(bool), np.maximum(f, POSITIVE), np.minimum(f, 600.))
    if not np.array_equal(g > 600, x.astype(bool)):
        raise AssertionError('Strict event projection failed')
    return g


def water_exact(q):
    optimizer.audit(q)
    values = [Fraction.from_float(float(v)) for v in q]
    stock, stocks = Fraction(2000), [Fraction(2000)]
    for v in values:
        stock += v - 120
        stocks.append(stock)
    errors = dict(production_below_zero=max(Fraction(), -min(values)), production_above_capacity=max(Fraction(), max(values) - 500),
                  stock_below_reserve=max(Fraction(), 800 - min(stocks)), stock_above_capacity=max(Fraction(), max(stocks) - 4000),
                  terminal_error=abs(stock - 2000), water_error=abs(sum(values) - 2880))
    return dict(residuals={k: str(v) for k, v in errors.items()}, maximum_residual=str(max(errors.values())),
                total_water_m3=str(sum(values)), nominal_energy_kwh=str(Fraction(17, 5) * sum(values)),
                minimum_stock_m3=str(min(stocks)), maximum_stock_m3=str(max(stocks)))


def summary(values):
    a = np.asarray(values, dtype=float)
    if a.ndim != 1 or not len(a) or not np.isfinite(a).all():
        raise ValueError('Finite nonempty outcomes required')
    return dict(mean=float(a.mean()), cvar90=optimizer.cvar(a), minimum=float(a.min()), maximum=float(a.max()))


def paired(candidate, control):
    a, b = np.asarray(candidate, dtype=float), np.asarray(control, dtype=float)
    if a.shape != b.shape or a.ndim != 1 or not len(a):
        raise ValueError('Paired one-dimensional outcomes required')
    d = a - b
    return dict(**summary(d), better=int(np.count_nonzero(d < 0)), equal=int(np.count_nonzero(d == 0)),
                worse=int(np.count_nonzero(d > 0)), below_resolution=int(np.count_nonzero(np.abs(d) < 1e-5)))


def compare(reference_pairs):
    """Two references, each containing paired cost and grid arrays."""
    if set(reference_pairs) != {'weather', 'satellite'}:
        raise ValueError('Both reference families required')
    axes, risk, differences = [], [], {}
    for reference in ('weather', 'satellite'):
        differences[reference] = {}
        if set(reference_pairs[reference]) != {'cost_eur', 'grid_kwh'}:
            raise ValueError('Cost and grid axes required')
        for metric in ('cost_eur', 'grid_kwh'):
            a, b = reference_pairs[reference][metric]
            delta = paired(a, b)
            differences[reference][metric] = delta
            sa, sb = summary(a), summary(b)
            for statistic in ('mean', 'cvar90'):
                difference = sa[statistic] - sb[statistic]
                axes.append(dict(reference=reference, metric=metric, statistic=statistic, candidate=sa[statistic], control=sb[statistic],
                                 difference=difference, nonregressing=difference <= 0, strict_gain=difference < 0, below_resolution=abs(difference) < 1e-5))
            if metric == 'cost_eur':
                value = delta['cvar90']
                risk.append(dict(reference=reference, cvar90_daily_regret=value, nonregressing=value <= 0,
                                 strict_gain=value < 0, below_resolution=abs(value) < 1e-5))
    return dict(axes=axes, risk=risk, paired_differences=differences,
                all_axis_pass=all(v['nonregressing'] for v in axes) and any(v['strict_gain'] for v in axes),
                risk_only_pass=all(v['nonregressing'] for v in risk) and any(v['strict_gain'] for v in risk))


def forecast_metrics(actual, forecast):
    a, f = np.asarray(actual, dtype=float), np.asarray(forecast, dtype=float)
    if a.shape != f.shape or a.ndim != 1 or not len(a) or not np.isfinite(a).all() or not np.isfinite(f).all():
        raise ValueError('Finite matched forecast rows required')
    truth, calls = a > 600, f > 600
    tp, fp, fn, tn = (int(np.count_nonzero(mask)) for mask in
                       (truth & calls, ~truth & calls, truth & ~calls, ~truth & ~calls))
    scores = {}
    for key, numerator, denominator in (('precision', tp, tp + fp), ('recall', tp, tp + fn), ('f1', 2 * tp, 2 * tp + fp + fn)):
        value = Fraction(numerator, denominator) if denominator else None
        scores[key] = None if value is None else dict(numerator=value.numerator, denominator=value.denominator, value=float(value))
    return dict(hours=len(a), tp=tp, fp=fp, fn=fn, tn=tn, positive_calls=tp + fp, **scores,
                mae_w_m2=float(np.abs(f - a).mean()), rmse_w_m2=float(np.sqrt(np.square(f - a).mean())))
