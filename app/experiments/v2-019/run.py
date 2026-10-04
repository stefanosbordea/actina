"""Two fixed logistic event heads on frozen v2/weather/context features."""
import os
for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[name] = "2"
import argparse
from datetime import datetime, timezone
from fractions import Fraction
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
SOURCE = HERE.parent / "v2-017"
CONTEXT = HERE.parent / "v2-018/result"
spec = importlib.util.spec_from_file_location("method017", SOURCE / "run.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
h, np, pd = m.h, m.np, m.pd
ARMS = ("core", "expanded")
ERROR_FEATURES = ["past_v2_bias", "past_v2_mae", "past_ecmwf_bias", "past_ecmwf_mae"]


def verify():
    lock = json.loads((HERE / "lock.json").read_text())
    for name, expected in lock["source_sha256"].items():
        assert h.sha(ROOT / name) == expected, name


def features(frame, ctx, arm):
    base = m.features(frame, "expanded")
    assert ctx.index.equals(frame.index) and list(ctx) == ERROR_FEATURES
    assert np.isfinite(ctx.to_numpy()).all()
    if arm == "core":
        return base
    assert arm == "expanded"
    return pd.concat([base, ctx], axis=1)


def save_model(model, columns, path):
    assert model.classes_.tolist() == [False, True]
    h.save(path, dict(features=list(columns), coefficients=model.coef_[0].tolist(),
        intercept=float(model.intercept_[0]), classes=model.classes_.tolist(),
        iterations=int(model.n_iter_[0]), parameters=model.get_params()))


def run(out):
    verify()
    train = h.load_frame(SOURCE / "inputs/train.csv", "origin")
    validation = h.load_frame(SOURCE / "inputs/validation.csv", "origin")
    train_context = h.load_frame(CONTEXT / "training-context.csv", "origin")
    assert len(train) == 10675 and len(validation) == 3566
    assert (train.index + h.DAY).max() < validation.index.min()
    truth = train["target"].to_numpy() > 600
    held_union = train["fold"].to_numpy() >= 3
    models, choices, fits = {}, {}, []
    for arm in ARMS:
        x = features(train, train_context, arm)
        forward = pd.Series(np.nan, index=train.index)
        for fold in range(3, 7):
            held = train["fold"] == fold
            first = train.index[held][0]
            fit = (train["fold"].to_numpy() < fold) & h.permitted(train.index, first)
            assert (train.index[fit] + h.DAY).max() < first
            model = h.fit_head("logistic", x.loc[fit], truth[fit])
            save_model(model, x.columns, out / f"{arm}-fold{fold}.json")
            forward.loc[held] = model.predict_proba(x.loc[held])[:, 1]
            pd.DataFrame({"origin": train.index.astype(str), "target_time": (train.index + h.DAY).astype(str),
                "fit": np.asarray(fit, dtype=int), "held": held.to_numpy(dtype=int)}).to_csv(
                    out / f"{arm}-fold{fold}-membership.csv", index=False)
            fits.append(dict(arm=arm, fold=fold, fit_rows=int(fit.sum()), held_rows=int(held.sum()),
                fit_target_last=str((train.index[fit] + h.DAY).max()), held_origin_first=str(first)))
        assert np.array_equal(forward.notna().to_numpy(), held_union)
        choice, table = m.select(truth[held_union], forward.to_numpy()[held_union],
                                train["ecmwf_day2"].to_numpy()[held_union] > 600)
        choices[arm] = choice
        pd.DataFrame(table).to_csv(out / f"{arm}-thresholds.csv", index=False)
        pd.DataFrame({"origin": train.index.astype(str), "fold": train["fold"].to_numpy(), "truth": truth.astype(int),
                      "forward_probability": forward.to_numpy()}).to_csv(out / f"{arm}-forward.csv", index=False)
        if choice is not None:
            models[arm] = h.fit_head("logistic", x, truth)
            save_model(models[arm], x.columns, out / f"{arm}-final.json")
        h.log(f"{arm}: fixed logistic training selection {choice}")
    frozen_models = {p.name: h.sha(p) for p in out.iterdir() if p.suffix == ".json" and p.name != "environment.json"}
    h.save(out / "head-freeze.json", dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        lock_sha256=h.sha(HERE / "lock.json"), selected_training_thresholds=choices, fits=fits,
        models_sha256=frozen_models, note="Fits/thresholds frozen before loading the saved sequential validation context."))
    h.log("HEAD_FREEZE saved. Reading unchanged strictly-past validation context from018.")
    validation_context = h.load_frame(CONTEXT / "validation-context.csv", "origin")
    decisions = pd.DataFrame({"base_prediction": validation["base_prediction"]}, index=validation.index)
    for arm, model in models.items():
        probability = model.predict_proba(features(validation, validation_context, arm))[:, 1]
        assert np.isfinite(probability).all()
        decisions[f"{arm}_probability"] = probability
        decisions[f"{arm}_call"] = (probability > choices[arm]["threshold"]).astype(int)
    decisions.to_csv(out / "validation-decisions.csv", index_label="origin")
    decision_sha = h.sha(out / "validation-decisions.csv")
    h.save(out / "decision-freeze.json", dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        head_freeze_sha256=h.sha(out / "head-freeze.json"), validation_decisions_sha256=decision_sha,
        context_sha256=h.sha(CONTEXT / "validation-context.csv"),
        note="Predictions fixed before full-reference scoring. Context includes strictly past validation observations.",))
    h.log("DECISION_FREEZE saved. Full-reference validation scoring begins.")
    supplied = h.load_frame(SOURCE / "inputs/cv_predictions_v2.csv")
    original = h.load_frame(SOURCE / "inputs/original-validation.csv")
    fixed008 = h.load_frame(SOURCE / "inputs/fixed008-validation.csv", "feature_time")
    for frame in (supplied, original, fixed008):
        assert frame.index.equals(validation.index)
    assert np.array_equal(supplied["actual"], original["actual"])
    assert np.array_equal(supplied["actual"], fixed008["weather_actual_w_m2"])
    actual = supplied["actual"].to_numpy()
    truth = actual > 600
    radiation = dict(base_refit=validation["base_prediction"].to_numpy(),
        supplied_v2_600=supplied["predicted"].to_numpy(), supplied_v2_562=supplied["predicted"].to_numpy(),
        supplied_raw_day1=supplied["forecast"].to_numpy(), retained_raw_day2=validation["ecmwf_day2"].to_numpy(),
        persistence=supplied["baseline"].to_numpy())
    calls = {name: values > (562 if name == "supplied_v2_562" else 600) for name, values in radiation.items()}
    calls["fixed008"] = fixed008["predicted_positive"].to_numpy(dtype=bool)
    calls.update({arm: decisions[f"{arm}_call"].to_numpy(dtype=bool) for arm in models})
    metrics = {}
    for name, call in calls.items():
        row = h.counts(truth, call)
        if name in radiation:
            row.update(h.regression(actual, radiation[name]))
        elif name in models:
            row.update(h.probability_metrics(truth, decisions[f"{name}_probability"].to_numpy()))
            row["unchanged_base_radiation_errors"] = h.regression(actual, radiation["base_refit"])
        metrics[name] = row
    assert metrics["fixed008"]["f1_exact"] == "271/299" and metrics["supplied_v2_600"]["f1_exact"] == "524/593"
    record = decisions.copy()
    record["actual"] = actual
    record["target_time"] = (validation.index + h.DAY).astype(str)
    for name, call in calls.items():
        record[f"call_{name}"] = call.astype(int)
    for name, values in radiation.items():
        record[f"radiation_{name}"] = values
    record.to_csv(out / "validation-evaluation.csv", index_label="origin")
    h.save(out / "day-bootstrap.json", m.intervals(validation.index, truth, calls, models))
    comparisons = {}
    for arm in ARMS:
        if arm not in models:
            comparisons[arm] = dict(status="inadmissible")
            continue
        comparisons[arm] = dict(status="evaluated",
            user_gate=Fraction(metrics[arm]["f1_exact"]) > Fraction(metrics["fixed008"]["f1_exact"]) and metrics[arm]["fp"] <= metrics["fixed008"]["fp"],
            deltas={control: {key: h.metric_difference(metrics[arm][key], metrics[control][key]) for key in ("tp", "fp", "fn", "precision", "recall", "f1")}
                    for control in ("core", "base_refit", "fixed008", "supplied_v2_600", "supplied_v2_562")
                    if control in metrics and control != arm})
    h.save(out / "summary.json", dict(status="completed", validation_hours=len(actual), metrics=metrics,
        selected_training_thresholds=choices, comparisons=comparisons,
        note="Bounded exploratory logistic replacement. Unchanged v2 curve and causal context. No test scoring or fresh-holdout claim."))
    assert h.sha(out / "validation-decisions.csv") == decision_sha
    assert all(h.sha(out / name) == digest for name, digest in frozen_models.items())
    verify()
    h.log(json.dumps(dict(metrics=metrics, comparisons=comparisons), allow_nan=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="result")
    args = parser.parse_args()
    out = HERE / args.out
    assert out.parent == HERE and out.name != "review"
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
