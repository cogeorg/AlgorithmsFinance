# Phase 4 runtime planning (M=1000 smoke extrapolation)

These are planning ranges, not measurements, confidence intervals or guaranteed bounds.
Per-phase 600s stopping and --skip-after-stop are included; all B repeats are unchanged.

| Part | A hours | B1+B2+B3 hours | Total hours |
|---|---|---|---|
| official | 2.47-15.31 | 0.14-0.43 | 2.61-15.75 |
| million | 0.69-0.73 | 0.29-1.18 | 0.98-1.91 |
| queue | 1.08-7.01 | 0.06-0.17 | 1.13-7.19 |
| liquidation | 1.66-14.50 | 0.09-0.32 | 1.76-14.83 |
| adversarial | 1.57-11.22 | 0.10-3.43 | 1.66-14.65 |
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
- 600s per engine phase; skip other instrumentation only after a timing stop
- startup/parse included; latency postprocessing/allocator/GC/cache scaling uncertain

Recommendation: run the three B variants first, then A in a separate resumable batch.
The Q7 construction/rebuild trials dominate the full baseline schedule; leave them overnight.
Do not silently reduce B warm-up/repeats. A's first over-limit trial stops the cell and omits its remaining repeats.
Use --skip-after-stop to avoid repeating known-stopped A cells in slower instrumentation; those modes are not_run, not invented results.
Review the first completed 10k cells before launching 100k/1M if the extrapolation is off.
