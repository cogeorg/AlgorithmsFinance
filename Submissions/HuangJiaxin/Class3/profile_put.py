"""Profiling (cProfile) of one Bitcoin one-year pricing, plain and numpy.

    python3 Submissions/HuangJiaxin/Class3/profile_put.py

Writes results/profile_plain.txt and results/profile_numpy.txt. Profiling slows the
code down, so these files are used only for shares of time, not for absolute times.
"""
import cProfile
import io
import pstats
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import data  # noqa: E402
import put  # noqa: E402

times, closes = data.load_closes("BTCUSDT")
c = data.calibrate(*data.window(times, closes, data.HOURS_PER_YEAR))
p = dict(S0=c["S0"], K=c["K"], u=c["u"], d=c["d"], R=c["R"], N=c["N"])
for name, fn in (("plain", put.price_plain), ("numpy", put.price_numpy)):
    pr = cProfile.Profile()
    pr.runcall(fn, **p)
    out = io.StringIO()
    pstats.Stats(pr, stream=out).strip_dirs().sort_stats("tottime").print_stats(12)
    (HERE / "results" / f"profile_{name}.txt").write_text(out.getvalue())
    print(name, "saved")
