# Runtime planning after declared A scope reduction (2026-11-22)

Decided BEFORE any A measurement in phase4_b3r_20261122; no long run has started.
A is not a candidate. These are planning estimates, not observations or guaranteed bounds.

| Part | A largest requested size | Requested A workers | Outside scope | A planning hours |
|---|---:|---:|---:|---:|
| official | 100000 | 180 | 0 | 2.158-8.279 |
| million | 1000000 | 20 | 0 | 0.689-0.722 |
| queue | 10000 | 48 | 24 | 0.075-0.427 |
| liquidation | 10000 | 72 | 36 | 0.160-0.926 |
| adversarial | 10000 | 72 | 36 | 0.063-0.346 |
| churn | 10000 | 12 | 8 | 0.001-0.003 |
| post_attack | 10000 | 32 | 24 | not estimated (new cases) |

Original-parts A subtotal: 3.15-10.70 hours, plus unestimated post_attack A.
B3r and the post_attack comparator timings have no new measurements; the entire session duration is not estimated.

Protocol and interpretation:

- Official: A through 100k; 1k/10k warm-up+5, 100k one measured trial without warm-up.
- Official million: one A trial, or stopped at 600 s. Large-size speedups say A: single trial.
- Queue/liquidation/adversarial/churn/post_attack: A only through 10k (--max-size 10000).
- All larger A cells there: **not measured (declared scope)**, never filled with extrapolated measurements.
- Any growth statement for supplementary A uses and labels its measured size range.
- B3r and B1/B2/B3 comparator coverage/repeats remain unchanged.
- No rows are fabricated in result CSVs for the excluded cells; this plan supplies their scope label.

Coverage: B3r 564 + old comparators 168 + A 436 = 1168 requested workers (previously 1296).
Modes: 276 timing, 276 latency, 276 counts, 340 memory; 128 former A workers / 44 cases are outside scope.
The added memory cases all have catalog size>10000, so A does not run them. B coverage is unchanged.

Estimate provenance and limits:

- Filtered the unchanged prior model at `00_docs/phase4_plan_20261122/runtime_estimate.json` to exactly the included A cases.
- Source: 1k smoke extrapolation with code-based growth assumptions, 0.5x..3x sensitivity and per-phase 600 s stops.
- No excluded 100k supplementary A projection is presented as a measurement or used for a growth claim.
- Historical source JSON/MD and all data/results remain unchanged.
- Reason for the scope decision: full supplementary 100k instrumentation would dominate an estimated 8-30 h without changing conclusions.
- The earlier 8-32 h full-plan figure is superseded for this scoped session; it was also a planning estimate.
- Session order stays data prep; B3r all parts; old comparators post_attack; A last.
- Actual stops/skip-after-stop may reduce completed work; no missing time is imputed.
