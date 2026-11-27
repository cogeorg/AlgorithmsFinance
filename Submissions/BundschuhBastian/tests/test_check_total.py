"""Tests for check_total.py (total vs prepare + query), on made-up and on saved data."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import check_total  # noqa: E402


def row(phase, median, low, high, method="hash_v1", n="10", q="1", hit="mixed"):
    return {"n": n, "q": q, "hit_rate": hit, "method": method,
            "algorithm": method.split("_")[0], "phase": phase,
            "median_seconds_per_batch": str(median),
            "min_seconds_per_batch": str(low), "max_seconds_per_batch": str(high)}


def test_ratio_and_spread_on_made_up_data():
    rows = [row("prepare", 2.0, 1.8, 2.2), row("query", 1.0, 0.9, 1.5),
            row("total", 2.4, 2.0, 2.8)]
    (entry,) = check_total.compute(rows)
    assert entry["ratio_total_over_sum"] == pytest.approx(0.8)
    assert entry["median_sum"] == pytest.approx(3.0)
    assert entry["spread_prepare"] == pytest.approx(2.2 / 1.8)
    assert entry["spread_query"] == pytest.approx(1.5 / 0.9)
    assert entry["spread_total"] == pytest.approx(1.4)
    assert entry["ranges_overlap"] is True          # total 2.0..2.8 vs sum 2.7..3.7


def test_ranges_that_do_not_overlap_are_flagged():
    rows = [row("prepare", 2.0, 1.9, 2.1), row("query", 1.0, 0.95, 1.05),
            row("total", 2.0, 1.9, 2.1)]            # total 1.9..2.1 vs sum 2.85..3.15
    (entry,) = check_total.compute(rows)
    assert entry["ranges_overlap"] is False
    assert check_total.summarize([entry])["ranges_do_not_overlap"] == 1


def test_missing_phase_is_an_error():
    with pytest.raises(ValueError):
        check_total.compute([row("prepare", 1, 1, 1), row("query", 1, 1, 1)])


def test_prepare_variation_skips_linear():
    rows = [row("prepare", 1.0, 1, 1, n="5", q="1"), row("prepare", 1.5, 1, 1, n="5", q="100"),
            row("prepare", 9.0, 1, 1, method="linear_v1", n="5")]
    variation = check_total.prepare_variation(rows)
    assert list(variation) == ["hash_v1 n=5"]
    assert variation["hash_v1 n=5"]["max_over_min"] == pytest.approx(1.5)


SAVED = ROOT / "results" / "timing_summary.csv"


@pytest.mark.skipif(not SAVED.exists(), reason="no saved timing results")
def test_saved_results_every_configuration_has_all_phases():
    entries = check_total.compute(check_total.load(SAVED))
    assert len(entries) == 3 * 2 * 3 * 4            # n * q * hit rates * methods
    for e in entries:
        manual = e["median_total"] / (e["median_prepare"] + e["median_query"])
        assert e["ratio_total_over_sum"] == pytest.approx(manual)
        assert 0.5 < manual < 2.0                    # guards against a broken file, not noise


@pytest.mark.skipif(not (ROOT / "results" / "total_consistency.csv").exists(),
                    reason="check_total.py not run yet")
def test_metadata_documents_total_vs_sum():
    metadata = json.loads((ROOT / "results" / "timing_metadata.json").read_text())
    note = metadata["total_vs_prepare_plus_query"]
    assert "measured on its own" in note["explanation"]
    assert note["configurations"] == 72
    assert note["below_0.97"] + note["above_1.03"] + note["within_3_percent"] == 72
