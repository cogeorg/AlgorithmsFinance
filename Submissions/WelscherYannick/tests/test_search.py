"""Run every contract check against every method of every registered version."""

import pytest
from contract import ALL_CHECKS, oracle
from datagen import GenSettings, generate
from registry import VERSIONS

CASES = [
    (f"{version}-{name}", method)
    for version, methods in VERSIONS.items()
    for name, method in methods.items()
]


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda c: c.__name__)
@pytest.mark.parametrize("label,method", CASES, ids=[label for label, _ in CASES])
def test_contract(label, method, check):
    check(method)


@pytest.mark.parametrize("version", list(VERSIONS))
def test_methods_agree_with_each_other(version):
    methods = VERSIONS[version]
    ids, queries = generate(GenSettings(n=1000, q=100, hit_rate=0.5, duplicate_rate=0.3, seed=7))
    expected = oracle(ids, queries)
    for name, method in methods.items():
        assert method.contains_all(ids, queries) == expected, name
