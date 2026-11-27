"""Small reproduction commands: python -m submission_tools --help.

No engine implementation lives here. The smoke copies unchanged code into a
fresh scratch workspace so the established runner cannot touch saved results.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def check_worked(path):
    """Check CLI results, final book and both proceeds fields against the fixture."""
    sys.path.insert(0,str(ROOT/'01_code'))
    from lob import METHODS
    from lob.replay import read_events
    expected = read_json(ROOT/'06_data/supplied/worked_expected.json')
    actual = [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    book = METHODS[('lob','B')]()
    replayed = [book.process(event) for event in read_events(ROOT/'06_data/supplied/worked_example.jsonl')]
    if actual != replayed:
        raise ValueError('worked CLI rows differ from final Version B replay')
    result = actual[-1]
    if {k:result[k] for k in expected['market_sell_result']} != expected['market_sell_result']:
        raise ValueError('market_sell_result differs from worked_expected.json')
    if book.snapshot() != expected['remaining_orders']:
        raise ValueError('remaining_orders differs from worked_expected.json')
    proceeds = sum(fill['price_ticks']*fill['qty_units'] for fill in result['fills'])
    if proceeds != expected['gross_proceeds_tick_units'] or f'{Decimal(proceeds)/10**10:.2f}' != expected['gross_proceeds_usd']:
        raise ValueError('proceeds differ from worked_expected.json')
    print('OK: worked example = worked_expected.json (CLI rows, fills, final book, proceeds)',flush=True)


def regenerate(workspace, *, small=False, verify_only=False):
    """Replay saved generator commands; verify content and record archive hashes.

    A different zlib may produce different gzip bytes. That is reported, never
    represented as an exact archive match; decoded content must still match.
    Committed manifests are read only; the local catalog stays ignored.
    """
    catalog = read_json(ROOT/'00_docs/POST_ATTACK_MANIFEST.json')
    entries = [dict(e) for e in catalog['entries'] if not small or
               (e['size'] == 1000 and e['seed'] == 42 and e['part'] != 'post_attack')]
    generators = {'supplied':'06_data/supplied/generate_orders.py',
                  'adversarial':'01_code/datagen/adversarial.py',
                  'own':'01_code/datagen/benchmark_own.py',
                  'post_attack':'01_code/datagen/attack_cases.py'}
    done = {}
    for entry in entries:
        generator = workspace/generators[entry['kind']]
        source = generator.read_bytes()
        actual_source_sha = hashlib.sha256(source).hexdigest()
        if actual_source_sha != entry['generator_sha256']:
            # Git may convert own Python sources to CRLF in a Windows checkout.
            # Preserve the bytes; accept only a proven line-ending-only change.
            lf = source.replace(b'\r\n',b'\n')
            variants = (hashlib.sha256(lf).hexdigest(),hashlib.sha256(lf.replace(b'\n',b'\r\n')).hexdigest())
            if entry['kind'] == 'supplied' or entry['generator_sha256'] not in variants:
                raise ValueError('generator SHA-256 mismatch: '+str(generator))
            print('GENERATOR LINE-ENDINGS ONLY: '+str(generator),flush=True)
        entry['reference_generator_sha256'] = entry['generator_sha256']
        entry['generator_sha256'] = actual_source_sha
        path = workspace/entry['path']
        if path not in done:
            if not path.exists():
                if verify_only: raise ValueError('missing generated input: '+str(path))
                subprocess.run([sys.executable,*entry['command'][1:]],cwd=workspace,check=True,
                               stdout=subprocess.DEVNULL)
            digest = hashlib.sha256(); events = 0
            with gzip.open(path,'rb') as stream:
                for chunk in iter(lambda:stream.read(1<<20),b''):
                    digest.update(chunk); events += chunk.count(b'\n')
            done[path] = dict(content_sha256=digest.hexdigest(),events=events,
                              sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size)
        stats = done[path]
        if any(stats[k] != entry[k] for k in ('events','content_sha256')):
            raise ValueError('generated content mismatch: '+entry['id'])
        exact = stats['sha256'] == entry['sha256']
        entry['reference_sha256'] = entry['sha256']
        entry.update(stats)
        print(('SHA256 OK: ' if exact else 'CONTENT OK; gzip SHA256 differs: ')+entry['id']+' '+stats['sha256'],flush=True)
    catalog = dict(entries=entries,data_only_not_measurement=True,
                   created_utc=datetime.now(timezone.utc).isoformat(),
                   physical_files=len(done),physical_compressed_bytes=sum(s['bytes'] for s in done.values()),
                   reproduction_reference='00_docs/POST_ATTACK_MANIFEST.json')
    path = workspace/'06_data/generated/reproduction/manifest.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(catalog,indent=2)+'\n',encoding='utf-8')
    print(f'OK: {len(entries)} catalog entries / {len(done)} files; local manifest: {path}',flush=True)
    return path


def smoke():
    (ROOT/'scratch').mkdir(exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix='submission_smoke_',dir=ROOT/'scratch'))
    for name in ('01_code','02_tests'):
        shutil.copytree(ROOT/name,workspace/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (workspace/'06_data/supplied').mkdir(parents=True)
    shutil.copy2(ROOT/'06_data/supplied/generate_orders.py',workspace/'06_data/supplied/generate_orders.py')
    for name in ('run.py','SPEC.md','requirements.txt','pytest.ini'):
        shutil.copy2(ROOT/name,workspace/name)
    print('SMOKE ONLY: M=1000, seed 42, A/B3r; all inputs/results under '+str(workspace),flush=True)
    manifest = regenerate(workspace,small=True)
    subprocess.run([sys.executable,'-m','run','bench.run_all','--part','smoke',
                    '--versions','A,B3r','--max-size','1000','--manifest',str(manifest)],
                   cwd=workspace,check=True)
    runs = list((workspace/'03_results/runs').iterdir())
    if len(runs) != 1: raise ValueError('smoke did not produce exactly one run')
    # A stopped worker is not a successful smoke, even if no worker crashed.
    import csv
    with (runs[0]/'cells.csv').open(encoding='utf-8',newline='') as stream:
        cells = list(csv.DictReader(stream))
    if not cells or any(r['status'] != 'ok' or int(r['size']) != 1000 for r in cells):
        raise ValueError('smoke has missing/stopped/failed or non-1k workers')
    print(f'OK: smoke {len(cells)} workers; sampled result checks passed; {runs[0]}',flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    worked = sub.add_parser('check-worked'); worked.add_argument('path',type=Path)
    sub.add_parser('smoke')
    data = sub.add_parser('data'); data.add_argument('--verify-only',action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'check-worked': check_worked(args.path)
        elif args.command == 'smoke': smoke()
        else: regenerate(ROOT,verify_only=args.verify_only)
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError) as exc:
        print('FAIL: '+str(exc),file=sys.stderr); return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
