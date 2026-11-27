# Hand trace: the worked example through version B

Traced by hand by Jiaxin Huang before checking against the code.

## Setup

Events 1 to 5 build this book (prices in dollars, quantities in BTC):

| Side | Price level | FIFO queue at that price (front first) | Live orders |
|---|---|---|---|
| BUY | 60,000 | b1 (1), b2 (1) | 2 |
| BUY | 59,900 | b3 (3) | 1 |
| BUY | 59,700 | b4 (5) | 1 |
| SELL | 60,100 | a1 (2) | 1 |

Bid heap (stored as negative prices, so the top is the best bid): 60,000, 59,900, 59,700

Event 6: market sell `s1` for **6 BTC**.

## Trace of FillMarketSell

Rules for each row:

1. Ask the heap for the best bid price. If the top price has no level any more (stale), pop it and look again.
2. Take the order at the FRONT of that price's queue.
3. Trade min(what s1 still wants, what the maker has left) at the maker's price.
4. Write what is left on both sides. If the maker is exhausted, pop it from the queue. If the level has no live order left, delete the level.

| Step | Heap top (stale popped?) | Best bid | Front order | Trade (BTC) | s1 still wants | Maker left | Level after |
|---|---|---|---|---|---|---|---|
| 1 | 60,000 (no) | 60,000 | b1 (1) | 1 | 5 | 0, popped | 60,000: b2 (1), live 1 |
| 2 | 60,000 (no) | 60,000 | b2 (1) | 1 | 4 | 0, popped |  60,000: deleted  |
| 3 | 60,000 (yes, popped)→ 59,900 | 59,900 |b3 (3)  | 3 | 1 | 0, popped | 59,900: deleted  |
| 4 | 59,900(yes, popped)→ 59,700  | 59,700 |b4 (5) | 1 | 0 | 4 | 59,700: b4 (4), live 1 |

**Stop because:** s1 wants 0 bitcoin, all the 6 bitcoin are sold.

## Result

**Fills (maker: BTC @ price):** b1: 1 @ 60,000, b2: 1 @ 60,000, b3: 3 @ 59,900, b4: 1 @ 59,700

**Status:** filled  **Unfilled:** 0 BTC

**Gross proceeds:** 359,400 dollars

**Book after the sale:** bids b4: 4 @ 59,700 ; asks a1: 2 @ 60,100

**Check against the code:** My trace matches the output of `python3 replay.py data/supplied/worked_example.jsonl`: 4 fills, 359,400 dollars, b4 4 BTC and a1 2 BTC left.
