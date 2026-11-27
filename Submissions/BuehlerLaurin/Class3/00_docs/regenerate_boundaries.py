"""Regenerate ignored all-asset boundary CSVs only; no benchmark reruns."""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    run=args.run.resolve()
    if not run.is_relative_to((root/'03_results/runs').resolve()):
        raise ValueError('Run must be inside this submission/03_results/runs')
    manifest=json.loads((run/'BOUNDARIES_MANIFEST.json').read_text(encoding='utf-8'))
    files=manifest['files']
    if not args.verify_only:
        sys.path.insert(0,str(root/'01_code'))
        from amput.pipeline import analyze
        from bench.run_lab import boundary_csv
        recorded=json.loads((run/'source_sha256.json').read_text(encoding='utf-8'))
        for rel,digest in recorded.items():
            if Path(rel).as_posix().replace('\\','/').startswith('01_code/'):
                if hashlib.sha256((root/rel).read_bytes()).hexdigest()!=digest:
                    raise ValueError(f'Measured source changed: {rel}')
        data=root.parents[2]/'Class3/data/hourly'
        for rel in sorted(files):
            destination=(run/rel).resolve()
            if not destination.is_relative_to(run):
                raise ValueError('Manifest path escapes run')
            window='1y' if rel.startswith('ALL1y_') else '5y'
            symbol=destination.stem
            destination.parent.mkdir(exist_ok=True)
            analysis=analyze(data/(symbol+'.csv'),window,'B')
            boundary_csv(destination,analysis)
            print(f'Regenerated {rel}',flush=True)
    for rel,info in files.items():
        path=run/rel
        if hashlib.sha256(path.read_bytes()).hexdigest()!=info['sha256']:
            raise ValueError(f'Boundary hash mismatch: {rel}')
    print(f'BOUNDARIES MANIFEST: PASS ({len(files)} files; no timing/memory benchmarks executed)')


if __name__=='__main__':
    main()
