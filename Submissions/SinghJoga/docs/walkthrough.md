# Worked search trace

This is a worked trace for review, generated with AI; it is not evidence that I
personally performed the trace.

```text
ids = [7, 11, 7]
queries = [11, 9, 7]
expected answers = [True, False, True]
```

## Linear search

- Query `11`: inspect `ids[0] = 7` (no match), then `ids[1] = 11` (match);
  answer `True`.
- Query `9`: inspect `7`, `11`, and `7`; the list is exhausted without a
  match, so answer `False`.
- Query `7`: inspect `ids[0] = 7` and stop at the first match; answer `True`.

## Recursive binary search

Binary search first sorts a copy, leaving `ids` unchanged:
`[7, 7, 11]`. Bounds below are inclusive `(low, high)` indexes; each midpoint
is `floor((low + high) / 2)`.

- Query `11`: bounds `(0, 2)`, middle `1` has value `7`; search right at
  `(2, 2)`. Middle `2` has value `11`, so answer `True`.
- Query `9`: bounds `(0, 2)`, middle `1` has value `7`; search right at
  `(2, 2)`. Middle `2` has value `11`; search left at `(2, 1)`. The bounds
  are empty, so answer `False`.
- Query `7`: bounds `(0, 2)`, middle `1` has value `7`, so answer `True`.

## Hash membership

Build the set `{7, 11}` once from the IDs, then check queries in order:

- `11` is in the set: `True`.
- `9` is not in the set: `False`.
- `7` is in the set: `True`.
