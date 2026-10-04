"""Reproduce the provided schedule in isolated directories; never alter root inputs."""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "app/handoff/scheduler-reproduction"
INPUTS = ["model/scheduler.py", "data/paphos_weather_data.csv",
          "eval/cv_predictions.csv", "eval/test_predictions.csv", "eval/schedule_hourly.csv"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(expected, actual):
    assert expected.columns.equals(actual.columns)
    assert expected["time"].equals(actual["time"])
    result = {}
    for column in expected.columns.drop("time"):
        a, b = expected[column].to_numpy(), actual[column].to_numpy()
        assert np.isfinite(a).all() and np.isfinite(b).all()
        same = np.isclose(a, b, atol=1e-8, rtol=0)
        result[column.strip()] = {
            "matching_rows": int(same.sum()), "different_rows": int((~same).sum()),
            "max_absolute_difference": float(np.abs(a - b).max()),
        }
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    identities = {name: digest(ROOT / name) for name in INPUTS}
    provided = pd.read_csv(ROOT / "eval/schedule_hourly.csv")
    source = (ROOT / "model/scheduler.py").read_text()
    selector = 'list(day["predicted"])'
    assert source.count(selector) == 1
    report = {"input_sha256": identities, "rows": len(provided), "runs": {}}
    for name, script in [("unchanged-model", source),
                         ("persistence-control", source.replace(selector, 'list(day["baseline"])'))]:
        with tempfile.TemporaryDirectory(prefix="aktina-scheduler-") as temp:
            work = Path(temp)
            for relative in INPUTS[1:4]:
                destination = work / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, destination)
            (work / "scheduler.py").write_text(script)
            run = subprocess.run([sys.executable, "scheduler.py"], cwd=work,
                                 capture_output=True, text=True, timeout=180)
            (OUT / f"{name}.log").write_text(run.stdout + run.stderr)
            if run.returncode:
                raise RuntimeError(f"{name} failed ({run.returncode}); see saved log")
            generated = work / "eval/schedule_hourly.csv"
            shutil.copyfile(generated, OUT / f"{name}.csv")
            report["runs"][name] = {
                "exit_code": run.returncode,
                "script_sha256": hashlib.sha256(script.encode()).hexdigest(),
                "source_change": None if name == "unchanged-model" else
                    'Only forecast selector: day["predicted"] to day["baseline"]',
                "output_sha256": digest(generated),
                "comparison_to_provided": compare(provided, pd.read_csv(generated)),
                "stdout": run.stdout,
            }
    assert identities == {name: digest(ROOT / name) for name in INPUTS}
    report["original_inputs_unchanged"] = True
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
