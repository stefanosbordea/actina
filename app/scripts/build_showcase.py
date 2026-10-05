"""Compose the 84-second music-only AquaShift film from retained real captures."""
import argparse
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WORK = Path('/Volumes/CARMIX-WORK/AquaShift-video-2026-10-02')
BUILD = WORK / 'showcase-bridgeclip'
ASSETS = BUILD / 'assets'
W, H, FPS, DURATION, RATE = 1920, 1080, 24, 84, 48000
FONT = '/System/Library/Fonts/HelveticaNeue.ttc'
FFMPEG = '/opt/homebrew/bin/ffmpeg'
WHITE, MUTED = '#f5f5f3', '#a4a4a4'
BEATS = [
    (0, 5, 'identity', 'AquaShift'),
    (5, 13, 'overview', 'Use surplus solar.'),
    (13, 20, 'storage', 'Store water for later.'),
    (20, 24, 'evening', 'Supply it when needed.'),
    (24, 31, 'reading', 'Start with\nthe reading.'),
    (31, 40, 'remaining', 'Test the\nremaining hours.'),
    (40, 48, 'returned', 'Review\nthe return.'),
    (48, 54, 'fair', 'Keep the\ncomparison fair.'),
    (54, 64, 'solar', 'Count the\nsolar used.'),
    (64, 72, 'limit', 'Check\nthe limit.'),
    (72, 78, 'evidence', 'Keep\nthe evidence.'),
    (78, 84, 'close', 'AquaShift'),
]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def smooth(x):
    x = max(0, min(1, x))
    return x * x * (3 - 2 * x)


@lru_cache(maxsize=30)
def font(size, bold=False):
    return ImageFont.truetype(FONT, size, index=int(bold))


@lru_cache(maxsize=8)
def source(path):
    with Image.open(path) as image:
        return image.convert('RGB')


def text(image, words, xy, size=32, fill=WHITE, bold=False, center=False):
    draw = ImageDraw.Draw(image)
    x, y = xy
    for line in words.split('\n'):
        px = x - draw.textlength(line, font=font(size, bold)) / 2 if center else x
        draw.text((round(px), round(y)), line, font=font(size, bold), fill=fill)
        y += size * 1.14


def panel(image, filename, crop, x, y, width, progress=0):
    picture = source(str(ASSETS / filename)).crop(crop)
    height = round(picture.height / picture.width * width)
    picture = picture.resize((width, height), Image.Resampling.LANCZOS)
    # A restrained camera move; screenshot content remains unchanged.
    image.paste(picture, (round(x + 18 * (1 - smooth(progress))), round(y)))


def label(image, words):
    draw = ImageDraw.Draw(image)
    text(image, words, (1830 - draw.textlength(words, font=font(24)), 76), 24, MUTED)


def bottom_gradient(image):
    overlay = Image.new('RGBA', image.size)
    draw = ImageDraw.Draw(overlay)
    for y in range(790, H):
        draw.line((0, y, W, y), fill=(0, 0, 0, round(215 * smooth((y - 790) / 280))))
    return Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB')


def frame(seconds):
    start, end, kind, title = next(beat for beat in BEATS if beat[0] <= seconds < beat[1])
    local, progress = seconds - start, (seconds - start) / (end - start)
    image = Image.new('RGB', (W, H), 'black')
    if kind in ('identity', 'close'):
        number = min(120, max(1, int(local * FPS) + 1))
        image = source(str(BUILD / 'symbol' / f'frame-{number:04d}.png')).copy()
        text(image, 'AquaShift', (960, 737), 96, bold=True, center=True)
        if kind == 'identity':
            text(image, 'Solar power into water.', (960, 867), 34, MUTED, center=True)
        else:
            text(image, 'Concept and working prototype', (960, 867), 32, MUTED, center=True)
            text(image, 'aquashift-pafos-2026.vercel.app', (960, 945), 27, center=True)
    elif kind in ('overview', 'storage', 'evening'):
        native = kind != 'evening'
        folder = WORK / ('render-native-24' if native else 'render-monochrome') / kind
        number = (min(216 if kind == 'overview' else 185, int(local * FPS) + 1) if native
                  else min(108, 36 + int(local * 12)))
        image = source(str(folder / f'frame-{number:04d}.png')).resize((W, H), Image.Resampling.LANCZOS)
        image = bottom_gradient(image)
        text(image, title, (88, 903), 76, bold=True)
        label(image, 'Concept illustration')
        if kind == 'overview':
            text(image, 'Desalination using otherwise-curtailed solar, where plant and grid conditions allow.', (93, 1001), 25, MUTED)
    else:
        label(image, 'Synthetic readings / 1 July' if kind in ('reading', 'remaining') else 'Illustrative comparison / 15 July')
        text(image, title, (88, 179), 76, bold=True)
        if kind == 'reading':
            text(image, '2,300', (88, 493), 142, bold=True)
            text(image, 'm³ in the tank at 12:00', (94, 666), 30, MUTED)
            text(image, 'First available at 12:02', (94, 734), 26, MUTED)
            if local < 4:
                panel(image, 'pilot-observations.png', (30, 1158, 930, 1696), 745, 301, 1080, progress)
            else:
                panel(image, 'observation-ledger.png', (30, 1460, 680, 1740), 745, 389, 1080, progress)
            text(image, 'Recorded time. Known availability. Gaps retained.', (94, 989), 25, MUTED)
        elif kind == 'remaining':
            outage = local >= 3.5
            panel(image, 'remaining-plan-outage.png' if outage else 'remaining-plan.png',
                  (30, 435, 680, 945), 840, 226, 990, progress)
            text(image, '640' if outage else '12:00', (88, 493), 142, bold=True)
            text(image, 'm³ below the end target' if outage else 'Start from the tank reading', (94, 666), 30, MUTED)
            text(image, 'After a four-hour production stop' if outage else '2,300 m³ starting water', (94, 741), 26, MUTED)
            text(image, 'Reserve and water service still hold in this case.' if outage else 'Assess the supplied plan from this point forward.',
                 (94, 990), 25, MUTED)
        elif kind == 'returned':
            picture = 'review-matched-full.png' if local < 2.5 else 'review-matched-noon.png' if local < 4.5 else 'review-matched-13.png'
            panel(image, picture, (24, 234, 694, 724), 740, 198, 1090, progress)
            text(image, 'Original\nReturned', (94, 553), 42)
            text(image, 'One case. One starting point.', (94, 761), 28, MUTED)
            text(image, 'Supplied example plans / no schedule generated by this review', (94, 990), 24, MUTED)
        elif kind == 'fair':
            panel(image, 'review-matched-full.png', (24, 724, 694, 972), 740, 433, 1090, progress)
            for y, number, unit in [(485, '2,880', 'm³ water served'), (652, '2,000', 'm³ at the end'), (819, '9,792', 'kWh total load')]:
                text(image, number, (93, y), 62, bold=True)
                text(image, unit, (98, y + 80), 26, MUTED)
            text(image, 'The same totals in both plans.', (790, 898), 31, MUTED)
        elif kind in ('solar', 'limit'):
            limited = kind == 'limit'
            panel(image, 'review-saturated-full.png' if limited else 'review-matched-full.png',
                  (25, 1032, 935, 1375), 745, 423, 1090, progress)
            text(image, '0' if limited else '+340', (88, 451), 159, bold=True)
            text(image, 'additional solar kWh' if limited else 'modeled solar kWh', (94, 645), 31, MUTED)
            text(image, '408 to 408 kWh' if limited else '408 to 748 kWh', (94, 742), 36)
            text(image, 'Allocation already fully used.' if limited else '9,792 kWh total load in both plans.', (94, 879), 28, MUTED)
            text(image, 'Same production shift. A different solar allocation.' if limited else 'A shared, declared plant allocation. Not measured recovery.',
                 (94, 990), 25, MUTED)
        elif kind == 'evidence':
            panel(image, 'review-export-ready.png', (24, 112, 935, 835), 840, 202, 970, progress)
            text(image, 'Export.\nReopen.\nRecalculate.', (94, 535), 46)
            text(image, 'Exact inputs and the decision travel together.', (94, 989), 25, MUTED)
    # Deliberate short fades, with long clean reading holds between cuts.
    fade = min(smooth(local / .32), smooth((end - seconds) / .28))
    if fade < 1:
        image = Image.blend(Image.new('RGB', (W, H), 'black'), image, fade)
    return image


def music():
    output = BUILD / 'score.wav'
    if output.exists():
        return output
    # Original deterministic instrumental score: soft harmonics, pulse, no voice source.
    rng = np.random.default_rng(20261002)
    length = DURATION * RATE
    left, right = np.zeros(length, np.float32), np.zeros(length, np.float32)
    chords = [(146.832, 220, 293.665, 329.628), (174.614, 261.626, 349.228, 440),
              (116.541, 174.614, 233.082, 293.665), (130.813, 195.998, 261.626, 349.228)]
    def add(start, seconds, frequencies, gain, decay=None, pan=.5):
        a, count = round(start * RATE), round(seconds * RATE)
        count = min(count, length - a)
        if count <= 0:
            return
        t = np.arange(count, dtype=np.float32) / RATE
        envelope = np.minimum(1, t / (.03 if decay else 1.8)) * np.minimum(1, (seconds - t) / (1 if decay else 2.4))
        if decay:
            envelope *= np.exp(-t / decay)
        samples = np.zeros(count, np.float32)
        for frequency in frequencies:
            samples += (np.sin(2 * np.pi * frequency * t) + .17 * np.sin(2 * np.pi * frequency * 2 * t)) / len(frequencies)
        samples *= envelope * gain
        left[a:a+count] += samples * math.sqrt(1 - pan)
        right[a:a+count] += samples * math.sqrt(pan)
    for index, start in enumerate(range(0, DURATION, 8)):
        add(start, 11, chords[index % 4], .19, pan=.45)
        add(start + .055, 10.9, [f * 1.0015 for f in chords[index % 4]], .13, pan=.65)
    for index, start in enumerate(np.arange(8, 77, .75)):
        chord = chords[int(start // 8) % 4]
        if start >= 24:
            add(float(start), 1.35, [chord[index % 4] * 2], .10, decay=.31, pan=.25 if index % 2 else .75)
        if index % 2 == 0:
            add(float(start), .7, [chord[0] / 2], .13, decay=.24)
        if start >= 31 and index % 2:
            a, n = round(start * RATE), int(.075 * RATE)
            noise = rng.standard_normal(n).astype(np.float32)
            noise[1:] -= .85 * noise[:-1].copy()
            noise *= np.exp(-np.arange(n) / (RATE * .011)) * .009
            left[a:a+n] += noise
            right[a:a+n] += noise
    ramp = np.minimum(1, np.arange(length) / (RATE * 2)) * np.minimum(1, (length - np.arange(length)) / (RATE * 3))
    stereo = np.column_stack((left * ramp, right * ramp)).astype('float32')
    subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-n', '-f', 'f32le', '-ar', str(RATE), '-ac', '2',
                    '-i', '-', '-af', 'loudnorm=I=-20:TP=-2:LRA=9', '-ar', str(RATE), '-c:a', 'pcm_s16le', str(output)],
                   input=stereo.tobytes(), check=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    if not Path('/Volumes/CARMIX-WORK').is_mount():
        raise RuntimeError('The external render volume is not mounted')
    (BUILD / 'previews').mkdir(exist_ok=True)
    if args.preview:
        for second in (2.5, 8, 16, 22, 26, 29, 33, 37, 46, 51, 59, 68, 75, 81):
            frame(second).save(BUILD / 'previews' / f'{second:05.1f}.png')
        return
    output = BUILD / 'AquaShift-Showcase-master.mp4'
    if output.exists():
        raise FileExistsError(output)
    soundtrack = music()
    command = [FFMPEG, '-hide_banner', '-loglevel', 'warning', '-n', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
               '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-i', str(soundtrack), '-map', '0:v', '-map', '1:a',
               '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-threads', '2', '-pix_fmt', 'yuv420p',
               '-c:a', 'aac', '-b:a', '256k', '-t', str(DURATION), '-movflags', '+faststart',
               '-metadata', 'title=AquaShift — Product Showcase', str(output)]
    with (BUILD / 'master-render.log').open('w') as log:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log)
        try:
            for index in range(FPS * DURATION):
                process.stdin.write(frame(index / FPS).tobytes())
                if index % (FPS * 8) == 0:
                    print(f'Composed {index // FPS}/{DURATION} seconds', flush=True)
            process.stdin.close()
            if process.wait() != 0:
                raise RuntimeError('Master encoder failed; see master-render.log')
        except BaseException:
            process.kill()
            process.wait()
            raise
    receipt = {'completed_at_utc': datetime.now(timezone.utc).isoformat(), 'duration_s': DURATION, 'fps': FPS,
               'size': [W, H], 'command': command, 'source_sha256': sha(__file__), 'master_sha256': sha(output),
               'master_bytes': output.stat().st_size, 'soundtrack_sha256': sha(soundtrack), 'voice_sources': [],
               'beats': BEATS, 'capture_sha256': {p.name: sha(p) for p in ASSETS.iterdir() if p.is_file()},
               'source_notes': 'Real current built-in-browser screenshots, native Blender symbol/overview/storage; evening concept upscaled from retained 720p/12fps. No invented operational results.'}
    (BUILD / 'composition.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(output)


if __name__ == '__main__':
    main()
