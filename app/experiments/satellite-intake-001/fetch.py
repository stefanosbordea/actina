"""Check a pinned satellite reference's availability; never score a model."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
DAYS = ("2025-12-10", "2026-07-03", "2026-10-01")
SOURCES = [
    "https://open-meteo.com/en/docs/satellite-radiation-api",
    "https://github.com/open-meteo/open-meteo/blob/main/Sources/App/Controllers/ForecastapiController.swift",
    "https://doi.org/10.5676/EUM_SAF_CM/SARAH/V003",
]


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def inspect(raw):
    value = json.loads(raw)
    if value.get("utc_offset_seconds") != 0:
        raise ValueError("Expected UTC labels")
    hourly = value["hourly"]
    times, radiation = hourly["time"], hourly["shortwave_radiation"]
    if len(times) != 24 or len(radiation) != 24 or len(set(times)) != 24:
        raise ValueError("Expected 24 distinct hourly values, including nulls")
    if any(type(t) is not int for t in times) or any(b-a != 3600 for a,b in zip(times,times[1:])):
        raise ValueError("Invalid UTC hour sequence")
    if value["hourly_units"]["shortwave_radiation"] != "W/m²":
        raise ValueError("Unexpected radiation units")
    if any(v is not None and (isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or v<0) for v in radiation):
        raise ValueError("Invalid radiation")
    return {"hours":24, "nulls":sum(v is None for v in radiation),
            "first_epoch":times[0], "last_epoch":times[-1],
            "returned_grid":{k:value.get(k) for k in ["latitude","longitude","elevation"]}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    out=parser.parse_args().output
    out.mkdir(parents=True,exist_ok=False)
    protocol={"created_at_utc":now(),"script_sha256":digest(Path(__file__).read_bytes()),
        "question":"Availability and schema of a satellite-derived reference for future independent-data comparisons; no forecast scoring.",
        "days":list(DAYS),"model":"eumetsat_sarah3","latitude":34.7744,"longitude":32.4229,
        "units":"W/m²","interval":"preceding-hour mean","timezone":"UTC",
        "selection":"Three dates fixed before intake: existing winter/July clock-check days and a recent date at least two days old. No selection by radiation or errors.",
        "limits":["Satellite retrieval is an estimate, not a local ground sensor.",
            "Returned product/version and interpolation must be reviewed before reference use.",
            "No comparison, target replacement or original dataset modification in this intake.",
            "These samples alone do not establish full-period availability or source independence."],
        "sources":SOURCES}
    save(out/"protocol.json",protocol)
    results=[]
    for day in DAYS:
        query={"latitude":34.7744,"longitude":32.4229,"start_date":day,"end_date":day,
               "hourly":"shortwave_radiation","models":"eumetsat_sarah3","timezone":"GMT","timeformat":"unixtime"}
        url="https://satellite-api.open-meteo.com/v1/archive?"+urllib.parse.urlencode(query)
        record={"day":day,"url":url,"started_at_utc":now()}
        try:
            with urllib.request.urlopen(url,timeout=45) as response:
                raw=response.read(2*1024*1024+1)
                record.update(http_status=response.status,headers=dict(response.headers),finished_at_utc=now())
            if len(raw)>2*1024*1024:
                raise ValueError("Response exceeds 2 MiB limit")
            (out/(day+".json")).write_bytes(raw)
            record.update(bytes=len(raw),sha256=digest(raw),**inspect(raw))
            expected=int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())
            if record["first_epoch"]!=expected:
                raise ValueError("Returned date differs from request")
            record["status"]="SCHEMA_VERIFIED"
        except (OSError,ValueError,KeyError,TypeError) as error:
            record.update(status="FAILED",error=str(error),finished_at_utc=now())
        save(out/(day+"-receipt.json"),record)
        results.append(record)
    summary={"status":"PASS" if all(r["status"]=="SCHEMA_VERIFIED" for r in results) else "INCOMPLETE",
        "forecast_metrics_calculated":False,"results":results}
    save(out/"summary.json",summary)
    print(json.dumps({"status":summary["status"],"samples":[{k:r.get(k) for k in ("day","status","hours","nulls","returned_grid","error")} for r in results]}))
    return 0 if summary["status"]=="PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
