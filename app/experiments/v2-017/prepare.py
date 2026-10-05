"""Prepare only matched training OOF and validation features, without scoring."""
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = ROOT / "app/experiments/v2-016"


def main():
    out = HERE / "inputs"
    out.mkdir(exist_ok=False)
    sources = {}
    def read(path):
        data = path.read_bytes()
        sources[str(path.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
        return data
    def table(path, key):
        rows = list(csv.DictReader(read(path).decode().splitlines()))
        result = {row[key]: row for row in rows}
        assert len(result) == len(rows)
        return result
    old_lock = json.loads(read(OLD / "lock.json"))
    for name, expected in old_lock["sha256"].items():
        assert hashlib.sha256((OLD / name).read_bytes()).hexdigest() == expected
    completion = json.loads(read(OLD / "result/completion.json"))
    assert completion["status"] == "completed"
    for name, expected in completion["output_sha256"].items():
        assert hashlib.sha256((OLD / "result" / name).read_bytes()).hexdigest() == expected
    oof = table(OLD / "result/base-oof.csv", "origin")
    val = table(OLD / "inputs/validation-features.csv", "time")
    base_val = table(OLD / "result/validation-decisions.csv", "origin")
    old_features = table(ROOT / "app/experiments/f1-008/result/features.csv", "feature_time")
    gfs_join = table(ROOT / "app/experiments/nwp-alternative-001/result/radiation-only.csv", "feature_time")
    archive_paths = [ROOT / "app/experiments/nwp-archive-001/archive.json",
                     ROOT / "app/experiments/nwp-alternative-001/result/response.json"]
    raw = []
    for path in archive_paths:
        hourly = json.loads(read(path))["hourly"]
        raw.append(dict(zip(hourly["time"], hourly["shortwave_radiation_previous_day2"])))
        assert len(raw[-1]) == len(hourly["time"])
    requests = json.loads(read(ROOT / "app/experiments/nwp-archive-001/requests.json"))
    ecmwf_request = next(row for row in requests if row["label"] == "archive")
    gfs_request = json.loads(read(ROOT / "app/experiments/nwp-alternative-001/result/request.json"))
    assert "models=ecmwf_ifs025" in ecmwf_request["url"]
    assert "models=gfs_global" in gfs_request["url"]
    geometry_path = ROOT / "app/experiments/f1-004/geometry.py"
    read(geometry_path)
    spec = importlib.util.spec_from_file_location("geometry017", geometry_path)
    geometry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(geometry)
    common = sorted(set(oof) & set(old_features) & set(gfs_join))
    assert len(common) == 10675 and len(val) == 3566 and set(val) <= set(old_features) & set(gfs_join)
    excluded = sorted(set(oof) - set(common))
    with (out / "excluded-oof-origins.csv").open("x", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["origin", "reason"])
        writer.writerows((origin, "Before fixed existing forecast-feature coverage") for origin in excluded)
    for split, origins in (("train", common), ("validation", sorted(val))):
        records = []
        for origin in origins:
            prior = oof[origin] if split == "train" else val[origin]
            target = datetime.fromisoformat(origin) + timedelta(hours=24)
            epoch = int(target.replace(tzinfo=timezone(timedelta(hours=3))).timestamp())
            retained, joined = old_features[origin], gfs_join[origin]
            assert datetime.fromisoformat(joined["target_time"]) == target and int(joined["target_epoch_utc"]) == epoch
            ec, gfs = float(retained["nwp_day2_radiation"]), float(retained["gfs_day2_radiation"])
            assert ec == raw[0][epoch] and gfs == raw[1][epoch] == float(joined["gfs_day2_radiation_w_m2"])
            scale = float(retained["solar_scale"])
            assert abs(scale - geometry.solar_features(target)[0]) <= 1e-10 and scale >= 100
            for name in ("temperature_2m", "shortwave_radiation", "relative_humidity_2m", "cloud_cover"):
                assert float(prior[name]) == float(retained[name])
            record = dict(origin=origin, target_time=str(target), target_epoch_utc=epoch,
                base_prediction=float(prior["base_prediction"] if split == "train" else base_val[origin]["base_prediction"]),
                nwp_radiation=float(prior["nwp_radiation"]), nwp_cloud=float(prior["nwp_cloud"]),
                ecmwf_day2=ec, gfs_day2=gfs, solar_scale=scale,
                **{name: float(retained[name]) for name in ("target_hour_sin", "target_hour_cos", "target_season_sin", "target_season_cos")})
            if split == "train":
                record.update(target=float(prior["target"]), fold=int(prior["fold"]))
            assert all(math.isfinite(value) for value in record.values() if isinstance(value, float))
            records.append(record)
        with (out / f"{split}.csv").open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    for name in ("cv_predictions_v2.csv", "original-validation.csv", "fixed008-validation.csv"):
        (out / name).write_bytes(read(OLD / "inputs" / name))
    manifest = dict(source_sha256=sources,
        files={path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(out.iterdir())},
        train_rows=len(common), excluded_oof_rows=len(excluded), validation_rows=len(val),
        fold_sizes={fold: sum(oof[origin]["fold"] == str(fold) for origin in common) for fold in range(1, 7)},
        requests=dict(ecmwf=ecmwf_request["url"], gfs=gfs_request["url"]),
        checks="Direct epoch radiation equality, target +24h, fixed+03 labels, solar reconstruction and original weather-feature identity all passed. No outcome metrics computed.")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(dict(train_rows=len(common), excluded=len(excluded), validation_rows=len(val), status="PASS")))


if __name__ == "__main__":
    main()
