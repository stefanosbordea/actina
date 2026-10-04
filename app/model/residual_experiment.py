"""One exploratory June-only residual hypothesis; never rescore or replace the frozen test model."""
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.train import FEATURES, build_features, fit, issue_time_persistence, load_weather, predict
from eval.evaluate import confusion, regression


def run():
    output = ROOT / "results/june_residual_experiment"
    output.mkdir(parents=True, exist_ok=True)
    weather_path = ROOT / "data/paphos_weather.csv"
    weather = load_weather(weather_path)
    # Keep July and all later targets entirely outside this exploratory experiment.
    frame = build_features(weather[weather.index.date < date(2026, 7, 1)])
    persistence = issue_time_persistence(weather[weather.index.date < date(2026, 7, 1)], frame.index)
    frame["latest_persistence"] = persistence.baseline
    frame = frame.dropna(subset=["latest_persistence"])
    if (persistence.reindex(frame.index).baseline_source_time > frame.forecast_issue_time).any():
        raise ValueError("Residual experiment persistence exceeds issue cutoff")
    train = frame[frame.index.date < date(2026, 6, 1)]
    june = frame[(frame.index.date >= date(2026, 6, 1)) & (frame.index.date < date(2026, 7, 1))]
    direct = fit(train)
    direct_predictions = predict(direct, june)
    features = FEATURES + ["latest_persistence"]
    residual = LGBMRegressor(n_estimators=100, random_state=20260930, n_jobs=2, verbosity=-1)
    residual.fit(train[features], train.actual - train.latest_persistence)
    residual_predictions = np.maximum(0, june.latest_persistence.to_numpy() + residual.predict(june[features]))
    predictions = pd.DataFrame({"time": [t.isoformat() for t in june.index], "actual": june.actual.to_numpy(),
                                "latest_persistence": june.latest_persistence.to_numpy(),
                                "direct_model": direct_predictions, "residual_model": residual_predictions,
                                "target_cloud_cover_for_analysis_only": weather.reindex(june.index).cloud_cover.to_numpy()})
    predictions.to_csv(output / "june_predictions.csv", index=False)
    residual.booster_.save_model(str(output / "residual_june_only.txt"))
    direct.booster_.save_model(str(output / "direct_june_only.txt"))
    columns = ["latest_persistence", "direct_model", "residual_model"]
    metrics = {
        "status": "Post-hoc exploratory development after inspecting the frozen July–September result; June-only evaluation",
        "hypothesis": "Learn a correction to the latest available same-hour persistence rather than forecast radiation directly",
        "parameters": "One100tree defaultLightGBM per model; seed20260930; no search or July evaluation",
        "train_rows": len(train), "train_last_target": train.index.max().isoformat(),
        "evaluation_rows": len(june), "evaluation_first": june.index.min().isoformat(),
        "evaluation_last": june.index.max().isoformat(), "frozen_july_model_replaced": False,
        "all": {col: regression(predictions.actual, predictions[col]) for col in columns},
        "daylight": {col: regression(predictions.loc[predictions.actual > 20, "actual"],
                                      predictions.loc[predictions.actual > 20, col]) for col in columns},
        "proxy_600": {col: confusion(predictions.actual, predictions[col], 600) for col in columns},
        "cloudiness_daylight": {},
        "limitations": ["Designed after frozen test failure; this is not a new blind validation.",
                        "June was already used for threshold selection in the original experiment.",
                        "Cloudiness strata use realized target cloud cover for diagnosis only, never as features.",
                        "Reconstructed IFS data does not certify issue-time source publication availability.",
                        "A model change requires a newly frozen future blind period before any deployment superiority claim."]}
    daylight = predictions[predictions.actual > 20]
    for name, lower, upper in [("low_0_to_20_percent", 0, 20), ("medium_20_to_60_percent", 20, 60),
                               ("high_60_to_100_percent", 60, 101)]:
        part = daylight[(daylight.target_cloud_cover_for_analysis_only >= lower) &
                        (daylight.target_cloud_cover_for_analysis_only < upper)]
        metrics["cloudiness_daylight"][name] = {"rows": len(part), **{
            col: regression(part.actual, part[col]) if len(part) else None for col in columns}}
    metrics["inputs_sha256"] = {
        "weather": hashlib.sha256(weather_path.read_bytes()).hexdigest(),
        "experiment_source": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "frozen_main_checkpoint": hashlib.sha256((ROOT / "model/reference_lightgbm.txt").read_bytes()).hexdigest()}
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": metrics["status"], "train_rows": len(train), "evaluation_rows": len(june),
                      "all": metrics["all"], "daylight": metrics["daylight"],
                      "cloudiness_daylight": metrics["cloudiness_daylight"]}))


if __name__ == "__main__":
    run()
