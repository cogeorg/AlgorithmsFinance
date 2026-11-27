"""Launcher: puts 01_code on sys.path, then runs a module as __main__.

Usage (from the exercise root):  python run.py <module> [args]
    python run.py amput                        # lists the registered versions
    python run.py amput.replay 06_data/supplied/x.jsonl
    python -m cProfile -s cumtime run.py bench.run_all
The working directory is not changed, so relative paths (03_results/, 06_data/) refer
to the exercise root.
"""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "01_code"))

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(2)
module = sys.argv[1]
sys.argv = [module] + sys.argv[2:]
runpy.run_module(module, run_name="__main__", alter_sys=True)
