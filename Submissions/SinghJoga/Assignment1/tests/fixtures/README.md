# Deterministic generated test streams

The three JSONL fixtures in this directory are small valid event streams for
future event-by-event comparison of implementation versions. They are test
data, not benchmark workloads and do not contain matching outcomes.

- Seeds: 13, 37, and 91.
- Events per stream: 18.
- Event sequence: 1 through 18, strictly increasing.
- Event cycle: `LIMIT`, `LIMIT`, `MARKET_SELL`, `CANCEL`, `LIMIT`,
  `MARKET_SELL`, repeated three times.
- Limit sides, prices, quantities, and cancellation targets are selected with
  `random.Random(seed)`. Prices are selected from 5,990,000, 6,000,000, and
  6,010,000 ticks; quantities are selected from 10,000,000, 25,000,000, and
  50,000,000 units.
- Submission identifiers are unique within each stream. Cancellation targets
  may refer to a prior submission or to a deliberately unknown identifier;
  either is a valid cancellation event.

Regenerate from the Assignment1 directory with:

```text
python tests/generate_spec_streams.py
```

The fixtures are intended to be replayed one event at a time through both
versions, comparing each event result and canonical book inspection. This
parity check is pending until both implementations exist; it does not replace
the hand-calculated expected cases in the specification tests.
