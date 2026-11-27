"""Regression contracts for submission copies without checkout provenance."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def submission_copy(tmp_path):
    copy = tmp_path/'submission'; copy.mkdir()
    for name in ('01_code','02_tests','04_dashboard'):
        shutil.copytree(ROOT/name,copy/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    files = ['run.py','submission_tools.py','pytest.ini','requirements.txt','SPEC.md',
             '00_docs/POST_ATTACK_MANIFEST.json','00_docs/FINAL_SELECTION.md',
             '06_data/supplied/generate_orders.py','07_attack/ATTACK_REPORT.md',
             '.streamlit/config.toml','05_evidence/final-b-registry-verification.json',
             '05_evidence/final-b-all-tests.xml','05_evidence/final-b-attack-tests.xml',
             '05_evidence/INDEX.md']
    for name in files:
        dest=copy/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,dest)
    sys.path.insert(0,str(ROOT/'04_dashboard'))
    import saved_results
    for run in saved_results.RUNS.values():
        dest=copy/'03_results/runs'/run;dest.mkdir(parents=True)
        for path in (ROOT/'03_results/runs'/run).iterdir():
            if path.is_file():shutil.copy2(path,dest/path.name)
    assert not (copy/'.git').exists()
    env=os.environ.copy();env['GIT_CEILING_DIRECTORIES']=str(tmp_path.resolve())
    return copy,env


def child(copy,env,*args,timeout=180):
    return subprocess.run([sys.executable,*args],cwd=copy,env=env,capture_output=True,
                          text=True,encoding='utf-8',timeout=timeout)


@pytest.mark.parametrize('mode',['no_checkout','no_git'])
def test_dashboard_loader_contract_in_no_checkout_copy(submission_copy,mode):
    copy,env=submission_copy
    if mode=='no_git':env['PATH']=''
    result=child(copy,env,'-m','pytest','-q',
        '02_tests/test_dashboard.py::test_loader_restricts_paths_and_uses_a_fixed_commit',
        '--basetemp=scratch/loader-contract')
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert '1 passed' in result.stdout


def test_submission_smoke_in_no_checkout_copy(submission_copy):
    copy,env=submission_copy
    # Also reject a misleading ancestor checkout around an ignored scratch copy.
    env.pop('GIT_CEILING_DIRECTORIES',None)
    result=child(copy,env,'-m','submission_tools','smoke',timeout=240)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    provenance='no git checkout (source not commit-verified)'
    assert provenance in result.stdout
    assert 'OK: smoke 108 workers; sampled result checks passed' in result.stdout
    runs=list((copy/'scratch').glob('submission_smoke_*/03_results/runs/*'))
    assert len(runs)==1
    metadata=json.loads((runs[0]/'env.json').read_text(encoding='utf-8'))
    assert metadata['source_provenance']==provenance
    assert metadata['source_commit_verified'] is False
    assert metadata['source_dirty_paths'] is None
    assert len(metadata['source_sha256'])==64


@pytest.mark.parametrize('resume',[False,True],ids=['new','resume'])
def test_official_run_rejected_without_checkout(submission_copy,resume):
    copy,env=submission_copy
    catalog=json.loads((copy/'00_docs/POST_ATTACK_MANIFEST.json').read_text(encoding='utf-8'))
    entry=next(e for e in catalog['entries'] if e['part']=='official' and e['size']==1000)
    (copy/'catalog.json').write_text(json.dumps({'entries':[entry]}),encoding='utf-8')
    before={p.name for p in (copy/'03_results/runs').iterdir()}
    if resume:
        script="""
from pathlib import Path
import json,sys
sys.path.insert(0,'01_code')
from bench.run_all import fingerprint
Path('scratch').mkdir()
Path('scratch/bench_session_portability.json').write_text(json.dumps(dict(
 source_sha256=fingerprint(),run_dir='03_results/runs/forbidden-resume',
 limit_s=600,limit_bytes=4*1024**3)))
"""
        prepared=child(copy,env,'-c',script)
        assert prepared.returncode==0,prepared.stderr
    result=child(copy,env,'-m','run','bench.run_all','--part','official','--allow-long',
                 '--manifest','catalog.json','--versions','B3r','--modes','timing',
                 '--session','portability')
    assert result.returncode!=0
    assert 'official runs require committed source in a git checkout' in result.stderr
    assert {p.name for p in (copy/'03_results/runs').iterdir()}==before
    assert '[1/' not in result.stdout


def test_official_run_still_rejects_dirty_source(tmp_path,monkeypatch):
    from argparse import Namespace
    import bench.run_all as runner
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runner,'fingerprint',lambda:'source-under-test')
    monkeypatch.setattr(runner,'source_dirty',lambda:['01_code/bench/run_all.py'])
    with pytest.raises(ValueError,match='official runs require committed source; changed paths'):
        runner.get_run(Namespace(session=None,part='official',limit_s=600,limit_bytes=4*1024**3))


def test_missing_git_smoke_metadata_is_unverified(submission_copy):
    copy,env=submission_copy;env['PATH']=''
    script="""
import json,sys
from argparse import Namespace
sys.path.insert(0,'01_code')
from bench.run_all import get_run
path=get_run(Namespace(session=None,part='smoke',limit_s=600,limit_bytes=4*1024**3))
env=json.loads((path/'env.json').read_text())
assert env['source_provenance']=='no git checkout (source not commit-verified)'
assert env['source_commit_verified'] is False
assert env['source_dirty_paths'] is None
print('PASS: missing Git is explicitly unverified')
"""
    result=child(copy,env,'-c',script)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
