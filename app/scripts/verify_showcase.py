"""Check the delivered film against its composition and retain visual evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw

from build_showcase import BEATS, DURATION, FPS, H, W, frame


def run(args):
    return subprocess.run(args, capture_output=True, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    probe = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(args.video)]).stdout)
    video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    sound = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
    assert (video['width'], video['height'], video['r_frame_rate']) == (W, H, f'{FPS}/1')
    assert abs(float(probe['format']['duration']) - DURATION) < .08
    assert sound['channels'] == 2
    run(['ffmpeg', '-v', 'error', '-xerror', '-threads', '2', '-i', str(args.video), '-f', 'null', '-'])
    samples = (2.5, 8, 16, 22, 26, 29, 33, 37, 46, 51, 59, 68, 75, 81)
    board = Image.new('RGB', (1440, 292 * 5), '#222222')
    comparisons = []
    for index, seconds in enumerate(samples):
        raw = run(['ffmpeg', '-v', 'error', '-threads', '2', '-ss', str(seconds), '-i', str(args.video),
                   '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']).stdout
        decoded = np.frombuffer(raw, np.uint8).reshape((H, W, 3))
        expected = np.asarray(frame(seconds))
        error = float(np.abs(decoded.astype(np.int16) - expected.astype(np.int16)).mean())
        assert error < 6, (seconds, error)
        comparisons.append({'second': seconds, 'mean_absolute_channel_error_255': round(error, 4)})
        still = Image.fromarray(decoded)
        still.save(args.output / f'frame-{seconds:05.1f}.jpg', quality=92)
        still.thumbnail((480, 270))
        x, y = index % 3 * 480, index // 3 * 292
        board.paste(still, (x, y))
        ImageDraw.Draw(board).text((x + 10, y + 273), f'{seconds:g}s', fill='white')
    board.save(args.output / 'contact-sheet.jpg', quality=92)
    audio = run(['ffmpeg', '-hide_banner', '-threads', '2', '-i', str(args.video),
                 '-vn', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-']).stderr.decode()
    levels, _ = json.JSONDecoder().raw_decode(audio[audio.rfind('{'):])
    assert float(levels['input_tp']) <= 0
    with args.video.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    receipt = {'status': 'PASS', 'video': str(args.video.resolve()), 'sha256': digest,
               'bytes': args.video.stat().st_size, 'probe': probe, 'complete_decode': 'PASS',
               'frame_comparisons': comparisons, 'audio_levels': levels,
               'audio_source': 'Original deterministic instrumental synthesis in build_showcase.py; no voice source',
               'beats': BEATS, 'limits': 'Real interface still captures with composited camera motion; illustrative cases; sampled visual comparison does not claim human full-film viewing.'}
    (args.output / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'seconds': DURATION, 'bytes': receipt['bytes'], 'sha256': digest,
                      'audio_lufs': levels['input_i'], 'audio_true_peak_db': levels['input_tp']}))


if __name__ == '__main__':
    main()
