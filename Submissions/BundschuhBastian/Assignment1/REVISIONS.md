# REVISIONS: Version A -> Version B

## 1. Data organization (Phase 3a, commit 2ef6e65)

| | Version A | Version B |
|---|---|---|
| Book | one list of `[id, price, qty, seq]` per side | per side: `dict price -> OrderedDict(order_id -> [qty, seq])` + sorted list of prices (asks stored as `-price`, so the best price is always the last element) |
| Index | none (scan) | `dict order_id -> (is_bid, price)` |
| Best price | O(B) scan | O(1) |
| Insert | O(B) (the scan for "is id live?") | O(1) at an existing price; O(P) for a new price (list insert) |
| Cancel | O(B) | O(1) at the level + O(P) if the level becomes empty |
| One fill | O(B) (find best, `list.pop`) | O(1) (+ O(1) pop of the best price when a level empties) |
| Empty levels | n/a | removed at once, so no stale entries |

`OrderedDict` (not a plain `dict`): `next(iter(...))` for the oldest order stays O(1) after many
deletions at the front; a plain dict would skip over deleted slots.

Step 9 (below) later replaced the per-level `OrderedDict` by a `deque` with lazy cancel. This table
describes the first correct B (`2ef6e65`).

## 2. Speed optimizations (Phase 3b)

Method for every row (`tools/ab_timing.py`): same machine, same stream (100,000 events, seed 42,
`python generate_orders.py --scenario {mixed,buildup} --events 100000 --seed 42 --out
data/generated/{scenario}_100000_s42.jsonl.gz`), parsing excluded, `gc` disabled while timing,
before and after run **interleaved**, 11 repeats, median. Output (all results + final snapshot)
must be identical, and all tests must pass. Profile first (`cProfile`).

Baseline profile (committed B): `validate()` is ~50% of the time on both streams.

| # | Change | mixed before -> after | buildup before -> after | Tests |
|---|---|---|---|---|
| 1 | `is_valid_fast()`: one-pass accept test for good events; only if it says "not sure" run the reference `validate()` (so reason codes cannot differ). New fuzz test `tests/test_validation_fast.py`. | 0.1993 s -> 0.1742 s (-12.6%) | 0.2198 s -> 0.2003 s (-8.9%) | 332 pass |
| 2 | `AddLimitOrder`: call the matching loop `_take` only if the order crosses the best opposite price (one comparison); inline `_Side.add` (no method call per insert). | 0.1747 s -> 0.1677 s (-4.0%) | 0.2009 s -> 0.1827 s (-9.0%) | 332 pass |
| 3 (rejected) | `_take`: iterate the level with `for ... in level.items()` and delete used-up makers afterwards, instead of `next(iter(level.items()))` per fill. | 0.1670 s -> 0.1678 s (+0.5%) | 0.1833 s -> 0.1812 s (-1.2%) | 332 pass; reverted (within noise: few fills per event in these streams) |
| 4 | `is_valid_fast` takes the order index itself (`order_id not in live_ids`) instead of a callable: one function call less per event. Fuzz test adapted (same checks). | 0.1671 s -> 0.1618 s (-3.2%) | 0.1836 s -> 0.1767 s (-3.7%) | 332 pass |
| 5 (rejected) | Inline the fast validation into `process()` (no `is_valid_fast` call). | 0.1607 s -> 0.1624 s (+1.1%) | 0.1784 s -> 0.1799 s (+0.8%) | 333 pass; reverted (a function call is not the cost) |
| 6 (rejected) | Best price with a heap + lazy deletion (bids stored as `-price`; emptied levels stay in the heap until they reach the top) instead of the sorted list + bisect. | 0.1610 s -> 0.1682 s (+4.5%) | 0.1736 s -> 0.1856 s (+7.0%) | 333 pass; not kept. With ~1,000 levels, `list.insert` / `del` is one C memmove and cheaper than heap pushes plus stale-entry cleanup. Amortized cost of the heap is also worse for memory (stale entries grow with cancel churn). |
| 7 (rejected) | Order record as a `__slots__` class (`rec.qty`, `rec.seq`) instead of the list `[qty, seq]`. | 0.1622 s -> 0.1646 s (+1.5%) | 0.1771 s -> 0.1845 s (+4.2%) | 333 pass; not kept (creating an object costs more than creating a small list) |
| 8 (rejected) | Order record as an immutable tuple `(qty, seq)`, replaced on a partial fill. | 0.1621 s -> 0.1604 s (-1.1%) | 0.1793 s -> 0.1750 s (-2.4%) | 333 pass; not kept (inside the ~2% noise; buildup minimum got worse) |
| 9 | Per price level a `deque` of records `[qty, seq, order_id]` with lazy cancel (qty set to 0, live/dead counters, compaction when more than half is dead) instead of an `OrderedDict`. Details, costs and memory: step 9 below. | 0.1657 s -> 0.1673 s (+1.0%) | 0.1790 s -> 0.1505 s (-15.9%) | 388 pass; kept. Also faster on sweep (-12.9%) and crowded (-12.5%), slower on cancel_churn (+11.6%) |
| 10 (rejected) | Pool of up to 32 emptied levels per side (deque cleared, counters reset) reused for new price levels instead of allocating `[deque(), 0, 0]`. Details: step 10 below. | 0.1646 s -> 0.1604 s (-2.6%) | 0.1445 s -> 0.1447 s (+0.1%) | 391 pass with the new pool tests; reverted: sweep +2.8% (+2.9%, +4.8% in the other runs) is past the 2% limit |

Cumulative, first correct B (`2ef6e65`) vs the current B (steps 1, 2, 4 and 9 kept; 3, 5, 6, 7, 8
and 10 rejected). Same method, one interleaved run over all five scenarios, identical output in all:

| Scenario | first correct B | current B | change |
|---|---|---|---|
| mixed | 0.2041 s | 0.1740 s | -14.8% |
| buildup | 0.2290 s | 0.1427 s | -37.7% |
| sweep | 0.2669 s | 0.1900 s | -28.8% |
| crowded | 0.2136 s | 0.1387 s | -35.0% |
| cancel_churn | 0.1635 s | 0.1382 s | -15.4% |

Measured earlier, after steps 1, 2, 4 only (before step 9): mixed 0.1995 s -> 0.1617 s (-19.0%),
buildup 0.2285 s -> 0.1748 s (-23.5%). Step 9 made `mixed` slightly slower than that (see step 9);
the absolute times of the first correct B differ between runs of this machine (0.1995 s earlier,
0.2041 s now), which is why only same-run interleaved pairs are compared.

New test from this step, kept: `tests/test_process_fuzz.py` feeds fuzzed good and bad events to A and B `process()` and requires identical results and snapshots (covers every reason code and every status).

Final state after steps 1-10: kept 1, 2, 4, 9. Rejected 3, 5, 6, 7, 8, 10. Profile of what was left before
step 9 (mixed, 100,000 events): `is_valid_fast` ~25%, `AddLimitOrder` ~18%, `_take` ~17%, `process` ~15%. What remains is
mostly the work the interface requires (one result dict per event, one fill dict per fill) and the
checks that make the engine safe against bad input.

### Step 9: `deque` per price level + lazy cancel

Design (code: `lob/version_b.py`). A price level is `[queue, live, dead]`. `queue` is a `deque` of
records `[qty, arrival_seq, order_id]` in arrival order. The order index maps `order_id ->
(is_bid, price, record)`.
- Insert: append a record, `live += 1`. O(1) (+ O(P) when the price level is new).
- Match: pop live records from the left; a dead record (qty 0) at the front is popped and skipped.
- Cancel: set `qty = 0` in the record (found through the index), `live -= 1`, `dead += 1`.
  If `live` is now 0 the whole level is dropped at once (so no empty levels, as before).
  If `dead * 2 > len(queue)` the deque is rebuilt without the dead records (compaction).
  The same compaction test runs at the end of a match on a level.

Amortized cost. A compaction costs O(len(queue)) and runs only when more than half of the
queue is dead, so it removes more than len/2 records. Each dead record was created by one cancel,
so each cancel pays for at most a constant number of record moves: cancel is O(1) amortized.
One single cancel can cost O(len of its queue) (the compaction). A dead record at the front
costs O(1) when matching reaches it, again paid by its cancel. Insert, match per fill and best
price are as in the first B.

Worst-case memory. After every operation, every level satisfies `dead * 2 <= len(queue)`, so
`len(queue) <= 2 * live`. All queues together hold at most `2 * B` records, with B the number
of active orders: the queues are O(B) and do not grow with the number of submissions. Stale
entries cannot pile up in them (the cancel-churn requirement of the assignment).
*Correction (Phase 6b):* the whole book is NOT O(current B). The order index (`_index`) is a
Python dict, and a dict never gives back its hash table when keys are deleted. So the memory of
Version B is O(peak B), the largest number of active orders at any time. Measured
(`bench/bench_memory.py`, `insert_then_cancel`: 100,000 non-crossing orders, then 99,999 cancels,
1 live order left): 4.05 MB are still held after the replay; the index alone is 3.84 MB
(`sys.getsizeof`, same 100,000-key table), the two `levels` dicts 37 KB each. The same stream with
10,000 orders leaves 0.42 MB. Version A, a plain list that is popped, holds 5.5 KB after the same
stream. The queues themselves are freed (a level is dropped when its last live order goes). This
memory is reused if the book grows again, so it is a one-time cost of the peak, not a leak that
grows with more events. No engine change was made for this; a fix would be to rebuild the index
when it is much larger than its content, at the price of an O(B) rebuild. Checked after EVERY event of the generated
streams by `tests/test_version_b_structure.py` (also mass cancels from the front, the back and
every second order, and a pinned order with 5,000 add/cancel pairs behind it). Two planted bugs
(no compaction; `dead` not decremented) make this test fail; A-vs-B results would not show them.

Timing (`tools/ab_timing.py`, same method as above, interleaved, 11 repeats, median; the three
rows per scenario are repeated runs of the same comparison):

| Scenario | run 1 | run 2 | run 3 |
|---|---|---|---|
| mixed | 0.1612 -> 0.1627 s (+1.0%) | 0.1657 -> 0.1673 s (+1.0%) | 0.1613 -> 0.1643 s (+1.8%) |
| buildup | 0.1867 -> 0.1619 s (-13.3%) | 0.1790 -> 0.1505 s (-15.9%) | 0.1746 -> 0.1453 s (-16.7%) |
| sweep | 0.2380 -> 0.2054 s (-13.7%) | 0.2212 -> 0.2003 s (-9.4%) | 0.2221 -> 0.1935 s (-12.9%) |
| crowded | 0.1532 -> 0.1344 s (-12.3%) | 0.1539 -> 0.1342 s (-12.8%) | not run |
| cancel_churn | 0.1215 -> 0.1371 s (+12.9%) | 0.1253 -> 0.1382 s (+10.3%) | not run |

Output of before and after was identical in every run. Summed over the five scenarios (run 2
values) the time goes from 0.845 s to 0.791 s (-6.5%). Why: the deque needs no hash-table entry and no linked-list node per order, so insert and
matching get cheaper (buildup, crowded, sweep). Every new price level now allocates a `deque`
(one 64-slot block); `cancel_churn` creates and drops a level for each order, and `mixed`
has many cancels, so those two pay for it. The profile before the change (sweep, 100,000 events)
showed the time in `AddLimitOrder` (creating and filling the per-level `OrderedDict`) and `_take`.

Memory (`tracemalloc`; events loaded before tracing; results discarded, so only the book is
counted; "after" = bytes still held after the replay):

| Stream | OrderedDict (peak / after) | deque + lazy (peak / after) | live orders at end / records in queues (deque) |
|---|---|---|---|
| cancel_churn, 100,000 events | 1.9 / 1.6 KiB | 2.6 / 1.3 KiB | 0 / 0 |
| pinned order + 100,000 add/cancel pairs | 2.4 / 2.2 KiB | 3.8 / 2.5 KiB | 1 / 1 |
| 50,000 orders at one price, then cancel all but the first | 12,592 / 4,894 KiB | 9,314 / 2,009 KiB | 1 / 2 |
| 50,000 orders at one price, then cancel all but the last | 12,592 / 4,894 KiB | 9,314 / 2,009 KiB | 1 / 2 |

On the real `cancel_churn` stream neither version accumulates anything. After the mass cancels the
`OrderedDict` still holds 4.9 MB for one live order (its hash table does not shrink); the
deque version holds 2.0 MB. Time on the three synthetic streams (replay only): pinned churn 0.415 s ->
0.515 s (+24%), mass cancel tail 0.315 s -> 0.423 s (+34%), front 0.297 s -> 0.416 s (+40%): the
compactions cost time, in return for the lower memory. These synthetic streams are single runs, not
repeated medians. tracemalloc counts Python allocations only, not the interpreter's own memory or
allocator overhead, so the numbers are not the same as total process memory.

Decision: kept. Faster on buildup, sweep and crowded, slower on cancel_churn and slightly slower on
mixed. If the evaluation data are mostly cancel-heavy, revert the step 9 commit (the
`OrderedDict` version is the code at `e519381`).

### Step 10 (rejected): pool of emptied price levels

Question: is allocating a level (`[deque(), 0, 0]`) a real cost on `cancel_churn`, where every order
creates and drops its own price level (step 9 made that scenario +10% to +13% slower)?

Profile first (`cProfile`, `cancel_churn`, 100,000 events, 0.343 s under the profiler): `is_valid_fast`
0.093 s, `AddLimitOrder` 0.074 s, `process` 0.058 s, `CancelOrder` 0.041 s, `drop_level` 0.025 s,
`_Side.cancel` 0.023 s. Allocation hides inside `AddLimitOrder`, so I timed it separately
(1,000,000 repetitions): `[deque(), 0, 0]` 0.179 s, `OrderedDict()` 0.063 s, `[[], 0, 0]` 0.043 s,
`deque.clear()` 0.015 s. The extra 0.116 microseconds per level times 50,000 levels is about 5.8 ms
of a replay of about 137 ms. So allocation explains roughly 40% of the 10-13% regression: a real
but partial cost. The rest is the larger record (three fields, a 3-tuple in the index) and the
lazy-cancel bookkeeping.

Change tried: each side keeps `pool`, a list of at most 32 emptied levels. `drop_level` clears the
deque, resets `dead`, and appends the level to the pool; a new price level takes one from the pool
if there is one. New tests (extra assertions in `check_structure`, which runs after every event, plus
three tests): a reused level starts with an empty deque and `live = dead = 0`, also when it held dead
records; a level emptied by matching is pooled and reused clean; the pool never exceeds 32 and no level
is in the pool and in the book at the same time. A planted bug (pool without `clear()`) was caught.
391 tests passed.

Timing (`tools/ab_timing.py`, interleaved, 11 repeats, median; before = step 9, after = pool):

| Scenario | run 1 | run 2 | run 3 |
|---|---|---|---|
| cancel_churn | 0.1410 -> 0.1357 s (-3.7%) | 0.1385 -> 0.1359 s (-1.9%) | 0.1386 -> 0.1348 s (-2.7%) |
| mixed | 0.1645 -> 0.1604 s (-2.5%) | 0.1646 -> 0.1604 s (-2.6%) | 0.1667 -> 0.1620 s (-2.8%) |
| buildup | 0.1448 -> 0.1451 s (+0.2%) | 0.1445 -> 0.1447 s (+0.1%) | 0.1459 -> 0.1462 s (+0.1%) |
| crowded | 0.1414 -> 0.1420 s (+0.4%) | 0.1418 -> 0.1421 s (+0.3%) | 0.1444 -> 0.1435 s (-0.6%) |
| sweep | 0.1937 -> 0.1992 s (+2.9%) | 0.1935 -> 0.1990 s (+2.8%) | 0.1949 -> 0.2043 s (+4.8%) |

Decision rule (set before the run): keep only if `cancel_churn` and `mixed` improve and nothing else
gets worse by more than about 2%. Both targets improved (about -2.8% and -2.6%), buildup and crowded
stayed flat, but `sweep` got worse by 2.8% to 4.8% in all three runs. Rejected and reverted
(code and pool tests). I did not find out why `sweep` loses: it drops about 1,000 levels and creates
almost none, so the pool cannot help there and only adds the `clear()` and the pool bookkeeping to
`drop_level`; the size of the effect is larger than that alone would explain, and I did not
investigate further within the time limit. The gain on `cancel_churn` (about 2.8%) would also have
removed only a quarter of its 10-13% loss from step 9.

## 3. All five scenarios, Version B (100,000 events, seed 42, `gc` off, median of 11)

Each scenario replayed alone, one variant per run (not interleaved), so compare the two median
columns only roughly; the interleaved comparison is the table in step 9.

| Scenario | median after step 4 (`OrderedDict`) | median after step 9 (`deque`) | min | max | fills | max B | price levels at end (bids+asks) |
|---|---|---|---|---|---|---|---|
| mixed | 0.1633 s | 0.1663 s | 0.1638 | 0.1700 | 38,988 | 15,118 | 1+845 |
| buildup | 0.1762 s | 0.1464 s | 0.1430 | 0.1485 | 0 | 100,000 | 1000+1000 |
| sweep | 0.2096 s | 0.1764 s | 0.1742 | 0.2021 | 50,035 | 80,000 | 0+1000 |
| crowded | 0.1644 s | 0.1394 s | 0.1373 | 0.1665 | 0 | 100,000 | 4+4 |
| cancel_churn | 0.1221 s | 0.1377 s | 0.1352 | 0.1392 | 0 | 1 | 0+0 |

(min, max and the level counts belong to the step 9 column.) No scenario is out of line. A was not
run at 100,000 events except on `cancel_churn` (B <= 1, so A is cheap there): A and B replay output
is identical (checked again after step 9: same checksum). A on the other 100,000-event streams
is a Phase 6 question (it is quadratic and may hit the run limit).
