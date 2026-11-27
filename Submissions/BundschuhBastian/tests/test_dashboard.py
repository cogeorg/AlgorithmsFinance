"""Tests for the dashboard: data helpers on the saved results and a headless app run."""
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))
import loaders  # noqa: E402

pytestmark = pytest.mark.skipif(loaders.missing_files(), reason="no saved results")


@pytest.fixture(scope="module")
def results():
    return loaders.load_results()


def test_total_vs_sum_matches_check_total_csv(results):
    mine = loaders.total_vs_sum(results["time_summary"])
    saved = pd.read_csv(ROOT / "results" / "total_consistency.csv").sort_values(
        loaders.KEY).reset_index(drop=True)
    assert len(mine) == len(saved) == 72
    assert mine["ratio"].tolist() == pytest.approx(saved["ratio_total_over_sum"].tolist())
    assert mine["spread_total"].tolist() == pytest.approx(saved["spread_total"].tolist())
    assert mine["ranges_overlap"].tolist() == saved["ranges_overlap"].tolist()


def test_scaled_times_units_and_per_query(results):
    summary = results["time_summary"]
    batch = loaders.scaled_times(summary, "total", False, 1e6)
    query = loaders.scaled_times(summary, "total", True, 1e6)
    assert (batch["value"] == batch["median_seconds_per_batch"] * 1e6).all()
    assert (query["value"] * query["q"]).tolist() == pytest.approx(batch["value"].tolist())
    prepare = loaders.scaled_times(summary, "prepare", True, 1.0)
    assert (prepare["per"] == "per batch").all()      # preparation has no per-query value


def test_version_comparison_ratio(results):
    versions = loaders.version_comparison(results["time_summary"])
    assert len(versions) == 3 * 2 * 3 * 3             # n * q * hit rates * phases
    row = versions.iloc[0]
    assert row["v2_over_v1"] == pytest.approx(row["v2_iterative"] / row["v1_recursive"])


def test_memory_table_shape(results):
    table = loaders.memory_table(results["mem_summary"], 100, "mixed", "median_peak_bytes")
    assert list(table.columns) == ["method", "phase", "n = 1,000", "n = 10,000", "n = 100,000"]
    assert len(table) == 4 * 3


def test_missing_results_are_reported(tmp_path):
    assert set(loaders.missing_files(tmp_path)) == set(loaders.REQUIRED)
    with pytest.raises(FileNotFoundError):
        loaders.load_results(tmp_path)


def test_dashboard_does_not_import_the_algorithms_or_benchmarks():
    import ast
    imported = set()
    for name in ("app.py", "loaders.py"):
        tree = ast.parse((ROOT / "dashboard" / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
    assert not imported & {"membership", "datagen", "bench_time", "bench_memory", "check_total"}


# ---- report helpers --------------------------------------------------------------

import report  # noqa: E402


@pytest.mark.parametrize("value,text", [(133.39, "133"), (0.1769, "0.177"), (21.94, "21.9"),
                                        (104628.0, "105,000"), (4194.52, "4,190"),
                                        (9.294, "9.29"), (0.0153, "0.0153"), (0, "0")])
def test_sig3(value, text):
    assert report.sig3(value) == text


def test_pick_unit():
    assert report.pick_unit(0.13) == ("ms", 1e3)
    assert report.pick_unit(5e-4) == ("µs", 1e6)
    assert report.pick_unit(5e-8) == ("ns", 1e9)


def test_log_domain_uses_powers_of_ten():
    assert report.log_domain(0.015, 25) == [0.01, 100]
    low, high = report.log_domain(10, 10)
    assert low == 10 and high > low


def test_spread_labels_keeps_order_and_separates_close_values():
    values = {"a": 100.0, "b": 101.0, "c": 5.0}
    adjusted = report.spread_labels(values, 0.1, -1, 3)
    assert sorted(adjusted, key=adjusted.get) == ["c", "a", "b"]
    assert abs(__import__("math").log10(adjusted["b"] / adjusted["a"])) >= 0.1 - 1e-9
    assert all(10 ** -1 <= v <= 10 ** 3 * (1 + 1e-9) for v in adjusted.values())


def test_findings_are_computed_from_the_saved_results(results):
    sentences = report.findings(results["time_summary"], results["mem_summary"])
    assert 2 <= len(sentences) <= 3
    summary = results["time_summary"]
    row = summary[(summary["n"] == 100000) & (summary["q"] == 100)
                  & (summary["hit_rate"] == "mixed") & (summary["method"] == "hash_v1")
                  & (summary["phase"] == "total")]
    hash_ms = report.sig3(float(row["median_seconds_per_batch"].iloc[0]) * 1e3)
    assert f"in {hash_ms} ms" in sentences[0]
    assert "linear search has the lowest total time at every n" in sentences[1]


def test_version_sentence_contains_measured_ratios(results):
    text = report.version_sentence(results["time_summary"], 100, "mixed")
    versions = loaders.version_comparison(results["time_summary"])
    query = versions[versions["phase"] == "query"]["v2_over_v1"]
    assert f"{query.min():.2f} to {query.max():.2f} over all settings" in text


# ---- the page ---------------------------------------------------------------------

def run_app():
    from streamlit.testing.v1 import AppTest
    return AppTest.from_file(str(ROOT / "dashboard" / "app.py"), default_timeout=90).run()


def test_app_runs_without_errors_for_every_setting():
    app = run_app()
    assert not app.exception
    q_radio, hit_radio, per_radio = app.radio
    for q in q_radio.options:
        for hit in ("mixed", "all-present", "all-absent"):
            for per in ("batch", "query"):
                app.radio[0].set_value(int(q) if q.isdigit() else q)
                app.radio[1].set_value(hit)
                app.radio[2].set_value(per)
                app.run()
                assert not app.exception, (q, hit, per)


def test_page_follows_the_report_layout():
    app = run_app()
    assert [t.value for t in app.title] == ["Membership search: Linear, Binary, Hash set"]
    assert len(app.sidebar) == 0 and len(app.tabs) == 0            # one page, no sidebar, no tabs
    for boxes in (app.info, app.success, app.warning, app.error, app.metric):
        assert len(boxes) == 0
    captions = [c.value for c in app.caption]
    assert captions[0].startswith("Bastian Bundschuh · Algorithms in Finance · commit ")
    assert "Python 3.11" in captions[0] or "Python 3." in captions[0]
    assert [c.split(".")[0] for c in captions[1:]] == ["Figure 1", "Figure 2", "Figure 3",
                                                      "Table 1"]
    assert [e.label for e in app.expander] == [
        "Appendix: protocol, raw repeats, environment and metadata"]
    assert app.expander[0].proto.expanded is False                 # collapsed


def test_page_text_has_no_bold_or_emoji():
    app = run_app()
    texts = [m.value for m in app.markdown if not m.value.startswith("<style>")]
    texts += [c.value for c in app.caption]
    assert not any("**" in t for t in texts)
    assert not any(ord(ch) > 0x2FFF for t in texts for ch in t)    # no emoji (· and µ are fine)


def test_app_shows_message_when_results_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(loaders, "RESULTS_DIR", tmp_path)
    app = run_app()
    assert not app.exception
    assert any("Saved results not found" in m.value for m in app.markdown)
    assert any("bench_time.py" in c.value and "bench_memory.py" in c.value for c in app.code)
    assert len(app.error) == 0
