"""Independently recompute the reference comparison from frozen source files."""
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def rows(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    inputs = json.loads((HERE / "inputs.json").read_text())
    for name, identity in inputs["inputs"].items():
        raw = (ROOT / name).read_bytes()
        assert len(raw) == identity["bytes"]
        assert hashlib.sha256(raw).hexdigest() == identity["sha256"], name
    report = json.loads((HERE / "result-amended/report.json").read_text())
    hourly = json.loads((HERE.parent / "satellite-reference-001/result/response.json").read_text())["hourly"]
    satellite = dict(zip(hourly["time"], hourly["shortwave_radiation"], strict=True))
    assert len(satellite) == len(hourly["time"])
    checked = 0
    for split, source_name in (("validation", "cv_predictions.csv"), ("test", "test_predictions.csv")):
        source = rows(ROOT / "eval" / source_name)
        # UTC is recovered independently from the origin; do not use the report's joined CSV.
        epochs = [int((datetime.fromisoformat(r["time"]).replace(tzinfo=timezone(timedelta(hours=3)))
                       + timedelta(hours=24)).timestamp()) for r in source]
        weather = [float(r["actual"]) for r in source]
        truth = [satellite[t] for t in epochs]
        common = [i for i, y in enumerate(truth) if y is not None]
        result = report["splits"][split]
        assert result["coverage"]["original_hours"] == len(source)
        assert result["coverage"]["scored_hours"] == len(common)
        cross = Counter(f"weather{int(weather[i] > 600)}_satellite{int(truth[i] > 600)}" for i in common)
        assert all(cross[k] == v for k, v in result["reference_event_cross_tabulation"].items())
        for method, bases in result["methods"].items():
            predictions = rows(HERE.parent / "f1-004/result/predictions" / f"{split}-{method}.csv")
            assert len(predictions) == len(source)
            assert [r["feature_time"] for r in predictions] == [r["time"] for r in source]
            points = [float(r["point_w_m2"]) for r in predictions]
            decisions = [float(r["probability"]) > .5 if method in ("analogue_raw", "analogue_solar", "global_residual")
                         else float(r["point_w_m2"]) > 600 for r in predictions]
            for basis, actual in bases.items():
                indexes = range(len(source)) if basis == "weather_full" else common
                reference = truth if basis == "satellite_common" else weather
                confusion = Counter((reference[i] > 600, decisions[i]) for i in indexes)
                tp, fp, fn, tn = (confusion[k] for k in ((True, True), (False, True), (True, False), (False, False)))
                errors = [points[i] - reference[i] for i in indexes]
                expected = dict(hours=len(errors), tp=tp, fp=fp, fn=fn, tn=tn,
                    precision=tp / (tp + fp) if tp + fp else None,
                    recall=tp / (tp + fn) if tp + fn else None,
                    f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
                    mae=math.fsum(map(abs, errors)) / len(errors),
                    rmse=math.sqrt(math.fsum(e * e for e in errors) / len(errors)))
                for key, value in expected.items():
                    assert actual[key] is None if value is None else math.isclose(actual[key], value, rel_tol=1e-12, abs_tol=1e-12), (split, method, basis, key)
                checked += 1
    print(json.dumps({"status": "PASS", "comparisons_recomputed": checked,
        "frozen_inputs_verified": len(inputs["inputs"]),
        "report_sha256": hashlib.sha256((HERE / "result-amended/report.json").read_bytes()).hexdigest(),
        "review_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
