"""Export all verified radiation targets while preserving the failed cloud intake."""
import csv
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUT=HERE/'result'
RAW_SHA='e41f4d3fbc498d4fb6e6be7706af3090904124291c2528cf55d2e9c9a4f14d19'
JOIN_SHA='6a201331af1ef8d8220251397cad86b1eccde0bf6b337f55c051442fd8039644'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    assert sha(OUT/'response.json')==RAW_SHA and sha(OUT/'diagnostic-join.csv')==JOIN_SHA
    with (OUT/'diagnostic-join.csv').open() as stream:rows=list(csv.DictReader(stream))
    fields=['feature_time','target_time','target_epoch_utc','valid_time_utc','radiation_interval_start_utc','gfs_day2_radiation_w_m2']
    assert len(rows)==17832 and all(math.isfinite(float(r[fields[-1]])) and float(r[fields[-1]])>=0 for r in rows)
    assert len(set(r['feature_time'] for r in rows))==len(rows)
    with (OUT/'radiation-only.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows({k:r[k] for k in fields} for r in rows)
    assert sha(OUT/'response.json')==RAW_SHA and sha(OUT/'diagnostic-join.csv')==JOIN_SHA
    result={'status':'RADIATION_ONLY_READY','prepared_at_utc':datetime.now(timezone.utc).isoformat(),'rows':len(rows),'missing_radiation':0,'invalid_radiation':0,'excluded_column':'All cloud values; eight out-of-range raw percentages preserved separately.','original_two_variable_intake_status':'FAILED','scores_computed':0,'models_fitted':0,'extra_data_requests':0,'source_raw_sha256':RAW_SHA,'source_diagnostic_join_sha256':JOIN_SHA,'radiation_only_protocol_sha256':sha(HERE/'RADIATION-ONLY.md'),'script_sha256':sha(Path(__file__)),'radiation_only_csv_sha256':sha(OUT/'radiation-only.csv')}
    with (OUT/'radiation-only-receipt.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
