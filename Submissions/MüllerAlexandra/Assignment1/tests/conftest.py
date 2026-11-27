"""Shared fixtures apply the same behavioral contract to both versions."""

from collections.abc import Callable

import pytest

from limit_order_book import BaselineOrderBook, RevisedOrderBook
from limit_order_book.interface import OrderBook


BookFactory = Callable[[], OrderBook]


@pytest.fixture(
    params=[BaselineOrderBook, RevisedOrderBook],
    ids=["baseline", "revised"],
)
def book_factory(request: pytest.FixtureRequest) -> BookFactory:
    return request.param


@pytest.fixture
def book(book_factory: BookFactory) -> OrderBook:
    return book_factory()

