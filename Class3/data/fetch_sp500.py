#!/usr/bin/env python3
"""Download hourly S&P 500 index levels into Class3/data/hourly/SP500.csv.

Index data are licensed by S&P Dow Jones Indices, so this repository does not
redistribute them. Run this script once on your own machine; it uses Yahoo
Finance's public chart endpoint and the Python standard library only.

    python3 Class3/data/fetch_sp500.py

The output has the same format as the other files in Class3/data/hourly/:

    timestamp_utc,close

Yahoo serves hourly bars for roughly the last two to three years only, and only
during New York trading hours (about seven bars per trading day). The file is
ignored by git: do not commit it.
"""

from __future__ import annotations

import csv
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=730d&interval=1h"


def main() -> int:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        result = json.load(r)["chart"]["result"][0]
    stamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    rows = [
        (datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), f"{c:.2f}")
        for t, c in zip(stamps, closes)
        if c is not None
    ]
    out = Path(__file__).with_name("hourly") / "SP500.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["timestamp_utc", "close"])
        w.writerows(rows)
    print(f"SP500: {len(rows)} hours, {rows[0][0]} to {rows[-1][0]} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
