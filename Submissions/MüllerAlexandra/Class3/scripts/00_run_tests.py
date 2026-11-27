"""Run the Class 3 test suite with the active Python interpreter."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
raise SystemExit(subprocess.call([sys.executable, "-m", "pytest"], cwd=ROOT))
