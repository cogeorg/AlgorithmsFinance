"""Runs every check_* in 02_tests/contract.py against every version."""
import inspect

import pytest

import contract

CHECKS = [f for n, f in inspect.getmembers(contract, inspect.isfunction) if n.startswith("check_")]


@pytest.mark.parametrize("check", CHECKS, ids=lambda f: f.__name__)
def test_contract(impl, check):
    check(impl)
