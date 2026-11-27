"""Seeded random event generators (own/attack) and the every-event comparison."""
import copy
import random

from oracle import Oracle

JUNK = [None, True, False, 0, -1, 1.0, 2.5, "5", "", " ", [], {}, (), float("nan"), float("inf")]
FIELDS = ["seq", "event_id", "type", "order_id", "side", "price_ticks", "qty_units",
          "target_order_id"]
REGIMES = ["narrow", "wide", "churn", "drift"]


def gen(seed, n, regime, junk=True):
    """narrow: 6 prices / 12 ids / tiny qty (ties, reuse, crosses, small id pool).
    wide:   prices up to 10**9, fresh ids, quantities up to 10**30, deep books.
    churn:  3 prices per side, cancel-heavy, long queues (lazy cleanup thresholds).
    drift:  the touch walks away, so emptied levels pile up and are revisited."""
    r = random.Random(f"{seed}-{regime}")
    out, seq, known = [], 0, []
    p_lim, p_mkt = {"narrow": (.62, .12), "wide": (.72, .08),
                    "churn": (.50, .02), "drift": (.52, .05)}[regime]
    for i in range(n):
        seq += r.choice([1, 1, 1, 2, 10])
        e = {"seq": seq, "event_id": f"e{i}"}
        x = r.random()
        if x < p_lim:
            if regime == "narrow":
                oid = f"o{r.randrange(12)}"
            elif regime in ("churn", "drift") and known and r.random() < .1:
                oid = r.choice(known)
            else:
                oid = f"w{r.randrange(10**9)}"
            side = r.choice(["BUY", "SELL"])
            if regime == "narrow":
                price, qty = r.randint(1, 6), r.randint(1, 4)
            elif regime == "wide":
                half = 5 * 10**8
                if r.random() < .5:
                    price = r.randint(1, 10**9)
                else:
                    price = r.randint(1, half) if side == "BUY" else r.randint(half, 10**9)
                qty = r.choice([1, 10**6, r.randint(1, 10**12), 10**30])
            elif regime == "churn":
                price = r.randint(98, 100) if side == "BUY" else r.randint(101, 103)
                if r.random() < .02:
                    price = r.randint(98, 103)
                qty = r.randint(1, 3)
            else:
                walk = 1000 + (i // 4) * (1 if seed % 2 else -1)
                price = max(1, walk + r.randint(-6, 6) * (1 if side == "SELL" else -1))
                qty = r.randint(1, 3)
            e.update(type="LIMIT", order_id=oid, side=side, price_ticks=price, qty_units=qty)
            known.append(oid)
        elif x < p_lim + p_mkt:
            big = [1, 2, 5, 10**6, 10**12] if regime == "wide" else [1, 2, 5, 20]
            e.update(type="MARKET_SELL", qty_units=r.choice(big),
                     order_id=f"m{i}" if r.random() < .9 else r.choice(known or ["m"]))
        else:
            target = r.choice(known[-60:]) if known and r.random() < .95 else f"x{i}"
            e.update(type="CANCEL", target_order_id=target)
        if junk:
            y = r.random()
            if y < .04:
                e[r.choice(FIELDS)] = copy.deepcopy(r.choice(JUNK))
            elif y < .06:
                e.pop(r.choice(FIELDS), None)
            elif y < .08:
                e["seq"] = max(1, seq - r.randint(0, 12))
            elif y < .09:
                e = copy.deepcopy(r.choice(JUNK))
        out.append(e)
    return out


DIRECT = ["AddLimitOrder", "FillMarketSell", "CancelOrder"]
BY_TYPE = {"LIMIT": DIRECT[0], "MARKET_SELL": DIRECT[1], "CANCEL": DIRECT[2]}


def compare(factory, events, direct_seed=None, inspect=True, scramble=False):
    """Return None, or (index, what, expected, actual) at the first difference."""
    o, b = Oracle(), factory()
    r = random.Random(direct_seed)
    for i, e in enumerate(events):
        m = "process"
        if direct_seed is not None and r.random() < .5:
            t = e.get("type") if isinstance(e, dict) else None
            m = BY_TYPE.get(t) if isinstance(t, str) else None
            if m is None or r.random() < .05:
                m = r.choice(DIRECT)
        mine = copy.deepcopy(e)
        before = repr(mine)
        want = o.call(m, copy.deepcopy(e))
        try:
            got = getattr(b, m)(mine)
        except Exception as ex:                                  # a crash is a finding
            return i, f"{m} raised", want, repr(ex)
        if repr(mine) != before:
            return i, "event mutated", before, repr(mine)
        if got != want or types(got) != types(want):
            return i, m, want, got
        if scramble:                                             # aliasing attack
            if isinstance(mine, dict):
                mine.clear()
            for f in got.get("fills", []):
                f.clear()
            got.clear()
        if inspect or i % 97 == 96 or i == len(events) - 1:
            for what in ("snapshot", "best_bid", "best_ask"):
                w, g = getattr(o, what)(), getattr(b, what)()
                if w != g or types(w) != types(g):
                    return i, what, w, g
                if scramble and what == "snapshot":
                    for d in g:
                        d.clear()
                    g.clear()
        if b.last_seq != o.last_seq:
            return i, "last_seq", o.last_seq, b.last_seq
    return None


def types(x):
    if isinstance(x, dict):
        return {k: types(v) for k, v in x.items()}
    if isinstance(x, list):
        return [types(v) for v in x]
    return type(x)


def shrink(factory, events, **kw):
    """Greedy delta debugging: a small subsequence that still differs."""
    ev, step = list(events), max(1, len(events) // 2)
    while step:
        i = 0
        while i < len(ev):
            cand = ev[:i] + ev[i + step:]
            if cand and compare(factory, cand, **kw) is not None:
                ev = cand
            else:
                i += step
        step //= 2
    return ev
