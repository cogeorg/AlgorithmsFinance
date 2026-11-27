"""Fetch pinned teacher CSVs and verify their Git blob hashes."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent

def main():
    manifest = ROOT / 'data_manifest.json'
    listing = json.loads(manifest.read_text())
    def download(entry):
        path = ROOT / 'work/data/hourly' / entry['name']
        data = path.read_bytes() if path.exists() else subprocess.run(
            ['curl', '-fsSL', '--retry', '3', '--max-time', '120', entry['download_url']],
            capture_output=True, check=True).stdout
        blob = b'blob ' + str(len(data)).encode() + b'\0' + data
        if hashlib.sha1(blob).hexdigest() != entry['sha']:
            raise ValueError(f"Git blob hash mismatch: {entry['name']}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return dict(entry, sha256=hashlib.sha256(data).hexdigest())
    with ThreadPoolExecutor(max_workers=4) as pool:
        listing['files'] = list(pool.map(download, listing['files']))
    assert len(listing['files']) == 40
    manifest.write_text(json.dumps(listing, indent=2) + '\n')
    print('Verified 40 data files at', listing['commit'], flush=True)

if __name__ == '__main__':
    main()
