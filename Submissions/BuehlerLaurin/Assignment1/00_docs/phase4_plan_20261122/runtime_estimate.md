# Phase 4 runtime planning (M=1000 smoke extrapolation)

These are planning ranges, not measurements, confidence intervals or guaranteed bounds.
Per-phase 600s stopping and --skip-after-stop are included; all B repeats are unchanged.

Declared 2026-11-22 BEFORE long measurements: A at 100k/1M uses one measured trial, no warm-up.
Report large-size speedups as A: single trial. A at 1k/10k retains warm-up + 5 repeats.

| Part | A hours | B1+B2+B3 hours | Total hours |
|---|---|---|---|
| official | 2.16-8.28 | 0.14-0.43 | 2.30-8.71 |
| million | 0.69-0.72 | 0.29-1.18 | 0.98-1.90 |
| queue | 1.08-4.42 | 0.06-0.17 | 1.13-4.59 |
| liquidation | 1.66-6.89 | 0.09-0.32 | 1.76-7.21 |
| adversarial | 1.57-5.59 | 0.10-3.43 | 1.66-9.02 |
| churn | 0.02-0.09 | 0.07-0.30 | 0.09-0.39 |

A predicted single-replay seconds before the 600s cap:

| Scenario | M | Extrapolated seconds | Predicted first-attempt stop |
|---|---|---|---|
| buildup | 100000 | 655.9 | True |
| crowded | 100000 | 721.6 | True |
| mixed | 100000 | 151.5 | False |
| sweep | 100000 | 598.5 | False |
| cancel_churn | 100000 | 0.2 | False |
| buildup | 1000000 | 65590.8 | True |
| crowded | 1000000 | 72157.3 | True |
| mixed | 1000000 | 15153.0 | True |
| sweep | 1000000 | 59850.6 | True |
| cancel_churn | 1000000 | 2.5 | False |

Assumptions:

- M=1000 seed42 only; fixed workload B/P/F relationships from generators
- A growing-book scenarios quadratic; constant-live churn linear
- B variants approximately linear at bounded price count; deep-book B1/B2 linear-to-quadratic
- 0.5x..3x sensitivity; not confidence bounds; stop-policy discontinuities possible
- 2026-11-22 deviation: A at 100k/1M one measured trial, no warm-up; A: single trial
- 600s per engine phase; skip other instrumentation only after a timing stop
- startup/parse included; latency postprocessing/allocator/GC/cache scaling uncertain

Full-run artifact planning (all parts in one session, no engines executed):

- 2032 workers; approximately 6112 files, of which 6096 local job/journal/log files.
- Commit about 16 root files, 22.2-46.3 MiB.
- Local internals: 52.0-108.3 MiB.
- Derived from smoke bytes per worker with 1.2..2.5x allowance, not a hard bound; stops/skips and fewer A trials reduce artifacts.

Recommendation: run the three B variants first, then A in a separate resumable batch.
The Q7 construction/rebuild trials dominate the full baseline schedule; leave them overnight.
Do not silently reduce B warm-up/repeats. A's first over-limit trial stops the cell and omits its remaining repeats.
Use --skip-after-stop to avoid repeating known-stopped A cells in slower instrumentation; those modes are not_run, not invented results.
Review the first completed 10k cells before launching 100k/1M if the extrapolation is off.
