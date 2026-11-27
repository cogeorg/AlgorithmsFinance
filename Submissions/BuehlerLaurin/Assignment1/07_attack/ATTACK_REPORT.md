# Attack report: Assignment 1, limit order book

Target: `Submissions/BuehlerLaurin/Assignment1` @ `56caf6f6e201273ab07c2fb434deaaf3d0caa42e` (branch `assignment1`)
Attacker: Claude Code (Opus 5.5), fresh session: yes   Date: 2026-11-22
Machine: Windows 11, AMD Ryzen AI 7 350, Python 3.13.15 (`aif-a1` venv), GC on unless stated

**Independence.** The attacker did not write the current engine: Codex built Phases 2–3b. Claude Code only built the Phase 1 tests (earlier session). Two limits follow: the Phase 1 tests and this oracle come from the same model family and could share a reading of the spec, and `SPEC.md` itself describes the engine internals (e.g. the threshold 32), so Step 1 was code-blind but not design-blind. `01_code` was opened only after the oracle and the Step 1 tests had run; `02_tests` was not opened.

**Versions at the original attack commit.** A, B1 (then registry name B), B2, B3. B3r did not exist yet: `B3rL`, `B3rF`, `B3rT` in `b3r_model.py` are **attack models** of plausible readings of the plan, not an implementation. Naming update 2026-11-23: current B means final B3r; rerun B1-specific checks with explicit B1. Historical measurements/log labels are unchanged.

**Rules kept.** Nothing written outside `07_attack/`, no git writes, no benchmark changes. For that reason `evidence.py` (writes to `05_evidence/`) was not used; logs are in `07_attack/logs/`. The known injection was ignored; no new one was seen in the files read.

Commands (PowerShell, from the exercise root; `$py = "$env:USERPROFILE\.venvs\aif-a1\Scripts\python.exe"`):
```
& $py -B -m pytest -p no:cacheprovider 07_attack -q -rx          # 1137 passed, 4 xfailed (= ATK-01)
& $py -B 07_attack/campaign.py 100 400                           # 0 breaks, 143 s
& $py -B 07_attack/cli_probe.py
& $py -B 07_attack/measure.py time far_end_flicker B1,B2,B3 12500,25000,50000,100000 2,2,1
& $py -B 07_attack/measure.py mem  rotating_bursts B1,B2 200x1000
& $py -B 07_attack/measure.py lat  growing B1,B2,B3 400000 [nogc]
```

## Summary
1. **Matching logic: no break found** in any version. One low-severity replay-CLI crash (ATK-01, all versions).
2. **B1 and B2 break on speed** (far end of the sorted price list): up to **21x** slower than B3, well beyond the known deep_book factor.
3. **New: every hash-based version is quadratic on colliding prices.** At 16k levels B3 is 107x slower than its control and slower than the naive baseline A.
4. **New: B2 also has a memory weakness** (burst capacity stays in each level); B1 and B3 hold up to 32 dead records per live order. These are bounded, unlike B3's drift.
5. **B3r:** the idea survives if it (a) filters the existing heap list, (b) counts stale keys per side. Rebuilding from the `levels` dict or counting both sides is a **new quadratic break** (13x and 299x). Two single-event spikes (58 ms, 38 ms at 100k) remain in every variant tested.

## Correctness breaks (reproduced)

### ATK-01 Replay CLI aborts on an integer with more than 4300 digits (low severity)
- Versions: A, B1, B2, B3 (shared `lob/replay.py`). Reproducer: `test_attack.py::test_atk01_replay_cli_accepts_unbounded_positive_int` (strict xfail: it turns red once fixed). Log: `logs/cli_probe.txt`.
- Rule: SPEC "Input domain" / rules 11–12: `qty_units` is a positive `int`, no upper bound; Interface: replay prints one result per event.
- Expected: three `resting` results. Actual: first result, then `ValueError: Exceeds the limit (4300 digits) for integer string conversion`, exit 1; the remaining events are lost. 4300 digits work.
- Cause: CPython's int-string limit inside `json.loads`, not the engine. Either fix or state an input limit in SPEC (Laurin's decision).

No other correctness break. Searched: see the matrix and "Survived" below.

## Performance / latency / memory breaks (reproduced)
Slopes: `growth.py` (least squares, log-log), median of 3 fresh processes per size, 60 s limit per run. Nothing was extrapolated. Claimed costs are from the SPEC tables. Ratios below are at the largest size.

### ATK-P0 Reproduction of the known Phase 4 results (`logs/P0_reproduction.txt`)
| Result | Phase 4 | This attack |
|---|---|---|
| deep_book 100k s42, B1 / B2 / B3 | 1846 / 1819 / 604 ms | 2062 / 2091 / 737 ms |
| B1 : B3 ratio | 3.06 | **2.80** |
| B3 drift, 1M events, 1 live order at the end (peak 2) | 37 MB | 36.9 MB (peak 37.8 MB) |

Both reproduce, but **deep_book sits at the 3x filter boundary**: the ratio changed from 3.06 to 2.80 between the two runs. An exclusion of B1/B2 should not rest on this scenario alone. ATK-P1 is the stronger evidence.

### ATK-P1 Far end of the sorted price list (B1, B2) (`logs/P1_price_list.txt`, `P5_...`)
Sizes 12.5k, 25k, 50k, 100k live levels. Deterministic streams, no seed. Claim: O(P+1) for new/emptied levels, so the claim itself is **not** violated; the result is an input for the 3x robustness filter.

| Stream | B1 slope (pred. 2) | B2 slope (pred. 2) | B3 slope (pred. 1) | 100k: B1 / B2 / B3 | B1 : B3 |
|---|---|---|---|---|---|
| `far_end_insert`: ever-worse prices | 1.66 | 1.73 | 1.10 | 3.61 / 3.62 / 0.597 s | 6.0x |
| `far_end_cancel`: cancel worst first | 1.75 | 1.80 | 1.04 | 3.30 / 3.23 / 0.264 s | 12.5x |
| `far_end_flicker`: add+cancel **one** worst price, book size constant | 1.88 | 1.87 | 1.01 | 12.80 / 12.53 / 0.614 s | **20.8x** |
| `improve_cancel_purge`: n better bids, cancelled worst first, one sell | 1.59 | 1.62 | 1.08 | 3.95 / 3.77 / 0.925 s | 4.3x |

- Cause (counter): `price_list_shifts` = 5.0e9 at n = 50k and 2.0e10 at 100k, exactly 2n². Test: `test_atkp1_...`.
- B1 `far_end_insert` (1.66) is outside the skill's tolerance for 2: at small n the memmove is cheaper than the Python work. The exponent still rises with n.
- B3 is flat here in time.

### ATK-P2 Colliding prices: all hash-based versions become quadratic (`logs/P2_hash.txt`) **new**
CPython: `hash(int) = int mod (2**61 - 1)`. Prices `k*(2**61-1)` all have hash 0 (so do the negated heap keys). SPEC has no price limit, so these events are valid. Test: `test_atkp2_...`.

| n = 16,000 levels | A | B1 | B2 | B3 | B3rF |
|---|---|---|---|---|---|
| colliding inserts, slope (1k–16k, 5 sizes) | 1.97 | 1.96 | 1.96 | **2.00** | n.m. |
| colliding inserts, time | 5.75 s | 4.30 s | 4.31 s | **9.10 s** | n.m. |
| control: same size, normal hashes | 5.82 s (1.95) | 0.079 s (1.00) | 0.075 s (0.98) | 0.085 s (1.01) | n.m. |
| slowdown against control | 1.0x | 54x | 58x | **107x** | n.m. |
| 4k rounds add + sell on 16k colliding levels, time (slope) | n.m. | 4.57 s (2.02) | 4.48 s (2.04) | 7.16 s (2.04) | 7.08 s (2.03) |

- Claimed: expected O(1) lookups, with the SPEC note that collisions have no O(1) guarantee. So this is a claimed exception that an input can actually trigger, at ~570 µs (B1) to ~900 µs (B3) per event.
- B3 is hit hardest: it adds an `in_heap` set, probed on each level creation (cause argued from the code, not profiled). **B3 is slower than baseline A.**
- B3 : B1 is 2.1x, under the 3x limit, so this does not decide the filter between B variants.
- Realistic? No: about 2.3e18 ticks (2.3e16 USD). A documented price cap would remove it; that is a rule change and Laurin's decision. The catalogue's low-bit attack (multiples of 2**20, up to 32k levels) **survived**: slopes 1.04–1.05, at most 1.16x the dense control. String ids use a per-process random hash and cannot be attacked this way.

### ATK-P3 B3: one event pays for all stale heap keys (`logs/P6_single_events.txt`)
Single event, prefill untimed, 12.5k–100k:

| Single event | B1 | B2 | B3 | B3rF |
|---|---|---|---|---|
| `spike_purge`: 1 live level under n cancelled better ones, one sell | 0.27 ms | 0.32 ms | **53 ms** (1.08) | 0.37 ms (rebuilt earlier) |
| `spike_purge_at_threshold`: n live + n stale above, one sell | 0.06 ms | 0.06 ms | **59 ms** (1.10) | **58 ms** (1.09) |
| `spike_rebuild`: the cancel that crosses stale > live | 0.46 ms | 0.10 ms | 0.08 ms | **38 ms** (1.12) |
| `spike_compaction`: the cancel that compacts 2n records | **12.8 ms** (1.04) | 0.04 ms | **14.0 ms** (1.06) | 12.8 ms |
| `spike_head_skip`: one sell skips n dead heads | **14.1 ms** (1.01) | 0.06 ms | **13.4 ms** (0.97) | 15.0 ms |
| `spike_sweep`: F = n fills on n levels | 177 ms (1.07) | 185 ms (1.08) | 253 ms (1.05) | 293 ms (1.07) |

- Normal stream of 200k events for comparison: p50 about 3.4–4.1 µs, p99 about 14–23 µs. Sub-millisecond cells are timing noise; their slopes are not used.
- Claimed as amortized (SPEC says the quote/match is not worst-case O(1)), so not a claim violation, but the amortized bound hides it from averages. Count: `test_atkp3_...` (500 pops in one sell).
- A sweep: A slope 2.10 (1k–8k; 4.78 s at 8k).

### ATK-P4 B3 memory grows with events under drift (known, confirmed) (`logs/P7b_memory.txt`)
50k/100k/200k/400k rounds, at most 2 live orders: B3 4.1 / 8.2 / 16.4 / 32.9 MB (slope ~1.0). A, B1, B2: constant 3–4 kB. **B3rF: constant 4.7 kB**, so the planned fix does remove this break. Test: `test_atkp4_...`.

### ATK-P5 B2 keeps the burst capacity of every live level (`logs/P7_memory.txt`) **new**
One resting order per level; a burst of K orders is added and cancelled at level 0, 1, 2, … Live orders never exceed P + K.

| P levels, K = 1000 (bytes at the end) | 25 | 50 | 100 | 200 |
|---|---|---|---|---|
| A | 18 kB | 25 kB | 38 kB | n.m. |
| B1 | 0.18 MB | 0.34 MB | 0.65 MB | 1.26 MB |
| **B2** | **1.10 MB** | **2.17 MB** | **4.31 MB** | **8.59 MB** |
| B3 | 0.19 MB | 0.34 MB | 0.65 MB | 1.27 MB |

- B2 at 200 levels: 43 kB per live order; the slope over P is about 1.0. It also scales with K: with P = 10, K = 5k/10k/20k/40k leaves 1.8 / 3.6 / 7.2 / 15.8 MB for **10 live orders**. B1 at K = 40k: 0.98 MB, mostly the retained `orders` table.
- Cause: an `OrderedDict` never shrinks on deletion, and a level with one live order keeps its table. Test: `test_atkp5_...`.
- **Bounded, not unbounded:** it saturates at (number of live levels) x (largest past queue). With 300 rounds over 100 levels B2 stays at 4.31 MB (same as after 100 rounds). B2's SPEC space bound is O(B+P+1) live objects with "allocated hash capacity extra", so the retained capacity is declared but not bounded there. Under the filter ("grows with event count rather than the live book") this is a judgement for Laurin: it grows with history, but saturates.

### ATK-P6 B1 and B3 pin up to 32 dead records behind every live order (`logs/P7_memory.txt`) **new**
One live order plus 32 cancelled orders per level, live size fixed: at 4000 levels B1 33.6 MB, B3 33.7 MB, **B2 2.8 MB, (A 0.30 MB at 1000 levels)**; per live order 8.4 kB (B1/B3) against 0.70 kB (B2), 12x. Linear in P (500–4000: 4.2 / 8.4 / 16.8 / 33.6 MB). Consistent with the claimed S <= B + 32P and bounded by it, so it is a constant-factor weakness, not a growth break. Test: `test_atkp6_...`.

### ATK-P7 GC pause: a single LIMIT event (all B variants) (`logs/P8_latency.txt`)
Growing book, 400k resting orders, 3 repeats; event 263,859 in every B run: max 44–46 ms (B1, B3), **82–90 ms (B2)**; the GC callback accounts for essentially the whole event. GC disabled: max 10–13 ms, now at event 349,525 (dict resize). Normal event p50 3.3–3.8 µs. At 50k–200k the largest pause is mostly 2–5 ms, with a single 33 ms GC outlier (B3, 200k) and a few non-GC outliers; only the 400k pause is stable. Cause: cyclic GC traversing all live objects **plus the preloaded 400k input dicts**, so part of the cost is the harness, not the engine. A was measured at 5k events only.

### ATK-P8 B3r models: attacks that still hurt (`logs/P3_*, P4_*, P9_*, P10_*`)
Models differ only in how the rebuild is done. `B3rL` iterates the `levels` dict, `B3rF` filters the existing heap list, `B3rT` filters but counts stale/live over both sides and rebuilds only the changed side. Their correctness held in fuzzing (B3rL, B3rF: 60 seeds x 4 regimes x 2 passes; B3rT not fuzzed).

| Attack (slope, time at largest n) | B3 | B3rF | B3rL | B3rT |
|---|---|---|---|---|
| `dead_slot_rebuild`: n levels once, all but one cancelled, then 87k add+cancel at distinct prices (n = 175k) | 1.02, 0.536 s | 1.01, 0.630 s | **1.72, 6.92 s (13x)** | n.m. |
| `two_side_thrash`: n live asks, n+1 stale bids, n ask cancels (n = 16k) | 1.00, 0.110 s | 1.02, 0.118 s | n.m. | **2.01, 32.9 s (299x)** |
| `flicker_set`: one live level, 2 alternating prices (100k rounds) | 0.608 s | 0.694 s (1.14x) | 0.697 s (1.15x) | n.m. |
| `amortized_rebuild`: n live, 2n drift cancels (n = 100k) | 1.21 s | 1.34 s (1.11x) | 1.37 s (1.13x) | n.m. |
| `touch_churn`: 400k live levels, best emptied each round | 3.96 s | 4.51 s (1.14x) | n.m. | n.m. |

Why `B3rL` breaks: after a peak, the `levels` dict keeps its dead slots; each rebuild (here after every second cancel) walks all of them. `heap = [k for k in heap if ...]` costs only live + stale. It needs only realistic prices and P <= 175k. Predicted slope 2, measured 1.72 over 10k–175k and increasing; it is not yet asymptotic at the small sizes.
Why `B3rT` breaks: rebuilding the ask side cannot remove stale bid keys, so the total never drops below the threshold and every cancel rebuilds n ask keys. With **per-side** counting this disappears.
Remaining in `B3rF`: the two single-event spikes of ATK-P3 (purge just under the threshold, and the rebuild itself), and a 7–14 % constant cost on churn streams. A minimum threshold (like the 32 in the deque rule) would likely reduce the small-book cost; **not tested**.
`len(heap) - len(levels)` per side gives the exact stale count, since every live level owns one key; a separate counter is unnecessary.
**Plan mismatch:** SPEC (amendment 2026-11-22) says the fallback rebuilds at "> **2x** live levels"; the brief for this attack says "> live levels". One of them needs to be corrected. Under 2x, the purge spike could be up to twice as large (argued, not measured).

## Survived (attacks that found nothing)
- **Input domain:** every field x about 40 odd values (incl. missing) x 4 entry points x 3 event types; all pairs of bad fields (first rule wins); non-objects; id collisions; seq at 2^63 and 10^40; event and result aliasing; independence of two books.
- **State sequences:** boundary price/depth grid, cancel at every queue position after every partial fill, lazy-cleanup thresholds with id re-use (32/33/34 …), level emptied and recreated with and without quotes, 50-level cross, 10^50 quantities.
- **Differential fuzz (compared after every event: result, snapshot, best bid/ask, `last_seq`):** pytest: 15 seeds x 4 regimes x 3 modes x 4 versions; campaign: seeds 10000–10099 x 4 regimes x 400 events x 2 passes (every event / sparse inspection) for each version, 160,000 events per version per pass, 0 differences. Regimes: narrow, wide, plus lazy-structure ones (churn, drift). The fuzzer caught all 5 planted bugs. All in `logs/campaign.txt`.
- **Replay CLI:** plain/gz, CRLF, no final newline, unicode, non-objects, empty file.
- **Compaction rule:** 200k-event thrash at 33 live: slope 1.01–1.03, counters 1.97 scanned records per cancel (< 2). `root_recreate` (best level emptied and recreated n times above 100k levels): B3 0.604 s vs B1 0.672 s, no thrash.
- **Very many levels:** `touch_churn` to 400k levels: B3 only 1.08x B1, all slopes 1.02–1.06.

## Suspected weaknesses (not reproduced, or outside the spec)
- **Memory at very large P:** a level costs ~1.14 kB (B1), 1.18 kB (B3), 0.71 kB (B2) per order with one order each; ~0.24 / 0.24 / 0.32 kB per order on 4 levels (B1 / B3 / B2, measured at 100k; `P7c`). By arithmetic the 4 GiB cap would be reached around 3–4M distinct levels for B1/B3. **Not run.**
- **B3 `snapshot()` after a peak:** O(peak) dead-slot scan with one live order (slope 0.87 over 12.5k–100k, 89 µs at 100k; B1/B2 flat; `P11`). SPEC already says O(H). Only matters if the workload ever inspects often.
- **Hash tables keep their peak:** after 100k levels and one live order left, 9.9 MB (B1, B2), 17.3 MB (B3), 9.1 MB (B3rF) remain; A 0.07 MB at 8k. SPEC declares retained capacity.
- **Replay CLI input robustness (SPEC is silent on file errors; `cli_probe.txt`):** a UTF-8 BOM (e.g. from a Windows editor or `Out-File`), malformed or truncated JSON, invalid UTF-8, or a deeply nested unused field ends with a traceback. For a malformed line, a truncated last line and deep nesting the results before it are printed.
- `OrderedDict` FIFO in B2: dict-table resize spikes of 5–14 ms in `rolling`; not separable from GC and noise here.

## Attack matrix
| Attack | A | B1 | B2 | B3 | B3r (models) |
|---|---|---|---|---|---|
| Input domain, sequences, differential fuzz | survived | survived | survived | survived | fuzz survived (L, F) |
| Replay CLI > 4300 digits (ATK-01) | broken | broken | broken | broken | n.a. |
| Far-end insert (P1) | slow (1.96) | slow (1.66) | slow (1.73) | survived (1.10) | n.m. |
| Far-end flicker | n.m. | slow (1.88, 21x) | slow (1.87) | survived (1.01) | n.m. |
| Far-end cancel | n.m. | slow (1.75) | slow (1.80) | survived (1.04) | n.m. |
| Colliding prices (P2) | slow (1.97, no hashing) | slow (1.96) | slow (1.96) | slow (2.00, 107x) | F: slow (2.03, match) |
| Low-bit collisions | n.m. | survived (1.05) | survived (1.04) | survived (1.04) | n.m. |
| One-event purge (P3) | n.m. | survived | survived | slow spike (1.08) | L n.m.; F survived below threshold, slow at it (1.09) |
| One-event heap rebuild | n.a. | n.a. | n.a. | n.a. | F: slow spike (1.12) |
| Compaction / head-skip spike | n.m. | slow spike (1.04 / 1.01) | survived | slow spike (1.06 / 0.97) | F slow spike (as B3) |
| Full sweep F = n | slow (2.10) | 1.07 | 1.08 | 1.05 | F 1.07 |
| Drift memory (P4) | survived | survived | survived | **broken** (grows with events) | F survived |
| Rotating bursts memory (P5) | survived | 6.3 kB/live order at P = 200 (saturates) | **broken-bounded**, 43 kB | 6.3 kB | n.m. |
| Pinned dead records (P6) | survived (to P = 1000) | 8.4 kB/live order | survived (0.70 kB) | 8.4 kB | n.m. |
| Retained capacity after a peak | ~0.07 MB at 8k | 9.9 MB at 100k | 9.9 MB | 17.3 MB | F 9.1 MB |
| Compaction thrash | n.m. | survived (1.01) | survived (1.02) | survived (1.03) | n.m. |
| Drift time | survived (1.00) | survived (1.01) | survived (1.01) | survived (1.01) | F 1.01 (1.14x) |
| Very many live levels (400k) | n.m. | 1.05 | n.m. | 1.06 | F 1.02 |
| Dead-slot rebuild | n.a. | n.a. | n.a. | n.a. (no rebuild) | **L slow (1.72, 13x)**, F survived |
| Two-side threshold thrash | n.a. | n.a. | n.a. | n.a. | **T slow (2.01, 299x)**, F survived |
| GC pause at 400k live | n.m. | 45 ms | 85 ms | 45 ms | n.m. |

n.m. = not measured, n.a. = not applicable. Slopes describe the measured range only. "Slow" = measured growth above the B3-class behaviour or an isolated spike; a claim in SPEC is violated only where stated (nowhere except the CLI, where the SPEC sets no upper bound).

## Proposed adversarial benchmark scenarios (need Laurin's OK; nothing was added)
1. `far_end_flicker` (P live levels, add+cancel of one worst price): stronger and more stable than `deep_book` for the B1/B2 filter. Deterministic, 2n events.
2. `dead_slot_rebuild` and `two_side_thrash`: regression scenarios for any heap-rebuild variant; use them as tests of B3r before it is measured.
3. `spike_purge_at_threshold` (n live + n stale, one sell): single-event latency (report max, not only p99) for B3 and B3r.
4. `rotating_bursts` (memory curve, B2) and `pinned_dead` (memory curve, B1/B3): they fill the gap that the current memory diagnostic (drift, B3 only) leaves.
5. Optional, only if an explicit price limit is not set: `hash_full` at 16k levels, as a declared pathological case. Not representative of any realistic price.

## Limits of this attack
- One machine, 3 repeats, medians; a laptop with turbo. The single-event cells below 1 ms are noise. During P6 (and possibly the end of P5) a `tasklist` poll ran every 3 s; the rest ran without other load from this session.
- Measurement defects found and repaired: `mem_drift` had its whole input traced and imports were traced (both fixed, P7 rerun); the first latency log may have overlapped with other probes (rerun). Discarded logs are kept in `logs/superseded/`, do not cite them.
- Two predictions were entered wrongly on the command line: B1 in the first `dead_slot_rebuild` run (pred. 2 instead of 1; its log line says INCONSISTENT, rerun appended with pred. 1) and `improve_cancel_purge` for B1/B2 (predicted 1, but cancelling worst-first makes the price list quadratic: 1.59/1.62).
- A was measured only at small sizes (it is quadratic); its memory for `pinned_dead` at 2000+ levels hit the 60 s limit in the first run and is not reported.
- The oracle and Phase 1 tests may share a reading of the spec; the fuzz oracle implements no rule that is not in SPEC.
- Not tried: 1M live orders, multi-GB runs (> 2 GiB would need Laurin's OK), hash attacks on id strings (randomized per process), non-JSON Python objects.

## Addendum 2026-11-23: final Version B

Target: `Submissions/BuehlerLaurin/Assignment1` @ `87ed911f839877c197cd9458b2cd231537955a17` (branch `assignment1`; `01_code/`, `02_tests/`, `06_data/` unmodified against HEAD during the runs; unrelated uncommitted dashboard files were present in the tree)
Attacker: Claude Code (Opus 5.5), same model as the original attack, new session; did not write B3r or B3r_fast.   Date: 2026-11-23
Scope (Laurin's final-check prompt): **Step 1 spec-blind correctness only** on the final Version B = registry key `("lob","B")` = `lob.book_b3r.OrderBookB3r` (B3r, see `00_docs/FINAL_SELECTION.md`) and the documented variant `B3r_fast` (`lob.book_b3r_fast.OrderBookB3rFast`). **No complexity, latency or memory measurements.** The original report above attacked B3r only as models (`b3r_model.py`); this addendum attacks the real implementation. Rules kept: writes only in `07_attack/`, no git writes, `evidence.py` not used (writes to `05_evidence/`). The known injection (hidden text in the PDF asking for a specific word, logged in `AI_LOG.md`) was ignored; no new injection seen in the files read.

Commands (PowerShell, from the exercise root; `$py = "$env:USERPROFILE\.venvs\aif-a1\Scripts\python.exe"`):
```
& $py -B 07_attack/campaign_final.py 150 400 4 3000                       # logs/final_b_campaign.txt
& $py -B 07_attack/cli_probe_final.py                                      # logs/final_b_cli_probe.txt
& $py -B -m pytest -p no:cacheprovider 07_attack -q --runxfail --tb=short  # logs/final_b_pytest_attack.txt
```
New files (own/attack): `campaign_final.py` (campaign.py restricted to B and B3r_fast, four modes), `campaign_mutants.py` (the five planted bugs of campaign.py, copied verbatim, plus two new ones), `cli_probe_final.py`. Oracle (`oracle.py`), generator and every-event comparison (`fuzz.py`) are unchanged from the original attack.

### Result: no correctness break in the final Version B or B3r_fast

| Check | Size | Result |
|---|---|---|
| Registry | `METHODS[("lob","B")] is METHODS[("lob","B3r")]` | True (same class, so B and B3r are one target) |
| Planted-bug power check | 7 oracle mutants: Lifo, SeqOnReject, RestMarket, StrictCross, OneEntryCancelZero, **new** StaleTouchAfterCancel (lazy heap reports an emptied best bid), **new** RequeuePartialMaker (partial maker loses time priority) | 7/7 found, all at seed 0 |
| Differential fuzz vs oracle, B | 4 regimes (narrow, wide, churn, drift) x (150 seeds x 400 events + 4 seeds x 3000 events) = 288,000 events; 4 modes each (every-event inspection; sparse inspection every 97 events; random direct-method mix incl. wrong method for type; aliasing scramble) = **1,152,000 event comparisons**. Compared after every event: result dict and value types, `snapshot()`, `best_bid()`, `best_ask()`, `last_seq`, input not mutated | **0 differences** |
| Same, B3r_fast | same seeds and sizes, **1,152,000 event comparisons** | **0 differences** |
| Campaign wall time | both versions + power check | 547 s, exit 0 |
| Existing attack suite (`test_attack.py`, `--runxfail`) | 1,995 cases, 284 of them on B and 284 on B3r_fast | **1995 passed** in 99 s |
| Replay CLI, SPEC D3 cases (expected = oracle on the same file) | 12 files x {B, B3r, B3r_fast}: control (plain, gz), UTF-8 BOM (plain, gz, with CRLF), qty with 4,301 / 100k / 1M digits (incl. fills and partial), price with 100k digits on both sides, seq with 100k digits then a smaller one (nonincreasing), negative 5,000-digit qty (bad_qty), BOM + huge ints in gz | **36/36 match the oracle line by line, exit 0**; `--version B` stdout byte-identical to `--version B3r` in 12/12 |

ATK-01 (int > 4300 digits) is **fixed** for the final versions (also 1M digits); BOM input is accepted as SPEC D3 states.

### Observations (no spec rule broken; for Laurin)
- **`replay` default is A:** without `--version`, `lob.replay` runs Version A (`01_code/lob/replay.py:35`, `default="A"`). SPEC's replay command always passes `--version`, so this is not a violation, but a grader who omits the flag gets the quadratic baseline. Changing the default to `B` or making the flag required is Laurin's call.
- **Unchanged CLI behaviour outside the spec** (SPEC is silent on file errors): UTF-16 file, a second BOM (start or mid-file), malformed JSON, invalid UTF-8 end with a traceback and exit 1; results printed before the bad line stay. Empty file and BOM-only file: exit 0, no output. Unknown/lowercase `--version` (`b`, `B4`): argparse error, exit 2.

### Limits of this addendum
- Correctness only; B3r's performance attacks (ATK-P8 models, spike at the threshold, hash collisions per SPEC D3) were not re-measured on the real implementation.
- The oracle and the planted bugs come from the same model family as the Phase 1 tests; they share its reading of SPEC. Fuzzer power is shown only for the seven planted bug types.
- Random streams, not exhaustive: books in the long streams reach at most a few thousand events of history; the 1M-event drift regime was not fuzzed against the oracle (the oracle is O(live) per event).
- Code was read only to identify the registry classes and the replay default (`replay.py`); the fuzz and CLI expectations come from `oracle.py` and SPEC D3 only.
