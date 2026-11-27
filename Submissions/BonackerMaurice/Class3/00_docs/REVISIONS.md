# Revisions (Class 3)

All three pricers are kept, pass the same tests, and are measured on identical
inputs. `vectorised` is the version used for BTC and the 40-asset runs.

| Version | File | Memory | Role |
|---|---|---|---|
| reference | `01_code/american_put/reference.py` | O(N): lists S, V (N+1 each) + boundary | original, slide pseudocode line by line |
| vectorised | `01_code/american_put/vectorised.py` | O(N): arrays S, V + temporaries of length t+1 | revised, NumPy, one vector step per date |
| fulltree | `01_code/american_put/fulltree.py` | O(N²): every node of the value tree | contrast only (naive) |

## Revision 1: reference → vectorised (speed)

**What changed:** the inner loop over j = 0..t is replaced by one NumPy
operation per date:

```python
St /= d                                               # S[j] = S[j]/d, in place
c = (q * V[1:t+2] + (1 - q) * V[:t+1]) / R            # continuation from the OLD V
exercise = K - St
V[:t+1] = np.maximum(np.maximum(exercise, 0.0), c)    # overwrite only after c is complete
```

**The trap:** the reference updates V[j] in increasing j, so V[j+1] is still the
old value when it is read. The vector version must not overwrite V before the
whole continuation vector is built. Here the right-hand side is evaluated into a
new array `c` first, so the assignment cannot read a value from the current
date.

**Same arithmetic:** the operations and their order are the same as in the
reference, including the initial prices S[j] = (S[j−1]·u)/d, which are built
with the same Python loop. Value and boundary are therefore identical bit for
bit. `test_random_trees_match_reference_exactly` checks this on 40 random trees,
and on BTC the full run checks it with `reference_equals_vectorised` in
`btc.csv` and the boundary hashes in `memory_curve.csv`.

**Effect (run `20261127-120909_184680a`, commit `184680a`):**

| N | reference | vectorised | speed-up |
|---|---|---|---|
| 8,760 (BTC, one year) | 5.96 s | 0.24 s | 25× |
| 20,000 | 30.0 s | 1.15 s | 26× |
| 43,822 (BTC, full file) | 152 s | 8.6 s | 18× |

Memory is unchanged: both versions are O(N), with a traced peak of 2.7 MiB at
N = 43,822 for the vectorised version. Every point is a single measurement. A
pre-commit run gave 6.3 s for the vectorised version at N = 43,822 (24×), so
the factor varies between runs (see the README).

## Revision 2: the boundary inside the backward pass

The boundary is one number per date. It is recorded while V[0..t] is updated:
the highest node j with K − S[j] > 0 and K − S[j] ≥ c. It needs no extra pass
and no stored tree, so total memory stays O(N). `fulltree.py` shows the naive
alternative: store the value tree, then read the boundary off it in a second
pass.

## Measurement fixes found while building (no algorithm change)

- **tracemalloc and pure Python.** Under `tracemalloc` the reference ran 166 s
  instead of 9 s at N = 8,760. Timings are now always taken without tracing.
  Traced memory comes from a second call (for the reference, only up to
  N = 5,000).
- **RAM-dependent limit.** Whether the full tree fits depends on free RAM, not
  on the algorithm. Free RAM is measured right before each full-tree attempt
  and saved (`memory_curve.csv` column `ram_available_gb`, and
  `environment.json`). A tree that needs more than 80% of free RAM is not
  attempted, so the laptop is never forced into swap.
