"""Mutation tests ("test the tests"), from the aif-tdd template.

Each mutant subclasses the base version and overrides ONE method so that exactly
one rule breaks; KILLED_BY names the contract check that must catch it with an
AssertionError. Any other exception means the mutant or the check is broken (fix it,
never count it as a kill). A surviving mutant means a missing test: add the test, never
delete the mutant.

Phase 2: the first 12 mutants change the PUBLIC API; five additional mutants use
A's internal selection, matching and residual-storage methods. Mutation analysis
is blocked unless every unmodified A contract check passes. B remains a stub.

Internal mutants added in Phase 2:
  * LIFO within a price level                -> check_fifo_within_price
  * partially filled maker re-queued at back  -> check_partial_maker_keeps_priority
  * priority by id spelling instead of seq    -> check_own_fifo_one_price
  * best price chosen from the wrong end      -> check_best_price_first
  * limit residual dropped instead of rested  -> check_crossing_sell_at_maker_price
"""
import functools
import inspect

import pytest

import contract                            # 02_tests/contract.py (02_tests is on pythonpath)
from lob import METHODS

# Mutants modify the baseline first (it exists before B). Phase 3: also run them on B.
BASE_KEY = ("lob", "A")
BASE = METHODS[BASE_KEY]

CHECKS = [f for name, f in inspect.getmembers(contract, inspect.isfunction) if name.startswith("check_")]

_GHOST = "\x00mutant-ghost"          # an id no test ever uses


def _is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


class MutantTakerPrice(BASE):
    """Reports the fills of an incoming LIMIT at the taker's limit price instead of the maker's price."""
    KILLED_BY = "check_fill_at_maker_price"

    def process(self, event):
        r = super().process(event)
        if isinstance(event, dict) and event.get("type") == "LIMIT" and r.get("fills"):
            r = {**r, "fills": [{**f, "price_ticks": event["price_ticks"]} for f in r["fills"]]}
        return r


class MutantMarketResidualRests(BASE):
    """Lets the unfilled market-sell residual rest (as a SELL limit at price 1) instead of discarding it."""
    KILLED_BY = "check_market_residual_discarded"

    def process(self, event):
        if isinstance(event, dict) and event.get("type") == "MARKET_SELL":
            r = super().process({**event, "type": "LIMIT", "side": "SELL", "price_ticks": 1})
            if r.get("status") == "resting":
                r = {**r, "status": "partial" if r["fills"] else "unfilled"}
            return r
        return super().process(event)


class MutantCancelKeepsOrder(BASE):
    """Reports 'cancelled' with the right quantity but leaves the order in the book."""
    KILLED_BY = "check_cancel_removes_exact_residual"

    def process(self, event):
        if isinstance(event, dict) and event.get("type") == "CANCEL":
            live = {row["order_id"]: row for row in self.snapshot()}
            target = event.get("target_order_id")
            if isinstance(target, str) and target in live:
                r = super().process({**event, "target_order_id": _GHOST})
                if r.get("status") == "not_found":
                    r = {**r, "target_order_id": target, "status": "cancelled",
                         "cancelled_qty_units": live[target]["qty_units"]}
                return r
        return super().process(event)


class MutantAcceptsBoolQty(BASE):
    """Accepts True as a quantity (treats it as 1), because isinstance(True, int) is True."""
    KILLED_BY = "check_rejects_bool_quantity"

    def process(self, event):
        if isinstance(event, dict) and event.get("qty_units") is True:
            event = {**event, "qty_units": 1}
        return super().process(event)


class MutantAcceptsIntegralFloatQty(BASE):
    """Accepts an integral float quantity such as 1.0 (converts it to int)."""
    KILLED_BY = "check_rejects_integral_float_quantity"

    def process(self, event):
        q = event.get("qty_units") if isinstance(event, dict) else None
        if isinstance(q, float) and q.is_integer():
            event = {**event, "qty_units": int(q)}
        return super().process(event)


class MutantSeqAdvancesOnReject(BASE):
    """A rejected event still advances the last accepted seq."""
    KILLED_BY = "check_rejected_event_does_not_advance_seq"

    def process(self, event):
        r = super().process(event)
        if r.get("status") == "rejected" and isinstance(event, dict) and _is_int(event.get("seq")):
            super().process({"seq": event["seq"], "event_id": _GHOST, "type": "CANCEL", "target_order_id": _GHOST})
        return r


class MutantNoDuplicateCheck(BASE):
    """Accepts a submission whose order_id is already live (no duplicate-live-id rule)."""
    KILLED_BY = "check_rejects_duplicate_live_id"

    def process(self, event):
        if (isinstance(event, dict) and event.get("type") in ("LIMIT", "MARKET_SELL")
                and isinstance(event.get("order_id"), str)
                and event["order_id"] in {row["order_id"] for row in self.snapshot()}):
            oid = event["order_id"]
            r = super().process({**event, "order_id": oid + _GHOST})
            if r.get("status") != "rejected":
                r = {**r, "order_id": oid, "fills": [{**f, "taker_id": oid} for f in r["fills"]]}
            return r
        return super().process(event)


class MutantFillsReversed(BASE):
    """Returns the fills of a market sell in reverse execution order."""
    KILLED_BY = "check_worked_example_market_sell"

    def process(self, event):
        r = super().process(event)
        if isinstance(event, dict) and event.get("type") == "MARKET_SELL" and r.get("fills"):
            r = {**r, "fills": list(reversed(r["fills"]))}
        return r


class MutantPartialReportedAsFilled(BASE):
    """Reports a partly executed market sell as 'filled'."""
    KILLED_BY = "check_market_sell_larger_than_depth_is_partial"

    def process(self, event):
        r = super().process(event)
        if r.get("status") == "partial":
            r = {**r, "status": "filled"}
        return r


class MutantMutatesInput(BASE):
    """Writes into the caller's event dict."""
    KILLED_BY = "check_input_event_not_mutated"

    def process(self, event):
        r = super().process(event)
        if isinstance(event, dict):
            event["_seen"] = True
        return r


class MutantAsksDescending(BASE):
    """Book inspection lists asks by DEcreasing price."""
    KILLED_BY = "check_snapshot_canonical_order"

    def snapshot(self):
        rows = super().snapshot()
        bids = [r for r in rows if r["side"] == "BUY"]
        asks = sorted((r for r in rows if r["side"] == "SELL"), key=lambda r: (-r["price_ticks"], r["arrival_seq"]))
        return bids + asks


class MutantBestBidIsBestAsk(BASE):
    """best_bid() returns the best ask (sides swapped in the inspection function)."""
    KILLED_BY = "check_one_limit_rests"

    def best_bid(self):
        return super().best_ask()


class MutantLifo(BASE):
    """Select the last arrival at the best price instead of the first."""
    KILLED_BY = "check_fifo_within_price"

    def _best_index(self, orders, side):
        if not orders:
            return None
        return min(range(len(orders)), key=lambda i: (
            -orders[i]["price_ticks"] if side == "BUY" else orders[i]["price_ticks"],
            -orders[i]["arrival_seq"]))


class MutantRequeuesPartialMaker(BASE):
    """Move a surviving partial maker to the back of its side's list."""
    KILLED_BY = "check_partial_maker_keeps_priority"

    def _match(self, event, side, limit):
        fills, remaining = super()._match(event, side, limit)
        if fills:
            orders = self.asks if side == "BUY" else self.bids
            for i, maker in enumerate(orders):
                if maker["order_id"] == fills[-1]["maker_id"]:
                    orders.append(orders.pop(i))
                    break
        return fills, remaining


class MutantPriorityById(BASE):
    """Break equal-price ties by identifier spelling instead of arrival."""
    KILLED_BY = "check_own_fifo_one_price"

    def _best_index(self, orders, side):
        if not orders:
            return None
        return min(range(len(orders)), key=lambda i: (
            -orders[i]["price_ticks"] if side == "BUY" else orders[i]["price_ticks"],
            orders[i]["order_id"]))


class MutantWrongPriceEnd(BASE):
    """Match the lowest bid or highest ask first."""
    KILLED_BY = "check_best_price_first"

    def _best_index(self, orders, side):
        if not orders:
            return None
        return min(range(len(orders)), key=lambda i: (
            orders[i]["price_ticks"] if side == "BUY" else -orders[i]["price_ticks"],
            orders[i]["arrival_seq"]))


class MutantDropsLimitResidual(BASE):
    """Report a limit residual but omit storing it."""
    KILLED_BY = "check_crossing_sell_at_maker_price"

    def _rest(self, event, remaining):
        pass


MUTANTS = [MutantTakerPrice, MutantMarketResidualRests, MutantCancelKeepsOrder, MutantAcceptsBoolQty,
           MutantAcceptsIntegralFloatQty, MutantSeqAdvancesOnReject, MutantNoDuplicateCheck,
           MutantFillsReversed, MutantPartialReportedAsFilled, MutantMutatesInput,
           MutantAsksDescending, MutantBestBidIsBestAsk, MutantLifo, MutantRequeuesPartialMaker,
           MutantPriorityById, MutantWrongPriceEnd, MutantDropsLimitResidual]


def _run(check, impl):
    """Return 'pass', 'killed' (AssertionError) or 'error: <Type>' (anything else)."""
    try:
        check(impl)
        return "pass"
    except AssertionError:
        return "killed"
    except Exception as exc:  # noqa: BLE001 - reported, never counted as a kill
        return f"error: {type(exc).__name__}: {exc}"


@functools.lru_cache(maxsize=None)
def _base_failures() -> tuple:
    """Checks the UNMODIFIED base fails. Mutation analysis is only meaningful from a passing base."""
    return tuple((c.__name__, o) for c in CHECKS if (o := _run(c, BASE)) != "pass")


@pytest.mark.parametrize("mutant", MUTANTS, ids=lambda m: m.__name__)
def test_mutant_killed_for_the_intended_reason(mutant):
    if _base_failures():
        pytest.fail(f"mutation analysis BLOCKED: the unmodified base {BASE.__name__} fails "
                    f"{len(_base_failures())} checks, e.g. {_base_failures()[0]}. Fix the base first.")
    assert any(c.__name__ == mutant.KILLED_BY for c in CHECKS), f"{mutant.KILLED_BY} is not a contract check"
    outcomes = {c.__name__: _run(c, mutant) for c in CHECKS}
    errors = {k: v for k, v in outcomes.items() if v.startswith("error")}
    assert not errors, f"{mutant.__name__} is not runnable / breaks the interface: {errors}"
    assert outcomes.get(mutant.KILLED_BY) == "killed", (
        f"{mutant.__name__} ({mutant.__doc__.strip()}) was not killed by {mutant.KILLED_BY}; "
        f"outcomes: {outcomes}")


def test_every_mutant_names_an_existing_check():
    names = {c.__name__ for c in CHECKS}
    missing = {m.__name__: m.KILLED_BY for m in MUTANTS if m.KILLED_BY not in names}
    assert not missing, missing


@pytest.mark.parametrize("key", sorted(METHODS), ids=lambda k: "-".join(k))
def test_real_versions_pass_all_checks(key):
    # Separate version cases expose B's expected Phase 3 red result explicitly.
    impl = METHODS[key]
    for check in CHECKS:
        assert _run(check, impl) == "pass", (key, check.__name__, _run(check, impl))
