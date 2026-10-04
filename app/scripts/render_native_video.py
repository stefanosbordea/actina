"""Render a separate Full HD, native 24fps Blender candidate; preserve the released film."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
WORK = Path('/Volumes/CARMIX-WORK/AquaShift-video-2026-10-02')
BLENDER = WORK / 'tools/Blender.app/Contents/MacOS/Blender'
SOURCE = ROOT / 'delivery/Blender-Scene-Source/blender_video.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(path, record):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, indent=2) + '\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmark', action='store_true', help='Render overview frames 1, 2 and 3 only')
    args = parser.parse_args()
    if not Path('/Volumes/CARMIX-WORK').is_mount():
        raise RuntimeError('Expected work volume is not mounted')
    output = WORK / 'render-native-24'
    if args.benchmark:
        output /= 'benchmark'
    output.mkdir(parents=True, exist_ok=True)
    receipt = ROOT / 'results' / ('native-render-benchmark.json' if args.benchmark else 'native-render-job.json')
    record = {'started_at_utc': now(), 'status': 'RUNNING', 'driver_pid': os.getpid(),
              'driver_sha256': sha(Path(__file__)), 'source_sha256': sha(SOURCE),
              'blender_executable': str(BLENDER), 'output': str(output),
              'requested': {'width': 1920, 'height': 1080, 'fps': 24, 'seconds_per_act': 9,
                            'samples_argument': 64, 'native_frames_per_act': 216},
              'scope': 'Symbolic concept scenes, never actual plant or recovered curtailment footage', 'acts': []}
    save(receipt, record)
    started = time.monotonic()
    for act in (('overview',) if args.benchmark else ('overview', 'storage', 'evening')):
        command = [str(BLENDER), '--background', '--python-exit-code', '1', '--python', str(SOURCE),
                   '--', '--output', str(output), '--act', act, '--width', '1920', '--height', '1080',
                   '--fps', '24', '--duration', '9', '--samples', '64']
        if args.benchmark:
            command += ['--frames', '1,2,3']
        entry = {'act': act, 'command': command, 'started_at_utc': now(), 'status': 'RUNNING'}
        record['acts'].append(entry)
        save(receipt, record)
        print(f'Rendering {act} at 1920×1080, native 24fps. Receipt: {receipt}', flush=True)
        start = time.monotonic()
        log = output / f'{act}.log'
        with log.open('w') as handle:
            process = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT)
            entry['blender_pid'] = process.pid
            save(receipt, record)
            status = process.wait()
        entry.update(exit_code=status, elapsed_seconds=time.monotonic()-start,
                     completed_at_utc=now(), log=str(log), status='PASS' if status == 0 else 'FAILED')
        if status:
            record.update(status='FAILED', elapsed_seconds=time.monotonic()-started)
            save(receipt, record)
            raise RuntimeError(f'{act} Blender exited {status}; inspect {log}')
        directory = output / act
        manifest = directory / 'render-manifest.json'
        metadata = json.loads(manifest.read_text())
        expected = [1, 2, 3] if args.benchmark else list(range(1, 217))
        if metadata['rendered_frames'] != expected:
            raise RuntimeError(f'{act}: unexpected rendered frame range')
        hashes = []
        for number in expected:
            path = directory / f'frame-{number:04d}.png'
            with path.open('rb') as handle:
                header = handle.read(24)
            if header[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>II', header[16:24]) != (1920, 1080):
                raise RuntimeError(f'Wrong image dimensions: {path}')
            hashes.append(sha(path))
        if len(set(hashes)) != len(expected):
            raise RuntimeError(f'{act}: duplicate native frames')
        entry.update(native_frame_count=len(expected), all_frames_unique=True,
                     manifest_sha256=sha(manifest), frame_sha256=hashes,
                     wall_seconds_per_frame=entry['elapsed_seconds']/len(expected))
        print(f'{act} passed: {len(expected)} unique frames, {entry["elapsed_seconds"]:.1f}s wall time.', flush=True)
        save(receipt, record)
    record.update(status='PASS', completed_at_utc=now(), elapsed_seconds=time.monotonic()-started)
    save(receipt, record)
    print(f'Native render finished. {receipt}', flush=True)


if __name__ == '__main__':
    main()
