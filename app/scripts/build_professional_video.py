"""Build the narrated concept/prototype film from Blender motion and real UI captures."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import math
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WORK = Path('/Volumes/CARMIX-WORK/AquaShift-video-2026-10-02')
BUILD = WORK / 'composition'
RENDERS = WORK / 'render-monochrome'
OUT = ROOT / 'delivery'
CAPTURE_DIR = OUT / 'professional-frames'
NATIVE_24 = False
FPS, W, H, DURATION, RATE = 24, 1920, 1080, 90, 48000
FFMPEG, FFPROBE = '/opt/homebrew/bin/ffmpeg', '/opt/homebrew/bin/ffprobe'
FONT = Path('/System/Library/Fonts/Supplemental')
NAVY, TEAL, MINT, GOLD, WHITE = '#0D0D0D', '#DADADA', '#B2B2B2', '#F0F0F0', '#F7F7F7'
SEGMENTS = [
    (0, 5, 'title', 'Solar power into water.', 'AquaShift. Solar power into water. Water stored for later.'),
    (5, 14, 'overview', 'Use otherwise curtailed solar.', 'When solar would otherwise be curtailed, the idea is to use it for desalination, where plant and grid conditions allow.'),
    (14, 23, 'storage', 'Store water. Use it later.', 'Make fresh water during that window. Store it in a tank. Use the water later, when people need it.'),
    (23, 32, 'evening', 'Stored water. Later demand.', "That's the concept. These are illustrations. No real curtailed solar has been recovered by this prototype."),
    (32, 42, 'grid', 'Inspect a day. Change the plan.', 'Here is the working draft. Choose a date, change the tank size, and inspect the proposed schedule.'),
    (42, 51, 'schedule', 'Same water. Same energy.', 'Same water. Same energy. In this scenario, the cost falls because of the assumed hourly prices.'),
    (51, 59, 'tank', 'Less storage. Less flexibility.', 'With less storage, there is less room to shift production. Water supply still comes first.'),
    (59, 69, 'forecast', 'Check the forecast.', 'In average error, the reference loses to the stronger simple control. Added AI value is unproven.'),
    (69, 77, 'sites', 'Water budget. Meter checks.', 'Sites tests an irrigation budget and an injected leak. The meter data is simulated.'),
    (77, 84, 'next', 'Next: connect real inputs.', 'Next: real grid signals, plant limits, water demand and tariffs. Then test the benefit.'),
    (84, 90, 'credits', 'A starting point for the team.', "Loucas's concept. Stefanos's expanded roadmap. An AI-assisted draft."),
]
SCREEN_FILES = {'grid': 'overview.jpg', 'schedule': 'operations.jpg',
                'tank': 'scenarios.jpg', 'forecast': 'evaluation.jpg', 'sites': 'alerts-sites.jpg'}
# Each window is an unaltered crop of the actual public workspace screenshot.
# The two endpoints pan from the explanatory cards to their supporting charts.
CROPS = {'grid': ((0, 0, 1280, 720), (0, 0, 1280, 720)),
         'schedule': ((250, 280, 1245, 840), (250, 325, 1245, 885)),
         'tank': ((250, 645, 1245, 1205), (250, 715, 1245, 1275)),
         'forecast': ((250, 415, 1245, 975), (250, 440, 1245, 1000)),
         'sites': ((250, 350, 1245, 910), (250, 605, 1245, 1165))}
PUBLIC_URL = 'https://aquashift-pafos-2026.vercel.app'
REVISION_URL = 'https://aquashift-pafos-2026-77qeepxuc-dlukels-projects.vercel.app'


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font(size, bold=False):
    return ImageFont.truetype(str(FONT / ('Arial Bold.ttf' if bold else 'Arial.ttf')), size)


FONTS = {(s, b): font(s, b) for s in (24, 28, 30, 32, 36, 38, 42, 50, 64, 70, 86, 112) for b in (False, True)}


def txt(draw, xy, text, size=36, fill=WHITE, bold=False):
    draw.text(xy, text, font=FONTS[size, bold], fill=fill)


def wrapped(text, size, width):
    draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    lines, line = [], ''
    for word in text.split():
        trial = f'{line} {word}'.strip()
        if line and draw.textlength(trial, font=FONTS[size, False]) > width:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


def caption_lines(text):
    lines = wrapped(text, 42, 1710)
    if len(lines) == 2:
        words = text.split()
        draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        choices = []
        for i in range(1, len(words)):
            a, b = ' '.join(words[:i]), ' '.join(words[i:])
            widths = [draw.textlength(s, font=FONTS[42, False]) for s in (a, b)]
            if max(widths) <= 1710:
                choices.append((abs(widths[0]-widths[1]), a, b))
        lines = list(min(choices)[1:])
    assert len(lines) <= 2, text
    return lines


CAPTIONS = {kind: caption_lines(narration) for _, _, kind, _, narration in SEGMENTS}


def ease(x):
    x = min(1, max(0, x))
    return x * x * (3 - 2 * x)


def timestamp(seconds):
    milliseconds = round(seconds * 1000)
    return f'{milliseconds//3600000:02}:{milliseconds//60000%60:02}:{milliseconds//1000%60:02},{milliseconds%1000:03}'


def prepare_audio():
    timeline = np.zeros(DURATION * RATE, dtype=np.float32)
    timings = []
    for i, (start, end, kind, _, narration) in enumerate(SEGMENTS):
        text_path, aiff = BUILD / f'voice-{i:02}.txt', BUILD / f'voice-{i:02}.aiff'
        changed = not text_path.exists() or text_path.read_text() != narration
        text_path.write_text(narration)
        if changed or not aiff.exists():
            run(['/usr/bin/say', '-v', 'Samantha', '-r', '155', '-f', str(text_path), '-o', str(aiff)])
        raw = run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-i', str(aiff), '-ar', str(RATE), '-ac', '1',
                   '-f', 'f32le', '-'], stdout=subprocess.PIPE).stdout
        samples = np.frombuffer(raw, np.float32).copy()
        active = np.flatnonzero(np.abs(samples) > .001)
        if active.size:
            samples = samples[max(0, active[0]-int(.04*RATE)):min(len(samples), active[-1]+int(.2*RATE))]
        available = end - start - .65
        tempo = max(1, len(samples) / RATE / available)
        if tempo > 1.18:
            raise ValueError(f'Narration {kind} requires an excessive tempo: {tempo:.3f}')
        if tempo > 1:
            adjusted = run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-f', 'f32le', '-ar', str(RATE), '-ac', '1',
                            '-i', '-', '-af', f'atempo={tempo:.7f}', '-f', 'f32le', '-'],
                           input=samples.tobytes(), stdout=subprocess.PIPE).stdout
            samples = np.frombuffer(adjusted, np.float32).copy()
        place = round((start + .3) * RATE)
        timeline[place:place+len(samples)] += samples
        timings.append({'kind': kind, 'start': start+.3, 'end': start+.3+len(samples)/RATE,
                        'voice': 'Samantha / macOS native en_US', 'tempo': tempo, 'text': narration})
    t = np.arange(DURATION * RATE, dtype=np.float32) / RATE
    music = np.zeros_like(t)
    # Original, quiet D-minor/evolving sine score. No samples or third-party music.
    for start in range(0, DURATION, 8):
        mask = (t >= start) & (t < min(start+9.5, DURATION))
        local = t[mask] - start
        env = np.minimum(1, local/1.2) * np.maximum(0, 1-local/9.5) ** 1.5
        tones = (146.832, 174.614, 220.0, 329.628) if start % 16 == 0 else (130.813, 174.614, 220.0, 293.665)
        pad = sum(np.sin(2*math.pi*hz*local + j*.7) / (j+2) for j, hz in enumerate(tones))
        music[mask] += pad * env * .009
    music *= np.minimum(1, t/2) * np.minimum(1, (DURATION-t)/3)
    voice_peak = np.max(np.abs(timeline))
    timeline *= .66 / max(voice_peak, .01)
    mix = np.clip(timeline + music, -.98, .98)
    stereo = np.column_stack((mix, mix)).astype('<f4')
    run([FFMPEG, '-y', '-hide_banner', '-loglevel', 'error', '-f', 'f32le', '-ar', str(RATE), '-ac', '2', '-i', '-',
         '-af', 'loudnorm=I=-18:TP=-1.5:LRA=8', '-ar', str(RATE), '-c:a', 'pcm_s16le', str(BUILD/'soundtrack.wav')],
        input=stereo.tobytes())
    (BUILD/'narration.json').write_text(json.dumps(timings, indent=2)+'\n')
    blocks = []
    for i, timing in enumerate(timings, 1):
        lines = CAPTIONS[timing['kind']]
        blocks.append(f"{i}\n{timestamp(timing['start'])} --> {timestamp(timing['end'])}\n" + '\n'.join(lines) + '\n')
    (OUT/'AquaShift-Concept-and-Prototype.srt').write_text('\n'.join(blocks))
    return timings


SCREENS = {}


def load_screens():
    for kind, filename in SCREEN_FILES.items():
        path = CAPTURE_DIR/filename
        with Image.open(path) as image:
            SCREENS[kind] = image.convert('L').convert('RGB')
        for left, top, right, bottom in CROPS[kind]:
            if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
                raise ValueError(f'{kind}: crop outside actual screenshot dimensions {image.size}')


def screen_image(kind, progress):
    a, b = CROPS[kind]
    motion = ease((progress-.10)/(.45 if kind == 'sites' else .64))
    window = tuple(round(x+(y-x)*motion) for x, y in zip(a, b))
    return SCREENS[kind].crop(window)


def fit(image, size, scale=1):
    ratio = min(size[0]/image.width, size[1]/image.height) * scale
    resized = image.resize((round(image.width*ratio), round(image.height*ratio)), Image.Resampling.LANCZOS)
    tile = Image.new('RGB', size, '#F0F0F0')
    tile.paste(resized, ((size[0]-resized.width)//2, (size[1]-resized.height)//2))
    return tile


def rail(draw, label, big, detail, y=320, color=MINT):
    txt(draw, (1380, y), label, 28, color, True)
    for i, line in enumerate(big.split('\n')):
        txt(draw, (1380, y+58+i*58), line, 50, WHITE, True)
    base = y+72+len(big.split('\n'))*58
    for i, line in enumerate(wrapped(detail, 30, 445)):
        txt(draw, (1380, base+i*42), line, 30, MINT)


def concept_image(kind, progress):
    frame = min(216, max(1, round(progress*216)+1))
    directory = RENDERS if NATIVE_24 else BUILD/'render-24'
    path = directory/kind/f'frame-{frame:04d}.png'
    if not path.exists():
        raise FileNotFoundError(path)
    with Image.open(path) as im:
        return im.convert('L').convert('RGB')


def interpolate_concept(kinds=('overview', 'storage', 'evening')):
    for kind in kinds:
        source = RENDERS/kind
        missing = [i for i in range(1, 109) if not (source/f'frame-{i:04d}.png').exists()]
        if missing:
            raise FileNotFoundError(f'{kind}: {len(missing)} native12fps Blender frames missing')
        destination = BUILD/'render-24'/kind
        destination.mkdir(parents=True, exist_ok=True)
        identity = {f'frame-{i:04d}.png': digest(source/f'frame-{i:04d}.png') for i in range(1, 109)}
        receipt = destination/'input-sha256.json'
        if (receipt.exists() and json.loads(receipt.read_text()) == identity
                and all((destination/f'frame-{i:04d}.png').exists() for i in range(1, 217))):
            continue
        run([FFMPEG, '-y', '-hide_banner', '-loglevel', 'warning', '-framerate', '12', '-i', str(source/'frame-%04d.png'),
             '-vf', 'minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:vsbmc=1,tpad=stop_mode=clone:stop_duration=0.25',
             '-frames:v', '216', str(destination/'frame-%04d.png')])
        assert all((destination/f'frame-{i:04d}.png').exists() for i in range(1, 217))
        receipt.write_text(json.dumps(identity, indent=2)+'\n')
        print(f'Interpolated {kind}:12fps native motion →24fps', flush=True)


def verify_native_concept():
    for kind in ('overview', 'storage', 'evening'):
        source = RENDERS/kind
        metadata = json.loads((source/'render-manifest.json').read_text())
        if (metadata['fps'], metadata['width'], metadata['height'], metadata['frames']) != (24, 1920, 1080, 216):
            raise ValueError(f'{kind}: native 24fps Full HD manifest required')
        if metadata['rendered_frames'] != list(range(1, 217)):
            raise ValueError(f'{kind}: complete native frame range required')
        if metadata['blend_sha256'] != digest(source/f'aquashift-{kind}.blend'):
            raise ValueError(f'{kind}: scene identity mismatch')
        if metadata['source_sha256'] != digest(source/'scene-source.py'):
            raise ValueError(f'{kind}: scene source identity mismatch')
        hashes = []
        for number in range(1, 217):
            path = source/f'frame-{number:04d}.png'
            with Image.open(path) as image:
                if image.size != (1920, 1080):
                    raise ValueError(f'{kind}: incorrect native frame dimensions')
            hashes.append(digest(path))
        if len(set(hashes)) != 216:
            raise ValueError(f'{kind}: duplicate native frames')
    print('648 unique Full HD native Blender frames verified; no interpolation.', flush=True)


def frame_at(seconds, timings):
    idx = next(i for i, s in enumerate(SEGMENTS) if s[0] <= seconds < s[1])
    start, end, kind, title, narration = SEGMENTS[idx]
    local, progress = seconds-start, (seconds-start)/(end-start)
    image = Image.new('RGB', (W, H), NAVY)
    draw = ImageDraw.Draw(image)
    txt(draw, (80, 51), 'AquaShift', 36, WHITE, True)
    badge = 'CONCEPT ILLUSTRATION' if kind in ('title', 'overview', 'storage', 'evening') else 'ACTUAL PROTOTYPE CAPTURES' if kind in SCREEN_FILES else 'TEAM REVIEW DRAFT'
    txt(draw, (1840-ImageDraw.Draw(image).textlength(badge, font=FONTS[24, True]), 60), badge, 24, MINT, True)
    if kind != 'title':
        offset = round(18*(1-ease(local/.6)))
        txt(draw, (80, 143+offset), title, 64, WHITE, True)
    if kind in ('overview', 'storage', 'evening'):
        stage = fit(concept_image(kind, progress), (1240, 698))
        image.paste(stage, (80, 244))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((79, 243, 1321, 943), radius=3, outline='#4C4C4C', width=2)
        if kind == 'overview':
            rail(draw, '01  /  ELECTRICITY', 'Solar →\ndesalination', 'Only where curtailment signals and operating conditions allow.', color=GOLD)
        elif kind == 'storage':
            rail(draw, '02  /  WATER', 'Make it now.\nStore it.', 'Water storage carries supply across time.')
        else:
            rail(draw, '03  /  LATER USE', 'Stored water.\nLater demand.', 'Symbolic 3D scene. Actual curtailed-solar use remains unproven.')
    elif kind in SCREEN_FILES:
        stage = fit(screen_image(kind, progress), (1240, 698))
        image.paste(stage, (80, 244))
        draw = ImageDraw.Draw(image)
        draw.rectangle((79, 243, 1321, 943), outline='#4C4C4C', width=2)
        if kind == 'grid':
            rail(draw, 'HISTORICAL DAY', '1 July\n2026', 'Weather reconstruction. Operator advice; no plant controls.')
        elif kind == 'schedule':
            rail(draw, 'MATCHED SCENARIO', '2,880 m³\n9,792 kWh', 'Same water and energy in both schedules. Price assumptions drive cost.', y=286)
            txt(draw, (1380, 760), '€0 added AI cost benefit', 30, GOLD, True)
        elif kind == 'tank':
            rail(draw, 'TANK CAPACITY', '500 versus\n8,000 m³', 'Same water and energy. Storage changes the modeled production plan.')
        elif kind == 'forecast':
            rail(draw, 'AVERAGE ERROR / W/m²', '8.81\nreference', '7.64 stronger simple control', y=282)
            txt(draw, (1380, 716), 'AI value: unproven', 32, GOLD, True)
            txt(draw, (1380, 780), '92 held-out days', 30, MINT)
        else:
            rail(draw, 'SITES EXPERIMENT', 'Budget +\nleak fixture', 'Meter data is simulated. Field detection accuracy is untested.')
    elif kind == 'title':
        txt(draw, (80, 302), 'Solar power', 112, WHITE, True)
        txt(draw, (80, 438), 'into water.', 112, MINT, True)
        txt(draw, (86, 626), 'Water stored for later.', 50, WHITE)
        txt(draw, (86, 767), 'Concept + working prototype', 30, MINT)
        for j, label in enumerate(('SOLAR ELECTRICITY', 'DESALINATION', 'WATER STORAGE')):
            y = 330+j*165
            txt(draw, (1240, y), f'0{j+1}', 50, WHITE, True)
            txt(draw, (1340, y+13), label, 28, MINT, True)
            draw.line((1240, y+90, 1790, y+90), fill='#454545', width=3)
            length = round(550*ease((seconds-.5-j*.8)/1.4))
            if length:
                draw.line((1240, y+90, 1240+length, y+90), fill=WHITE, width=3)
    elif kind == 'next':
        rows = [('01', 'Grid signals for one plant'), ('02', 'Plant limits + water demand'), ('03', 'Real tariffs + matched controls')]
        for j, (number, text) in enumerate(rows):
            x = 100+int(30*(1-ease((local-j*.15)/.6)))
            y = 315+j*172
            draw.rounded_rectangle((x, y, 1820, y+124), radius=8, fill='#272727')
            txt(draw, (x+28, y+33), number, 42, GOLD, True)
            txt(draw, (x+135, y+28), text, 50, WHITE, True)
        txt(draw, (104, 862), 'Measure whether prediction adds value.', 38, MINT)
    else:
        credits = [
            ('Loucas Louka', 'Original concept and philosophy'),
            ('Στέφανος Μπορτέας', 'Roadmap expansion'),
            ('Andreas Nikolaides + Cleopas Cleopa', 'Business case + pitch roles'),
        ]
        for j, (name, role) in enumerate(credits):
            y = 320+j*160
            txt(draw, (80, y), name, 38, WHITE, True)
            txt(draw, (80, y+54), role, 30, MINT)
        txt(draw, (80, 874), 'AI-assisted draft · Prepared for team review', 32, GOLD)
    # Spoken captions sit below the visual stage, never over application data.
    timing = timings[idx]
    if timing['start'] <= seconds <= timing['end']:
        lines = CAPTIONS[kind]
        y = 962 if len(lines) == 2 else 990
        for line in lines:
            width = draw.textlength(line, font=FONTS[42, False])
            txt(draw, ((W-width)/2, y), line, 42, WHITE)
            y += 50
    draw.rectangle((80, 1070, 1840, 1074), fill='#353535')
    draw.rectangle((80, 1070, 80+int(1760*seconds/DURATION), 1074), fill=TEAL)
    fade = min(1, seconds/.35, (DURATION-seconds)/.35)
    if fade < 1:
        image = Image.blend(Image.new('RGB', (W, H), NAVY), image, max(0, fade))
    return image


def verify(output):
    decoded = subprocess.run([FFMPEG, '-hide_banner', '-v', 'error', '-i', str(output), '-f', 'null', '-'],
                             text=True, capture_output=True)
    if decoded.returncode or decoded.stderr.strip():
        raise RuntimeError(f'Full decode failed: {decoded.stderr}')
    info = json.loads(run([FFPROBE, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(output)],
                          stdout=subprocess.PIPE, text=True).stdout)
    assert abs(float(info['format']['duration'])-DURATION) < .05
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    sound = next(s for s in info['streams'] if s['codec_type'] == 'audio')
    assert (video['width'], video['height'], video['r_frame_rate']) == (W, H, '24/1')
    assert int(video['nb_frames']) == FPS*DURATION
    assert sound['sample_rate'] == str(RATE)
    levels = subprocess.run([FFMPEG, '-hide_banner', '-i', str(output), '-af', 'volumedetect', '-vn', '-f', 'null', '-'],
                            text=True, capture_output=True, check=True).stderr
    (BUILD/'audio-levels.log').write_text(levels)
    level_lines = [line for line in levels.splitlines() if 'mean_volume:' in line or 'max_volume:' in line]
    return info, level_lines


def main():
    global BUILD, RENDERS, OUT, CAPTURE_DIR, CROPS, REVISION_URL, NATIVE_24
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--previews', action='store_true')
    parser.add_argument('--interpolate-kind', choices=('overview', 'storage', 'evening'))
    parser.add_argument('--native-24', action='store_true', help='Build an isolated candidate from native Full HD 24fps renders')
    parser.add_argument('--capture-directory', type=Path, help='Folder containing the five actual workspace screenshots')
    parser.add_argument('--capture-revision', help='Immutable deployed revision actually shown in the screenshots')
    args = parser.parse_args()
    if args.native_24:
        if args.interpolate_kind:
            parser.error('Native 24fps composition does not use interpolation')
        if not args.capture_directory or not args.capture_revision:
            parser.error('Native candidate requires explicit screenshot directory and captured revision')
        NATIVE_24 = True
        BUILD = WORK/'composition-native-24'
        RENDERS = WORK/'render-native-24'
        OUT = BUILD/'candidate-delivery'
        CROPS = {**CROPS,
                 'grid': ((250, 145, 1245, 705), (250, 215, 1245, 775)),
                 'schedule': ((250, 268, 1245, 828), (250, 330, 1245, 890)),
                 'tank': ((250, 595, 1245, 1155), (250, 645, 1245, 1205))}
    if args.capture_directory:
        CAPTURE_DIR = args.capture_directory.resolve()
    if args.capture_revision:
        REVISION_URL = args.capture_revision
    if not Path('/Volumes/CARMIX-WORK').is_mount():
        raise RuntimeError('Expected mounted work volume is absent')
    BUILD.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(exist_ok=True)
    timings = prepare_audio()
    metrics = json.loads((ROOT/'results/metrics.json').read_text())
    assert round(metrics['all']['model']['mae'], 2) == 8.81
    assert round(metrics['all']['persistence']['mae'], 2) == 7.64
    if args.interpolate_kind:
        interpolate_concept((args.interpolate_kind,))
        return
    if args.prepare:
        print('Narration, original score and captions prepared.', flush=True)
        return
    load_screens()
    if NATIVE_24:
        verify_native_concept()
    else:
        interpolate_concept()
    if args.previews:
        for seconds in (2.5, 9.5, 18.5, 27.5, 37, 46.5, 55, 64, 73, 80.5, 87):
            frame_at(seconds, timings).save(BUILD/f'preview-{seconds:04.1f}.jpg', quality=92)
        print('All chapter previews generated.', flush=True)
        return
    output = BUILD/'AquaShift-Concept-and-Prototype.mp4'
    command = [FFMPEG, '-y', '-hide_banner', '-loglevel', 'warning', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
               '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-i', str(BUILD/'soundtrack.wav'),
               '-t', str(DURATION), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p',
               '-c:a', 'aac', '-b:a', '192k', '-ar', str(RATE), '-movflags', '+faststart',
               '-metadata', 'title=AquaShift — Concept and Prototype', str(output)]
    with (BUILD/'encode.log').open('w') as log:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log)
        try:
            for i in range(FPS*DURATION):
                process.stdin.write(frame_at(i/FPS, timings).tobytes())
                if i % (FPS*5) == 0:
                    print(f'Composed {i//FPS}/{DURATION}s', flush=True)
            process.stdin.close()
            status = process.wait()
            if status:
                raise RuntimeError(f'Video encoder exited {status}; inspect {BUILD/"encode.log"}')
        finally:
            if process.poll() is None:
                process.terminate()
    info, levels = verify(output)
    final = OUT/output.name
    temporary = OUT/(output.name+'.tmp')
    shutil.copyfile(output, temporary)
    temporary.replace(final)
    frame_at(9.5, timings).save(OUT/'AquaShift-Concept-and-Prototype-poster.jpg', quality=94)
    contact = Image.new('RGB', (1280, 6*385), NAVY)
    contact_draw = ImageDraw.Draw(contact)
    for j, seconds in enumerate((2.5, 9.5, 18.5, 27.5, 37, 46.5, 55, 64, 73, 80.5, 87)):
        preview = frame_at(seconds, timings)
        preview.save(BUILD/f'preview-{seconds:04.1f}.jpg', quality=92)
        x, y = (j % 2)*640, (j//2)*385
        contact.paste(preview.resize((640, 360), Image.Resampling.LANCZOS), (x, y))
        contact_draw.text((x+8, y+362), f'{seconds:.1f}s', fill=WHITE, font=FONTS[24, False])
    contact.save(BUILD/'contact-sheet.jpg', quality=94)
    inputs = {str(CAPTURE_DIR/file): digest(CAPTURE_DIR/file) for file in SCREEN_FILES.values()}
    for name in ('results/metrics.json', 'results/independent-review.json'):
        inputs[name] = digest(ROOT/name)
    inputs[str(BUILD/'soundtrack.wav')] = digest(BUILD/'soundtrack.wav')
    inputs[str(OUT/'AquaShift-Concept-and-Prototype.srt')] = digest(OUT/'AquaShift-Concept-and-Prototype.srt')
    for kind in ('overview', 'storage', 'evening'):
        blend = RENDERS/kind/f'aquashift-{kind}.blend'
        inputs[str(blend)] = digest(blend)
        for i in range(1, 217 if NATIVE_24 else 109):
            path = RENDERS/kind/f'frame-{i:04d}.png'
            inputs[str(path)] = digest(path)
    record = {'completed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': ('27 seconds of actual animated Blender concept renders at native Full HD 24 fps, with no interpolation; '
                        if NATIVE_24 else '27 seconds of actual animated Blender concept renders at native 12 fps, motion-interpolated to 24 fps; ')
                       + 'crop/pan composition around actual public app screenshots; not a continuous live recording',
              'limitations': ['3D is symbolic, not an actual plant', 'No real curtailment recovery demonstrated',
                              'Historical weather reconstruction and illustrative operating/tariff assumptions',
                              'Reference forecast does not beat primary simple control; added AI value unproven',
                              'Sites meter fixture is synthetic; field accuracy untested'],
              'audio': {'voice': 'macOS Samantha native en_US', 'sample_rate_hz': RATE,
                        'music': 'Original synthesized sine score, no third-party samples', 'levels': levels},
              'command': command, 'reproducing_command': [sys.executable, str(Path(__file__)), *sys.argv[1:]],
              'screenshot_provenance': [{'file': str(CAPTURE_DIR/filename),
                  'sha256': inputs[str(CAPTURE_DIR/filename)], 'view': kind,
                  'public_url': PUBLIC_URL, 'immutable_revision_url': REVISION_URL,
                  'capture_method': 'Parent agent isolated IAB CUA screenshot; actual deployed workspace',
                  'retained_at_utc': datetime.datetime.fromtimestamp((CAPTURE_DIR/filename).stat().st_mtime, datetime.timezone.utc).isoformat(),
                  'historical_date': '2026-07-01', 'inspect_hour': 13,
                  'tank_capacity_m3': 4000 if kind in ('grid', 'schedule') or (NATIVE_24 and kind == 'tank') else 500,
                  'comparison_tanks_m3': [500, 8000] if kind == 'tank' else None,
                  'crop_pan_endpoints': CROPS[kind]}
                  for kind, filename in SCREEN_FILES.items()],
              'full_decode_exit_status': 0, 'probe': info, 'input_sha256': inputs,
              'output_sha256': digest(output), 'script_sha256': digest(Path(__file__)),
              'contact_sheet': str(BUILD/'contact-sheet.jpg'), 'visual_review': 'Pending individual chapter review'}
    receipt = 'professional-video-native24-candidate.json' if NATIVE_24 else 'professional-video.json'
    receipt_text = json.dumps(record, indent=2)+'\n'
    if NATIVE_24:
        (BUILD/receipt).write_text(receipt_text)
    (ROOT/'results'/receipt).write_text(receipt_text)
    print(f'Completed {final}; full decode verified.', flush=True)


if __name__ == '__main__':
    main()
