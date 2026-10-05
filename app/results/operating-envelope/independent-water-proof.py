"""Exact water balance for two frozen synthetic traces; no operating-review imports."""
from fractions import Fraction as F
import json


def replay(points):
    stock, demand, capacity, reserve, target = F(2), F(2), F(4), F(1), F(2)
    extrema = [(F(0), stock)]
    produced, intervals = F(0), []
    for (start, first), (end, last) in zip(points, points[1:]):
        width = end - start
        slope = (last - first) / width

        def inventory(offset):
            return stock + (first - demand) * offset + slope * offset * offset / 2

        if slope:
            stationary = (demand - first) / slope
            if 0 < stationary < width:
                extrema.append((start + stationary, inventory(stationary)))
        next_stock = inventory(width)
        volume = (first + last) * width / 2
        produced += volume
        intervals.append(volume / width)
        stock = next_stock
        extrema.append((end, stock))
    values = [value for _, value in extrema]
    assert min(values) >= reserve and max(values) <= capacity and stock == target
    return {
        "initial_m3": "2", "capacity_m3": str(capacity), "reserve_m3": str(reserve),
        "demand_m3_h": str(demand), "target_m3": str(target),
        "produced_m3": str(produced), "delivered_m3": str(demand * (points[-1][0] - points[0][0])),
        "unserved_m3": "0", "spilled_m3": "0", "end_m3": str(stock),
        "minimum_m3": str(min(values)), "maximum_m3": str(max(values)),
        "hourly_mean_rates_m3_h": list(map(str, intervals)),
        "extrema": [{"elapsed_h": str(t), "stock_m3": str(v)} for t, v in extrema],
    }


traces = {
    "flat": [(F(0), F(2)), (F(1), F(2)), (F(2), F(2))],
    "triangle": [(F(0), F(0)), (F(1), F(4)), (F(2), F(0))],
}
results = {name: replay(points) for name, points in traces.items()}
assert results["flat"]["hourly_mean_rates_m3_h"] == results["triangle"]["hourly_mean_rates_m3_h"] == ["2", "2"]
assert results["triangle"]["minimum_m3"] == "3/2"
assert results["triangle"]["maximum_m3"] == "5/2"
print(json.dumps({
    "kind": "synthetic_matched_water_proof", "arithmetic": "Python Fraction, exact rational arithmetic",
    "scope": "Fixed supplied analytical traces only. No plant, solar, electrical or field-benefit claim.",
    "results": results,
}, indent=2))
