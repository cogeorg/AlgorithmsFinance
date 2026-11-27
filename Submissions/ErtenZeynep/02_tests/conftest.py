"""Shared pytest configuration for the laboratory test suite."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import importlib
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "01_source"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


SearchFunction = Callable[[Sequence[int], Sequence[int]], list[bool]]

ALGORITHM_TARGETS = (
    (
        "linear_search",
        "algorithms_finance.algorithms.algorithm_01_linear_search",
        "linear_search",
    ),
    (
        "binary_search_recursive",
        "algorithms_finance.algorithms.algorithm_02_binary_search_recursive",
        "binary_search_recursive",
    ),
    (
        "binary_search_iterative",
        "algorithms_finance.algorithms.algorithm_03_binary_search_iterative",
        "binary_search_iterative",
    ),
    (
        "hash_set_membership",
        "algorithms_finance.algorithms.algorithm_04_hash_set_membership",
        "hash_set_membership",
    ),
)


@pytest.fixture(params=ALGORITHM_TARGETS, ids=lambda target: target[0])
def algorithm(request: pytest.FixtureRequest) -> SearchFunction:
    """Load every required implementation without skipping missing targets."""

    display_name, module_name, function_name = request.param
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(
            f"Required algorithm module for {display_name!r} is missing: "
            f"{module_name}"
        ) from error

    try:
        function = getattr(module, function_name)
    except AttributeError as error:
        raise AttributeError(
            f"Required function {function_name!r} is missing from {module_name}"
        ) from error

    if not callable(function):
        raise TypeError(f"{module_name}.{function_name} must be callable")
    return function
