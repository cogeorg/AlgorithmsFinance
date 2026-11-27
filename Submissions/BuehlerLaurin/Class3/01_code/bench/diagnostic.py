"""Independent pre-implementation data diagnostic, not the production calibrator."""
import csv
import math
import statistics
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[2]
    source = root.parents[2] / 'Class3/data/hourly'
    rows = []
    for path in sorted(source.glob('*.csv')):
        with path.open(newline='', encoding='utf-8') as f:
            closes = [float(r['close']) for r in csv.DictReader(f)]
        for window, prices in [('1y', closes[-8761:]), ('5y', closes)]:
            n = len(prices) - 1
            s = statistics.stdev([math.log(b / a) for a, b in zip(prices, prices[1:])])
            rows.append(dict(symbol=path.stem, window=window, N=n, s=s, s_times_N=s*n,
                             terminal_min_log_offset=-s*n, terminal_max_log_offset=s*n))
    target = root / '00_docs/CALIBRATION_DIAGNOSTIC.csv'
    with target.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f'Diagnostic: {len(rows)} asset/window rows -> {target.relative_to(root)}')
    print(f"s*N range: {min(r['s_times_N'] for r in rows):.6f} .. {max(r['s_times_N'] for r in rows):.6f}")


if __name__ == '__main__':
    main()
