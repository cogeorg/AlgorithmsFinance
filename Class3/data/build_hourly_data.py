#!/usr/bin/env python3
"""Rebuild the hourly price files in Class3/data/hourly/ from Binance public data.

You do not need to run this script: the CSV files are already in the repository.
It documents where the data come from and lets anyone reproduce them.

Source: Binance spot klines (candlesticks), 1-hour interval, monthly archives at
https://data.binance.vision/?prefix=data/spot/monthly/klines/
Each output file holds one asset quoted in Tether (USDT, a US-dollar stablecoin):

    timestamp_utc,close
    2021-11-01T00:00:00Z,61560.49

`timestamp_utc` is the start of the hour; `close` is the last trade price in that
hour. Hours in which the exchange did not trade (outages) are missing, not filled.

Standard library only. Usage:
    python3 Class3/data/build_hourly_data.py            # all assets, 60 months
    python3 Class3/data/build_hourly_data.py --check    # report coverage only
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://data.binance.vision/data/spot/monthly/klines/{s}/1h/{s}-1h-{m}.zip"
FIRST_MONTH = (2021, 11)  # five full years: November 2021 to October 2026
LAST_MONTH = (2026, 10)

# PAXG is Pax Gold, a token backed by one fine troy ounce of London Good Delivery
# gold; its price tracks the gold spot price. The other assets are large
# cryptocurrencies traded against USDT over the whole window.
SYMBOLS = [
    "BTCUSDT", "PAXGUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "SOLUSDT",
    "DOGEUSDT", "DOTUSDT", "LTCUSDT", "LINKUSDT", "BCHUSDT", "TRXUSDT", "AVAXUSDT",
    "ATOMUSDT", "XLMUSDT", "ETCUSDT", "FILUSDT", "UNIUSDT", "NEARUSDT", "ALGOUSDT",
    "ICPUSDT", "AAVEUSDT", "VETUSDT", "HBARUSDT", "SANDUSDT", "MANAUSDT", "AXSUSDT",
    "EGLDUSDT", "THETAUSDT", "XTZUSDT", "GRTUSDT", "CHZUSDT", "CRVUSDT", "COMPUSDT",
    "SNXUSDT", "ENJUSDT", "ZECUSDT", "DASHUSDT", "NEOUSDT",
]


def months():
    y, m = FIRST_MONTH
    while (y, m) <= LAST_MONTH:
        yield f"{y:04d}-{m:02d}"
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def fetch(url: str) -> bytes | None:
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def rows_for(symbol: str, month: str):
    blob = fetch(BASE.format(s=symbol, m=month))
    if blob is None:
        return None
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        text = z.read(z.namelist()[0]).decode()
    out = []
    for rec in csv.reader(io.StringIO(text)):
        if not rec or not rec[0].isdigit():
            continue  # header line, present in some archives
        t = int(rec[0])
        if t > 10**14:  # Binance spot switched to microseconds in 2025
            t //= 1000
        stamp = datetime.fromtimestamp(t / 1000, tz=timezone.utc)
        close = rec[4].rstrip("0").rstrip(".") if "." in rec[4] else rec[4]
        out.append((stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), close))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="report coverage only")
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("hourly"))
    ap.add_argument("symbols", nargs="*", default=SYMBOLS)
    args = ap.parse_args()
    if args.check:
        first, last = "%04d-%02d" % FIRST_MONTH, "%04d-%02d" % LAST_MONTH
        for s in args.symbols:
            ok = [fetch(BASE.format(s=s, m=m)) is not None for m in (first, last)]
            print(s, "complete" if all(ok) else "MISSING", flush=True)
        return 0
    args.out.mkdir(parents=True, exist_ok=True)
    for s in args.symbols:
        rows = []
        for m in months():
            r = rows_for(s, m)
            if r is None:
                print(f"{s}: no archive for {m}; skipped asset", file=sys.stderr)
                rows = None
                break
            rows.extend(r)
        if rows is None:
            continue
        rows = sorted(dict(rows).items())  # drop duplicate hours, keep order
        with open(args.out / f"{s}.csv", "w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["timestamp_utc", "close"])
            w.writerows(rows)
        print(f"{s}: {len(rows)} hours, {rows[0][0]} to {rows[-1][0]}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
