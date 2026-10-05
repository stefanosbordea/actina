"""Download real gridded IFS historical weather; retain raw response and provenance."""
import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["shortwave_radiation", "cloud_cover", "temperature_2m",
          "relative_humidity_2m", "et0_fao_evapotranspiration", "precipitation"]


def fetch(start="2024-07-01", end="2026-09-30", output=ROOT / "data"):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    local = ZoneInfo("Asia/Nicosia")
    first = datetime.fromisoformat(start).replace(tzinfo=local)
    stop = (datetime.fromisoformat(end) + timedelta(days=1)).replace(tzinfo=local)
    params = {"latitude": 34.7754, "longitude": 32.4245,
              "start_date": first.astimezone(timezone.utc).date().isoformat(),
              "end_date": (stop.astimezone(timezone.utc) - timedelta(hours=1)).date().isoformat(),
              "hourly": ",".join(FIELDS), "models": "ecmwf_ifs", "timezone": "UTC"}
    url = "https://archive-api.open-meteo.com/v1/archive?" + urlencode(params)
    with urlopen(url, timeout=120) as response:
        raw = response.read()
    payload = json.loads(raw)
    hours = payload["hourly"]
    if any(len(hours[k]) != len(hours["time"]) for k in FIELDS):
        raise ValueError("API arrays have different lengths")
    rows = []
    missing = []
    for i, stamp in enumerate(hours["time"]):
        utc = datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc)
        stamp_local = utc.astimezone(local)
        if first <= stamp_local < stop:
            values = [hours[field][i] for field in FIELDS]
            if any(x is None or not math.isfinite(float(x)) for x in values):
                missing.append(stamp_local.isoformat())
            rows.append([stamp_local.isoformat()] + values)
    raw_path = output / "open_meteo_ifs_raw.json"
    raw_path.write_bytes(raw)
    if missing:
        raise ValueError(f"{len(missing)} incomplete hourly records; first {missing[:3]}. Raw response retained.")
    expected = int((stop.astimezone(timezone.utc) - first.astimezone(timezone.utc)).total_seconds() / 3600)
    if len(rows) != expected:
        raise ValueError(f"Expected {expected} continuous hourly records, found {len(rows)}")
    csv_path = output / "paphos_weather.csv"
    with csv_path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["time"] + FIELDS)
        writer.writerows(rows)
    metadata = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "url": url,
        "documentation": "https://open-meteo.com/en/docs/historical-weather-api",
        "source": "Open-Meteo historical API, ECMWF IFS gridded historical reconstruction",
        "model": "ecmwf_ifs", "requested_coordinates": [34.7754, 32.4245],
        "returned_coordinates": [payload["latitude"], payload["longitude"]],
        "elevation_m": payload.get("elevation"), "units": payload["hourly_units"],
        "requested_local_start": start, "requested_local_end": end,
        "rows": len(rows), "first_time": rows[0][0], "last_time": rows[-1][0],
        "timezone": "Asia/Nicosia", "raw_timezone": payload["timezone"],
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "attribution": "Weather data by Open-Meteo and ECMWF. CC BY 4.0; API used for non-commercial prototype.",
        "limitations": ["Gridded model estimates, not Paphos sensor measurements.",
                        "Historical reconstruction is not a forecast archive or original publication vintage.",
                        "Shortwave radiation is the preceding-hour mean; it is not measured grid curtailment.",
                        "IFS upgrades can affect comparability across dates."]}
    (output / "weather_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({"rows": len(rows), "first": rows[0][0], "last": rows[-1][0],
                      "raw_sha256": metadata["raw_sha256"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2024-07-01")
    parser.add_argument("--end", default="2026-09-30")
    parser.add_argument("--output", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    fetch(args.start, args.end, args.output)
