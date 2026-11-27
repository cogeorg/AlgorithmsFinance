# Assignment 1 — BTC limit order book

Stéphane Martin Ambassa. Requirements: [ASSIGNMENT.md](ASSIGNMENT.md).
Submission deadline: **26 November 2026, 18:00 Europe/Zurich**.

## Status and evidence

Baseline and Revised implement the same sequential BTC market rules. Baseline uses an order list;
Revised adds an active-ID index, FIFO price deques, bounded price heaps and lazy cancellation.
The shared validation/matching logic is preserved. Existing behavioral assertions and supplied fixtures
remain unchanged. The initial gate at reviewed commit 49c144b passed 99 tests.

Current measurement coverage, actual outcomes and any unmet work are recorded in
[coverage.md](results/phase1_final/coverage.md) and [verification.json](results/phase1_final/verification.json).
Stopped groups are attempted coverage with unavailable estimates, not completed five-repeat medians.
Historical manifests, raw measurements and audits are retained; later documentation is not measured engine code.
The required matrix has 99 cases and 891 phase groups: 759 completed and 132 documented stops,
with no missing, failed or unattempted required measurements. Historical initial failing-TDD evidence
is unavailable and is explicitly listed as an evidence gap; no retroactive red-phase claim is made.
One new small sale run overlapped an audit. It was preserved, excluded from final selection and
repeated in a fresh directory; see results/phase1_final/provenance_corrections.json.

The concise submission report is [REPORT.md](REPORT.md).
The full Streamlit/Matplotlib interface is dashboard.py. dashboard.html is a replay-only offline companion.

## Clean setup (PowerShell)

Use Python **3.14.5**, the measured CPython version. The engine, generators and original correctness
suites use the standard library. Final dashboard/reporting checks also need requirements.txt:
Streamlit 1.67.0, Matplotlib 3.11.2, pandas 3.0.5 and NumPy 2.5.1.

Open a terminal in this Assignment1 directory:

~~~console
python -m venv .venv_phase1
.\.venv_phase1\Scripts\python.exe -m pip install -r requirements.txt
.\.venv_phase1\Scripts\python.exe -B -m unittest -v test_order_book test_price_heaps test_lazy_cancellation test_benchmark test_benchmark_report test_phase1_results
.\.venv_phase1\Scripts\python.exe -B phase1_results.py
.\.venv_phase1\Scripts\python.exe -m streamlit run dashboard.py
~~~

With the environment activated, the dashboard command is:

~~~console
streamlit run dashboard.py
~~~

The application reads saved data only. It never starts a benchmark.
Use the explicit environment executable when PowerShell activation policy prevents activation;
no repository-wide or system execution-policy changes are needed.

## Interface, units and worked example

Both versions expose process_event(event), AddLimitOrder(event), FillMarketSell(event),
CancelOrder(event) and inspect_book(). Inspection returns active bids/asks sorted in price-time order.
create_order_book explicitly selects baseline, revised or compare. Comparison mode checks ordered
results and canonical books after every event, including rejected events.

price_ticks is a positive built-in Python int in USD cents/BTC: USD 60,000 is 6000000.
qty_units is a positive built-in Python int in 10^-8 BTC: one BTC is 100000000.
seq is a strictly increasing positive built-in int. Booleans, floats, invalid fields and nonpositive
submitted prices/quantities are rejected without mutation or consuming the sequence.
Market residuals never rest. Executions use resting-maker prices. A partial maker retains FIFO priority.

~~~console
python -B dispatcher.py data/worked_example.jsonl --implementation baseline
python -B dispatcher.py data/worked_example.jsonl --implementation revised
python -B dispatcher.py data/worked_example.jsonl --implementation compare
~~~

The six-BTC sell fills b1, b2, b3, b4 in order for 1, 1, 3, 1 BTC.
Proceeds are **USD 359,400**. Four BTC remain on b4; the two-BTC ask a1 is unchanged.
Integer proceeds are sum(price_ticks * qty_units), divided by 10000000000 for USD display.
Independent literals, conservation assertions and the supplied expected JSON verify these outcomes.

## Tests and separate diagnostics

~~~console
python -B -m unittest -v test_order_book test_price_heaps test_lazy_cancellation test_benchmark test_benchmark_report test_phase1_results
python -B test_order_book.py --implementation baseline
python -B test_order_book.py --implementation revised
python -B test_order_book.py --implementation compare
python -B profile_diagnostic.py
python -B verify_dashboard.py
~~~

The profiling/operation-count run is deliberately separate from primary measurements.
Its text profiles, exact ID-probe counts and worked-example check are under results/phase1_final/.
The dashboard check requires the audited index and the pinned dashboard dependencies.
No unsupported claim of an observed initial failing TDD phase is made.

## Reproduce measurements

Never overwrite a saved run. Use new output paths. The exact executed commands, source hashes,
settings, raw repetitions, summaries and command wall times are retained per run.
Do not rerun valid groups or documented stops merely to obtain a preferred result.

~~~console
python -B benchmark.py run --counts 100000 --seeds 43 --scenarios buildup crowded mixed sweep cancel_churn --experiments replay --versions revised --levels 1000 --worker-seconds 60 --campaign-seconds 900 --out results/replay_example_new --label final-revised-replay
python -B phase1_campaign.py --count 1000 --seed 42 --experiment market-sell --sale-percent 10 --levels 1000 --out results/sale_example_new
python -B phase1_campaign.py --count 1000 --seed 42 --experiment queue-concentration --levels 4 --out results/queue_example_new
python -B phase1_campaign.py --count 1000 --seed 42 --experiment cancel-churn --levels 1 --out results/churn_example_new
~~~

The optional million-event probe uses the same limits and both implementations. Its input is
generated in the ignored cache, excluded from submission, and reproducible from saved settings/checksums:

~~~console
python -B benchmark.py run --counts 1000000 --seeds 42 --scenarios mixed --experiments replay --versions baseline revised --levels 1000 --worker-seconds 60 --campaign-seconds 900 --data-dir .cache/optional_million --out results/phase1_final/optional_million_mixed_new --label optional-million-limit-probe
~~~

Its audited outcomes are separate from the required matrix in results/phase1_final/optional_audit.json.
The million-sample latency JSON has a lossless gzip transport copy with both checksums in that audit;
its original local bytes are ignored by Git. Compression occurs after measurement. Historical paths
and manifests remain unchanged; decompress to the recorded original path if those raw samples are needed.

phase1_campaign.py selects one controlled case and delegates unchanged worker measurement functions
to benchmark.py, with both versions and identical inputs. A single case per command prevents unrelated
cases from becoming unattempted when a slow case reaches its limit.
phase1_queue.py records the executed sequential remaining-replay/controlled commands and wall times;
it resumes only saved attempts and never overwrites their directories.

Limits are 60 seconds per worker (including loading and warm-up), 900 seconds per measurement campaign
(excluding preparation), 128 MiB compressed/decoded input, and 512 MiB traced allocations.
There is no OS RSS hard cap. Input generation occurs before measurement. All market arithmetic stays integer.

I/O, engine timing, event-latency instrumentation, tracemalloc and diagnostics are separate processes.
Each primary group has a full untimed warm-up, five repetitions and fresh books.
Construction is separate from measured sales and included in per-repeat total compute.
Throughput uses processed replay events, or one measured sale, divided by replay seconds.
Median averages a central pair; P95/P99 use nearest rank without interpolation.
Memory excludes preloaded inputs/imports and includes construction, transient results and cleanup;
no history is saved. Traced allocation is not RSS.

Requested count means stream size for replay, initial order count for sales/concentration, and
insert/cancel pair count for anchored churn. A sale processes one measured event after N setup events;
churn processes 2*N+2 events. These count meanings are distinct in the dashboard.
Sale quantities use integer ceiling. price_levels_visited counts distinct executed fill prices,
computed after the primary timer, and is null for ordinary replay.

## Audit and regenerate the final report

~~~console
python -B phase1_results.py
python -B phase1_finalize.py
~~~

The audit covers complete case identities, raw calculations, repetition medians, input checksums,
integer fields, independent ordered sale plans, latency percentiles, memory records and available
cross-batch diagnostics. Only complete groups with matching input/code/environment/protocol and
matching diagnostic pairs yield cross-version comparisons.

Historical full-checkout preservation snapshots describe their original checkout. The final reader
checks measured-source fingerprints and saved data without rewriting historical manifests or audits.
README/dashboard edits do not retroactively change measured engine code.
The submission's measured code version is recorded in each manifest; the final commit remains under
the author's control. No publication, commit, push or pull request is performed automatically.
