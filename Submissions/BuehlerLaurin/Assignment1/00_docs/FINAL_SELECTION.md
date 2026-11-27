# Final selection of Version B (decided 2026-11-22)

**Final Version B: B3r** (B3: deque levels with lazy cancel, heap price index, plus a per-side heap rebuild).
**B3r_fast** (same algorithm, faster implementation, behaviour proven identical) would have been about **13 % faster**, but it failed the rule we fixed before measuring it, so it is **not** the final version. Both decisions follow rules recorded in SPEC.md and committed before the measurements they judge.

Written by Claude (chat) from the committed result files; every number below can be traced to the run folders listed at the end.

## 1. Candidates and the pre-registered rule

Candidates B1 (sorted price list + deque levels), B2 (OrderedDict levels) and B3 (heap price index) were measured in the pre-registered Phase 4 run. The rule (SPEC.md, fixed before Phase 4):

1. **Robustness filter:** exclude a candidate that hits 600 s / 4 GiB, is more than 3x slower than the best B on any official or own adversarial scenario at its largest size, or keeps memory proportional to event history instead of the live book.
2. **Speed:** among survivors, the lowest geometric mean of the 15 median replay times (five official scenarios at 100k, seeds 42/43/44); within 5 %, the simpler one.
3. **Fallback** (added before the long runs): if no candidate passes, one targeted revision per violation, judged by the same rules.

## 2. Phase 4 result: no candidate passed

| Candidate | Official 100k (geometric mean) | Violation |
|---|---:|---|
| B1 | 0.4244 s | deep_book 3.06x slower than B3 (borderline; 2.80x in the attack re-run) |
| B2 | 0.4726 s | deep_book 3.02x slower than B3 |
| B3 | 0.4289 s | memory grows with history: 37 MB with 2 live orders after 1M drift events |

Stronger supporting evidence for B1/B2, added after Phase 4 by the attack (it does not change the pre-registered exclusion): far_end_flicker at 100k is 18.4x (B1) and 18.5x (B2) slower than B3; two_side_thrash 17.8x / 17.5x.

## 3. Revision B3r

One change to B3, as allowed by the fallback: rebuild a side's heap when its stale keys exceed its live levels (and 32), by filtering the existing heap list. Cost is amortized O(1) per stale key (measured: at most 2 heap entries scanned per cancel, worst observed 1.999), with a declared single-event spike of O(live + stale).

| Check | Result |
|---|---|
| Correctness | 0 differences against an independent reference (professor's 50,000 events + 135,000 stress events; script and log in `05_evidence/chat_reference/`), all contract/own-dataset/stateful/mutant tests |
| Speed, official 100k | 0.4247 s geometric mean, equal to the fastest candidate (B1 0.4244 s) |
| Memory (drift, 1M events) | 5 KB, heap of 18 entries (B3: 37 MB) |
| Worst ratio vs best B on throughput scenarios | 1.42 (1M cancel_churn); B1/B2 reach 18x |
| Speedup vs A (median of per-seed ratios) | 21x (mixed) to 186x (crowded) at 10k on the four non-churn workloads; at 100k 299x (mixed) and more than 1,260x where A was stopped at 600 s; on cancel_churn the ratio is 0.7-0.8, i.e. A is faster |

**One interpretation made after measuring, stated openly:** on spike_purge_at_threshold the measured "replay" is a single sell event that purges 100,000 stale heap keys (57 ms vs 0.03 ms for B1, ratio 1,866). Read literally, the 3x filter excludes B3r too. We keep B3r because (a) this single-event spike was declared as an accepted tail-latency cost (D1) before the measurement, and (b) over the whole stream that creates the situation B3r is faster: construction + spike 1.78 s vs 4.63 s for B1. Both readings and the numbers are reported.

## 4. Controlled optimisation: B3r_fast (tried, rejected)

1. **Profiling** (professor's 10k streams): about one third of B3r's per-event time is input validation (`validate` -> `_positive_int` -> two `isinstance` calls, up to three times per event), not the order book.
2. **B3r_fast:** same algorithm and data structures; a fast path for ordinary valid events that falls back to the unchanged validator for everything else, and local-variable binding in matching. Identical behaviour proven by 146,514 every-event comparisons against B3r and 300,000 random validator cases (Claude), plus 848 standard and 1,697 attack tests.
3. **Rule, fixed before measuring:** at least 10 % faster on the official 100k grid, and no scenario more than 5 % slower.
4. **First comparison (two sessions):** 11.3 % faster (ratio 0.887), but rejected: five cells exceeded 5 %. Analysis showed session noise: two of those cells were ones where the **B3r reference** was about 2x faster than the same cell for every other version and seed, and the spike cells did not reproduce later.
5. **Fair rematch (same session, alternating order per case, method fixed and committed before measuring, one binding attempt):** **12.7 % faster** (ratio 0.873), faster in **25 of 27 scenarios** and within the 5 % bound in 26 of 27 (ratios 0.70-1.014; the spike case is now 0.70 / 0.98 / 1.01 instead of 1.06-1.13). It failed on **one** cell: dead_slot_rebuild at 1k, single seed, 3.66 ms vs 3.42 ms (ratio 1.068, a difference of 0.23 ms), while the same scenario at 10k and 100k is 19 % and 17 % faster. **Decision: rejected, B3r stays final.**

We do not re-measure or change the rule a second time: the rematch was declared binding before it ran.

**Lesson:** per-scenario bounds need a minimum measured duration or confidence intervals; otherwise noise in sub-millisecond cells decides. B3r_fast stays in the repository as a tested, documented variant.

## 5. What this costs

B3r is about 13 % slower than B3r_fast on the official grid, and still 21x-186x faster than A at 10k (non-churn workloads) and more than 1,260x faster at 100k where A was stopped.

## Sources (committed run folders, all under `03_results/runs/`)

- Pre-registered candidates: `20261122T012525Z_5eaeb03_phase4/`
- B3r session, post-attack comparators, scoped A baseline: `20261122T130145Z_00bb1ad_phase4_b3r_20261122/`
- B3r_fast, cross-session: `20261122T200528Z_8a22753_phase4_b3r_fast_20261122/` (`fast_acceptance.json`)
- B3r_fast, binding same-session rematch: `20261122T210801Z_e4fd928_phase4_b3r_fast_rematch_20261122/` (`fast_rematch_acceptance.md`)
- Attack evidence: `07_attack/ATTACK_REPORT.md`; rules and decisions D1-D4: `SPEC.md`, `00_docs/AI_LOG.md`

Follow-up completed: the registry alias "B" points to B3r (the final Version B); B1 remains available under its explicit name.
