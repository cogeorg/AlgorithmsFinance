"""Run a command and save it as an evidence file, the moment it happens.

Usage (from the exercise root):
    python <skills>/aif-verify/scripts/evidence.py <label> -- <command ...>
    python evidence.py tests-red -- python -m pytest -q
    python evidence.py fresh-venv-pytest -- python -m pytest -q

Writes 05_evidence/<UTC stamp>_<commit7>[-dirty]_<label>.txt with the command, cwd,
commit, dirty flag, Python version, exit code, duration and full output, and
appends one line to 05_evidence/INDEX.md. The exit code of the command is passed
through, so the script can be used in a chain. Evidence is never back-dated:
re-created evidence gets today's stamp and should say so in its label.
Timeout: 3600 s by default; override with the environment variable EVIDENCE_TIMEOUT_S.
"""
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import os

TIMEOUT_S = float(os.environ.get("EVIDENCE_TIMEOUT_S", "3600"))  # exit code 124 on timeout


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=10).stdout.strip()
    except Exception:
        return ""


def main() -> int:
    if "--" not in sys.argv or sys.argv.index("--") != 2:
        print(__doc__)
        return 2
    label = sys.argv[1].replace(" ", "-")
    cmd = sys.argv[3:]
    commit = git("rev-parse", "--verify", "-q", "HEAD")
    dirty = bool(git("status", "--porcelain"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    t0 = time.perf_counter()
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        out = out.decode("utf-8", "replace") if isinstance(out, bytes) else out
        cp = subprocess.CompletedProcess(cmd, 124, out, f"\n[evidence] TIMEOUT after {TIMEOUT_S}s\n")
    dur = time.perf_counter() - t0
    out_dir = Path("05_evidence"); out_dir.mkdir(exist_ok=True)
    base = f"{stamp}_{commit[:7] or 'nogit'}{'-dirty' if dirty else ''}_{label}"
    name, k = f"{base}.txt", 2
    while (out_dir / name).exists():          # same label within one second: never overwrite
        name, k = f"{base}-{k}.txt", k + 1
    header = (f"label: {label}\ncommand: {' '.join(cmd)}\ncwd: {Path.cwd()}\n"
              f"commit: {commit or 'n/a'}\ndirty: {dirty}\npython: {sys.version.split()[0]}\n"
              f"utc: {stamp}\nexit_code: {cp.returncode}\nduration_s: {dur:.2f}\n{'-' * 60}\n")
    (out_dir / name).write_text(header + cp.stdout + cp.stderr, encoding="utf-8")
    last = (cp.stdout.strip().splitlines() or [""])[-1][:120]
    with (out_dir / "INDEX.md").open("a", encoding="utf-8") as f:
        f.write(f"- {stamp} · {commit[:7] or 'nogit'}{' dirty' if dirty else ''} · **{label}** · "
                f"exit {cp.returncode} · `{last}` · [{name}]({name})\n")
    print(cp.stdout, end=""); print(cp.stderr, end="", file=sys.stderr)
    print(f"[evidence] saved 05_evidence/{name} (exit {cp.returncode})")
    return cp.returncode


if __name__ == "__main__":
    sys.exit(main())
