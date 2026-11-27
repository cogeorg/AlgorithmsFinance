"""Three small follow-up experiments on the two order books (not part of the main benchmark).

    py -3.13 -B experiments.py            run all three
    py -3.13 -B experiments.py 2          run only experiment 2

1. Break-even depth   add-then-cancel churn on top of a book of D resting orders:
                      from which D on is version B faster than version A?
2. Cancel position    N orders queue at one price; cancel at the front, middle or back of the queue.
3. Rejected events    the same stream length with a growing share of invalid events.

The parameters below are chosen by the person running the experiment. Timing follows the main
benchmark: time.perf_counter, one warm-up, REPEATS timed runs on fresh books, median reported;
building events and books is outside the timed region. Results go to results/experiments.json.
"""
import json
import platform
import statistics
import sys
import time
from pathlib import Path

from book_a import OrderBookA
from book_b import OrderBookB
from events import BUY, SELL

# ---------------------------------------------------------------- parameters: fill these in
BOOK_DEPTHS = [0, 2, 5, 10, 15, 18, 20, 22, 25, 28, 30, 33, 35, 38, 40, 45, 50, 75, 100, 200, 500, 1000, 2000]
QUEUE_LENGTHS = [50,100,1000,5000,10000,30000]      # experiment 2: orders queued at one price, e.g. 100 up to 30000
REJECT_SHARES = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9]      # experiment 3: share of invalid events, numbers from 0.0 to 0.9

REPEATS = 5
CHURN_CYCLES = 5_000    # experiment 1: add+cancel pairs that are timed
CANCELS_TIMED = 100     # experiment 2: neighbouring cancels timed at each position
STREAM_EVENTS = 50_000  # experiment 3: events per stream
VERSIONS = (("A", OrderBookA), ("B", OrderBookB))
BID, ASK = 1_000_000, 2_000_000      # far apart: nothing in these experiments ever trades


def limit(seq, order_id, side, price, qty=100):
    return {"event_id": f"e{seq}", "type": "LIMIT", "order_id": order_id, "side": side,
            "price_ticks": price, "qty_units": qty, "seq": seq}


def cancel(seq, target):
    return {"event_id": f"e{seq}", "type": "CANCEL", "target_order_id": target, "seq": seq}


def timed(cls, setup, events):
    """Median seconds over REPEATS for replaying `events` on a fresh book that has replayed `setup`."""
    samples = []
    for run in range(REPEATS + 1):               # run 0 is the warm-up
        book = cls()
        process = book.ProcessEvent
        for event in setup:
            process(event)
        start = time.perf_counter()
        for event in events:
            process(event)
        elapsed = time.perf_counter() - start
        if run:
            samples.append(elapsed)
        del book
    return statistics.median(samples)


def statuses(cls, setup, events):
    book = cls()
    for event in setup:
        book.ProcessEvent(event)
    return [book.ProcessEvent(event)["status"] for event in events]


# ---------------------------------------------------------------- 1. break-even depth
def churn_events(depth):
    """`depth` resting orders (half bids, half asks, one per price), then add+cancel pairs on top."""
    setup, seq = [], 0
    for i in range(depth):
        seq += 1
        if i % 2:
            setup.append(limit(seq, f"rest{i}", BUY, BID - i))
        else:
            setup.append(limit(seq, f"rest{i}", SELL, ASK + i))
    events = []
    for j in range(CHURN_CYCLES):
        side, price = (BUY, BID - j % 50) if j % 2 else (SELL, ASK + j % 50)
        events.append(limit(seq + 1, f"churn{j}", side, price))
        events.append(cancel(seq + 2, f"churn{j}"))
        seq += 2
    return setup, events


def experiment_1():
    rows = []
    print(f"{'resting orders':>15} {'A µs/event':>12} {'B µs/event':>12} {'B/A':>7}")
    for depth in BOOK_DEPTHS:
        setup, events = churn_events(depth)
        assert statuses(OrderBookA, setup, events) == statuses(OrderBookB, setup, events)
        a, b = (timed(cls, setup, events) / len(events) * 1e6 for _, cls in VERSIONS)
        rows.append({"resting_orders": depth, "a_us_per_event": a, "b_us_per_event": b, "b_over_a": b / a})
        print(f"{depth:>15,} {a:>12.2f} {b:>12.2f} {b / a:>7.2f}")
    return rows


# ---------------------------------------------------------------- 2. cancel position
def queue_events(length, position):
    """`length` bids at one price; then cancel CANCELS_TIMED neighbours at the given queue position."""
    setup = [limit(i + 1, f"q{i}", BUY, BID) for i in range(length)]
    count = min(CANCELS_TIMED, length)
    if position == "front":
        targets = range(count)
    elif position == "middle":
        targets = range(length // 2 - count // 2, length // 2 - count // 2 + count)
    else:
        targets = range(length - 1, length - 1 - count, -1)
    events = [cancel(length + 1 + n, f"q{i}") for n, i in enumerate(targets)]
    return setup, events


def experiment_2():
    rows = []
    print(f"{'queue length':>13} {'position':>9} {'A µs/cancel':>12} {'B µs/cancel':>12}")
    for length in QUEUE_LENGTHS:
        for position in ("front", "middle", "back"):
            setup, events = queue_events(length, position)
            assert set(statuses(OrderBookA, setup, events)) == set(statuses(OrderBookB, setup, events)) == {"cancelled"}
            a, b = (timed(cls, setup, events) / len(events) * 1e6 for _, cls in VERSIONS)
            rows.append({"queue_length": length, "position": position, "a_us_per_cancel": a, "b_us_per_cancel": b})
            print(f"{length:>13,} {position:>9} {a:>12.2f} {b:>12.2f}")
    return rows


# ---------------------------------------------------------------- 3. rejected events
def stream_with_rejects(share):
    """STREAM_EVENTS events; about `share` of them invalid (four kinds in turn), the rest add or cancel.

    Valid events keep roughly 50 orders resting, so both versions stay fast and comparable."""
    events, resting, seq, credit, bad_kind, n = [], [], 0, 0.0, 0, 0
    while len(events) < STREAM_EVENTS:
        credit += share
        if credit >= 1.0:
            credit -= 1.0
            bad_kind += 1
            if bad_kind % 4 == 0 and resting:    # order_id is already active
                events.append(limit(seq + 1, resting[-1], BUY, BID))
            elif bad_kind % 4 == 1:              # quantity zero
                events.append(limit(seq + 1, f"bad{bad_kind}", BUY, BID, qty=0))
            elif bad_kind % 4 == 2:              # arrival rank not increasing
                events.append(cancel(seq, "nobody"))
            else:                                # unknown event type
                events.append({"event_id": f"x{bad_kind}", "type": "AMEND", "seq": seq + 1})
            continue
        seq += 1
        if len(resting) >= 50:
            events.append(cancel(seq, resting.pop(0)))
        else:
            n += 1
            side, price = (BUY, BID - n % 20) if n % 2 else (SELL, ASK + n % 20)
            events.append(limit(seq, f"o{n}", side, price))
            resting.append(f"o{n}")
    return events


def experiment_3():
    rows = []
    print(f"{'share asked':>12} {'rejected':>9} {'A µs/event':>12} {'B µs/event':>12}")
    for share in REJECT_SHARES:
        events = stream_with_rejects(share)
        seen = statuses(OrderBookA, [], events)
        assert seen == statuses(OrderBookB, [], events)
        rejected = seen.count("rejected")
        a, b = (timed(cls, [], events) / len(events) * 1e6 for _, cls in VERSIONS)
        rows.append({"share_requested": share, "events": len(events), "rejected": rejected,
                     "a_us_per_event": a, "b_us_per_event": b})
        print(f"{share:>12.2f} {rejected:>9,} {a:>12.2f} {b:>12.2f}")
    return rows


EXPERIMENTS = {
    "1": ("break_even_depth", "BOOK_DEPTHS", experiment_1),
    "2": ("cancel_position", "QUEUE_LENGTHS", experiment_2),
    "3": ("rejected_events", "REJECT_SHARES", experiment_3),
}


def main(argv):
    chosen = argv or sorted(EXPERIMENTS)
    path = Path(__file__).parent / "results" / "experiments.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for key in chosen:
        name, parameter, run = EXPERIMENTS[key]
        if not globals()[parameter]:
            print(f"Experiment {key} ({name}): {parameter} is empty - choose the values at the top of this file.\n")
            continue
        print(f"Experiment {key}: {name}")
        saved[name] = {
            "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "python": platform.python_version(),
            "parameters": {parameter: globals()[parameter], "REPEATS": REPEATS, "CHURN_CYCLES": CHURN_CYCLES,
                           "CANCELS_TIMED": CANCELS_TIMED, "STREAM_EVENTS": STREAM_EVENTS},
            "rows": run(),
        }
        print()
        path.write_text(json.dumps(saved, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
