"""Figure for Tasks 2-4: Bitcoin closes against the early-exercise boundary.

Reads results/BTCUSDT_<horizon>_boundary.csv (written by lab.py --boundary-dir) and
writes results/btc_exercise_boundary.png. Needs matplotlib (python -m pip install matplotlib).
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"

SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
PRICE, BOUNDARY = "#2a78d6", "#eb6834"          # categorical slots 1 and 2


def load(horizon):
    stamps, closes, bound = [], [], []
    with (RESULTS / f"BTCUSDT_{horizon}_boundary.csv").open() as handle:
        for row in csv.DictReader(handle):
            stamps.append(datetime.strptime(row["timestamp_utc"], "%Y-%m-%dT%H:%MZ"))
            closes.append(float(row["close_P_t"]))
            bound.append(float(row["boundary"]) if row["boundary"] else float("nan"))
    strike = closes[0]
    hit = next((i for i, (p, b) in enumerate(zip(closes, bound)) if b == b and p <= b), None)
    return stamps, closes, bound, strike, hit


LAYOUT = {  # legend position and annotation offset (points) per panel, chosen to avoid the data
    "1y": dict(legend="upper center", note=(-150, 75), strike_at=1.0),
    "5y": dict(legend="upper left", note=(16, 34), strike_at=0.15),
}


def panel(ax, horizon, title):
    layout = LAYOUT[horizon]
    stamps, closes, bound, strike, hit = load(horizon)
    ax.set_facecolor(SURFACE)
    ax.axhline(strike, color=INK_2, lw=1, ls=(0, (4, 3)), zorder=1)
    at = min(int(layout["strike_at"] * (len(stamps) - 1)), len(stamps) - 1)
    ax.text(stamps[at], strike, f"strike K = P₀ = {strike:,.0f}  ", color=INK_2,
            va="bottom", ha="right" if layout["strike_at"] >= 1 else "left", fontsize=8.5)
    ax.plot(stamps, closes, color=PRICE, lw=1.5, label="BTC close $P_t$", zorder=2)
    ax.plot(stamps, bound, color=BOUNDARY, lw=1.5, label="Exercise boundary", zorder=3)
    if hit is not None:
        ax.plot(stamps[hit], closes[hit], "o", ms=8, mfc=INK, mec=SURFACE, mew=2, zorder=4)
        ax.annotate(f"first exercise {stamps[hit]:%d %b %Y %H:%M} UTC\n"
                    f"$P_t$ = {closes[hit]:,.0f}, payoff = {strike - closes[hit]:,.0f}",
                    (stamps[hit], closes[hit]), xytext=layout["note"], textcoords="offset points",
                    fontsize=8.5, color=INK, arrowprops=dict(arrowstyle="-", color=INK_2, lw=1))
    ax.set_title(title, loc="left", fontsize=10.5, color=INK, pad=8)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:,.0f}k"))
    ax.set_ylabel("US dollars (USDT)", color=INK_2, fontsize=9)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=7))
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    ax.grid(axis="y", color=GRID, lw=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=8.5)
    ax.legend(loc=layout["legend"], frameon=False, fontsize=8.5, labelcolor=INK)


def main():
    horizons = [h for h in ("1y", "5y") if (RESULTS / f"BTCUSDT_{h}_boundary.csv").exists()]
    titles = {"1y": "One year, N = 8,760 hours", "5y": "Full file, N = 43,822 hours"}
    fig, axes = plt.subplots(len(horizons), 1, figsize=(9, 3.6 * len(horizons)), squeeze=False)
    fig.patch.set_facecolor(SURFACE)
    for ax, horizon in zip(axes[:, 0], horizons):
        panel(ax, horizon, titles[horizon])
    fig.suptitle("At-the-money American put on Bitcoin: when would the holder exercise?",
                 x=0.01, ha="left", fontsize=12, color=INK)
    fig.tight_layout()
    out = RESULTS / "btc_exercise_boundary.png"
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    print(out)


if __name__ == "__main__":
    main()
