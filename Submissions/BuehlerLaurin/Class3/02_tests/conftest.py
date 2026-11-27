"""Run every contract test against every registered version."""
import inspect

import pytest

import contract
from amput import METHODS

# Fail loudly instead of skipping: no versions or no checks means no evidence.
if not METHODS:
    raise pytest.UsageError("amput.METHODS is empty: register at least one version "
                            "(a NotImplementedError stub is fine for the red run).")
if not [n for n, _ in inspect.getmembers(contract, inspect.isfunction) if n.startswith("check_")]:
    raise pytest.UsageError("02_tests/contract.py defines no check_* functions: nothing would be tested.")


@pytest.fixture(params=sorted(METHODS), ids=lambda k: "-".join(map(str, k)))
def impl(request):
    return METHODS[request.param]
