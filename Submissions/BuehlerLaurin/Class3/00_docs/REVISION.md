# Revision log
## Explicit deviation: slide line 10
Slides pp.23/25 line 10: `(q*V_up+(1-q)*V_down)/R`. A and B evaluate the algebraically equivalent `(V_down+q*(V_up-V_down))/R`. Expanding the latter yields the former in exact arithmetic. Binary64 weighted evaluation in the tie regression gave 50.00000000000001 instead of 50.0, which incorrectly excluded exercise under the exact >= rule. The affine evaluation preserves that tie without relaxing a tolerance or changing any expected result. This evaluation change is separate from the stable-S construction deviation.

## Versions and measurements
1. A implements the slides' increasing-j two-array induction, with independently reconstructed stable stock layers and O(N) boundary output. Exact-tie regression preserved by affine continuation evaluation. Evidence: tests-green-A (23 passed).
2. Profile A on actual BTC1y: pricing accounts for 84.339/84.977 profiled seconds. Python per-node work dominates, including 38.38m exponentials and 76.76m max calls.
3. B changes the inner layer to NumPy array operations, retaining recurrence, exact exercise comparison, full-node maximum boundary and stable stock reconstruction. Preallocated O(N) buffers avoid a stored tree. No pruning or contiguity assumption.
4. Shared contracts, exact oracle and Hypothesis differential are green (36 passed). BTC1y A/B values match exactly, with zero boundary exceptions.
5. The first B measured BTC1y median 1.072288 s / BTC5y 13.492199 s. Cache the 2N+1 distinct reciprocal-CRR stocks/payoffs in O(N), using layer views instead of repeated exponentials. All tests stayed green; revised BTC1y 0.718781 s / BTC5y 7.199832 s. This revision trades a larger linear cache for fewer exp calls.
6. Final A/B BTC1y median ratio 41.754947 on the same data/machine; A reused only after source dependency hash checks. Final grid and raw repeats are in 20261127T121436Z_279b029-dirty_fast_blocks12. All40 5y median 284.649042 s, primary peak 8731641 bytes. Direct-process growth exponents A=1.961, B=1.266 over completed 1k–8k cells; A8k stopped. The exponent observation does not alter the quadratic node count.
