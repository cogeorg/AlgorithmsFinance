# Peer Review — Search Algorithms
**Reviewed project:** Algorithms in Finance — Phase 1, Zeynep Erten

## 1. Overview

I manually tested the four search implementations:

- Linear Search
- Recursive Binary Search
- Iterative Binary Search
- Hash-Set Membership

The objective was to investigate how the algorithms behave when given unusual or invalid inputs, particularly nested arrays, strings, Boolean values, and floating-point numbers.

The tests were executed directly in Python using a `check()` function that passes identical inputs to all four algorithms and prints their results or exceptions.

## 2. Test Results

### Test 1 — String instead of integer query

**Input:**
```python
check([1, 2, 3], ["2"])
```

**Observed results:**

| Algorithm | Result |
|---|---|
| Linear Search | `[False]` |
| Recursive Binary Search | `TypeError` |
| Iterative Binary Search | `TypeError` |
| Hash Search | `[False]` |

**Explanation:**

Linear Search and Hash Search treat the string `"2"` as different from the integer `2` and return `False`.

Both Binary Search implementations raise `TypeError` because Python cannot compare strings and integers using the `<` operator.

**Finding:** The algorithms handle invalid query types inconsistently.

### Test 2 — Nested array among integer IDs

**Input:**
```python
check([1, [2, 3], 4], [2])
```

**Observed results:**

| Algorithm | Result |
|---|---|
| Linear Search | `[False]` |
| Recursive Binary Search | `TypeError` |
| Iterative Binary Search | `TypeError` |
| Hash Search | `TypeError` |

**Explanation:**

Linear Search compares each array element with the query `2`. Since `[2, 3]` is not equal to `2`, it returns `False`.

Binary Search fails because it cannot sort a mixture of integers and lists.

Hash Search fails because lists are unhashable and cannot be inserted into a Python set.

**Finding:** The implementations respond differently to malformed arrays because they do not perform shared input validation.

### Test 3 — Mixed invalid types with a present query

**Input:**
```python
check([1, ["1", 3], "$"], [1])
```

**Observed results:**

| Algorithm | Result |
|---|---|
| Linear Search | `[True]` |
| Recursive Binary Search | `TypeError` |
| Iterative Binary Search | `TypeError` |
| Hash Search | `TypeError` |

**Explanation:**

Linear Search finds `1` at the first position and immediately stops searching. It never examines the invalid elements `["1", 3]` and `"$"`.

Both Binary Search implementations fail during sorting, while Hash Search fails because the nested list is unhashable.

**Finding:** Linear Search can return a successful result even when the input array contains invalid elements. Early termination allows malformed data to go unnoticed.

### Test 4 — Boolean and floating-point queries

**Input:**
```python
check([1, 2, 3], [True, 2.0])
```

**Observed results:**

All four algorithms returned:

```python
[True, True]
```

**Explanation:**

Python considers the following comparisons true:

```python
True == 1
2.0 == 2
```

Consequently, all four algorithms accept the Boolean `True` and floating-point value `2.0` as matches for integer IDs.

**Finding:** Invalid query types can produce successful membership matches without any warning or exception.

### Test 5 — Boolean and floating-point values inside the array

**Input:**
```python
check([True, 2.0, 3], [1, 2])
```

**Observed results:**

All four algorithms returned:

```python
[True, True]
```

**Explanation:**

This reverses the previous experiment. The queries are valid integers, but the input array contains a Boolean and a floating-point number.

Because `True == 1` and `2.0 == 2`, all implementations report successful matches.

**Finding:** Non-integer elements in the original array can be treated as valid integer IDs.

## 3. Overall Assessment

The tests revealed two main weaknesses.

**1. Inconsistent handling of invalid inputs**

When arrays contain strings or nested lists, the algorithms behave differently. Linear Search may return a Boolean result, while Binary Search and Hash Search raise exceptions.

**2. Silent acceptance of invalid numeric types**

All four algorithms accept certain Boolean and floating-point values as matches for integers. This happens because Python's equality rules treat these values as numerically equivalent.

These issues are particularly relevant when searching for financial transaction IDs, where strict data types may be important.

However, the assignment explicitly specifies integer arrays and integer queries. The adversarial inputs used in these tests fall outside that specification. Therefore, the findings demonstrate robustness and input-validation weaknesses, rather than proving that the search algorithms are incorrect for valid inputs.

## 4. Suggested Improvements

I recommend adding a shared input-validation function that:

- Checks that every array element is an integer.
- Checks that every query is an integer.
- Explicitly rejects Booleans and floating-point numbers.
- Raises a consistent `TypeError` when invalid inputs are detected.

For example:

```python
def validate_inputs(ids, queries):
    if not all(type(x) is int for x in ids):
        raise TypeError("All IDs must be integers")

    if not all(type(q) is int for q in queries):
        raise TypeError("All queries must be integers")
```

This function could be called before executing any of the four search algorithms.

## 5. Conclusion

The implementations appear to work correctly for the normal integer-search cases examined through code inspection, although this review did not establish correctness for every valid input.

My manual adversarial tests identified a common weakness: **the algorithms do not explicitly validate input types**.

This leads to inconsistent error handling for malformed arrays and potentially misleading successful matches involving Booleans and floating-point numbers.

Adding consistent input validation would improve robustness, predictability, and reliability without requiring changes to the underlying search algorithms.
