"""Verify the NWP merge and preservation of the original source tree."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE='2a093aba97f6ad615c43fa7c514044342af16e3a0'
MERGE='3f3b3038fd112b3554b21ae24eeaf6eb886d1f69'
UPSTREAM='85097a560769ad8a1459ce55f0b3a4c301202405'
ADDED=['data/download_nwp.py','data/features_v2.py','data/featuresv2.csv','data/paphos_nwp_data.csv',
       'data/paphos_weather_datav2.csv','eval/cv_predictions_v2.csv','model/train_modelv2.py']


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def verify():
    parents=git('show','-s','--format=%P',MERGE).decode().strip().split()
    assert len(parents)==2 and parents[1]==UPSTREAM
    changes=git('diff','--name-status',BASE,MERGE,'--','model','data','eval').decode().splitlines()
    assert sorted(changes)==sorted('A\t'+name for name in ADDED)
    old=git('ls-tree','-r','--name-only',BASE,'--','model','data','eval').decode().splitlines()
    assert len(old)==17
    checked={'added_from_upstream':{},'preserved_original':{}}
    for group,names,reference in (('added_from_upstream',ADDED,UPSTREAM),('preserved_original',old,BASE)):
        for name in names:
            expected=git('show',f'{reference}:{name}')
            merged=git('show',f'{MERGE}:{name}')
            working=(ROOT/name).read_bytes()
            assert expected==merged==working,name
            checked[group][name]={'sha256':digest(expected),'bytes':len(expected)}
    return dict(status='PASS',verifier_sha256=digest(Path(__file__).read_bytes()),baseline=BASE,merge=MERGE,
        upstream=UPSTREAM,merge_parents=parents,added_files=len(ADDED),preserved_files=len(old),
        merge_and_working_files_match=True,files=checked,training_or_scoring_executed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    result=verify()
    output=HERE/'source-integration.json'
    if args.check:
        assert result==json.loads(output.read_text())
    else:
        with output.open('x') as stream:
            json.dump(result,stream,indent=2)
            stream.write('\n')
    print(json.dumps(result))
