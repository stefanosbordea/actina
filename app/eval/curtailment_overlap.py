"""Retrospective timing overlap with EAC windows; never recovered plant energy."""
import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from model.scheduler import KWH_PER_M3, schedule_day

ROOT = Path(__file__).resolve().parents[1]
TANKS = (500, 1000, 2000, 4000, 8000)


def window_weights(windows):
    """Fraction of each local hour in non-overlapping same-day Group 1 windows."""
    weights = np.zeros(24)
    previous_end = -1
    for window in sorted(windows, key=lambda w: w["start_local"]):
        start = dt.datetime.strptime(window["start_local"], "%H:%M")
        end = dt.datetime.strptime(window["end_local"], "%H:%M")
        a, b = start.hour * 60 + start.minute, end.hour * 60 + end.minute
        if a >= b or a < previous_end:
            raise ValueError("Group 1 windows must be ordered, distinct and inside the same day")
        previous_end = b
        weights += np.array([max(0, min(b, (h + 1) * 60) - max(a, h * 60)) / 60 for h in range(24)])
    return weights


def load_in_window(energy_kwh, weights):
    energy_kwh = np.asarray(energy_kwh, dtype=float)
    if energy_kwh.shape != (24,) or not np.isfinite(energy_kwh).all() or (energy_kwh < -1e-6).any():
        raise ValueError("Expected 24 finite, nonnegative hourly energy values")
    return float(np.dot(energy_kwh, weights))


def main():
    source = ROOT / "data/eac_curtailment_days.json"
    reports = json.loads(source.read_text())
    forecast_file, weather_file = ROOT / "data/test_predictions.csv", ROOT / "data/paphos_weather.csv"
    predictions, weather = pd.read_csv(forecast_file), pd.read_csv(weather_file)
    for frame in (predictions, weather):
        frame["stamp"] = pd.to_datetime(frame.time, utc=True).dt.tz_convert("Europe/Nicosia")
        frame["date"] = frame.stamp.dt.date.astype(str)
    rows = []
    for day in reports["days"]:
        p = predictions[predictions.date == day["date"]].sort_values("stamp")
        w = weather[weather.date == day["date"]].sort_values("stamp")
        if len(p) != 24 or len(w) != 24 or not p.stamp.reset_index(drop=True).equals(w.stamp.reset_index(drop=True)):
            raise ValueError(f"Weather/reference hours differ: {day['date']}")
        weights = window_weights(day["windows"])
        day["hour_overlap_fraction"] = weights.tolist()
        day["overlap"] = []
        for tank in TANKS:
            loads = {}
            for label, values in [("reference", p.predicted), ("persistence", p.baseline), ("price_only", np.zeros(24))]:
                result = schedule_day(values.to_numpy() if isinstance(values, pd.Series) else values, p.actual.to_numpy(), w.temperature_2m.to_numpy(), tank_capacity=tank)
                loads[label] = load_in_window(result["frame"].energy_kwh, weights)
                if result["totals"]["safety_violations"] or abs(result["totals"]["energy_kwh"] - result["totals"]["baseline_energy_kwh"]) > 1e-6:
                    raise ValueError("Scenario comparison lost matched energy or safety")
            flat = load_in_window(np.full(24, 120 * KWH_PER_M3), weights)
            entry = {"tank_m3": tank, "reference_load_kwh": loads["reference"], "flat_load_kwh": flat,
                     "persistence_load_kwh": loads["persistence"], "price_only_load_kwh": loads["price_only"],
                     "reference_minus_flat_kwh": loads["reference"] - flat,
                     "reference_minus_price_only_kwh": loads["reference"] - loads["price_only"]}
            day["overlap"].append(entry)
            rows.append({"date": day["date"], "window_hours": float(weights.sum()), **entry})
    reports["overlap_scope"] = "Existing scenario plant electricity scheduled during retrospectively reported Group 1 windows, assuming uniform within-hour load and Cyprus civil time; temporal coincidence only. Grid access, locally available renewable power, dispatch permission and actual recovery are not established."
    reports["overlap_decision_inputs"] = "EAC windows are evaluation inputs only and never enter the reference scheduler. Assumed tariffs remain unchanged."
    (ROOT / "data/eac_curtailment_days.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n")
    evidence_path = ROOT / "data/research_evidence.json"
    evidence = json.loads(evidence_path.read_text())
    evidence["daily"] = reports
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    frame = pd.DataFrame(rows)
    frame.to_csv(ROOT / "results/curtailment-overlap.csv", index=False)
    totals = frame.groupby("tank_m3")[["reference_load_kwh", "flat_load_kwh", "persistence_load_kwh", "price_only_load_kwh"]].sum()
    record = {"checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "command": ".venv/bin/python -m eval.curtailment_overlap", "days": len(reports["days"]), "matched_cases": len(rows), "scope": reports["overlap_scope"], "decision_inputs": reports["overlap_decision_inputs"], "summed_kwh_by_tank": totals.to_dict(orient="index"), "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "data/grid-reports/eac-report-sources.json", forecast_file, weather_file, ROOT / "model/scheduler.py", ROOT / "eval/curtailment_overlap.py")}}
    (ROOT / "results/curtailment-overlap.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({k: v for k, v in record.items() if k not in ("source_sha256", "summed_kwh_by_tank")}, indent=2))


if __name__ == "__main__":
    main()
