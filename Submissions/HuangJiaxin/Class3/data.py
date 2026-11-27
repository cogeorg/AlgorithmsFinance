"""Step 2: read hourly closes and calibrate the binomial tree (Class 3 slides 29 and 30).

Data: Class3/data/hourly/<SYMBOL>.csv with columns timestamp_utc, close.
Hours without trades are missing, so the number of rows is counted, never assumed.

Calibration for a window of N + 1 closes P_0, ..., P_N:
    r_t = ln(P_t / P_{t-1}),  t = 1..N           hourly log returns
    s   = sample standard deviation of r_t     (divides by N - 1)
    u   = e^s,  d = 1/u                         one tree period = one row step (one hour)
    T   = time from P_0 to P_N in years         from the timestamps, 365.25-day years
    R   = e^(0.04 T / N)                        gross risk-free return per period
    q   = (R - d) / (u - d)                     risk-neutral probability of an up move
Contract: American put with S0 = K = P_0 (at the money), exercisable at 0..N.
"""
import csv
import math
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
HOURLY = REPO / "Class3" / "data" / "hourly"
RATE = 0.04                                  # 4 % a year, continuously compounded
SECONDS_PER_YEAR = 365.25 * 24 * 3600        # 2024 is a leap year inside the data
HOURS_PER_YEAR = 8760                        # "last year" window: N = 8,760 periods


def symbols():
    """All assets in the data folder (the S&P 500 file is optional and excluded)."""
    return sorted(p.stem for p in HOURLY.glob("*.csv") if p.stem != "SP500")


def load_closes(symbol):
    """Timestamps (UTC datetimes) and closes (floats) of one asset, in file order."""
    times, closes = [], []
    with open(HOURLY / f"{symbol}.csv", newline="") as f:
        for row in csv.DictReader(f):
            times.append(datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00")))
            closes.append(float(row["close"]))
    if any(not (c > 0) for c in closes):
        raise ValueError(f"{symbol}: non-positive close")
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError(f"{symbol}: timestamps not strictly increasing")
    return times, closes


def window(times, closes, n):
    """The last n + 1 closes (n periods). n=None means the whole file."""
    if n is None:
        n = len(closes) - 1
    if not 1 <= n <= len(closes) - 1:
        raise ValueError(f"need 1 <= n <= {len(closes) - 1}, got {n}")
    return times[-(n + 1):], closes[-(n + 1):]


def calibrate(times, closes, rate=RATE):
    """Tree parameters for one window (see module docstring). Needs N >= 2."""
    n = len(closes) - 1
    if n < 2:
        raise ValueError("need at least 3 closes for a sample standard deviation")
    r = [math.log(b / a) for a, b in zip(closes, closes[1:])]
    mean = sum(r) / n
    s = math.sqrt(sum((x - mean) ** 2 for x in r) / (n - 1))
    u = math.exp(s)
    d = 1 / u
    years = (times[-1] - times[0]).total_seconds() / SECONDS_PER_YEAR
    R = math.exp(rate * years / n)
    if not 0 < d < R < u:
        raise ValueError(f"no-arbitrage condition d < R < u fails: d={d}, R={R}, u={u}")
    q = (R - d) / (u - d)
    return {"N": n, "S0": closes[0], "K": closes[0], "s": s, "u": u, "d": d, "R": R, "q": q,
            "T_years": years, "hours_spanned": (times[-1] - times[0]).total_seconds() / 3600,
            "start": times[0].isoformat(), "end": times[-1].isoformat()}
