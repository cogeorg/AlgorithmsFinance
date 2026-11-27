# Version A: baseline order book

The baseline keeps individual resting orders in a list. `process_event` validates an event before advancing the accepted sequence and dispatching it to `AddLimitOrder`, `CancelOrder`, or `FillMarketSell`. Call these operations through `process_event`: the three dispatch methods assume their event has already been validated. `inspect_book` returns sorted copies so callers cannot alter the live book.

For each fill, matching scans the list for the best eligible opposite-side price and uses the earliest arrival sequence to break ties. It trades at the maker's price, removes exhausted makers, and preserves the arrival sequence of partially filled makers. A limit residual rests; a market-sell residual is discarded. Cancellation removes only the target's remaining quantity.

## Pseudocode

```
AddLimitOrder(event):
    while remaining quantity and an eligible opposite order exists:
        scan for best price, then earliest arrival
        execute the smaller quantity at the maker's price
        update quantities and remove an exhausted maker
    append any residual with its original arrival sequence
    return this event's fills and residual

CancelOrder(event):
    scan for the target; remove it and return its remaining quantity
    if absent, return not_found and zero

FillMarketSell(event):
    repeatedly scan for the highest bid, then earliest arrival
    execute and update quantities until filled or no bid remains
    return fills and any discarded residual
```

## Complexity and limitations

Let B be the active order count before the operation, P the occupied price levels, and F the number of maker fills. Validation of a submission scans up to B orders for a duplicate live identifier. Appending a non-crossing limit is amortized O(1), but the full validated insertion scans the book and costs O(B). A crossing limit or market sell costs O((F+1)B) in the worst case: each fill scans for the best maker, and removing an exhausted list element can also cost O(B). Cancellation is O(B), including lookup and list removal. Inspection sorts and copies the active orders in O(B log B) time and O(B) additional space. An event's fill list uses O(F) space; resting storage uses O(B). P is at most B, but this implementation has no price-level index, so the scan costs depend on B rather than P. These are theoretical bounds, not measured bottlenecks.

  ## Verification
  

On 23 November 2026, Python 3.14.6 ran the existing suite with its version selection temporarily set to Version A in the test runner, without editing the tests. Of 19 test methods, 18 passed and the comparison of both versions was skipped. There were no failing tests and no implementation corrections were necessary during this run. The worked example confirmed makers `b1`, `b2`, `b3`, `b4` with 1, 1, 3, 1 BTC fills, $359,400 gross proceeds, four BTC remaining on `b4`, and the unchanged ask. The supplied-file manifest check also passed. Both-version differential testing awaits Version B.

## Version A — Diagnostic Performance and Bottlenecks

Indicative measurements on 23 November 2026 used Python 3.14.6 and the machine details recorded in `40_Results/diagnostic_v1_20261123_152031/environment.json`. Each input was loaded once, warmed up once, and replayed five times on fresh books. Times are medians; throughput is events divided by median replay time. File reading and parsing were measured once separately and saved with raw repeats. Inputs use seed 42 and 1,000 levels; 10,000-event files were supplied, and 1,000-event files were generated with the instructor's generator.

| Scenario | 1,000 events: seconds / events per second | 10,000 events: seconds / events per second |
|---|---:|---:|
| buildup | 0.0657 / 15,212 | 6.4078 / 1,561 |
| crowded | 0.0475 / 21,037 | 5.2559 / 1,903 |
| mixed | 0.0130 / 76,835 | 0.8026 / 12,459 |
| sweep | 0.0523 / 19,131 | 33.2677 / 301 |
| cancel churn | 0.00385 / 259,902 | 0.03037 / 329,253 |

Ten times as many events took roughly 97, 111, 62, and 636 times as long in buildup, crowded, mixed, and sweep respectively; cancellation churn took about 8 times as long. These are different generated streams and workload compositions, not a controlled estimate of a single complexity exponent. At 10,000 events, buildup and crowded reached 10,000 active orders, mixed 1,588, sweep 8,000, and churn just one.

In a separate per-event run, the 10,000-event buildup's first 10% had a 48 microsecond median versus 1,431 microseconds for the final 10%. Sweep market sells had median, 95th and 99th percentile latencies of 520, 9,985 and 16,640 microseconds. Mixed cancellations had a 29.5 microsecond median; churn cancellations had 1.5 microseconds. Percentiles use the nearest-rank convention, ceiling(p × sample count), on sorted event times. These are processing times, not network or queueing delays.

In independent five-repeat trials, 1,000 bids at four prices took a median 0.034 seconds to fill 10% (100 makers) and 0.206 seconds to fill 100% (1,000 makers). At 1,000 prices the corresponding medians were 0.051 and 0.254 seconds. The 200% requests filled all 1,000 makers and returned 10,000 units unfilled. These trials count fills and distinct executed prices; they do not count examined orders. The saved data also include construction times and cancellation trials: cancelling the final order took median 3.2 microseconds with 10 orders versus 72.9 microseconds with 1,000. Trial variability and different fill counts limit causal comparison.

Repeated list scans are the strongest supported bottleneck: buildup latency rises with book size, and large sweeps touch many makers while the code rescans the book for each fill. The diagnostic evidence is consistent with the theoretical cost; it does not isolate every contribution such as duplicate-ID validation or list removal. Version B could investigate faster best-price discovery and order lookup, while retaining FIFO and measuring trade-offs; its design remains open.

The separate `tracemalloc` run starts after input loading, so preloaded input allocations are excluded. It includes the book, the currently retained event result and fills, and temporary sets used to count price levels; the traced peak can therefore include measurement overhead. It is not total process memory. At 10,000 events, buildup peaked at 2,149,840 traced bytes with 10,000 orders remaining; churn peaked at 544 bytes and ended at 88 bytes with no active orders. End values include the last retained result and tracing bookkeeping, not just book storage.

Raw timing, latency, memory, and controlled-trial CSV files are in the result directory. Run `python -B 20_Code/diagnose_v1.py` from the project root to repeat; it creates a new timestamped result directory and expects the saved 1,000-event inputs. The run verified identical final books across repeats, nonnegative times, the saved medians, all supplied-file manifest hashes, and the Version A source hash. No full correctness suite was rerun for this diagnostic.

## Version A — Diagnostic Dashboard

From the project root, run `python 20_Code/dashboard.py`. The script requires Matplotlib (tested with 3.11.1); it uses Python's standard library for CSV and JSON. It reads `timing.csv`, `latency.csv`, `memory.csv`, `diagnostics.csv`, and `environment.json` from the saved diagnostic directory, and writes `40_Results/diagnostic_dashboard/overview.png`, `summary.csv`, and `sources.txt`. It does not run the order book or benchmark. It replaces the dashboard outputs when regenerated; the raw measurements stay unchanged.

Throughput is event count divided by median replay time. Latency is the time for an individual event in a separate instrumented run; throughput does not reveal its distribution. Event types absent from a workload have no latency measurement. Memory is traced Python allocation, including measurement overhead, rather than total process memory. Sweep is slower than cancellation churn in these runs: sweep builds a large book and executes sells across makers, whereas churn leaves at most one active order. Repeated list scanning is consistent with the observed growth in latency, though the measurements do not isolate every cost.

To include later results, pass multiple result directories using the same CSV schema and `version` field, for example `python 20_Code/dashboard.py 40_Results/diagnostic_v1_20261123_152031 40_Results/<future-result-directory>`. The loader normalizes `version` to `algorithm_version` and labels each series with its source, seed and price-range setting. `sources.txt` records full environment metadata. Compare runs only after checking workloads, inputs, measurement boundaries and machine settings; labels do not guarantee compatibility. The charts show only saved observations and do not predict Version B performance.
