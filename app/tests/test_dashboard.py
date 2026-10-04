"""Reproduce dashboard interactions against the generated evidence files."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def metric(app, label):
    return next(value.value for value in app.metric if value.label == label)


def slider(app, label):
    return next(value for value in app.slider if value.label == label)


def run():
    records = []
    app = AppTest.from_file(str(ROOT / "app/app.py")).run(timeout=60)
    assert not app.exception and not app.error
    assert [tab.label for tab in app.tabs] == ["Grid overview", "Forecast evidence", "Sites lab", "Assumptions & handoff"]
    assert metric(app, "Tank safety violations") == "0"
    assert metric(app, "Flagged fixture hours") == "4"
    assert any("does not beat the stronger persistence control" in value.value for value in app.warning)
    assert app.selectbox[0].value.isoformat() == "2026-07-15"
    records.append({"case": "default evidence dashboard", "status": "PASS", "metrics": {value.label: value.value for value in app.metric}, "warnings": [value.value for value in app.warning]})

    slider(app, "Tank capacity · m³").set_value(500)
    app.run(timeout=60)
    assert not app.exception and not app.error
    assert metric(app, "Tank safety violations") == "0"
    records.append({"case": "small tank", "status": "PASS", "tank_capacity_m3": 500, "illustrative_cost_reduction": metric(app, "Illustrative cost reduction"), "safety_violations": 0})

    app.toggle[0].set_value(False)
    app.run(timeout=60)
    assert not app.exception and not app.error
    assert metric(app, "Flagged fixture hours") == "0"
    records.append({"case": "no-leak control", "status": "PASS", "alerts": 0})

    app.selectbox[0].select(app.selectbox[0].options[-1])
    app.run(timeout=60)
    assert not app.exception and not app.error
    assert app.selectbox[0].value.isoformat() == "2026-09-30"
    records.append({"case": "last complete held-out date", "status": "PASS", "date": app.selectbox[0].value.isoformat()})

    slider(app, "Unit production · m³/hour").set_value(100)
    app.run(timeout=60)
    assert not app.exception
    assert len(app.error) == 1 and "infeasible" in app.error[0].value
    assert len(app.metric) == 0
    records.append({"case": "insufficient production capacity", "status": "PASS", "message": app.error[0].value, "plan_displayed": False})

    evidence = {
        "command": ".venv/bin/python tests/test_dashboard.py",
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "input_sha256": {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in ["data/test_predictions.csv", "data/paphos_weather.csv", "results/metrics.json", "app/app.py", "model/scheduler.py", "model/sites.py"]},
        "checks": records,
        "status": "PASS",
    }
    (ROOT / "results/dashboard_check.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(records)} dashboard interaction checks; results/dashboard_check.json")


if __name__ == "__main__":
    run()
