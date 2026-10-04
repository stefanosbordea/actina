"""Matched v2-dependent context heads, with and without additional weather forecasts."""
import os
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "2"
from datetime import datetime, timezone
from fractions import Fraction
import argparse
import importlib.util
import json
from pathlib import Path
import resource
import signal
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INPUTS = HERE / "inputs"
helper_path = HERE.parent / "v2-016/run.py"
spec = importlib.util.spec_from_file_location("helpers016", helper_path)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
np, pd = h.np, h.pd
ARMS = ("core", "expanded")
CORE = ["v2_margin", "day1_minus_v2", "day1_cloud", "v2_solar_ratio",
        "target_hour_sin", "target_hour_cos", "target_season_sin", "target_season_cos"]
EXTRA = ["ecmwf_minus_v2", "gfs_minus_v2", "forecast_disagreement"]


def features(frame, arm):
    base = frame["base_prediction"]
    out = pd.DataFrame({"v2_margin": (base - 600) / 100,
        "day1_minus_v2": (frame["nwp_radiation"] - base) / 100,
        "day1_cloud": frame["nwp_cloud"] / 100,
        "v2_solar_ratio": base / frame["solar_scale"],
        **{name: frame[name] for name in CORE[4:]}}, index=frame.index)
    assert (frame["solar_scale"] >= 100).all()
    if arm == "expanded":
        out["ecmwf_minus_v2"] = (frame["ecmwf_day2"] - base) / 100
        out["gfs_minus_v2"] = (frame["gfs_day2"] - base) / 100
        out["forecast_disagreement"] = np.abs(frame["gfs_day2"] - frame["ecmwf_day2"]) / 100
    else:
        assert arm == "core"
    assert list(out) == CORE + (EXTRA if arm == "expanded" else [])
    assert np.isfinite(out.to_numpy()).all()
    return out


def select(truth, probability, raw_ecmwf):
    cap = h.counts(truth, raw_ecmwf)["fp"]
    rows = []
    for tick in range(10, 191):
        row = dict(tick=tick, threshold=tick / 200, **h.counts(truth, probability > tick / 200))
        row["raw_ecmwf_fp_cap"] = cap
        row["eligible"] = row["fp"] <= cap and row["f1_exact"] is not None
        rows.append(row)
    eligible = [row for row in rows if row["eligible"]]
    chosen = max(eligible, key=lambda row: (Fraction(row["f1_exact"]), -abs(row["tick"] - 100), row["tick"])) if eligible else None
    return chosen, rows


def verify():
    lock = json.loads((HERE / "lock.json").read_text())
    for name, expected in lock["source_sha256"].items():
        assert h.sha(ROOT / name) == expected, name
    return lock


def intervals(index, truth, calls, admitted):
    dates = (index + h.DAY).normalize()
    days = dates.unique()
    draws = np.random.default_rng(17017).integers(0, len(days), size=(2000, len(days)))
    f1 = {}
    for name, call in calls.items():
        blocks = np.array([[np.sum(truth[dates == day] & call[dates == day]),
                            np.sum(~truth[dates == day] & call[dates == day]),
                            np.sum(truth[dates == day] & ~call[dates == day])]
                           for day in days], dtype=np.int64)
        total = blocks[draws].sum(axis=1)
        denominator = 2 * total[:, 0] + total[:, 1] + total[:, 2]
        f1[name] = np.divide(2 * total[:, 0], denominator, where=denominator != 0,
                             out=np.full(len(denominator), np.nan))
    result = {}
    for arm in admitted:
        for control in ("core", "base_refit", "supplied_v2_600", "supplied_v2_562", "fixed008"):
            if arm == control or control not in calls:
                continue
            delta = f1[arm] - f1[control]
            finite = delta[np.isfinite(delta)]
            result[f"{arm}_minus_{control}"] = dict(
                lower_025=float(np.quantile(finite, .025)) if len(finite) else None,
                upper_975=float(np.quantile(finite, .975)) if len(finite) else None,
                undefined_replicates=int(np.sum(~np.isfinite(delta))))
    return dict(seed=17017, replicates=2000, target_day_blocks=len(days), comparisons=result,
                limit="Descriptive paired historical-day intervals, without repeated-validation or selection-bias correction.")


def run(out):
    verify()
    train = h.load_frame(INPUTS / "train.csv", "origin")
    validation = h.load_frame(INPUTS / "validation.csv", "origin")
    assert len(train) == 10675 and len(validation) == 3566
    assert "target" not in validation and "fold" not in validation
    assert (train.index + h.DAY).max() < validation.index.min()
    assert pd.DatetimeIndex(pd.to_datetime(train["target_time"])).equals(train.index + h.DAY)
    assert pd.DatetimeIndex(pd.to_datetime(validation["target_time"])).equals(validation.index + h.DAY)
    truth = train["target"].to_numpy() > 600
    held_union = train["fold"].to_numpy() >= 3
    selected, final_models, fits = {}, {}, []
    for arm in ARMS:
        x = features(train, arm)
        probabilities = pd.Series(np.nan, index=train.index)
        for fold in range(3, 7):
            held = train["fold"] == fold
            first = train.index[held][0]
            fit = (train["fold"].to_numpy() < fold) & h.permitted(train.index, first)
            assert (train.index[fit] + h.DAY).max() < first
            model = h.fit_head("boosted", x.loc[fit], truth[fit])
            model.booster_.save_model(str(out / f"{arm}-fold{fold}.txt"))
            probabilities.loc[held] = model.predict_proba(x.loc[held])[:, 1]
            membership = pd.DataFrame({"origin": train.index.astype(str), "target_time": (train.index + h.DAY).astype(str),
                                      "fit": np.asarray(fit, dtype=int), "held": held.to_numpy(dtype=int)})
            membership.to_csv(out / f"{arm}-fold{fold}-membership.csv", index=False)
            fits.append(dict(arm=arm, fold=fold, fit_rows=int(fit.sum()), held_rows=int(held.sum()),
                fit_target_last=str((train.index[fit] + h.DAY).max()), held_origin_first=str(first)))
        assert np.array_equal(probabilities.notna().to_numpy(), held_union)
        choice, grid = select(truth[held_union], probabilities.to_numpy()[held_union],
                              train["ecmwf_day2"].to_numpy()[held_union] > 600)
        selected[arm] = choice
        pd.DataFrame(grid).to_csv(out / f"{arm}-thresholds.csv", index=False)
        pd.DataFrame({"origin": train.index.astype(str), "fold": train["fold"].to_numpy(), "truth": truth.astype(int),
                      "forward_probability": probabilities.to_numpy()}).to_csv(out / f"{arm}-forward.csv", index=False)
        if choice is not None:
            final_models[arm] = h.fit_head("boosted", x, truth)
            final_models[arm].booster_.save_model(str(out / f"{arm}-final.txt"))
            pd.DataFrame({"feature": x.columns,
                "gain_importance": final_models[arm].booster_.feature_importance(importance_type="gain"),
                "split_importance": final_models[arm].booster_.feature_importance(importance_type="split")}).to_csv(
                    out / f"{arm}-importance.csv", index=False)
        h.log(f"{arm}: training selection {choice}")
    prediction = pd.DataFrame({"base_prediction": validation["base_prediction"]}, index=validation.index)
    for arm, model in final_models.items():
        p = model.predict_proba(features(validation, arm))[:, 1]
        assert np.isfinite(p).all() and np.all((p >= 0) & (p <= 1))
        prediction[f"{arm}_probability"] = p
        prediction[f"{arm}_call"] = (p > selected[arm]["threshold"]).astype(int)
    prediction.to_csv(out / "validation-decisions.csv", index_label="origin")
    frozen = {path.name: h.sha(path) for path in out.iterdir() if path.suffix == ".txt"}
    frozen["validation-decisions.csv"] = h.sha(out / "validation-decisions.csv")
    h.save(out / "policy-freeze.json", dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        lock_sha256=h.sha(HERE / "lock.json"), selected_training_thresholds=selected, fits=fits,
        feature_names={arm: list(features(train, arm)) for arm in ARMS}, frozen_files_sha256=frozen,
        note="No validation outcome file has been parsed. Inadmissible arms have no event decisions."))
    assert all(h.sha(out / name) == expected for name, expected in frozen.items())
    h.log("Policy/model/decision freeze saved. One validation scoring pass begins.")
    supplied = h.load_frame(INPUTS / "cv_predictions_v2.csv")
    original = h.load_frame(INPUTS / "original-validation.csv")
    fixed008 = h.load_frame(INPUTS / "fixed008-validation.csv", "feature_time")
    for frame in (supplied, original, fixed008):
        assert frame.index.equals(validation.index)
    assert np.array_equal(supplied["actual"], original["actual"])
    assert np.array_equal(supplied["actual"], fixed008["weather_actual_w_m2"])
    assert np.array_equal(supplied["baseline"], original["baseline"])
    assert np.allclose(supplied["forecast"], validation["nwp_radiation"], rtol=0, atol=1e-12)
    actual = supplied["actual"].to_numpy()
    truth = actual > 600
    radiation = dict(base_refit=validation["base_prediction"].to_numpy(),
        supplied_v2_600=supplied["predicted"].to_numpy(), supplied_v2_562=supplied["predicted"].to_numpy(),
        supplied_raw_day1=supplied["forecast"].to_numpy(), retained_raw_day2=validation["ecmwf_day2"].to_numpy(),
        persistence=supplied["baseline"].to_numpy())
    calls = {name: value > (562 if name == "supplied_v2_562" else 600) for name, value in radiation.items()}
    calls["fixed008"] = fixed008["predicted_positive"].to_numpy(dtype=bool)
    calls.update({arm: prediction[f"{arm}_call"].to_numpy(dtype=bool) for arm in final_models})
    metrics = {}
    for name, call in calls.items():
        row = h.counts(truth, call)
        if name in radiation:
            row.update(h.regression(actual, radiation[name]))
        elif name in final_models:
            row.update(h.probability_metrics(truth, prediction[f"{name}_probability"].to_numpy()))
            row["unchanged_base_radiation_errors"] = h.regression(actual, radiation["base_refit"])
        metrics[name] = row
    assert metrics["fixed008"]["f1_exact"] == "271/299" and metrics["supplied_v2_600"]["f1_exact"] == "524/593"
    record = prediction.copy()
    record["actual"] = actual
    record["target_time"] = (validation.index + h.DAY).astype(str)
    for name, call in calls.items():
        record[f"call_{name}"] = call.astype(int)
    for name, values in radiation.items():
        record[f"radiation_{name}"] = values
    record.to_csv(out / "validation-evaluation.csv", index_label="origin")
    uncertainty = intervals(validation.index, truth, calls, final_models)
    h.save(out / "day-bootstrap.json", uncertainty)
    comparisons = {}
    for arm in ARMS:
        if arm not in final_models:
            comparisons[arm] = dict(status="inadmissible", reason="No training threshold met the declared false-positive constraint")
            continue
        better = Fraction(metrics[arm]["f1_exact"]) > Fraction(metrics["fixed008"]["f1_exact"])
        comparisons[arm] = dict(status="evaluated", user_gate=better and metrics[arm]["fp"] <= metrics["fixed008"]["fp"],
            higher_f1_than_008=better, no_additional_fp_vs_008=metrics[arm]["fp"] <= metrics["fixed008"]["fp"],
            higher_f1_than_both_supplied_v2=all(Fraction(metrics[arm]["f1_exact"]) > Fraction(metrics[k]["f1_exact"])
                                             for k in ("supplied_v2_600", "supplied_v2_562")),
            deltas={control: {key: h.metric_difference(metrics[arm][key], metrics[control][key])
                             for key in ("tp", "fp", "fn", "precision", "recall", "f1")}
                    for control in ("core", "base_refit", "fixed008", "supplied_v2_600", "supplied_v2_562")
                    if control in metrics and control != arm})
    h.save(out / "summary.json", dict(status="completed", train_oof_hours=len(train), validation_hours=len(actual),
        metrics=metrics, selected_training_thresholds=selected, comparisons=comparisons,
        note="Exploratory reused validation. Training FP constraint is not a validation guarantee. No base refit, validation threshold selection, test scoring or promotion."))
    assert all(h.sha(out / name) == expected for name, expected in frozen.items())
    verify()
    h.log(json.dumps(dict(metrics=metrics, comparisons=comparisons), allow_nan=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="result")
    args = parser.parse_args()
    out = HERE / args.out
    assert out.parent == HERE and out.name not in ("inputs", "review")
    verify()
    out.mkdir(exist_ok=False)
    start, cpu = time.monotonic(), time.process_time()
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("1800-second budget exceeded")))
    signal.alarm(1800)
    h.save(out / "environment.json", dict(command=sys.argv, started_at_utc=datetime.now(timezone.utc).isoformat(),
        python=sys.version, versions={name: h.version(name) for name in ("numpy", "pandas", "lightgbm", "scikit-learn")},
        thread_cap=2, lock_sha256=h.sha(HERE / "lock.json")))
    status, failure = "completed", None
    try:
        with h.threadpool_limits(limits=2):
            run(out)
    except BaseException as error:
        status, failure = "failed", repr(error)
        (out / "failure.txt").write_text(traceback.format_exc())
        raise
    finally:
        signal.alarm(0)
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
        h.save(out / "completion.json", dict(status=status, error=failure,
            completed_at_utc=datetime.now(timezone.utc).isoformat(), wall_seconds=time.monotonic() - start,
            cpu_seconds=time.process_time() - cpu, peak_rss_bytes=rss,
            output_sha256={p.name: h.sha(p) for p in sorted(out.iterdir()) if p.is_file()}))


if __name__ == "__main__":
    main()
