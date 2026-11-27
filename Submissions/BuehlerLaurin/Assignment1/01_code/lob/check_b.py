"""Compatibility command: run the maintained pytest internal checks.

Usage: python run.py lob.check_b
All assertions live in 02_tests/test_b_internal.py and run in the full suite.
"""
import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[2]
    return subprocess.run([sys.executable, "-m", "pytest", "-q",
                           "02_tests/test_b_internal.py"], cwd=root).returncode


if __name__ == "__main__":
    raise SystemExit(main())
