# Hand traces

Traces 1 and 3 were worked out by hand by Jiaxin Huang. The table format and
Trace 2 were prepared with help from an AI assistant and then checked by hand.
All traces were checked against the code afterwards.

Small examples traced by hand before running the code (slide 58).
Positions start at 0, as in Python.

## Trace 1: BinarySearch (binary_v2), absent query

**Input:** sorted_ids = [2, 4, 7, 11], x = 9
**Start:** lo = 0, hi = 3

| Step | lo | hi | mid | Read A[mid] | Compare | Write |
|---|---|---|---|---|---|---|
| 1 | 0 | 3 | 1 | 4 | 4 < 9 | lo = 2 |
| 2 |  2 | 3  |  2 | 7  |  7 < 9 | lo=3  |
| 3 |  3 | 3  |  3 |  11 |  11 > 9 | hi = 2  |

**Result:** returns False because lo = 3 > hi = 2, so the search range is empty.
**Count:** 3 array reads, 6 comparisons.
**Invariant check:** before each step, if 9 occurs, it lies in positions lo..hi.
Step 1 discards positions 0 and 1, because they hold values ≤ 4 < 9.

## Trace 2: BinarySearch (binary_v2), present query at the last position

**Input:** sorted_ids = [2, 4, 7, 11], x = 11
**Start:** lo = 0, hi = 3

| Step | lo | hi | mid | Read A[mid] | Compare | Write |
|---|---|---|---|---|---|---|
| 1 |  0 |  3 | 1  | 4  | 4 < 11  | lo=2 |
| 2 |  2 | 3  |  2 | 7  |  7 < 11 | lo=3  |
| 3 |  3 | 3  |  3 |  11 |  11 = 11 | return True |

**Result:** returns True at step 3, because A[3] = 11 equals x.
**Count:** 3 array reads, 5 comparisons (2 + 2 + 1)

## Trace 3: LinearSearch (linear_v1), slide example

**Input:** ids = [7, 11, 7], queries = [11, 9, 7]
**Expected output:** [True, False, True]

### Query 11

| Step | i | Read ids[i] | Compare | Write |
|---|---|---|---|---|
| 1 | 0  | 7  | 7 = 11? no  | i = 1  |
| 2 |  1 |  11 |  11 = 11? Yes | return True  |

### Query 9

| Step | i | Read ids[i] | Compare | Write |
|---|---|---|---|---|
| 1 |  0 |  7 | 7 = 9? No  |i = 1   |
| 2 |  1 |  11 |  11 = 9? No | i = 2  |
| 3 |  2 |  7 |  7 = 9? No | i = 3  |
| end | 3  |  loop ends |   | return False  |

### Query 7

| Step | i | Read ids[i] | Compare | Write |
|---|---|---|---|---|
| 1 | 0  | 7  | 7 = 7? Yes  |  Return True |

### Summary

| Query | Positions read | Comparisons | Result |
|---|---|---|---|
| 11 | 0,1  | 2  |  True |
| 9 |  0,1,2 |  3 | False  |
| 7 | 0  |  1 | True  |

**Output:** [True, False, True]
**Total comparisons:** 6
**Note:** position 2 is never read for query 11, because the match at position 1 returns True.