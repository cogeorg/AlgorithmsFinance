"""White-box attack streams (own/attack). Deterministic (no randomness unless seeded).

Each builder returns (prefill, attack): the prefill is replayed OUTSIDE timing, only the
attack part is timed. `n` scales both unless the docstring says otherwise.
BID-side streams; TOP is the supplied generator's best bid price.
"""
import random

TOP = 6_000_000
M61 = 2**61 - 1                       # CPython: hash(int) == int mod M61 for positive ints


class Stream:
    def __init__(self):
        self.seq = 0

    def add(self, oid, price, qty=1, side="BUY"):
        self.seq += 1
        return {"seq": self.seq, "event_id": f"e{self.seq}", "type": "LIMIT", "order_id": oid,
                "side": side, "price_ticks": price, "qty_units": qty}

    def sell(self, qty=1):
        self.seq += 1
        return {"seq": self.seq, "event_id": f"e{self.seq}", "type": "MARKET_SELL",
                "order_id": f"m{self.seq}", "qty_units": qty}

    def cancel(self, target):
        self.seq += 1
        return {"seq": self.seq, "event_id": f"e{self.seq}", "type": "CANCEL",
                "target_order_id": target}


# ------------------------------------------------------------------ throughput
def far_end_insert(n):
    """n bids, each one tick worse than all before: B1/B2 insert at index 0."""
    s = Stream()
    return [], [s.add(f"o{i}", TOP - i) for i in range(n)]


def far_end_cancel(n):
    """n levels; cancel from the worst price up: B1/B2 delete at index 0 every time."""
    s = Stream()
    pre = [s.add(f"o{i}", TOP + i) for i in range(n)]
    return pre, [s.cancel(f"o{i}") for i in range(n)]


def far_end_flicker(n):
    """n live levels stay; n rounds of add + cancel of ONE worst price (book size constant)."""
    s = Stream()
    pre = [s.add(f"o{i}", TOP + i) for i in range(n)]
    out = []
    for i in range(n):
        out += [s.add("x", TOP - 1), s.cancel("x")]
    return pre, out


def hash_full(n):
    """n bid levels at price k*(2**61-1): every price has hash 0. Ascending, so B1/B2 append."""
    s = Stream()
    return [], [s.add(f"o{i}", (i + 1) * M61) for i in range(n)]


def hash_control(n):
    """Same shape and big-int size as hash_full, but ordinary hashes (+i)."""
    s = Stream()
    return [], [s.add(f"o{i}", (i + 1) * M61 + i * 7919 + 1) for i in range(n)]


def hash_lowbits(n):
    """Catalogue attack: multiples of 2**20 (same low bits, different hashes)."""
    s = Stream()
    return [], [s.add(f"o{i}", (i + 1) << 20) for i in range(n)]


def dense_control(n):
    s = Stream()
    return [], [s.add(f"o{i}", i + 1) for i in range(n)]


def hash_match(n):
    """n colliding levels resting; then n/4 rounds of add+sell at the colliding best price."""
    s = Stream()
    pre = [s.add(f"o{i}", (i + 1) * M61) for i in range(n)]
    out = []
    for i in range(n // 4):
        out += [s.add("x", (n + 5) * M61), s.sell(1)]
    return pre, out


def touch_churn(n):
    """n deep levels; n rounds: new best level, one market sell empties it (B3 push + pop)."""
    s = Stream()
    pre = [s.add(f"o{i}", TOP - n + i) for i in range(n)]
    out = []
    for i in range(n):
        out += [s.add(f"x{i}", TOP + 1 + i % 2), s.sell(1)]
    return pre, out


def improve_cancel_purge(n):
    """n ever-better bids (full heap sift-up each), all cancelled, then one sell purges all."""
    s = Stream()
    out = [s.add("keep", 1)] + [s.add(f"o{i}", TOP + i) for i in range(n)]
    out += [s.cancel(f"o{i}") for i in range(n)] + [s.sell(1)]
    return [], out


def root_recreate(n):
    """One best level emptied and recreated at the heap root n times above n deep levels."""
    s = Stream()
    pre = [s.add(f"o{i}", TOP - n + i) for i in range(n)]
    out = []
    for i in range(n):
        out += [s.add("x", TOP + 1), s.cancel("x")]
    return pre, out


def compaction_thrash(n):
    """One level held at 33 live; cancel the oldest, add a new one, n rounds."""
    s = Stream()
    pre = [s.add(f"o{i}", TOP) for i in range(33)]
    out = []
    for i in range(n):
        out += [s.cancel(f"o{i}"), s.add(f"o{33 + i}", TOP)]
    return pre, out


def drift_churn(n):
    """Best bid stays; n rounds add + cancel at ever-worse prices (stale keys never reach the root)."""
    s = Stream()
    pre = [s.add("keep", TOP)]
    out = []
    for i in range(n):
        out += [s.add("x", TOP - 1 - i), s.cancel("x")]
    return pre, out


def flicker_set(n):
    """Aimed at B3r: one live level and 2 alternating prices, 2n events. B3 reuses its two keys
    for ever (no push); B3r rebuilds every second cancel and must push again."""
    s = Stream()
    pre = [s.add("keep", TOP)]
    out = []
    for i in range(n):
        out += [s.add("x", TOP - 1 - i % 2), s.cancel("x")]
    return pre, out


def amortized_rebuild(n):
    """Aimed at B3r: n live levels, 2n add+cancel at distinct worse prices (a rebuild of size n
    after every n+1 removals: should amortize to O(1))."""
    s = Stream()
    pre = [s.add(f"o{i}", TOP + i) for i in range(n)]
    out = []
    for i in range(2 * n):
        out += [s.add("x", TOP - 1 - i), s.cancel("x")]
    return pre, out


def dead_slot_rebuild(n):
    """Aimed at B3r: n levels existed once, all but one cancelled (untimed). The levels dict keeps
    its dead slots. Then n/2 add+cancel at distinct worse prices: a rebuild after every second
    cancel. A rebuild that iterates the dict walks O(n) dead slots for ONE live level.
    n should sit just above a dict resize (2**m * 2/3) so that the table does not shrink."""
    s = Stream()
    pre = [s.add("keep", TOP + 2 * n)] + [s.add(f"o{i}", TOP + i) for i in range(n - 1)]
    pre += [s.cancel(f"o{i}") for i in range(n - 1)]
    out = []
    for i in range(n // 2):
        out += [s.add("x", TOP - 1 - i), s.cancel("x")]
    return pre, out


def two_side_thrash(n):
    """Aimed at a B3r that counts both sides: n live asks and one live bid; n + 1 stale bid keys
    (stale == live, no rebuild). Then every ask cancel crosses the total threshold, but a rebuild
    of the ask side cannot remove the stale BID keys: O(n) rebuild per cancel."""
    s = Stream()
    pre = [s.add(f"a{i}", TOP + 10 + i, 1, "SELL") for i in range(n)] + [s.add("keep", TOP)]
    for i in range(n + 1):
        pre += [s.add("x", TOP - 1 - i), s.cancel("x")]
    out = []
    for i in range(n):
        out += [s.add("y", TOP + 10 + n + i, 1, "SELL"), s.cancel("y")]
    return pre, out


# ---------------------------------------------------------------- single events
def spike_purge(n):
    """1 live worst level under n cancelled better ones; ONE market sell."""
    s = Stream()
    pre = [s.add("keep", 1)] + [s.add(f"o{i}", TOP + i) for i in range(n)]
    pre += [s.cancel(f"o{i}") for i in range(n)]
    return pre, [s.sell(1)]


def spike_purge_at_threshold(n):
    """n live levels under n cancelled better ones: stale == live, so B3r does not rebuild;
    ONE market sell pops them all."""
    s = Stream()
    pre = [s.add(f"k{i}", TOP - n + i, 2) for i in range(n)]
    pre += [s.add(f"o{i}", TOP + i) for i in range(n)]
    pre += [s.cancel(f"o{i}") for i in range(n)]
    return pre, [s.sell(1)]


def spike_rebuild(n):
    """n live levels, n stale keys strictly worse than the best; the next cancel crosses
    stale > live: ONE cancel pays the B3r rebuild."""
    s = Stream()
    pre = [s.add(f"k{i}", TOP + i) for i in range(n)]
    pre += [s.add(f"o{i}", TOP - 1 - i) for i in range(n + 1)]
    pre += [s.cancel(f"o{i}") for i in range(n)]
    return pre, [s.cancel(f"o{n}")]


def spike_compaction(n):
    """One level, n live + n dead behind a live head; the next cancel compacts 2n records."""
    s = Stream()
    pre = [s.add(f"o{i}", TOP) for i in range(2 * n)]
    pre += [s.cancel(f"o{i}") for i in range(1, n + 1)]
    return pre, [s.cancel(f"o{n + 1}")]


def spike_head_skip(n):
    """One level, n dead heads in front of n live orders; ONE unit market sell skips them all."""
    s = Stream()
    pre = [s.add(f"o{i}", TOP, 2) for i in range(2 * n)]
    pre += [s.cancel(f"o{i}") for i in range(n)]
    return pre, [s.sell(1)]


def spike_sweep(n):
    """One market sell that fills n makers on n levels (F = n: result construction)."""
    s = Stream()
    pre = [s.add(f"o{i}", TOP + i) for i in range(n)]
    return pre, [s.sell(n)]


# ------------------------------------------------------- memory streams (no prefill)
def mem_rotating_bursts(levels, burst, rounds=None):
    """`levels` levels with one resting order each; then at level 0,1,2,... a burst of `burst`
    orders is added and cancelled again. Live orders never exceed levels + burst."""
    s = Stream()
    for j in range(levels):
        yield s.add(f"k{j}", TOP + j)
    for j in range(rounds if rounds is not None else levels):
        for i in range(burst):
            yield s.add(f"x{i}", TOP + j % levels)
        for i in range(burst):
            yield s.cancel(f"x{i}")


def mem_pinned_dead(levels, dead=32):
    """`levels` levels: one live order at the head and `dead` cancelled ones behind it."""
    s = Stream()
    for j in range(levels):
        yield s.add(f"k{j}", TOP + j)
    for d in range(dead):
        for j in range(levels):
            yield s.add(f"pinned-dead-record-{d}-{j}", TOP + j)
            yield s.cancel(f"pinned-dead-record-{d}-{j}")


def mem_drift(rounds):
    s = Stream()                       # lazy: the input must not be part of the traced bytes
    yield s.add("keep", TOP)
    for i in range(rounds):
        yield s.add("x", TOP - 1 - i)
        yield s.cancel("x")


def mem_peak_then_empty(n):
    """n levels at once, then everything cancelled except one."""
    s = Stream()
    for i in range(n):
        yield s.add(f"o{i}", TOP + i)
    for i in range(1, n):
        yield s.cancel(f"o{i}")


def mem_deep(n):
    s = Stream()
    for i in range(n):
        yield s.add(f"o{i}", TOP + i)


def mem_crowded(n):
    s = Stream()
    for i in range(n):
        yield s.add(f"o{i}", TOP + i % 4)


# -------------------------------------------------------------- latency streams
def lat_normal(n, seed=42):
    """Comparison stream: 60 % limits on 200 price levels per side, 30 % cancels, 10 % sells."""
    r, s, out, known = random.Random(seed), Stream(), [], []
    for i in range(n):
        x = r.random()
        if x < .6 or not known:
            known.append(f"o{i}")
            if r.random() < .5:
                out.append(s.add(f"o{i}", TOP - r.randrange(200), r.randint(1, 9)))
            else:
                out.append(s.add(f"o{i}", TOP + 1 + r.randrange(200), r.randint(1, 9), "SELL"))
        elif x < .9:
            out.append(s.cancel(known.pop(r.randrange(len(known)))))
        else:
            out.append(s.sell(r.randint(1, 20)))
    return out


def lat_growing(n):
    """n resting orders on 1000 levels: no cancels, no matches (dict growth + GC only)."""
    s = Stream()
    return [s.add(f"o{i}", TOP + i % 1000) for i in range(n)]


def lat_rolling(n):
    """One level held at n/4 live orders: add one at the tail, sell one at the head."""
    s = Stream()
    k = n // 4
    out = [s.add(f"o{i}", TOP) for i in range(k)]
    while len(out) < n:
        out += [s.add(f"p{s.seq}", TOP), s.sell(1)]
    return out[:n]


TIMED = {f.__name__: f for f in (
    far_end_insert, far_end_cancel, far_end_flicker, hash_full, hash_control, hash_lowbits,
    dense_control, hash_match, touch_churn, improve_cancel_purge, root_recreate,
    compaction_thrash, drift_churn, flicker_set, amortized_rebuild, dead_slot_rebuild,
    two_side_thrash,
    spike_purge, spike_purge_at_threshold, spike_rebuild, spike_compaction, spike_head_skip,
    spike_sweep)}
