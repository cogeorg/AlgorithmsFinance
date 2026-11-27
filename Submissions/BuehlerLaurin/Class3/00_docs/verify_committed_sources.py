"""Check measured source bytes against a human commit; never rerun benchmarks.

Default: read manifests/mappings and their targets from HEAD via git show.
--working-tree: precommit mapping check only; cannot certify a commit.
"""
import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime,timezone
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--working-tree',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]; repo=root.parents[2]
    prefix=root.relative_to(repo).as_posix()
    names=['20261127T120831Z_279b029-dirty_fast_blocks12','20261127T121436Z_279b029-dirty_fast_blocks12']
    def blob(path):
        return subprocess.run(['git','show','HEAD:'+path],cwd=repo,capture_output=True,check=True).stdout
    def content(path):
        return (repo/path).read_bytes() if args.working_tree else blob(path)
    head=subprocess.run(['git','rev-parse','HEAD'],cwd=repo,capture_output=True,text=True,check=True).stdout.strip()
    results=[]
    for name in names:
        run=prefix+'/03_results/runs/'+name
        recorded=json.loads(content(run+'/source_sha256.json'))
        mapping=json.loads(content(run+'/SOURCE_MAP.json'))
        if set(recorded)!=set(mapping):
            raise ValueError('Source map must cover every recorded entry exactly')
        for rel,digest in recorded.items():
            item=mapping[rel]; target=item['committed_path']
            if not target.startswith(prefix+'/') or '..' in Path(target).parts:
                raise ValueError('Source target escapes submission')
            actual=hashlib.sha256(content(target)).hexdigest()
            if actual!=digest or item['sha256']!=digest:
                raise ValueError(f'Source mismatch: {name}: {rel} -> {target}')
            results.append(dict(run=name,measured_path=rel,committed_path=target,kind=item['kind'],sha256=actual))
    if args.working_tree:
        print(f'WORKING-TREE SOURCE MAP: PASS ({len(results)} exact-byte matches; post-commit verification still pending)')
        return
    report=dict(verified_commit=head,utc=datetime.now(timezone.utc).isoformat(),
                method='git show HEAD:path raw blobs; no line-ending normalization or benchmark reruns',files=results)
    target=root/'03_results/COMMITTED_SOURCE_VERIFICATION.json'
    target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    readme=root/'README.md'; text=readme.read_text(encoding='utf-8')
    status=(f'<!-- COMMITTED_SOURCE_STATUS_BEGIN -->\nVerified against human commit `{head}`: '
            f'all {len(results)} recorded source hashes match committed Git blobs exactly via SOURCE_MAP.json '
            '(current implementation/tests plus explicit historical runner/B/SPEC snapshots). '
            'Both runs remain **quick (dirty tree)** measurements; no timings were rerun. '
            'Details: [committed-source verification](03_results/COMMITTED_SOURCE_VERIFICATION.json).\n'
            '<!-- COMMITTED_SOURCE_STATUS_END -->')
    updated,n=re.subn(r'<!-- COMMITTED_SOURCE_STATUS_BEGIN -->.*?<!-- COMMITTED_SOURCE_STATUS_END -->',lambda _:status,text,flags=re.S)
    if n!=1:
        raise ValueError('README must contain exactly one committed-source status block')
    readme.write_text(updated,encoding='utf-8')
    print(f'COMMITTED SOURCE HASHES: PASS ({len(results)} entries at {head}; README updated; no benchmark reruns)')


if __name__=='__main__':
    main()
