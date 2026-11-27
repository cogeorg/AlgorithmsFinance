"""Direct tests of the SHARED validation module lob/validation.py (SPEC.md, Validation).

Both versions call this module, so an A/B comparison cannot catch a validation bug.
These tests pin every rule and the fixed check order on the module itself; the
contract checks (check_rejects_*) pin the same rules through each version's process().
Expected reasons come from the hand-written table datagen.own_cases.INVALID_EVENTS.
"""
import copy

import pytest

from datagen.own_cases import C, INVALID_EVENTS, INVALID_SETUP_LAST_SEQ, INVALID_SETUP_LIVE, L, M
from lob import validation as V


def is_live(order_id):
    return order_id in INVALID_SETUP_LIVE


@pytest.mark.parametrize("row", INVALID_EVENTS, ids=lambda r: r["label"])
def test_validate_returns_first_failing_rule(row):
    event = copy.deepcopy(row["event"])
    assert V.validate(event, INVALID_SETUP_LAST_SEQ, is_live) == row["reason"]
    assert event == row["event"], "validate() must not mutate the event"


@pytest.mark.parametrize("row", INVALID_EVENTS, ids=lambda r: r["label"])
def test_rejection_result_shape(row):
    assert V.rejection(row["event"], row["reason"]) == {
        "event_id": row["result_event_id"], "status": "rejected", "reason": row["reason"]}


VALID = {
    "limit-buy": L(3, "n1", "BUY", 99, 1),
    "limit-sell-price-1": L(3, "n1", "SELL", 1, 1),
    "limit-seq-gap": L(1_000_000, "n1", "BUY", 99, 1),
    "limit-huge": L(3, "n1", "BUY", 10**30, 10**30),
    "limit-reuses-inactive-id": L(3, "gone", "BUY", 99, 1),
    "market-sell": M(3, "n1", 1),
    "market-reuses-inactive-id": M(3, "gone", 5),
    "cancel-live": C(3, "b1"),
    "cancel-live-ask": C(3, "a1"),
    "cancel-unknown-target-is-valid": C(3, "never-seen"),
}


@pytest.mark.parametrize("name", VALID)
def test_validate_accepts_valid_events(name):
    assert V.validate(copy.deepcopy(VALID[name]), INVALID_SETUP_LAST_SEQ, is_live) is None


def test_first_event_after_empty_start():
    """Before any accepted event last_seq is 0, so seq 1 is valid."""
    assert V.validate(L(1, "b1", "BUY", 100, 1), 0, lambda _id: False) is None


def test_is_live_not_consulted_for_cancel_target():
    """A cancel target need not be live (SPEC.md): validate never rejects it for that."""
    assert V.validate(C(3, "b1"), 2, lambda _id: False) is None


@pytest.mark.parametrize("expected_type", V.EVENT_TYPES)
@pytest.mark.parametrize("actual_type", V.EVENT_TYPES)
def test_direct_method_type_check_order(expected_type, actual_type):
    event = {"seq": 3, "type": actual_type}
    reason = "missing_field:event_id" if actual_type == expected_type else "wrong_type_for_method"
    assert V.validate(event, 2, is_live, expected_type=expected_type) == reason
    assert V.validate({**event, "type": []}, 2, is_live, expected_type=expected_type) == "unknown_type"
    assert V.validate({**event, "seq": 2}, 2, is_live, expected_type=expected_type) == "nonincreasing_seq"


def test_extra_market_fields_are_not_validated():
    event = {**M(3, "s", 1), "side": [], "price_ticks": False, "comment": "own test"}
    assert V.validate(event, 2, is_live, expected_type="MARKET_SELL") is None
