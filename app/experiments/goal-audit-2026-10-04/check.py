"""Read-only goal evidence checks, with outputs confined to this audit folder."""
import csv
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
checks, evidence = 0, {}


def check(value, label):
    global checks
    checks += 1
    if not value:
        raise AssertionError(label)


def remember(path):
    path = ROOT / path
    evidence[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path


def rows(path):
    with remember(path).open(newline='') as f:
        return list(csv.DictReader(f))


def load(path):
    return json.loads(remember(path).read_text())


def command(args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    check(result.returncode == 0, 'command succeeded '+args[0])
    return result.stdout.strip()


goal = remember('app/experiments/RESEARCH-GOAL.md').read_text()
check('same-hour' in goal.lower() and 'six primary comparisons' in goal, 'goal source')
report = load('app/experiments/f1-009/result/report.json')
policy = load('app/experiments/f1-009/result/validation-selection.json')['policies']['joint']['policy']
features = {r['feature_time']:r for r in rows('app/experiments/f1-008/result/features.csv')}
references = {r['feature_time']:r for r in rows('app/experiments/reference-training-001/result/joined-reference.csv')}
counts, comparisons = [], []
for split, filename in [('validation','cv_predictions.csv'),('test','test_predictions.csv')]:
    original = rows('eval/'+filename)
    candidate = rows(f'app/experiments/f1-009/result/predictions/{split}-joint.csv')
    old008 = rows(f'app/experiments/f1-008/result/predictions/{split}-consensus_two_source.csv')
    check([r['time'] for r in original] == [r['feature_time'] for r in candidate] == [r['feature_time'] for r in old008], 'same-hour candidate and control order')
    check(len(candidate) == (3566 if split == 'validation' else 3567), 'complete original membership')
    calls, weather, satellite, availability = [], [], [], []
    for o,c,e in zip(original,candidate,old008):
        r,f = references[o['time']],features[o['time']]
        check(float(o['actual']) == float(c['weather_w_m2']) == float(r['weather_actual_w_m2']), 'unchanged weather label')
        check(datetime.fromisoformat(c['target_time']) == datetime.fromisoformat(o['time'])+timedelta(hours=24) == datetime.fromisoformat(r['target_time']), 'target hour join')
        known = bool(r['satellite_w_m2'])
        check(known == bool(int(c['satellite_available'])), 'same satellite missingness')
        if known:
            check(float(c['satellite_w_m2']) == float(r['satellite_w_m2']), 'same satellite label')
        nwp = float(f['nwp_day2_radiation']) > 600
        check(nwp == bool(int(c['nwp_positive'])), 'fixed archived control')
        predicted = float(c['probability']) > policy['lower' if nwp else 'upper']
        check(predicted == bool(int(c['predicted_positive'])), 'frozen strict probability policy')
        calls.append({'original':float(o['predicted'])>600,'persistence':float(o['baseline'])>600,'nwp_day2':nwp,'joint':predicted,'f1_008_frozen':bool(int(e['predicted_positive']))})
        weather.append(float(o['actual'])>600)
        satellite.append(float(r['satellite_w_m2'])>600 if known else None)
        availability.append(known)
    for basis in ('weather_full','weather_common','satellite_common'):
        mask = [True]*len(candidate) if basis == 'weather_full' else availability
        truth = satellite if basis == 'satellite_common' else weather
        exact = {}
        for method in calls[0]:
            tp=fp=fn=tn=0
            for yes,y,call in zip(mask,truth,calls):
                if not yes:
                    continue
                predicted = call[method]
                tp += int(predicted and y)
                fp += int(predicted and not y)
                fn += int(not predicted and y)
                tn += int(not predicted and not y)
            metrics = {'precision':Fraction(tp,tp+fp),'recall':Fraction(tp,tp+fn),'f1':Fraction(2*tp,2*tp+fp+fn)}
            saved = report['methods'][method][split]['events'][basis]
            check((tp,fp,fn,tn,sum(mask)) == tuple(saved[k] for k in ('tp','fp','fn','tn','hours')), 'independent confusion counts')
            for metric,value in metrics.items():
                check(float(value) == saved[metric], 'exact fraction metric '+metric)
            exact[method] = metrics
            counts.append(dict(split=split,basis=basis,method=method,hours=sum(mask),tp=tp,fp=fp,fn=fn,tn=tn,**{k:float(v) for k,v in metrics.items()},**{k+'_fraction':str(v) for k,v in metrics.items()}))
        if basis != 'weather_common':
            for control in ('original','persistence','nwp_day2'):
                for metric in ('precision','recall','f1'):
                    difference = exact['joint'][metric]-exact[control][metric]
                    comparisons.append(dict(split=split,basis=basis,control=control,metric=metric,status='improved' if difference>0 else 'equal' if difference==0 else 'regressed',difference_fraction=str(difference),difference=float(difference)))

inventory = {}
for experiment, result in [('f1-001','result-retry1'),('f1-002','result-retry1'),*[(f'f1-{n:03d}','result') for n in range(3,11)],('physical-011','result'),('physical-012','result')]:
    path=f'app/experiments/{experiment}/{result}/report.json'
    r=load(path)
    inventory[experiment]={'report':path,'status':r.get('status'),'sha256':evidence[path]}
    if 'test_gate' in r:
        inventory[experiment]['test_gate']=r['test_gate']
    if 'experiment_gate' in r:
        inventory[experiment]['experiment_gate']=r['experiment_gate']
for name in ['f1-009/review/result.json','f1-009/review/uncertainty-result.json','f1-009/review/uncertainty-review.json','f1-010/review/result.json','physical-011/review/result.json','physical-011/uncertainty/review/result.json','physical-011/uncertainty/review/frequency-result.json','physical-012/review/result.json','physical-012/inputs.json']:
    load('app/experiments/'+name)
for name in ['full-pdf-followthrough.md','correction-regret-hypothesis.md','physical-decision-study.md','conditional-scenarios.md']:
    remember('app/experiments/research-2026-10-04/'+name)
remember('app/experiments/f1-009/PROTOCOL.md')
remember('app/experiments/f1-009/run.py')
remember('app/experiments/f1-009/bqn.py')
remember('app/experiments/f1-010/run.py')
remember('app/experiments/physical-012/run.py')
for path in sorted((ROOT/'app/experiments/f1-009/result/models').glob('*.npz')):
    remember(path.relative_to(ROOT))

base='2a093aba97f6ad615c43fa7c514044342af16e3a'
head=command(['git','rev-parse','HEAD'])
remote=command(['git','ls-remote','origin','refs/heads/stefanos-model']).split()[0]
protected=command(['git','diff','--name-status',base,'--','model','data','eval'])
check(not protected,'protected original directories unchanged')
check(head==remote,'authorized remote matches local commit at audit')
runs=json.loads(command(['gh','run','list','--branch','stefanos-model','--limit','5','--json','databaseId,headSha,status,conclusion,name']))
authors=command(['git','log','-5','--format=%H %an%n%B'])
result={'status':'EVIDENCE_CHECKS_PASS_NOT_GOAL_COMPLETE','checked_at_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'point_score_clause':{'method':'f1-009 joint BQN frozen policy','comparisons':comparisons,'all_36_primary_point_comparisons_strictly_improve':all(r['status']=='improved' for r in comparisons),'limits':'Published-method adaptation. Already-inspected periods. This does not establish novelty, uncertainty-separated superiority or downstream value of this candidate.'},'experiment_inventory':inventory,'protected_originals':{'baseline_commit':base,'directories':['model','data','eval'],'git_diff_name_status':protected},'publication':{'local_head':head,'remote_stefanos_model':remote,'recent_runs':runs,'recent_authors_and_messages':authors},'inputs_sha256':evidence,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
for name,digest in evidence.items():
    check(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,'evidence unchanged '+name)
result['checks']=checks
with (HERE/'event-metrics.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=counts[0])
    w.writeheader()
    w.writerows(counts)
(HERE/'evidence.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':result['status'],'checks':checks,'all_36_primary_point_comparisons_strictly_improve':result['point_score_clause']['all_36_primary_point_comparisons_strictly_improve'],'head':head,'pinned_files':len(evidence)}))
