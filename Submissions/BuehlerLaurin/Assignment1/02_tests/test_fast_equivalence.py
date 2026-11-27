"""Mandatory G1/G2 gates; reference code and expected files remain unchanged."""
from copy import deepcopy
import inspect
from itertools import combinations, product
from pathlib import Path
import runpy

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import invariant
import pytest

from lob.book_b3r import OrderBookB3r
from lob.book_b3r_fast import OrderBookB3rFast, validate_fast
from lob.validation import validate
from lob.replay import read_events
from test_stateful import DifferentialMachine

ROOT = Path(__file__).resolve().parents[1]
ATTACK = runpy.run_path(str(ROOT/'07_attack/gen_attack.py'))
MISSING = object()


class IntSubclass(int):
    pass


class StringSubclass(str):
    pass


class DictSubclass(dict):
    pass


ODD = [True, False, 0, -1, 1.0, '5', None, [], {}, 10**40,
       IntSubclass(2), IntSubclass(0), IntSubclass(-1), '', StringSubclass('live'), MISSING]
BASES = [
    dict(seq=2, type='LIMIT', event_id='e', order_id='live', side='BUY', price_ticks=5, qty_units=3),
    dict(seq=2, type='MARKET_SELL', event_id='e', order_id='live', qty_units=3),
    dict(seq=2, type='CANCEL', event_id='e', target_order_id='live'),
]
FIELDS = ('seq','type','event_id','order_id','target_order_id','side','price_ticks','qty_units','comment')
EXPECTED = (None, 'LIMIT', 'MARKET_SELL', 'CANCEL', 'unknown', [], {}, StringSubclass('LIMIT'))


def validator_pair(event, last_seq, expected, live):
    calls_a, calls_b = [], []
    def is_live_a(oid):
        calls_a.append(oid)
        return live
    def is_live_b(oid):
        calls_b.append(oid)
        return live
    a = validate(event, last_seq, is_live_a, expected)
    b = validate_fast(event, last_seq, is_live_b, expected)
    assert a == b, (event, last_seq, expected, live, a, b)
    assert calls_a == calls_b, ('is_live invocation/order changed', event, calls_a, calls_b)


def mutated(base, changes):
    event = dict(base)
    for field, value in changes:
        if value is MISSING:
            event.pop(field, None)
        else:
            event[field] = value
    return event


def test_g1_exhaustive_validator_corpus():
    count = 0
    def check(event):
        nonlocal count
        for expected, last, live in product(EXPECTED, (0, 2, 10**40, IntSubclass(0)), (False, True)):
            validator_pair(event, last, expected, live)
            count += 1
    for base in BASES:
        check(base)
        check(DictSubclass(base))
        for field, value in product(FIELDS, ODD):
            check(mutated(base, [(field, value)]))
        # Every pair of fields, every combination of corpus values (including
        # valid-but-unusual and missing values): first failing rule must agree.
        for f1, f2 in combinations(FIELDS, 2):
            for v1, v2 in product(ODD, repeat=2):
                check(mutated(base, [(f1, v1), (f2, v2)]))
    for event in (None, [], (), 1, True, 'event', IntSubclass(2)):
        check(event)
    print(f'G1 exhaustive validator comparisons: {count}; callback traces identical')


JSON_VALUE = st.recursive(st.none() | st.booleans() | st.integers() |
    st.floats(allow_nan=False, allow_infinity=False) | st.text(),
    lambda child: st.lists(child, max_size=5) | st.dictionaries(st.text(), child, max_size=6), max_leaves=25)
JSON_EVENT = st.one_of(JSON_VALUE, st.dictionaries(st.sampled_from(FIELDS), JSON_VALUE, max_size=9))


@settings(max_examples=1500, deadline=None)
@given(event=JSON_EVENT, expected=JSON_VALUE, last=st.integers(min_value=0), live=st.booleans())
def test_g1_hypothesis_arbitrary_json(event, expected, last, live):
    validator_pair(event, last, expected, live)


def test_g1_callback_exception_is_not_swallowed_or_retried():
    for function in (validate, validate_fast):
        calls = []
        def is_live(oid):
            calls.append(oid)
            raise KeyError('callback failure, not a missing event field')
        with pytest.raises(KeyError):
            function(BASES[0], 0, is_live)
        assert calls == ['live'], 'callback must run once, including when it raises'


def compare_events(events, label, counted):
    a = OrderBookB3r(count_operations=counted)
    b = OrderBookB3rFast(count_operations=counted)
    count = 0
    for i, event in enumerate(events, 1):
        ra, rb = a.process(deepcopy(event)), b.process(deepcopy(event))
        assert ra == rb and list(ra) == list(rb), (label, i, event, ra, rb)
        for fa, fb in zip(ra.get('fills', ()), rb.get('fills', ())):
            assert list(fa) == list(fb), (label, i, 'fill key order')
        assert a.snapshot() == b.snapshot(), (label, i, event, 'snapshot')
        assert (a.best_bid(), a.best_ask()) == (b.best_bid(), b.best_ask()), (label, i, event, 'quotes')
        assert a.last_seq == b.last_seq
        if counted:
            assert a.counters.as_dict() == b.counters.as_dict(), (label, i, event, 'counters')
        count += 1
    print(f'G2 {label}, counted={counted}: {count} every-event comparisons')


SUPPLIED = sorted(p for p in (ROOT/'06_data/supplied').glob('*.jsonl*') if p.suffix in ('.jsonl', '.gz'))
assert len(SUPPLIED) == 6, 'five complete supplied streams and the worked example required'
OWN = sorted((ROOT/'06_data/own').glob('*.jsonl'))


@pytest.mark.parametrize('counted', [False, True])
@pytest.mark.parametrize('path', SUPPLIED+OWN, ids=lambda p: p.name)
def test_g2_all_supplied_and_own_every_event(path, counted):
    compare_events(read_events(path), path.name, counted)


ATTACK_NAMES = sorted(set(ATTACK['TIMED']) | {name for name, value in ATTACK.items()
    if inspect.isfunction(value) and name.startswith(('mem_', 'lat_'))})


def attack_events(name):
    if name in ATTACK['TIMED']:
        pre, events = ATTACK[name](96)
        return pre+events
    if name == 'mem_rotating_bursts':
        return ATTACK[name](12, 70, 24)
    return ATTACK[name](192)


@pytest.mark.parametrize('counted', [False, True])
@pytest.mark.parametrize('name', ATTACK_NAMES)
def test_g2_all_attack_stream_families(name, counted):
    compare_events(attack_events(name), name, counted)


class FastDifferential(DifferentialMachine):
    B_CLS = OrderBookB3rFast

    def __init__(self):
        super().__init__()
        self.a = OrderBookB3r(count_operations=True)
        self.b = OrderBookB3rFast(count_operations=True)

    @invariant()
    def counters_identical(self):
        assert self.a.counters.as_dict() == self.b.counters.as_dict()


TestFastDifferential = FastDifferential.TestCase
TestFastDifferential.settings = settings(max_examples=300, stateful_step_count=60, deadline=None)
