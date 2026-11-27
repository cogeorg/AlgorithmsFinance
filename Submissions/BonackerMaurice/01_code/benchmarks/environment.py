"""Machine, Python, package and git details saved with every run.

Deliberately omits the hostname, user name and absolute paths (the repository is public).
"""
import hashlib
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

PACKAGES = ("pytest", "streamlit", "altair", "pandas", "psutil")


def _cpu_name() -> str:
    try:
        if sys.platform == "win32":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        if sys.platform == "darwin":
            return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                  capture_output=True, text=True).stdout.strip()
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or "unknown"


def _ram_bytes():
    try:
        import psutil  # optional
        return psutil.virtual_memory().total
    except Exception:
        return None


def _git(project_dir, *args):
    """Command output, or None if git is missing or the command fails."""
    try:
        out = subprocess.run(["git", *args], cwd=project_dir, capture_output=True,
                             text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def git_info(project_dir) -> dict:
    """dirty: True/False, or None when git cannot tell (no git, not a repository)."""
    commit = _git(project_dir, "rev-parse", "HEAD")
    # Dirty = uncommitted changes in the code folder (01_code/: algorithms, generator,
    # benchmarks, tests, dashboard). Docs and 02_results/ do not affect measurements.
    status = _git(project_dir, "status", "--porcelain", "--", ".")
    return {"commit": commit or None, "short": commit[:7] if commit else None,
            "branch": _git(project_dir, "rev-parse", "--abbrev-ref", "HEAD") or None,
            "dirty": None if status is None else bool(status),
            "dirty_files": status.splitlines() if status else []}


SOURCE_DIRS = ("search_algos", "datagen", "benchmarks")


def source_fingerprint(project_dir) -> dict:
    """SHA-256 over the measured code (works without git; line endings normalized).
    Recomputed at the end of a run to prove the code did not change mid-run."""
    digest = hashlib.sha256()
    files = sorted(p for d in SOURCE_DIRS for p in (Path(project_dir) / d).rglob("*.py"))
    for path in files:
        digest.update(path.relative_to(project_dir).as_posix().encode() + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return {"sha256": digest.hexdigest(), "files": len(files), "dirs": list(SOURCE_DIRS)}


def collect_environment(project_dir) -> dict:
    clock = time.get_clock_info("perf_counter")
    packages = {}
    for name in PACKAGES:
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_build": " ".join(platform.python_build()),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu": _cpu_name(),
        "cpu_count_logical": os.cpu_count(),
        "ram_bytes": _ram_bytes(),
        "timer": {"function": "time.perf_counter", "implementation": clock.implementation,
                  "resolution_s": clock.resolution, "monotonic": clock.monotonic},
        "packages": packages,
        "git": git_info(project_dir),
        "source": source_fingerprint(project_dir),
    }
