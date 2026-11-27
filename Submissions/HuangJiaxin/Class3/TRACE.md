# Hand trace: American put on a three-period tree

Traced by hand by Jiaxin Huang before checking against the code. The result is used as
an independent test case in `test_put.py`.

## Inputs

S0 = 100, K = 100, u = 2, d = 0.5, R = 1.25, N = 3.

Check no arbitrage: d < R < u, that is 0.5 < 1.25 < 2.

q = (R − d) / (u − d) = 0.5

## Rules

* Node (t, j): date t, j up moves. Stock price S = S0 · u^j · d^(t − j).
* At expiry (t = 3): V = max(K − S, 0).
* Earlier: exercise = max(K − S, 0); continuation c = (q · V_up + (1 − q) · V_down) / R,
  where V_up is node (t + 1, j + 1) and V_down is node (t + 1, j).
  V = max(exercise, c). Write "yes" if exercising is optimal (exercise > 0 and exercise ≥ c).

## Date 3 (expiry)

| j | S | V = max(K − S, 0) |
|---|---|---|
| 3 | 800 | 0 |
| 2 | 200 | 0 |
| 1 | 50 | 50 |
| 0 | 12.5 | 87.5 |

## Date 2

| j | S | Exercise | Continuation c | V | Exercise optimal? |
|---|---|---|---|---|---|
| 2 | 400 | 0 | 0 | 0 | no |
| 1 | 100 | 0 | 20 | 20 | no |
| 0 | 25 | 75 | 55 | 75 | yes |

## Date 1

| j | S | Exercise | Continuation c | V | Exercise optimal? |
|---|---|---|---|---|---|
| 1 | 200 | 0 | 8 | 8 | no |
| 0 | 50 | 50 | 38 | 50 | yes |

## Date 0

| j | S | Exercise | Continuation c | V | Exercise optimal? |
|---|---|---|---|---|---|
| 0 | 100 | 0 | 23.2 | 23.2 | no |

## Result

**Put value at date 0:** 23.2

**Early-exercise boundary** (for each date, the highest S where exercising is optimal,
or "none"): t = 0: none ; t = 1: 50 ; t = 2: 25 ; t = 3: 50

**Check against the code:** `price_plain`, `price_numpy` and `price_full_tree` all return 23.2 and the boundary none, 50, 25, 50 (`test_jiaxin_hand_trace` in `test_put.py`). The European put on the same tree is worth 15.2, so the right to exercise early adds 8.0.
