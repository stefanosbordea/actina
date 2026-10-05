"""Create a 90-second captioned backup from actual CUA dashboard captures."""
from pathlib import Path
import datetime
import hashlib
import json
import shutil
import subprocess
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'delivery'
FRAMES = OUT / 'demo-frames'
FRAMES.mkdir(exist_ok=True)
BUILD = ROOT / 'build' / 'backup-video'
BUILD.mkdir(parents=True, exist_ok=True)
SEQUENCE = [
    ('grid-clean.png',10,'AquaShift: a working water-planning demo','Historical weather, scenario demand and tariffs; operator advice only.'),
    ('schedule-clean.png',16,'Grid: produce equal water at a different time','2,880 m³ and 9,792 kWh in both schedules; cost change comes from clock prices.'),
    ('small-tank-clean.png',12,'Change the tank: the schedule responds','A 500 m³ tank reduces flexibility; the modeled supply and safety constraints still hold.'),
    ('forecast-evidence-clean.png',14,'Evaluation: test the model against a fair simple method','The reference loses on average error: 8.8 vs 7.6 W/m². AI benefit remains unproven.'),
    ('forecast-chart-clean.png',14,'Inspect actual, model and simple prediction','Real historical reconstruction; solar radiation is a weather proxy, not measured grid surplus.'),
    ('sites-clean.png',14,'Sites: irrigation budget and injected leak','Four synthetic leak hours detected. Meter data is simulated; field accuracy is untested.'),
    ('handoff-clean.png',10,'A reproducible prototype with a clear next pilot','Reference model replaceable by Stefanos; site data, real tariffs and operating limits are next.'),
]
for name, *_ in SEQUENCE:
    source = ROOT / 'build/screens' / name
    target = FRAMES / name
    if source.exists():
        shutil.copyfile(source,target)
    if not target.exists():
        raise FileNotFoundError(target)

def timestamp(seconds):
    return f'{int(seconds)//3600:02}:{int(seconds)//60%60:02}:{int(seconds)%60:02},000'

caption_path = OUT / 'AquaShift-Backup-Captions.srt'
elapsed = 0
blocks = []
for index,(_,seconds,title,body) in enumerate(SEQUENCE,1):
    blocks.append(f'{index}\n{timestamp(elapsed)} --> {timestamp(elapsed+seconds)}\n{title}\n{body}\n')
    elapsed += seconds
assert elapsed == 90
caption_path.write_text('\n'.join(blocks))
playlist = BUILD / 'frames.ffconcat'
playlist.write_text('ffconcat version 1.0\n'+''.join(f"file '{FRAMES / name}'\nduration {duration}\n" for name,duration,*_ in SEQUENCE)+f"file '{FRAMES / SEQUENCE[-1][0]}'\n")
output = OUT / 'AquaShift-90s-Backup.mp4'
font_root = Path('/System/Library/Fonts/Supplemental')
title_font = ImageFont.truetype(str(font_root/'Arial Bold.ttf'),22)
body_font = ImageFont.truetype(str(font_root/'Arial.ttf'),18)
caption_frames = []
for index,(_,duration,title,body) in enumerate(SEQUENCE):
    strip = Image.new('RGB',(1280,80),'#153643')
    draw = ImageDraw.Draw(strip)
    assert draw.textlength(title,font=title_font)<1200
    assert draw.textlength(body,font=body_font)<1200
    draw.text((32,12),title,font=title_font,fill='white')
    draw.text((32,43),body,font=body_font,fill='#C8E8E0')
    strip_path = BUILD/f'caption-{index}.png'
    strip.save(strip_path)
    caption_frames.append((strip_path,duration))
caption_playlist = BUILD/'captions.ffconcat'
caption_playlist.write_text('ffconcat version 1.0\n'+''.join(f"file '{name}'\nduration {duration}\n" for name,duration in caption_frames)+f"file '{caption_frames[-1][0]}'\n")
command = ['ffmpeg','-y','-hide_banner','-loglevel','warning','-f','concat','-safe','0','-i',str(playlist),
           '-f','concat','-safe','0','-i',str(caption_playlist),'-filter_complex',
           '[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:800:0:0:color=0x153643[screen];[screen][1:v]overlay=0:720',
           '-r','24','-t','90','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(output)]
completed = subprocess.run(command,text=True,capture_output=True)
(ROOT/'results/backup-video.log').write_text(completed.stdout+completed.stderr)
if completed.returncode:
    raise RuntimeError(completed.stderr)
probe_command = ['ffprobe','-v','error','-show_entries','format=duration:stream=width,height,codec_name','-of','json',str(output)]
probe = subprocess.run(probe_command,text=True,capture_output=True,check=True)
info = json.loads(probe.stdout)
assert abs(float(info['format']['duration'])-90)<0.05
record = {'scope':'Captioned walkthrough assembled from actual dashboard screenshots; not a continuous live recording',
          'capture_method':'Codex CUA isolated in-app browser; no personal Chrome tabs or messages included',
          'completed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'command':command,'exit_status':completed.returncode,'ffprobe':info,
          'input_sha256':{str((FRAMES/name).relative_to(ROOT)):hashlib.sha256((FRAMES/name).read_bytes()).hexdigest() for name,*_ in SEQUENCE},
          'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest()}
(ROOT/'results/backup-video.json').write_text(json.dumps(record,indent=2)+'\n')
print(f'Created {output.name}: {info["format"]["duration"]} seconds.')
