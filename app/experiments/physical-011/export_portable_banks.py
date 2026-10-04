"""Export Unicode timestamps without loading the original object member."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
NUMERIC=('residuals','permutations','source_positions','weather','satellite','nwp')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main(out):
    report=json.loads((HERE/'result/report.json').read_text())
    if report['status']!='COMPLETE':raise ValueError('Wait for immutable completed run')
    target_path=ROOT/'app/experiments/f1-006/result/feature-targets.csv'
    pins=json.loads((HERE/'inputs.json').read_text())
    if sha(target_path)!=pins[str(target_path.relative_to(ROOT))]:raise ValueError('Pinned target source changed')
    with target_path.open() as stream:targets=list(csv.DictReader(stream))
    out.mkdir(exist_ok=False)
    receipt=dict(recorded_at_utc=datetime.now(timezone.utc).isoformat(),command=[sys.executable,*sys.argv],utility_sha256=sha(Path(__file__)),
                 purpose='Metadata-only portability export. Original object member is never loaded. No optimizer or scoring is invoked.',
                 target_source_sha256=sha(target_path),stages={})
    for stage in ('validation','test'):
        source=HERE/'result'/stage/'bank.npz'
        before=sha(source)
        with np.load(source,allow_pickle=False) as bank:
            if set(bank.files)!=set(NUMERIC)|{'source_target_time'}:raise ValueError('Unexpected bank schema')
            values={name:bank[name] for name in NUMERIC}
        positions=values['source_positions']
        if positions.shape!=(64,24) or not np.issubdtype(positions.dtype,np.integer) or np.any((positions<0)|(positions>=len(targets))):raise ValueError('Invalid source positions')
        strings=[targets[int(p)]['target_time'] for p in positions.reshape(-1)]
        if any(len(t)!=19 for t in strings):raise ValueError('Unexpected target timestamp format')
        timestamps=np.asarray(strings,dtype='U19').reshape(64,24)
        destination=out/f'{stage}-bank-portable.npz'
        np.savez_compressed(destination,**values,source_target_time=timestamps)
        with np.load(destination,allow_pickle=False) as portable:
            for name in NUMERIC:
                if portable[name].dtype!=values[name].dtype or not np.array_equal(portable[name],values[name]):raise AssertionError('Numerical member changed')
            if portable['source_target_time'].dtype.kind!='U' or not np.array_equal(portable['source_target_time'],timestamps):raise AssertionError('Unicode identity failed')
        if sha(source)!=before:raise AssertionError('Original bank changed')
        receipt['stages'][stage]=dict(original_sha256=before,portable_sha256=sha(destination),source_positions_shape=list(positions.shape),
                                    numerical_members_unchanged=list(NUMERIC),timestamp_dtype=str(timestamps.dtype),timestamps_reconstructed_from_pinned_rows=len(strings))
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt['stages']))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=HERE/'portable')
    main(parser.parse_args().out.resolve())
