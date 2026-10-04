"""Fixed forecast-only path distance and strictly historical paired-day pool."""
import numpy as np
import pandas as pd


def descriptor(ghi):
    values = np.asarray(ghi, dtype=np.float64)
    if values.shape != (24,) or not np.isfinite(values).all():
        raise ValueError('A finite 24-hour forecast is required')
    power = np.minimum(1700., 1.7 * np.maximum(values, 0.))
    total = 0.
    result = np.empty(24, dtype=np.float64)
    for h in range(24):
        total += float(power[h])
        result[h] = total / 3.4
    return result


def distances(history, forecast):
    history = np.asarray(history, dtype=np.float64)
    forecast = np.asarray(forecast, dtype=np.float64)
    if history.ndim != 2 or history.shape[1] != 24 or forecast.shape != (24,) or not np.isfinite(history).all() or not np.isfinite(forecast).all():
        raise ValueError('Finite historical and target descriptor vectors are required')
    result = np.zeros(len(history), dtype=np.float64)
    for h in range(24):
        result += np.abs(history[:, h] - forecast[h])
    return result / 24.


def choose(days, distance):
    distance = np.asarray(distance, dtype=np.float64)
    if distance.shape != (len(days),) or not np.isfinite(distance).all() or np.any(distance < 0) or len(set(days)) != len(days):
        raise ValueError('Distinct source days and finite nonnegative distances are required')
    if len(days) < 64:
        raise ValueError('Fewer than 64 eligible source days')
    order = np.asarray(sorted(range(len(days)), key=lambda i: (float(distance[i]), days[i])), dtype=int)
    selected = np.asarray(sorted(order[:64], key=lambda i: days[i]), dtype=int)
    rank = np.empty(len(days), dtype=int)
    rank[order] = np.arange(1, len(days) + 1)
    return selected, rank


def eligible_pool(target, nwp, weather, satellite, cutoff):
    target = pd.DatetimeIndex(target)
    arrays = [np.asarray(v, dtype=float) for v in (nwp, weather, satellite)]
    if target.hasnans or not target.is_monotonic_increasing or not target.is_unique or any(v.shape != (len(target),) for v in arrays):
        raise ValueError('Aligned unique chronological hourly source data are required')
    days, positions, records = [], [], []
    normalized = target.normalize()
    for day in sorted(set(normalized)):
        indices = np.flatnonzero(normalized == day)
        before = bool(np.all(target[indices] < cutoff))
        complete = len(indices) == 24 and list(target[indices].hour) == list(range(24)) and bool(np.all(target[indices] == pd.date_range(day, periods=24, freq='h')))
        finite = [bool(np.isfinite(v[indices]).all()) for v in arrays]
        eligible = before and complete and all(finite)
        records.append(dict(day=str(day.date()), first_endpoint=str(target[indices[0]]), last_endpoint=str(target[indices[-1]]),
            strictly_before_cutoff=before, complete_24=complete, nwp_complete=finite[0], weather_complete=finite[1], satellite_complete=finite[2], eligible=eligible))
        if eligible:
            days.append(str(day.date()))
            positions.append(indices)
    if len(days) < 64:
        raise ValueError('Fewer than 64 complete paired historical days')
    return days, np.stack(positions), records
