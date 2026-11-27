"""Extra 5: Bitcoin price path with the early-exercise boundary, drawn from saved results.

    python3 Submissions/HuangJiaxin/Class3/plot_btc.py           # reads results/btc_*_boundary.csv

Writes results/btc_<label>_boundary.png and .pdf. Does not rerun any pricing.
"""
import csv
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / (sys.argv[1] if len(sys.argv) > 1 else "results")


def plot(label):
    path = RESULTS / f"btc_{label}_boundary.csv"
    if not path.exists():
        return
    rows = list(csv.DictReader(open(path)))
    times = [datetime.fromisoformat(r["timestamp_utc"]) for r in rows]
    price = [float(r["price"]) for r in rows]
    bound = [float(r["boundary"]) if r["boundary"] else float("nan") for r in rows]
    K = price[0]
    ex = next((t for t in range(1, len(rows))
               if bound[t] == bound[t] and price[t] <= bound[t] and K - price[t] > 0), None)

    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.plot(times, price, color="#1f4e79", lw=1, label="Bitcoin close (USDT)")
    ax.plot(times, bound, color="#c0504d", lw=1.2, label="Early-exercise boundary b(t)")
    ax.axhline(K, color="grey", ls="--", lw=0.8, label=f"Strike K = P0 = {K:,.0f}")
    ax.fill_between(times, 0, bound, color="#c0504d", alpha=0.08, step=None)
    if ex is not None:
        ax.scatter([times[ex]], [price[ex]], color="black", zorder=5,
                   label=f"First exercise: {times[ex]:%d %b %Y %H:%M} UTC, "
                         f"payoff {K - price[ex]:,.0f}")
    else:
        ax.plot([], [], " ", label="Never exercised")
    ax.set_title(f"American put on Bitcoin, {label} window: exercise when the price is "
                 f"at or below the boundary")
    ax.set_ylabel("US dollars (USDT) per BTC")
    ax.set_ylim(0, max(price) * 1.05)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2, fontsize=8,
              frameon=False)      # below the plot: never hides the price path
    ax.grid(alpha=0.3)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(RESULTS / f"btc_{label}_boundary.{ext}", dpi=150)
    plt.close(fig)
    print("saved", RESULTS / f"btc_{label}_boundary.png")


if __name__ == "__main__":
    for label in ("1y", "5y", "quick"):
        plot(label)
