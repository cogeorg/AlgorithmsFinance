"""Step 1: spec-blind correctness attack. Expected results come from SPEC.md (rule
numbers cited) or from oracle.py; every test runs against every registered version.
Run from the exercise root:  python -B -m pytest -p no:cacheprovider 07_attack -q
"""
import copy
import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "01_code"), str(ROOT / "07_attack")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fuzz import REGIMES, compare, gen, shrink  # noqa: E402
from lob import METHODS  # noqa: E402
from oracle import Oracle  # noqa: E402

VERSIONS = {k[1]: f for k, f in METHODS.items()}  # B is final B3r; B1 stays explicit.


@pytest.fixture(params=list(VERSIONS))
def factory(request):
    return VERSIONS[request.param]


def L(seq, oid, side, p, q, **kw):
    return {"seq": seq, "event_id": f"e{seq}", "type": "LIMIT", "order_id": oid, "side": side,
            "price_ticks": p, "qty_units": q, **kw}


def S(seq, oid, q, **kw):
    return {"seq": seq, "event_id": f"e{seq}", "type": "MARKET_SELL", "order_id": oid,
            "qty_units": q, **kw}


def C(seq, t, **kw):
    return {"seq": seq, "event_id": f"e{seq}", "type": "CANCEL", "target_order_id": t, **kw}


def check(factory, events, **kw):
    d = compare(factory, events, **kw)
    assert d is None, f"event {d[0]} {d[1]}\n expected {d[2]}\n actual   {d[3]}"


def test_versions_present():
    assert set(VERSIONS) >= {"A", "B", "B1", "B2", "B3", "B3r", "B3r_fast"}


@pytest.mark.parametrize('version', list(VERSIONS))
def test_measure_factory_preserves_explicit_versions(version):
    from measure import make
    assert type(make(version)) is VERSIONS[version]


# ---------------------------------------------------------------- input domain
BASE = {"LIMIT": L(10, "n", "BUY", 5, 5), "MARKET_SELL": S(10, "n", 1), "CANCEL": C(10, "b1")}
MISSING = "<missing>"
VALUES = [None, True, False, 0, -1, 1, 1.0, 5.5, "5", "", " ", "\t", "\x00", "É",
          "\U0001f642", "\ud800", "x" * 100_000, "b1", "B1", "BUY", "buy", "SELL", "LIMIT",
          "limit", "LIMIT ", "MARKET_BUY", 10**30, -10**30, 2**63, 2**64, [], [1], {},
          {"a": 1}, (), b"LIMIT", float("nan"), float("inf"), complex(1, 0), MISSING]
FIELDS = ["seq", "event_id", "type", "order_id", "side", "price_ticks", "qty_units",
          "target_order_id"]
PRE = [L(1, "b1", "BUY", 5, 3), L(2, "a1", "SELL", 9, 3), L(3, "dead", "BUY", 4, 1), C(4, "dead")]


def put(e, f, v):
    if isinstance(v, str) and v == MISSING:
        e.pop(f, None)
    else:
        e[f] = copy.deepcopy(v)


@pytest.mark.parametrize("method", ["process", "AddLimitOrder", "FillMarketSell", "CancelOrder"])
def test_every_field_times_every_odd_value(factory, method):
    """SPEC rules 1-13. Each odd value in each field; a rejected event must leave book and
    last_seq unchanged, so the same seq is usable afterwards."""
    for base in BASE.values():
        for f in FIELDS:
            for v in VALUES:
                o, b = Oracle(), factory()
                for e in PRE:
                    o.process(e), b.process(e)
                e = copy.deepcopy(base)
                put(e, f, v)
                want, got = o.call(method, copy.deepcopy(e)), getattr(b, method)(e)
                assert got == want and {k: type(x) for k, x in got.items()} == {
                    k: type(x) for k, x in want.items()}, (method, f, repr(v)[:40], want, got)
                assert b.snapshot() == o.snapshot() and b.last_seq == o.last_seq
                assert (b.best_bid(), b.best_ask()) == (o.best_bid(), o.best_ask())
                follow = S(10 if want["status"] == "rejected" else o.last_seq + 1, "f", 2)
                assert b.process(follow) == o.process(follow), (method, f, repr(v)[:40])


@pytest.mark.parametrize("f2", FIELDS)
def test_two_bad_fields_first_rule_wins(factory, f2):
    bad = [None, True, 0, "", "??", [], MISSING]
    for base in BASE.values():
        for f1 in FIELDS:
            for v1 in bad:
                for v2 in bad:
                    e = copy.deepcopy(base)
                    put(e, f1, v1)
                    put(e, f2, v2)
                    o, b = Oracle(), factory()
                    assert b.process(e) == o.process(copy.deepcopy(e)), e


@pytest.mark.parametrize("e", [None, 1, "x", [], (), [["seq", 1]], True, 1.0, set(), object()],
                         ids=lambda x: type(x).__name__)
def test_not_an_object(factory, e):
    for m in ("process", "AddLimitOrder", "FillMarketSell", "CancelOrder"):
        b = factory()
        assert getattr(b, m)(e) == {"event_id": None, "status": "rejected",
                                    "reason": "not_an_object"}
        assert b.snapshot() == [] and b.last_seq == 0


def test_id_collisions(factory):
    """event_id == order_id == target; market id == former maker id; keywords as ids."""
    ev = [L(1, "e1", "BUY", 5, 5), {**L(2, "LIMIT", "SELL", 6, 5), "event_id": "e1"},
          S(3, "BUY", 2), C(4, "BUY"), C(5, "e3"), L(6, "BUY", "BUY", 5, 1), S(7, "e1", 1),
          S(8, "z", 3), S(9, "e1", 1), C(10, "e1"), L(11, "e1", "BUY", 1, 1),
          C(12, "LIMIT"), C(13, "LIMIT")]
    check(factory, ev)


def test_seq_boundaries(factory):
    ev = [L(2**63, "a", "BUY", 5, 5), L(2**63, "b", "BUY", 5, 5), L(2**63 - 1, "b", "BUY", 5, 5),
          L(10**40, "b", "BUY", 0, 5), L(10**40, "b", "BUY", 5, 5),
          L(10**40 + 1, "a", "BUY", 5, 5), L(10**40 + 1, "c", "BUY", 5, 5),
          C(10**41, "nope"), C(10**41, "a"), C(10**41 + 1, "a")]
    check(factory, ev)


# ------------------------------------------------------------- state sequences
def test_empty_book_everything(factory):
    check(factory, [S(1, "s", 1), C(2, "s"), S(3, "s", 10**30), L(4, "a", "SELL", 1, 1),
                    S(5, "s", 1), C(6, "a"), L(7, "b", "BUY", 1, 1), S(8, "s", 1), S(9, "s", 1)])


@pytest.mark.parametrize("side", ["BUY", "SELL"])
@pytest.mark.parametrize("limit", [4, 5, 6, 7, 8])
@pytest.mark.parametrize("qty", [1, 5, 6, 7, 11, 12, 13, 99])
def test_exact_price_and_depth_boundaries(factory, side, limit, qty):
    """Rule 1 (>= / <=): 6 units at each of two prices; one tick / one unit around each edge."""
    opp = "SELL" if side == "BUY" else "BUY"
    ev = [L(1, "z9", opp, 5, 2), L(2, "a1", opp, 5, 4), L(3, "z8", opp, 7, 6),
          L(4, "t", side, limit, qty), L(5, "u", opp, 6, 1), C(6, "a1"), S(7, "m", 3), C(8, "t")]
    check(factory, ev)


@pytest.mark.parametrize("side", ["BUY", "SELL"])
@pytest.mark.parametrize("pos", range(5))
@pytest.mark.parametrize("used", range(11))
def test_cancel_at_every_position_after_partial(factory, side, pos, used):
    opp = "SELL" if side == "BUY" else "BUY"
    ev = [L(i + 1, f"o{9 - i}", side, 5, 2) for i in range(5)]
    if used:
        ev.append(L(6, "t", opp, 5, used))
    ev += [C(7, f"o{9 - pos}"), C(8, f"o{9 - pos}"), L(9, f"o{9 - pos}", side, 5, 3),
           L(10, "t2", opp, 5, 4), L(11, "t3", opp, 5, 40)]
    check(factory, ev)


@pytest.mark.parametrize("n,c", [(33, 32), (34, 33), (66, 32), (66, 33), (66, 34), (64, 32),
                                 (65, 33), (200, 100), (200, 101), (200, 199), (200, 200)])
@pytest.mark.parametrize("where", ["head", "tail", "middle", "alternate"])
def test_cancel_many_then_reuse_ids(factory, n, c, where):
    """Catalogue 'lazy structures': thresholds (n, n+1), the same ids re-used at the same key
    while dead records may still be stored, then a full sweep and recreation of the level."""
    ids = [f"k{i}" for i in range(n)]
    mid = (n - c) // 2
    pick = {"head": ids[:c], "tail": ids[-c:], "middle": ids[mid:mid + c],
            "alternate": (ids[::2] + ids[1::2])[:c]}[where]
    ev = [L(i + 1, o, "BUY", 5, 1 + i % 3) for i, o in enumerate(ids)]
    q = len(ev)
    for o in pick:
        q += 1
        ev.append(C(q, o))
    for o in pick[::-1]:
        q += 1
        ev.append(L(q, o, "BUY", 5, 2))
    ev += [S(q + 1, "m1", 3), S(q + 2, "m2", n), C(q + 3, pick[-1]), S(q + 4, "m3", 10 * n),
           L(q + 5, pick[0], "BUY", 5, 1), S(q + 6, "m4", 1), S(q + 7, "m5", 1)]
    check(factory, ev, inspect=False)
    check(factory, ev)


def test_same_id_cancel_readd_200_times(factory):
    ev, q = [L(1, "keep", "BUY", 5, 1)], 1
    for i in range(200):
        ev += [L(q + 1, "x", "BUY", 5, i + 1), C(q + 2, "x")]
        q += 2
    ev += [L(q + 1, "x", "BUY", 5, 7), S(q + 2, "m", 4), S(q + 3, "n", 9)]
    check(factory, ev, inspect=False)


def test_level_emptied_and_recreated_with_and_without_quotes(factory):
    ev, q = [], 0
    for i in range(60):
        p = 100 + (i % 3)
        out = C(q + 2, f"a{i}") if i % 2 else S(q + 2, f"s{i}", 1)
        ev += [L(q + 1, f"a{i}", "BUY", p, 1), out, L(q + 3, f"b{i}", "SELL", p, 1),
               L(q + 4, f"c{i}", "BUY", p - (i % 2), 1), C(q + 5, f"b{i}"),
               L(q + 6, f"d{i}", "SELL", p - 1, 1)]
        q += 6
    for mode in (True, False):
        check(factory, ev, inspect=mode)


def test_limit_crosses_many_levels_and_rests(factory):
    ev = [L(i + 1, f"a{i}", "SELL", 100 + i, 2) for i in range(50)]
    ev += [L(51, "t", "BUY", 124, 1000), L(52, "u", "SELL", 124, 3),
           L(53, "v", "SELL", 1, 5000), S(54, "m", 1)]
    check(factory, ev)


def test_huge_prices_and_quantities(factory):
    ev = [L(1, "a", "BUY", 10**30, 10**40), L(2, "b", "BUY", 10**30 + 1, 1),
          L(3, "c", "SELL", 10**31, 10**50), S(4, "m", 10**40),
          L(5, "d", "BUY", 10**32, 10**50 + 1), S(6, "n", 10**60)]
    check(factory, ev)


def test_returned_objects_and_events_are_not_aliases(factory):
    for seed in range(20):
        check(factory, gen(seed, 200, "narrow"), scramble=True)


def test_two_books_are_independent(factory):
    b1, b2 = factory(), factory()
    b1.process(L(1, "a", "BUY", 5, 5))
    assert b2.snapshot() == [] and b2.best_bid() is None
    assert b2.process(S(1, "m", 1))["status"] == "unfilled"


def test_failed_direct_call_then_right_call_same_seq(factory):
    b = factory()
    e = L(1, "a", "BUY", 5, 5)
    assert b.CancelOrder(e)["reason"] == "wrong_type_for_method"
    assert b.FillMarketSell(e)["reason"] == "wrong_type_for_method"
    assert b.AddLimitOrder(e)["status"] == "resting"


# --------------------------------------------------------- differential fuzzing
@pytest.mark.parametrize("regime", REGIMES)
@pytest.mark.parametrize("mode", ["every", "sparse", "direct"])
def test_fuzz(factory, regime, mode):
    kw = {"every": {}, "sparse": {"inspect": False}, "direct": {"direct_seed": 7}}[mode]
    for seed in range(15):
        ev = gen(seed, 250, regime)
        if compare(factory, ev, **kw):
            small = shrink(factory, ev, **kw)
            pytest.fail(f"seed {seed}: {compare(factory, small, **kw)}\n"
                        f"{json.dumps(small, default=repr)}")


# ------------------------------------------------------------------- replay CLI
def replay(tmp_path, raw, version="B1", name="x.jsonl"):
    f = tmp_path / name
    f.write_bytes(gzip.compress(raw) if name.endswith(".gz") else raw)
    return subprocess.run([sys.executable, "-B", str(ROOT / "run.py"), "lob.replay", str(f),
                           "--version", version], capture_output=True, text=True,
                          encoding="utf-8", cwd=ROOT, timeout=60)


def want_lines(lines):
    o = Oracle()
    return [o.process(json.loads(x)) for x in lines]


@pytest.mark.parametrize("version", list(VERSIONS))
@pytest.mark.parametrize("name", ["x.jsonl", "x.jsonl.gz"])
def test_replay_cli_matches_oracle(tmp_path, version, name):
    lines = [json.dumps(e) for e in gen(3, 200, "narrow")]
    p = replay(tmp_path, ("\n".join(lines) + "\n").encode(), version, name)
    assert p.returncode == 0, p.stderr
    assert [json.loads(x) for x in p.stdout.splitlines()] == want_lines(lines)


@pytest.mark.parametrize("version", list(VERSIONS))
def test_replay_cli_non_objects_unicode_crlf_no_final_newline(tmp_path, version):
    lines = ["[1, 2]", "null", "3", '"x"',
             json.dumps(L(1, "é\U0001f642", "BUY", 5, 5), ensure_ascii=False),
             json.dumps(L(2, "\ud800", "BUY", 5, 5)), json.dumps(S(3, "m", 7))]
    p = replay(tmp_path, "\r\n".join(lines).encode("utf-8"), version)
    assert p.returncode == 0, p.stderr
    assert [json.loads(x) for x in p.stdout.splitlines()] == want_lines(lines)


@pytest.mark.parametrize("version", list(VERSIONS))
def test_replay_cli_empty_file(tmp_path, version):
    p = replay(tmp_path, b"", version)
    assert p.returncode == 0 and p.stdout.strip() == ""


# ------------------------------------------------------------ reproduced breaks
@pytest.mark.xfail(strict=True, reason="ATK-01: json.loads int limit (4300 digits) aborts replay")
@pytest.mark.parametrize("version", list(VERSIONS))
def test_atk01_replay_cli_accepts_unbounded_positive_int(tmp_path, version):
    """SPEC 'Input domain': qty_units is a positive int, no upper bound (rule 12); replay prints
    one result per event. Expected: 3 results, all resting. Actual: ValueError after event 1."""
    lines = [json.dumps(L(1, "a", "BUY", 5, 1)),
             json.dumps(L(2, "b", "BUY", 5, 1)).replace('"qty_units": 1', '"qty_units": ' + "9" * 4301),
             json.dumps(L(3, "c", "BUY", 5, 1))]
    p = replay(tmp_path, "\n".join(lines).encode(), version)
    assert p.returncode == 0 and len(p.stdout.splitlines()) == 3


# The tests below PASS: they pin the operation counts that cause the performance breaks.
def feed(book, events):
    for e in events:
        book.process(e)
    return book


def test_atkp1_b1_shifts_two_references_per_live_level_per_flicker():
    import gen_attack
    n = 500
    pre, out = gen_attack.far_end_flicker(n)
    b = feed(VERSIONS["B1"](count_operations=True), pre)
    before = b.counters.price_list_shifts
    feed(b, out)
    assert b.counters.price_list_shifts - before == 2 * n * n


def test_atkp2_all_attack_prices_share_one_hash():
    import gen_attack
    _, out = gen_attack.hash_full(1000)
    assert {hash(e["price_ticks"]) for e in out} == {0} == {hash(-e["price_ticks"]) for e in out}


def test_atkp3_b3_one_sell_pops_every_stale_key():
    import gen_attack
    pre, out = gen_attack.spike_purge_at_threshold(500)
    b = feed(VERSIONS["B3"](count_operations=True), pre)
    assert len(b.bids.heap) == 1000 and len(b.bids.levels) == 500
    before = b.counters.heap_stale_pops
    b.process(out[0])
    assert b.counters.heap_stale_pops - before == 500


def test_atkp4_b3_stale_keys_grow_with_events():
    import gen_attack
    b = feed(VERSIONS["B3"](), list(gen_attack.mem_drift(3000)))
    assert len(b.orders) == 1 and len(b.bids.heap) == 3001


def test_atkp5_b2_level_with_one_order_keeps_burst_capacity():
    import gen_attack
    b = feed(VERSIONS["B2"](), gen_attack.mem_rotating_bursts(4, 2000))
    fresh = feed(VERSIONS["B2"](), [L(1, "k", "BUY", 5, 1)])
    small = sys.getsizeof(next(iter(fresh.bids.levels.values())).queue)
    assert len(b.orders) == 4
    assert all(sys.getsizeof(v.queue) > 50 * small for v in b.bids.levels.values())


def test_atkp6_b1_b3_keep_32_dead_records_per_live_order():
    import gen_attack
    for v in ("B1", "B3"):
        b = feed(VERSIONS[v](), gen_attack.mem_pinned_dead(20))
        assert len(b.orders) == 20 and sum(len(x.queue) for x in b.bids.levels.values()) == 33 * 20
