# Hand trace: Version A on the supplied worked example

Date: 2026-11-21. Worked out by Codex from the six input events and SPEC.md,
with AI help; not an execution dump. Pending Laurin / Claude (chat) review.
Sources: `06_data/supplied/worked_example.jsonl` and `worked_expected.json`.

Notation: `id@price:quantity#arrival_seq`; prices are ticks, quantities units.
Books below use canonical inspection order, bids then asks. A stores unsorted
lists; here the bids happen to arrive in descending price order.
T = total resting quantity across both sides. Every event passes validation.

Book states, written out so every before/after state is explicit:

| State | Bids | Asks | T |
|---|---|---|---|
| S0 | `[]` | `[]` | 0 |
| S1 | `[b1@6000000:100000000#1]` | `[]` | 100000000 |
| S2 | `[b1@6000000:100000000#1, b2@6000000:100000000#2]` | `[]` | 200000000 |
| S3 | `[b1@6000000:100000000#1, b2@6000000:100000000#2, b3@5990000:300000000#3]` | `[]` | 500000000 |
| S4 | `[b1@6000000:100000000#1, b2@6000000:100000000#2, b3@5990000:300000000#3, b4@5970000:500000000#4]` | `[]` | 1000000000 |
| S5 | `[b1@6000000:100000000#1, b2@6000000:100000000#2, b3@5990000:300000000#3, b4@5970000:500000000#4]` | `[a1@6010000:200000000#5]` | 1200000000 |
| S6 | `[b4@5970000:400000000#4]` | `[a1@6010000:200000000#5]` | 600000000 |

| Event | Before -> after | Matching decision / result | Conservation (C1, C6) |
|---|---|---|---|
| 1: BUY b1, 6000000, 100000000 | S0 -> S1 | No asks; append b1. `resting`, unfilled 100000000, fills `[]`. | 100000000 = 0 fills + 100000000 residual; T: 0 + 100000000 = 100000000. |
| 2: BUY b2, 6000000, 100000000 | S1 -> S2 | No asks; append b2 behind b1. `resting`, unfilled 100000000, fills `[]`. | 100000000 = 0 + 100000000; T: 100000000 + 100000000 = 200000000. |
| 3: BUY b3, 5990000, 300000000 | S2 -> S3 | No asks; append b3. `resting`, unfilled 300000000, fills `[]`. | 300000000 = 0 + 300000000; T: 200000000 + 300000000 = 500000000. |
| 4: BUY b4, 5970000, 500000000 | S3 -> S4 | No asks; append b4. `resting`, unfilled 500000000, fills `[]`. | 500000000 = 0 + 500000000; T: 500000000 + 500000000 = 1000000000. |
| 5: SELL a1, 6010000, 200000000 | S4 -> S5 | Scan 4 bids; b1 wins the 6000000 tie. 6010000 > 6000000, so no cross; append a1. `resting`, unfilled 200000000, fills `[]`. | 200000000 = 0 + 200000000; T: 1000000000 + 200000000 = 1200000000. |
| 6: MARKET_SELL s1, 600000000 | S5 -> S6 | Four fills below; `filled`, unfilled 0. Ask untouched. | 600000000 = 600000000 fills + 0 residual; T: 1200000000 - 600000000 = 600000000. |

Event 6, inner loop (each fill has taker_id `s1`):

| Fill | Scan / maker | Incoming before | Fill at resting price | Maker after | Incoming after |
|---|---|---|---|---|---|
| 1 | Scan 4 bids; b1 wins tie with b2 by earlier list position | 600000000 | min(600000000,100000000) = 100000000 at 6000000 | b1 exhausted, delete | 500000000 |
| 2 | Scan 3 bids; b2 best | 500000000 | min(500000000,100000000) = 100000000 at 6000000 | b2 exhausted, delete | 400000000 |
| 3 | Scan 2 bids; b3 best | 400000000 | min(400000000,300000000) = 300000000 at 5990000 | b3 exhausted, delete | 100000000 |
| 4 | Scan 1 bid; b4 best | 100000000 | min(100000000,500000000) = 100000000 at 5970000 | b4 remains 400000000, same position and arrival_seq 4 | 0; stop |

C2: maker losses = 100000000 + 100000000 + 300000000 + 100000000 = 600000000.
C3: no cancellations. C5: no market residual rests; this sell has residual zero.
C4 integer proceeds:
6000000*100000000 + 6000000*100000000 + 5990000*300000000 +
5970000*100000000 = 3594000000000000 tick-units.
Divide by 10000000000 to get exactly 359400.00 USD; round only for display.

After every event: all resting quantities positive, ids unique, priority preserved;
last accepted seq = 1,2,3,4,5,6. Before event 5 one side is empty; afterwards
best_bid < best_ask (6000000 < 6010000, then 5970000 < 6010000).
The final book and event-6 result agree with the supplied expected file.
Automated confirmation: the worked-example checks in Phase 2 A contract evidence.

Hand-counted event-6 matching work: 4 best-order scans, visiting 4+3+2+1 = 10
records; 6 price comparisons after each scan's first candidate; 4 fills;
3 maker deletions; 1 surviving partial maker. Logical counts only, not timing
or benchmark instrumentation. Duplicate validation additionally scans 5 live ids.
