"""Small deterministic transition streams shared by both engine versions."""

from __future__ import annotations

import random
import unittest

from support import ENGINE_CLASSES, cancel, limit, market_sell, verify_transition


SEEDS = tuple(range(10))
EVENTS_PER_SEED = 40


def _next_seq(last_accepted_seq: int | None, rng: random.Random) -> int:
    if last_accepted_seq is None:
        return rng.randint(1, 5)
    return last_accepted_seq + rng.randint(1, 3)


def _event_for_step(engine, seed: int, step: int, rng: random.Random) -> tuple[dict, bool]:
    snapshot = engine.canonical_snapshot()
    seq = _next_seq(engine.last_accepted_seq, rng)
    event_id = f"random-{seed}-{step}"
    order_id = f"order-{seed}-{step}"

    if step % 10 == 9:
        invalid_kind = (step // 10) % 3
        if invalid_kind == 0:
            return limit(seq, event_id, order_id, "BUY", 100, 0), False
        if invalid_kind == 1 and engine.last_accepted_seq is not None:
            return market_sell(engine.last_accepted_seq, event_id, order_id, 1), False
        if snapshot:
            duplicate = rng.choice(snapshot)["order_id"]
            return limit(seq, event_id, duplicate, "SELL", 100, 1), False
        return limit(seq, event_id, order_id, "BUY", 100, 0), False

    choice = rng.random()
    if choice < 0.55:
        return (
            limit(
                seq,
                event_id,
                order_id,
                rng.choice(("BUY", "SELL")),
                rng.randint(98, 102),
                rng.randint(1, 5),
            ),
            True,
        )
    if choice < 0.78:
        return market_sell(seq, event_id, order_id, rng.randint(1, 7)), True
    if snapshot and choice < 0.92:
        target = rng.choice(snapshot)["order_id"]
    else:
        target = f"missing-{seed}-{step}"
    return cancel(seq, event_id, target), True


class TestRandomizedTransitions(unittest.TestCase):
    def test_fixed_seed_streams_preserve_public_transition_invariants(self) -> None:
        for engine_class in ENGINE_CLASSES:
            for seed in SEEDS:
                with self.subTest(engine=engine_class.__name__, seed=seed):
                    engine = engine_class()
                    rng = random.Random(seed)
                    for step in range(EVENTS_PER_SEED):
                        before = engine.canonical_snapshot()
                        before_seq = engine.last_accepted_seq
                        event, should_be_valid = _event_for_step(engine, seed, step, rng)
                        result = engine.process_event(event)
                        after = engine.canonical_snapshot()
                        if should_be_valid:
                            self.assertNotEqual(result["status"], "rejected")
                        else:
                            self.assertEqual(result["status"], "rejected")
                        verify_transition(
                            before,
                            event,
                            result,
                            after,
                            before_seq,
                            engine.last_accepted_seq,
                        )


if __name__ == "__main__":
    unittest.main()

