# Algorithm Revision History

## Original Version

The original Binary Search uses a manually implemented recursive helper. It
creates a sorted copy of the input array, searches each query independently,
and preserves the original array.

## Revised Version

The revised Binary Search replaces recursion with an iterative `while` loop.
It preserves the same sorted-copy preparation, input/output contract, and
asymptotic running time. The revision removes recursive call overhead and the
`O(log n)` call stack while retaining the original version for direct testing
and measurement.

Both versions are evaluated by the same contract, edge-case, failure-mode, and
deterministic randomized test suite.
