"""Render a silent, 60-second screenshot walkthrough through pinned BridgeClip."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
APP = HERE.parents[1]
STATES = [('01-home.png', 6), ('02-summer.png', 9), ('03-summer-cost.png', 6),
          ('04-winter.png', 8), ('05-winter-cost.png', 6), ('06-change.png', 9),
          ('07-benchmark.png', 8), ('08-experiments.png', 8)]
WIDTH, HEIGHT, FPS = 1600, 900, 30
OUTPUT_WIDTH, OUTPUT_HEIGHT = 1920, 1080


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(path):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames',
        '-show_entries', 'format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,nb_read_frames',
        '-of', 'json', str(path)], text=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--captures', type=Path, default=HERE / 'captures')
    parser.add_argument('--bridgeclip', type=Path, required=True)
    parser.add_argument('--deps', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=HERE.parent / 'Aktina-Backup.mp4')
    parser.add_argument('--work-dir', type=Path, default=HERE / 'render')
    args = parser.parse_args()
    output = args.output.absolute()
    work = args.work_dir.absolute()
    if output.exists() or output.with_suffix('.bridgeclip.json').exists() or work.exists():
        raise ValueError('Use new output and work paths; existing evidence is preserved')
    captures = HERE / 'captures'
    captures.mkdir(exist_ok=True)
    timeline, clock = [], 0
    for name, duration in STATES:
        source = args.captures / name
        if not source.exists():
            source = source.with_suffix('.jpg')
        media = probe(source)['streams']
        if len(media) != 1 or media[0]['codec_name'] not in ('png', 'mjpeg') or (media[0]['width'], media[0]['height']) != (WIDTH, HEIGHT):
            raise ValueError(f'Expected an actual {WIDTH}×{HEIGHT} PNG or JPEG: {source}')
        retained = captures / Path(name).with_suffix('.png' if media[0]['codec_name'] == 'png' else '.jpg')
        if retained.exists() and sha(retained) != sha(source):
            raise ValueError(f'Retained capture differs: {name}')
        if not retained.exists():
            shutil.copy2(source, retained)
        timeline.append(dict(file='captures/' + retained.name, start_seconds=clock, duration_seconds=duration,
                             sha256=sha(retained), image_codec=media[0]['codec_name']))
        clock += duration
    if clock != 60:
        raise ValueError('Timeline must last exactly 60 seconds')
    if len({item['sha256'] for item in timeline}) != len(STATES):
        raise ValueError('Expected eight distinct interface captures')
    work.mkdir(parents=True)
    commands = []

    def run(argv, log):
        commands.append(argv)
        print(log, flush=True)
        with (work / log).open('x') as stream:
            subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT, check=True)

    sequence = work / 'sequence.ffconcat'
    sequence.write_text('ffconcat version 1.0\n' + ''.join(
        f"file '{(HERE / item['file']).as_posix()}'\nduration {item['duration_seconds']}\n" for item in timeline)
        + f"file '{(HERE / timeline[-1]['file']).as_posix()}'\n")
    master = work / 'screenshot-master.mp4'
    run(['ffmpeg', '-v', 'warning', '-nostdin', '-n', '-protocol_whitelist', 'file,pipe,fd',
         '-f', 'concat', '-safe', '0', '-i', str(sequence), '-vf', 'scale=1920:1080:flags=lanczos,fps=30,format=yuv420p',
         '-filter_threads', '1', '-frames:v', '1800', '-an', '-c:v', 'libx264', '-preset', 'medium',
         '-crf', '17', '-threads', '2', '-movflags', '+faststart', '-map_metadata', '-1', str(master)], 'compose.log')
    adapter = APP / 'scripts/export_bridgeclip_showcase.py'
    run([sys.executable, str(adapter), '--source', str(master), '--output', str(output),
         '--bridgeclip', str(args.bridgeclip.resolve()), '--deps', str(args.deps.resolve()), '--keep', '0:60'], 'bridgeclip.log')
    media = probe(output)
    streams = media['streams']
    if len(streams) != 1 or streams[0]['codec_type'] != 'video':
        raise ValueError('Final movie must contain one video stream and no audio')
    video = streams[0]
    expected = dict(codec_name='h264', width=OUTPUT_WIDTH, height=OUTPUT_HEIGHT, r_frame_rate='30/1', nb_read_frames='1800')
    if any(video[key] != value for key, value in expected.items()) or abs(float(media['format']['duration']) - 60) > .001:
        raise ValueError(f'Unexpected picture or clock: {media}')
    run(['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-i', str(output), '-f', 'null', '-'], 'decode.log')
    for item in timeline:
        if sha(HERE / item['file']) != item['sha256']:
            raise ValueError('Capture changed during export')
    for source_name, retained_name in [('LICENSE', 'BridgeClip-LICENSE.txt'), ('engine/LICENSE', 'BridgeClip-engine-LICENSE.txt')]:
        shutil.copyfile(args.bridgeclip / source_name, HERE / retained_name)
    receipt = dict(schema=1, status='EXPORTED_AND_DECODED', description='Actual-interface screenshot walkthrough; not a live interaction recording.',
        width=OUTPUT_WIDTH, height=OUTPUT_HEIGHT, capture_width=WIDTH, capture_height=HEIGHT,
        scaling='1600×900 captures upscaled to 1920×1080 with Lanczos; pinned BridgeClip minimum landscape size is 1080p.',
        fps=FPS, duration_seconds=clock, frames=1800, audio_tracks=0,
        timeline=timeline, output=dict(path=str(output), sha256=sha(output), probe=media),
        adapter_sha256=sha(adapter), compositor_sha256=sha(Path(__file__)), commands=commands,
        presentation='Eight uncropped screenshots, readable holds and hard cuts; no synthetic cursor, overlays, voice, music or added branding.',
        verification=dict(full_decode='passed', captures_unchanged=True, no_audio=True))
    (work / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'status': receipt['status'], 'output': str(output), 'sha256': sha(output), 'bytes': output.stat().st_size}), flush=True)


if __name__ == '__main__':
    main()
