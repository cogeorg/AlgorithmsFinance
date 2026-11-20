"""Reproduce false stale-source warnings after harmless line-ending conversion."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile


def load_dashboard(path: Path):
    spec = importlib.util.spec_from_file_location("audited_dashboard", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load audited dashboard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_lf_bytes(path: Path) -> bytes:
    text = path.read_text(encoding="utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "LiuHaina",
        help="Path to the pinned Submissions/LiuHaina directory",
    )
    args = parser.parse_args()
    target = args.target.resolve()

    with tempfile.TemporaryDirectory(prefix="liuhaina-crlf-audit-") as temporary:
        copied = Path(temporary) / "LiuHaina"
        shutil.copytree(target, copied)
        metadata = json.loads((copied / "results" / "metadata.json").read_text())

        # Simulate Git's normal LF-to-CRLF checkout conversion in the copy only.
        for name in metadata["source_sha256"]:
            path = copied / name
            canonical = canonical_lf_bytes(path).decode("utf-8")
            path.write_text(canonical.replace("\n", "\r\n"), encoding="utf-8", newline="")

        dashboard = load_dashboard(copied / "dashboard.py")
        payload = dashboard.build_payload(copied / "results")
        mismatches = payload["source_mismatches_at_build"]
        print(f"dashboard_source_mismatches={mismatches}")

        normalized_matches = []
        for name, expected in metadata["source_sha256"].items():
            actual = hashlib.sha256(canonical_lf_bytes(copied / name)).hexdigest()
            normalized_matches.append(actual == expected)
        print(f"all_lf_normalized_hashes_match={all(normalized_matches)}")

        expected_names = set(metadata["source_sha256"])
        if set(mismatches) != expected_names or not all(normalized_matches):
            raise AssertionError("The line-ending false positive was not reproduced")

    print("BUG REPRODUCED: semantically unchanged CRLF files are reported as stale")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
