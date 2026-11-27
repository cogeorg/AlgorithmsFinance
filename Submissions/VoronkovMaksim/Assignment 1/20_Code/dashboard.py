"""Plot saved diagnostics; pass additional result directories to compare versions."""
import argparse
import csv
import json
import statistics
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / '40_Results' / 'diagnostic_v1_20261123_152031'
OUTPUT = ROOT / '40_Results' / 'diagnostic_dashboard'


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row['algorithm_version'] = row['version']
    return rows


def median(rows, field):
    return statistics.median(float(row[field]) for row in rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories', nargs='*', type=Path, default=[DEFAULT],
                        help='one or more result directories; default is the saved Version A run')
    args = parser.parse_args()
    OUTPUT.mkdir(exist_ok=True)
    datasets = []
    for directory in args.directories:
        directory = directory if directory.is_absolute() else ROOT / directory
        with (directory / 'environment.json').open(encoding='utf-8') as f:
            meta = json.load(f)
        data = {name: read_csv(directory / (name + '.csv'))
                for name in ('timing', 'latency', 'memory', 'diagnostics')}
        versions = {r['algorithm_version'] for rows in data.values() for r in rows}
        if len(versions) != 1:
            raise ValueError(f'{directory}: expected exactly one algorithm version')
        version = versions.pop()
        # Each series carries settings and source so differing runs remain identifiable.
        label = f"{version} | seed {meta['seed']}, levels {meta['levels']} | {directory.name}"
        datasets.append((label, data, meta))

    plt.rcParams.update({'font.size': 9, 'axes.grid': True, 'grid.alpha': .22,
                         'figure.facecolor': 'white'})
    fig, axes = plt.subplots(4, 2, figsize=(20, 22), layout='constrained')
    ax_runtime, ax_throughput, ax_latency, ax_memory, ax_sell, ax_growth, ax_cancel, ax_table = axes.flat
    summary = []
    for dataset_index, (label, data, meta) in enumerate(datasets):
        timing, lat, mem, diag = (data[x] for x in ('timing', 'latency', 'memory', 'diagnostics'))
        scenarios = sorted({r['scenario'] for r in timing})
        for scenario in scenarios:
            subset = [r for r in timing if r['scenario'] == scenario]
            sizes = sorted({int(r['events']) for r in subset})
            meds = [median([r for r in subset if int(r['events']) == n], 'elapsed_seconds') for n in sizes]
            series_label = f'{scenario} — {label}'
            ax_runtime.plot(sizes, meds, marker='o', label=series_label)
            ax_throughput.plot(sizes, [n/t for n, t in zip(sizes, meds)], marker='o', label=series_label)
            for n, t in zip(sizes, meds):
                summary.append(dict(algorithm_version=subset[0]['algorithm_version'], source=label,
                                    scenario=scenario, events=n, median_seconds=t,
                                    throughput_events_per_second=n/t))
        for group, marker in (('LIMIT', 'o'), ('MARKET_SELL', 's'), ('CANCEL', '^')):
            for row in lat:
                if row['events'] == '10000' and row['group'] == group:
                    ax_latency.plot([f"{row['scenario']}\n{group}"], [float(row['median_us'])], marker=marker,
                                    color=f'C{dataset_index}', linestyle='none')
                    ax_latency.vlines(f"{row['scenario']}\n{group}", float(row['median_us']), float(row['p99_us']),
                                      color=f'C{dataset_index}', alpha=.6)
                    ax_latency.scatter(f"{row['scenario']}\n{group}", float(row['p95_us']), marker='_', color=f'C{dataset_index}')
                    ax_latency.scatter(f"{row['scenario']}\n{group}", float(row['p99_us']), marker='x', color=f'C{dataset_index}')
        for row in mem:
            if row['events'] == '10000':
                x = f"{row['scenario']}\n{row['algorithm_version']} ({dataset_index + 1})"
                ax_memory.bar(x, int(row['peak_traced_bytes'])/1024**2, alpha=.7)
                ax_memory.annotate(f"{row['peak_active_orders']}", (x, int(row['peak_traced_bytes'])/1024**2),
                                   ha='center', xytext=(0, 3), textcoords='offset points', fontsize=8)
        for levels in sorted({int(r['price_levels']) for r in diag if r['test'] == 'sell'}):
            subset = [r for r in diag if r['test'] == 'sell' and int(r['price_levels']) == levels]
            percents = sorted({int(r['percent']) for r in subset})
            ax_sell.plot(percents, [median([r for r in subset if int(r['percent']) == p], 'elapsed_seconds') for p in percents],
                         marker='o', label=f'{levels} prices — {label}')
            for p in percents:
                matching = [r for r in subset if int(r['percent']) == p]
                counts = {(r['fills'], r['unfilled_qty']) for r in matching}
                if len(counts) != 1:
                    raise ValueError('trial fills or residuals differ across repeats')
                fills, unfilled = counts.pop()
                ax_table.text(.02, .96 - len(ax_table.texts)*.055,
                              f'{label}: {levels} prices, {p}%: {fills} fills, {unfilled} units unfilled',
                              transform=ax_table.transAxes, va='top', fontsize=8)
        growth = [r for r in lat if r['scenario'] == 'buildup' and r['events'] == '10000'
                  and r['group'] in ('early_10_percent', 'late_10_percent')]
        growth.sort(key=lambda r: 0 if r['group'].startswith('early') else 1)
        if growth:
            ax_growth.plot([r['group'].replace('_10_percent', '') for r in growth],
                           [float(r['median_us']) for r in growth], marker='o', label=label)
        cancels = [r for r in diag if r['test'] == 'cancel_last']
        sizes = sorted({int(r['initial_orders']) for r in cancels})
        if sizes:
            ax_cancel.plot(sizes, [1e6*median([r for r in cancels if int(r['initial_orders']) == n], 'elapsed_seconds')
                                   for n in sizes], marker='o', label=label)

    for ax in (ax_runtime, ax_throughput):
        ax.set_xscale('log'); ax.set_yscale('log'); ax.set_xlabel('Events (log scale)')
        ax.legend(fontsize=6, loc='best')
    ax_runtime.set(title='Replay time', ylabel='Median seconds (log scale)')
    ax_throughput.set(title='Throughput: events ÷ median replay time', ylabel='Events / second (log scale)')
    ax_latency.set(title='10,000 events: median marker, p95 dash, p99 cross', ylabel='Processing latency (µs, log scale)')
    ax_latency.set_yscale('log'); ax_latency.tick_params(axis='x', labelrotation=45, labelsize=7)
    for dataset_index, (label, _, _) in enumerate(datasets):
        ax_latency.plot([], [], marker='o', linestyle='none', color=f'C{dataset_index}', label=label)
    ax_latency.legend(fontsize=6, loc='upper left')
    ax_latency.text(.01, .01, 'Absent event types have no saved latency.', transform=ax_latency.transAxes, fontsize=8)
    ax_memory.set(title='Peak traced memory; labels show peak active orders', ylabel='MiB (log scale)')
    ax_memory.set_yscale('log'); ax_memory.tick_params(axis='x', labelrotation=55, labelsize=6)
    ax_memory.margins(y=.25)
    ax_memory.text(.01, .01, 'Traced Python allocations, not total process memory.', transform=ax_memory.transAxes, fontsize=8)
    ax_sell.set(title='Large market sells: median of five trials', xlabel='Percent of available bid quantity', ylabel='Seconds')
    ax_sell.set_xticks([10, 100, 200]); ax_sell.legend(fontsize=6)
    ax_growth.set(title='Buildup: first and last 10% of events', ylabel='Median processing latency (µs)')
    ax_growth.legend(fontsize=6)
    ax_cancel.set(title='Cancel last order in book', xlabel='Initial active orders (log scale)', ylabel='Median latency (µs)')
    ax_cancel.set_xscale('log'); ax_cancel.legend(fontsize=6)
    ax_table.axis('off'); ax_table.set_title('Liquidation outcomes (quantity units)')
    if not ax_table.texts:
        ax_table.text(.02, .9, 'No sell-trial data available.', transform=ax_table.transAxes)
    fig.suptitle('Order book diagnostic dashboard — saved measurements only', fontsize=17)
    fig.text(.5, .001, 'Source IDs and settings appear in legends; check sources.txt for machine and Python differences before comparing runs.', ha='center', fontsize=8)
    fig.savefig(OUTPUT / 'overview.png', dpi=160)
    plt.close(fig)
    with (OUTPUT / 'summary.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0]))
        writer.writeheader(); writer.writerows(summary)
    with (OUTPUT / 'sources.txt').open('w', encoding='utf-8') as f:
        for label, _, meta in datasets:
            f.write(label + '\n' + json.dumps(meta, indent=2) + '\n')
    print(f'Dashboard written to {OUTPUT}')


if __name__ == '__main__':
    main()
