"""Verify supplied data against its checksums before using it.

Usage:
    python verify_manifest.py <package_dir>               # uses <dir>/MANIFEST.json if present
    python verify_manifest.py <package_dir> --metadata    # also checks every *.metadata.json

MANIFEST.json shape: {"files": {"<relative path>": {"sha256": "...", "bytes": N}, ...}}
*.metadata.json shape: {"sha256": "...", ...} next to the data file it describes.
Prints one line per file (OK / MISMATCH / MISSING) and the number of files verified.

FAIL (exit 1) when: the directory does not exist · nothing was verified · a checksum
differs · a file listed in MANIFEST.json is missing · a data file referenced by a
*.metadata.json is missing. Missing OS clutter files (.DS_Store, Thumbs.db) are
reported but do not fail. A metadata file without a sha256 is reported, not counted.
"""
import hashlib
import json
import sys
from pathlib import Path

CLUTTER = {".DS_Store", "Thumbs.db"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__); return 2
    root = Path(sys.argv[1])
    if not root.is_dir():
        print(f"ERROR    {root} is not an existing directory")
        print("RESULT: FAIL (0 files verified)")
        return 1
    failed = False
    checked = 0
    manifest = root / "MANIFEST.json"
    if manifest.exists():
        files = json.loads(manifest.read_text(encoding="utf-8")).get("files", {})
        for rel, info in files.items():
            p = root / rel
            if not p.exists():
                fatal = Path(rel).name not in CLUTTER
                failed |= fatal
                print(f"MISSING  {rel}{'' if fatal else '  (OS clutter, ignored)'}")
                continue
            checked += 1
            if sha256(p) != info["sha256"]:
                failed = True; print(f"MISMATCH {rel}")
            else:
                print(f"OK       {rel}")
    if "--metadata" in sys.argv:
        for meta in sorted(root.rglob("*.metadata.json")):
            data = meta.with_name(meta.name[: -len(".metadata.json")])
            rel = data.relative_to(root).as_posix()
            want = json.loads(meta.read_text(encoding="utf-8")).get("sha256")
            if want is None:
                print(f"NO-SHA   {meta.relative_to(root).as_posix()} (no sha256 field, not counted)")
                continue
            if not data.exists():
                failed = True; print(f"MISSING  {rel} (referenced by metadata)")
                continue
            checked += 1
            ok = sha256(data) == want
            failed |= not ok
            print(f"{'OK      ' if ok else 'MISMATCH'} {rel} (metadata)")
    if checked == 0:
        failed = True
        print("ERROR    nothing was verified: no MANIFEST.json entries or metadata checksums found")
    print(f"RESULT: {'FAIL' if failed else 'PASS'} ({checked} files verified)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
