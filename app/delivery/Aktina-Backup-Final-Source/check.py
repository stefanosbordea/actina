"""Independently decode the final movie and retain one frame per UI state."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
receipt = json.loads((HERE/'render/verification.json').read_text())
movie = HERE.parent/'Aktina-Backup-Final.mp4'
if sha(movie) != receipt['output']['sha256']: raise ValueError('Final movie hash changed')
commands = []


def run(command):
    commands.append(command)
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


probe = json.loads(run(['ffprobe','-v','error','-count_frames','-show_entries',
    'format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,nb_read_frames',
    '-of','json',str(movie)]))
streams = probe['streams']
if len(streams) != 1 or streams[0] != dict(codec_name='h264',codec_type='video',width=1920,height=1080,r_frame_rate='30/1',nb_read_frames='1320'):
    raise ValueError('Unexpected stream: require1320 H264 frames at1080p30, zero audio')
if float(probe['format']['duration']) != 44: raise ValueError('Unexpected duration')
run(['ffmpeg','-v','error','-xerror','-nostdin','-protocol_whitelist','file,pipe,fd','-i',str(movie),'-f','null','-'])
frames = HERE/'render/qa-frames'
frames.mkdir(exist_ok=False)
records = []
for index,item in enumerate(receipt['timeline'],1):
    moment = item['start_seconds']+item['duration_seconds']/2
    output = frames/f'{index:02}.png'
    run(['ffmpeg','-v','error','-nostdin','-n','-ss',str(moment),'-i',str(movie),'-frames:v','1',str(output)])
    records.append({'file':str(output.relative_to(HERE)),'at_seconds':moment,'sha256':sha(output),'source_capture':item['file']})
prior = json.loads((HERE/'v2-preservation.json').read_text())
if any(sha(ROOT/name) != value for name,value in prior.items()): raise ValueError('Prior version changed')
result = {'status':'PASS','output_sha256':sha(movie),'probe':probe,'full_decode':'passed','audio_streams':0,
    'frames':records,'prior_v2_files_unchanged':len(prior),'check_sha256':sha(Path(__file__)),
    'commands':commands,'scope':'Media identity, decode, clock and extracted frames; human visual inspection recorded separately.'}
(HERE/'render/independent-check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({key:result[key] for key in ['status','output_sha256','audio_streams','prior_v2_files_unchanged']}))
