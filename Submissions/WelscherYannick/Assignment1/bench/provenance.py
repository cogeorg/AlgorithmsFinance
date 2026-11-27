#!/usr/bin/env python3
"""Provenance that survives copying the folder into the course repository.

Writes
  results/code_fingerprint.json  SHA-256 of every code file now and in the measured commit
                                 (results/env.json -> git_commit), plus the lob/ diff between them;
  provenance/git_history.txt     readable history of the working repository (oldest first);
  provenance/history.bundle      the complete working-repository history (git bundle verify / clone).
Run it after the last code commit; the bundle then contains every commit up to that point.
"""
import hashlib
import json
import subprocess

from _util import RESULTS, ROOT, save_json


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def main():
    measured = json.loads((RESULTS / "env.json").read_text())["git_commit"]
    head = git("rev-parse", "HEAD").decode().strip()
    files = git("ls-files", "lob", "bench", "tests", "dashboard/build.py", "replay.py").decode().split()
    rows = []
    for f in files:
        now = hashlib.sha256((ROOT / f).read_bytes()).hexdigest()
        try:
            then = hashlib.sha256(git("show", f"{measured}:{f}")).hexdigest()
        except subprocess.CalledProcessError:
            then = None  # file did not exist in the measured commit
        rows.append({"file": f, "sha256_submitted": now, "sha256_measured_commit": then, "identical": now == then})
    lob = [r for r in rows if r["file"].startswith("lob/")]
    save_json(RESULTS / "code_fingerprint.json", {
        "measured_commit": measured, "fingerprinted_at_commit": head,
        "engine_files_identical": all(r["identical"] for r in lob),
        "lob_diff_vs_measured_commit": git("diff", measured, "--", "lob").decode(),
        "files": rows})
    out = ROOT / "provenance"
    out.mkdir(exist_ok=True)
    (out / "git_history.txt").write_bytes(git("log", "--reverse", "--date=iso", "--stat",
                                              "--format=commit %H%nDate:   %ad%n%n    %s%n"))
    subprocess.run(["git", "bundle", "create", str(out / "history.bundle"), "--all"], cwd=ROOT, check=True,
                   capture_output=True)
    changed = [r["file"] for r in lob if not r["identical"]]
    print(f"measured {measured[:8]} -> now {head[:8]}; engine files changed since measurement: {changed or 'none'}")


if __name__ == "__main__":
    main()
