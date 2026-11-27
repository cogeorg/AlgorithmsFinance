# Correctness coverage map

This review adds coverage without changing expected answers or engine code.
The three existing 18-event generated fixtures remain useful short parity
checks; the bounded independent oracle and supplied 10,000-event parity
attempts are separate checks, not benchmark measurements.

| Requirement | Existing or added check |
|---|---|
| Supplied six-BTC example: exact fills, integer proceeds, residual book | `test_supplied_worked_example_matches_supplied_expected_result`; added `test_replay_jsonl_and_gzip_dispatch_worked_example` compares the replayed final event/book to the supplied JSON, including integer tick-unit proceeds and `$359,400` display conversion. |
| Empty, exact, and oversized market sells; market residual never rests | `test_market_sell_against_empty_book_is_unfilled_and_does_not_rest`; `test_one_bid_market_sell_depth_cases` cases `smaller-than-depth`, `equal-to-depth`, and `larger-than-depth-market-residual-does-not-rest`. |
| Invalid input preserves book and accepted sequence | `test_missing_required_fields_are_rejected_without_state_change`; `test_invalid_values_are_rejected_without_mutating_book_or_sequence`; `test_duplicate_live_submission_id_is_rejected_without_mutation`; `test_nonincreasing_sequence_is_rejected_without_mutation`; `test_rejected_sequence_can_be_used_by_a_later_valid_event`. |
| Unknown cancellation accepted and advances sequence | `test_valid_unknown_cancel_advances_accepted_sequence`. |
| FIFO, best-price, adversarial ID spelling | `test_long_same_price_queue_uses_arrival_not_identifier_order`; `test_market_sell_prioritizes_higher_bid_before_earlier_lower_bid`; crossing-limit tests check best price then FIFO. |
| Partial maker retains priority | `test_partial_fill_then_next_sell_keeps_maker_fifo_priority`; `test_partial_maker_keeps_fifo_priority_across_events`. |
| Cancel after partial/full fill and repeated cancel | `test_cancel_after_partial_execution_removes_only_the_residual`; `test_cancel_after_full_execution_returns_not_found`; `test_repeated_cancellation_is_not_found_after_first_cancel`; middle-queue removal is checked by `test_cancelling_middle_of_price_queue_preserves_fifo`. |
| Crossing buys/sells, equality, maker prices, resting residuals | `test_crossing_limit_buy_uses_best_asks_then_fifo_and_maker_prices`; `test_crossing_limit_sell_uses_best_bids_then_fifo`; `test_limit_buy_crosses_at_price_equality`; `test_limit_sell_crosses_at_price_equality`; `test_worse_limit_buy_does_not_cross_and_rests`; `test_worse_limit_sell_does_not_cross_and_rests`; partial residual tests. |
| 2,000-order same-price queue with arrival-order expectations | Added `test_2000_order_same_price_queue_uses_literal_arrival_order`, parameterized over both engines; IDs are reverse-spelled relative to arrival. |
| Fixed-book 10%/100%/200%, conservation, ceiling below 10 units | Added `test_fixed_book_sell_sizes_preserve_quantity_and_do_not_rest`; existing `test_ceil_percent_uses_integer_ceiling`; added `test_ten_percent_uses_ceiling_below_ten_units` for available quantities 1 through 9. |
| 5,000 add/cancel pairs and revised heap cleanup | Added `test_five_thousand_add_cancel_pairs_leave_no_revised_storage`; `test_repeated_churn_stays_bounded_while_another_price_is_active` and the other `tests/test_revised_storage.py` regressions cover bounded stale entries, empty sides, reactivation and cleanup. |
| Independent hand-calculated mixed stream | Added `test_hand_calculated_mixed_event_sequence`; checks crossing residual, sell fills, cancellations, quantity conservation, integer proceeds, and final empty state. |
| JSONL/gzip loading and actual event dispatch | Added `test_replay_jsonl_and_gzip_dispatch_worked_example`; writes the supplied six-event stream in both formats and calls the replay dispatcher for both versions. |
| Historical ID reuse vs duplicate live IDs | Existing `test_duplicate_live_submission_id_is_rejected_without_mutation`; added `test_id_can_be_reused_after_order_is_no_longer_live`. The README excludes historical-ID bans, so only currently live duplicates are rejected. |
| Independent bounded oracle | No independent brute-force oracle existed. Added `BruteForceSpecificationBook` and `test_seeded_events_match_independent_brute_force_oracle`: seeds 42/43/44, 1,500 events per seed, both engines checked against a separate list-scanning/select-one-maker model after every event. It shares no engine validation, matching, or canonical-ordering helpers. The generator mixes limit adds/crosses, sells, cancellations, invalid quantities and nonincreasing sequences; active state is asserted below 100 orders. |

## Supplied 10,000-event parity attempt

`results/check_supplied_stream_parity.py` performs untimed A/B replay and
compares the ordered result, accepted sequence, canonical book, and basic book
invariants after every event for one supplied compressed stream. The Python
supervisor in `results/run_correctness_review.py` gives each scenario its own
enforced 60-second deadline, terminates only that scenario's worker on timeout,
and the worker atomically saves progress every 100 events. Per-stream results
and partial progress are recorded in `results/correctness_review/` and
summarized in `results/correctness_review_log.txt`. This check does not invoke
benchmark tools, counters, profiles, or timing instrumentation.

The full test suite is run once after additions. See
`results/correctness_review_log.txt` for exact commands, counts, elapsed
times, stopped checks, and any remaining gaps.

## Review execution results

- New focused checks: **30 passed**.
- Latest complete assignment suite: **185 passed** in 62.04 seconds in the
  final index-copy environment; details are in
  `results/final_packaging_verification.txt`.
- Earlier correctness-review run: **185 passed** in 72.60 seconds.
- Independent oracle: all three seeds (42, 43, 44), 1,500 events each, passed
  for both engines; the generated active-book peak stayed under the asserted
  100-order cap.
- Supplied stream parity: mixed and cancel-churn completed 10,000/10,000
  events. Buildup stopped at 4,600, crowded at 4,700, and sweep at 4,300
  under their individual enforced 60-second deadlines. No mismatch was
  observed in completed prefixes; progress is preserved. These three streams
  remain unchecked beyond their saved prefixes.
- No engine or expected-answer file changed, and no benchmark was run.
