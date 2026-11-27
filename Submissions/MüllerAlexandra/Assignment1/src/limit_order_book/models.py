"""Internal value objects shared without sharing matching logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Side = Literal["BUY", "SELL"]


@dataclass
class RestingOrder:
    """One active individual order and its remaining quantity."""

    order_id: str
    side: Side
    price_ticks: int
    qty_units: int
    arrival_seq: int


@dataclass(frozen=True)
class Fill:
    """One execution between an incoming taker and a resting maker."""

    maker_id: str
    taker_id: str
    price_ticks: int
    qty_units: int

