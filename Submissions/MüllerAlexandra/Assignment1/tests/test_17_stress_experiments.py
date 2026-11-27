"""Liquidation and diagnostics preserve fresh state and explicit counts."""

from __future__ import annotations

from collections.abc import Iterator
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys

from limit_order_book.baseline import BaselineOrderBook
from limit_order_book.stress_experiments import (
    build_liquidation_events,
    diagnose_replay,
    liquidation_quantities,
    measure_liquidation_scenarios,
    measure_liquidation_sale_memory,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRESS_SCRIPT = PROJECT_ROOT / "scripts" / "08_run_stress.py"


def test_liquidation_quantities_round_ten_percent_up() -> None:
    assert liquidation_quantities(7) == {
        "10_percent": 1,
        "100_percent": 7,
        "200_percent": 14,
    }


def test_liquidation_rebuilds_identical_book_for_every_repeat() -> None:
    events = build_liquidation_events(
        order_count=4,
        price_levels=2,
        base_price_ticks=1_000,
        quantity_cycle=(1, 2, 3),
    )
    books: list[BaselineOrderBook] = []
    clock_values: Iterator[float] = iter(float(value) for value in range(24))

    def factory() -> BaselineOrderBook:
        book = BaselineOrderBook()
        books.append(book)
        return book

    measurement = measure_liquidation_scenarios(
        factory,
        events,
        warmups=1,
        repeats=2,
        clock=lambda: next(clock_values),
    )

    assert measurement["available_qty_units"] == 7
    assert len(books) == 9
    assert len(measurement["records"]) == 6
    assert all(record["construction_seconds"] == 1.0 for record in measurement["records"])
    assert all(record["sale_seconds"] == 1.0 for record in measurement["records"])

    by_size = {
        record["sale_size"]: record
        for record in measurement["records"]
        if record["repeat"] == 1
    }
    assert (
        by_size["10_percent"]["requested_qty_units"],
        by_size["10_percent"]["executed_qty_units"],
        by_size["10_percent"]["unfilled_qty_units"],
        by_size["10_percent"]["makers_touched"],
        by_size["10_percent"]["price_levels_visited"],
    ) == (1, 1, 0, 1, 1)
    assert (
        by_size["100_percent"]["requested_qty_units"],
        by_size["100_percent"]["executed_qty_units"],
        by_size["100_percent"]["unfilled_qty_units"],
        by_size["100_percent"]["makers_touched"],
        by_size["100_percent"]["price_levels_visited"],
    ) == (7, 7, 0, 4, 2)
    assert (
        by_size["200_percent"]["requested_qty_units"],
        by_size["200_percent"]["executed_qty_units"],
        by_size["200_percent"]["unfilled_qty_units"],
        by_size["200_percent"]["makers_touched"],
        by_size["200_percent"]["price_levels_visited"],
    ) == (14, 7, 7, 4, 2)


def test_liquidation_memory_excludes_prebuilt_book_and_retains_sale_result() -> None:
    events = build_liquidation_events(order_count=4, price_levels=2)
    measurement = measure_liquidation_sale_memory(
        BaselineOrderBook,
        events,
        sale_size="200_percent",
    )

    assert measurement["requested_qty_units"] == 2 * measurement["available_qty_units"]
    assert measurement["executed_qty_units"] == measurement["available_qty_units"]
    assert measurement["unfilled_qty_units"] == measurement["available_qty_units"]
    assert measurement["fill_count"] == 4
    assert measurement["current_bytes"] >= 0
    assert measurement["peak_bytes"] >= measurement["current_bytes"]
    assert measurement["inclusions"] == {
        "prebuilt_book_allocations": False,
        "sale_matching_temporaries": True,
        "retained_sale_result_and_fills": True,
        "python_tracemalloc_only": True,
    }


def test_diagnostic_replay_counts_events_fills_and_book_peaks() -> None:
    events = [
        {"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1", "side": "BUY", "price_ticks": 100, "qty_units": 5},
        {"seq": 2, "event_id": "e2", "type": "LIMIT", "order_id": "a1", "side": "SELL", "price_ticks": 101, "qty_units": 2},
        {"seq": 3, "event_id": "e3", "type": "MARKET_SELL", "order_id": "s1", "qty_units": 3},
        {"seq": 4, "event_id": "e4", "type": "CANCEL", "target_order_id": "a1"},
    ]

    result = diagnose_replay(BaselineOrderBook, events)

    assert result == {
        "event_count": 4,
        "event_type_counts": {"CANCEL": 1, "LIMIT": 2, "MARKET_SELL": 1},
        "total_fills": 1,
        "rejected_events": 0,
        "peak_active_orders": 2,
        "peak_occupied_price_levels": 2,
        "final_active_orders": 1,
        "final_occupied_price_levels": 1,
        "final_unique_order_ids": True,
        "final_positive_quantities": True,
        "final_uncrossed": True,
    }


def test_stress_cli_saves_liquidation_memory_and_five_diagnostics(
    tmp_path: Path,
) -> None:
    output = tmp_path / "stress.json.gz"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [
            sys.executable,
            str(STRESS_SCRIPT),
            "--version",
            "baseline",
            "--order-count",
            "4",
            "--price-levels",
            "2",
            "--warmups",
            "0",
            "--repeats",
            "1",
            "--diagnostic-events",
            "10",
            "--out",
            str(output),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    with gzip.open(output, "rt", encoding="utf-8") as stream:
        document = json.load(stream)
    assert document["phase"] == "stress_and_diagnostic"
    assert document["version"] == "baseline"
    assert document["settings"] == {
        "liquidation_order_count": 4,
        "liquidation_price_levels": 2,
        "warmups": 0,
        "repeats": 1,
        "diagnostic_event_count": 10,
        "diagnostic_seed": 42,
    }
    assert len(document["liquidation_timing"]["records"]) == 3
    assert len(document["liquidation_memory"]) == 3
    assert len(document["diagnostics"]) == 5
    assert all(item["counts"]["rejected_events"] == 0 for item in document["diagnostics"])
    assert document["environment"]["python_version"]
