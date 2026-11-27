"""Regression gates for ZIP dashboards, final-B default and replay diagnostics."""
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from lob import METHODS
from lob import replay
from lob.book_b3r import OrderBookB3r

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / '04_dashboard'))
import saved_results as saved

EVENT = dict(seq=1,event_id='e1',type='LIMIT',order_id='o1',side='BUY',price_ticks=5,qty_units=1)
LINE = json.dumps(EVENT).encode('utf-8')
EXPECTED = dict(event_id='e1',order_id='o1',status='resting',unfilled_qty_units=1,fills=[])
BOM = b'\xef\xbb\xbf'


def cli(path, *args):
    return subprocess.run([sys.executable,str(ROOT / 'run.py'),'lob.replay',str(path),*args],
                          cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=45)


def test_default_replay_instantiates_final_b(monkeypatch,tmp_path,capsys):
    assert METHODS[('lob','B')] is OrderBookB3r
    created = []
    def final_book():
        created.append(OrderBookB3r)
        return OrderBookB3r()
    def wrong_default():
        raise AssertionError('default replay instantiated A instead of final B')
    monkeypatch.setattr(replay,'METHODS',{('lob','B'):final_book,('lob','A'):wrong_default})
    path = tmp_path / 'default.jsonl'; path.write_bytes(LINE+b'\n')
    monkeypatch.setattr(sys,'argv',['lob.replay',str(path)])
    replay.main()
    assert created == [OrderBookB3r]
    captured = capsys.readouterr()
    assert not captured.err and json.loads(captured.out) == EXPECTED


def test_replay_default_cli_and_help(tmp_path):
    path = tmp_path / 'default.jsonl'; path.write_bytes(LINE+b'\n')
    default, explicit = cli(path),cli(path,'--version','B3r')
    assert default.returncode == explicit.returncode == 0
    assert default.stdout == explicit.stdout
    help_result = cli(path,'--help')
    assert help_result.returncode == 0 and 'default: B' in help_result.stdout


BAD = [
    ('json',LINE+b'\n\n{broken}\n'+LINE,3,'invalid JSON',1),
    ('utf8',LINE+b'\n\n{"x":"\xff"}\n'+LINE,3,'UTF-8',1),
    ('utf16',LINE.decode().encode('utf-16'),1,'UTF-16',0),
    ('utf16le',LINE.decode().encode('utf-16-le'),1,'UTF-16',0),
    ('utf16be',LINE.decode().encode('utf-16-be'),1,'UTF-16',0),
    ('double_bom',BOM+BOM+LINE,1,'BOM',0),
    ('mid_bom',LINE+b'\n\n'+BOM+LINE,3,'BOM',1),
    ('space_bom',LINE+b'\n\n  '+BOM+LINE,3,'BOM',1),
    ('utf8_late',LINE+b'\n'+b' '*20000+b'\xff',2,'UTF-8',1),
]


@pytest.mark.parametrize('compressed',[False,True],ids=['plain','gzip'])
@pytest.mark.parametrize('name,raw,line,problem,prefix_count',BAD,ids=[x[0] for x in BAD])
def test_replay_input_error_is_one_located_line(tmp_path,compressed,name,raw,line,problem,prefix_count):
    path = tmp_path / (name+'.jsonl'+('.gz' if compressed else ''))
    path.write_bytes(gzip.compress(raw) if compressed else raw)
    result = cli(path)
    assert result.returncode != 0
    assert 'Traceback' not in result.stderr
    errors = result.stderr.splitlines()
    assert len(errors) == 1, result.stderr
    assert errors[0].startswith(f'{path}:{line}: ')
    assert problem in errors[0]
    assert len(result.stdout.splitlines()) == prefix_count
    if prefix_count: assert json.loads(result.stdout.splitlines()[0]) == EXPECTED


@pytest.mark.parametrize('compressed',[False,True],ids=['plain','gzip'])
def test_valid_bom_crlf_bare_cr_and_embedded_bom_are_preserved(tmp_path,compressed):
    second = dict(EVENT,seq=2,event_id='inside\ufeffstring',order_id='o2')
    raw = BOM+LINE+b'\r\n\r'+json.dumps(second,ensure_ascii=False).encode('utf-8')+b'\r'
    path = tmp_path / ('valid.jsonl'+('.gz' if compressed else ''))
    path.write_bytes(gzip.compress(raw) if compressed else raw)
    result = cli(path)
    assert result.returncode == 0 and not result.stderr
    assert [json.loads(s) for s in result.stdout.splitlines()] == [EXPECTED,dict(EXPECTED,event_id=second['event_id'],order_id='o2')]


@pytest.mark.parametrize('compressed',[False,True],ids=['plain','gzip'])
def test_default_valid_huge_integer_output_is_unchanged(tmp_path,compressed):
    raw = BOM+LINE.replace(b'"qty_units": 1',b'"qty_units": '+b'9'*5000)+b'\r\n'
    path = tmp_path / ('huge.jsonl'+('.gz' if compressed else ''))
    path.write_bytes(gzip.compress(raw) if compressed else raw)
    result = cli(path)
    assert result.returncode == 0 and not result.stderr
    assert json.loads(result.stdout,parse_int=lambda s:len(s))['unfilled_qty_units'] == 5000


def test_missing_git_selects_disk_mode(monkeypatch):
    def missing_git(*args,**kwargs): raise FileNotFoundError('git is unavailable')
    monkeypatch.setattr(saved.subprocess,'run',missing_git)
    assert saved.head() is None


def test_disk_store_keeps_the_allowlist(tmp_path):
    assert hasattr(saved,'DiskStore'), 'a labelled disk fallback is required'
    store = saved.DiskStore(tmp_path)
    with pytest.raises(ValueError): store.text('01_code/lob/book_a.py')
    with pytest.raises(ValueError): store.text('05_evidence/../README.md')
    assert store.text('05_evidence/missing.json') is None


@pytest.mark.parametrize('mode',['no_checkout','no_git'])
def test_every_tab_in_temporary_submission_copy_without_git(tmp_path,mode):
    copy = tmp_path / mode; copy.mkdir()
    shutil.copytree(ROOT/'04_dashboard',copy/'04_dashboard',ignore=shutil.ignore_patterns('__pycache__'))
    for run in saved.RUNS.values():
        dest = copy/'03_results/runs'/run; dest.mkdir(parents=True)
        # Exclude local per-worker journals/logs; include all top-level saved tables.
        for path in (ROOT/'03_results/runs'/run).iterdir():
            if path.is_file(): shutil.copy2(path,dest/path.name)
    files = ['00_docs/FINAL_SELECTION.md','07_attack/ATTACK_REPORT.md','.streamlit/config.toml',
             '05_evidence/final-b-registry-verification.json','05_evidence/final-b-all-tests.xml',
             '05_evidence/final-b-attack-tests.xml','05_evidence/INDEX.md']
    for name in files:
        dest = copy/name; dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,dest)
    assert not (copy/'.git').exists()
    env = os.environ.copy()
    # Test copies stay inside Assignment1; prevent Git finding its ancestor checkout.
    env['GIT_CEILING_DIRECTORIES'] = str(tmp_path.resolve())
    if mode == 'no_git': env['PATH'] = ''
    script = '''
import sys
from pathlib import Path
from streamlit.testing.v1 import AppTest
root=Path(sys.argv[1]); sys.path.insert(0,str(root/'04_dashboard'))
import saved_results
assert saved_results.head() is None
app=AppTest.from_file(str(root/'04_dashboard/app.py'),default_timeout=120).run()
assert not app.exception,[e.message for e in app.exception]
assert len(app.tabs)==9 and app.tabs[0].label=='Final selection'
assert all(len(t.dataframe)+len(t.markdown)>0 for t in app.tabs)
banner='Reading files from disk (no git checkout): values are not verified against a commit.'
assert banner in [w.value for w in app.warning]
assert app.main.children[0].value==banner
assert {m.label:m.value for m in app.metric}['B3r official 100k geomean']=='0.4247 s'
print('PASS: nine tabs, top disk banner, unchanged CSV headline, no checkout')
'''
    result = subprocess.run([sys.executable,'-c',script,str(copy)],cwd=copy,env=env,
                            capture_output=True,text=True,encoding='utf-8',timeout=150)
    assert result.returncode == 0, result.stdout+'\n'+result.stderr
    assert 'PASS: nine tabs' in result.stdout
