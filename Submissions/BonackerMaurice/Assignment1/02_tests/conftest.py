"""Shared pytest setup: every test that uses the `lob` fixture runs once per
order-book version listed here."""

import importlib

import pytest

VERSIONS = ["lob_a", "lob_b_sorted", "lob_b_heap"]


@pytest.fixture(params=VERSIONS)
def lob(request):
    """The order-book module under test (lob_a, later lob_b)."""
    return importlib.import_module(request.param)
