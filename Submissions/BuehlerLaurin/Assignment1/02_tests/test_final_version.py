"""Final public alias and explicit historical variants, without measurements."""
from copy import deepcopy
import json

import pytest

import contract
from bench.core import make_book
from bench.sanity import VERSIONS as SANITY_VERSIONS
from lob import (METHODS, OrderBookA, OrderBookB, OrderBookB2, OrderBookB3,
                 OrderBookB3r, OrderBookB3rFast)
from lob.replay import read_events


VERSION_MAP = {
    'A': OrderBookA, 'B': OrderBookB3r, 'B1': OrderBookB,
    'B2': OrderBookB2, 'B3': OrderBookB3, 'B3r': OrderBookB3r,
    'B3r_fast': OrderBookB3rFast,
}


@pytest.mark.parametrize('version,expected', VERSION_MAP.items())
def test_final_registry_version_map(version, expected):
    assert METHODS.get(('lob', version)) is expected


@pytest.mark.parametrize('counted', [False, True])
@pytest.mark.parametrize('version,expected', VERSION_MAP.items())
def test_factory_preserves_explicit_version(version, expected, counted):
    if version == 'A' and counted:
        # The existing diagnostic A adapter intentionally subclasses A.
        assert isinstance(make_book(version, counted), expected)
    else:
        assert type(make_book(version, counted)) is expected


def test_sanity_uses_explicit_b1():
    assert dict(SANITY_VERSIONS)['B1'] == 'B1'


DATASETS = [('worked_example', contract.SUPPLIED / 'worked_example.jsonl')]
DATASETS += [(name, contract.OWN / f'{name}.jsonl') for name in contract.OWN_CASES]


@pytest.mark.parametrize('counted', [False, True])
@pytest.mark.parametrize('name,path', DATASETS, ids=[name for name, _ in DATASETS])
def test_final_b_matches_b3r_after_every_event(name, path, counted):
    alias = METHODS[('lob', 'B')](count_operations=counted)
    explicit = METHODS[('lob', 'B3r')](count_operations=counted)
    results = []
    for event in read_events(path):
        actual, expected = alias.process(deepcopy(event)), explicit.process(deepcopy(event))
        assert actual == expected, (name, event, actual, expected)
        assert list(actual) == list(expected), (name, event, 'result key order')
        assert alias.snapshot() == explicit.snapshot(), (name, event)
        assert alias.best_bid() == explicit.best_bid(), (name, event)
        assert alias.best_ask() == explicit.best_ask(), (name, event)
        if counted:
            assert alias.counters.as_dict() == explicit.counters.as_dict(), (name, event)
        results.append(actual)
    if name != 'worked_example':
        expected = json.loads(path.with_suffix('.expected.json').read_text(encoding='utf-8'))
        assert results == expected['results']
        assert alias.snapshot() == expected['final_book']
    else:
        expected = json.loads((contract.SUPPLIED / 'worked_expected.json').read_text(encoding='utf-8'))
        assert results[-1] == expected['market_sell_result']
