# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportReturnType=false
# (pandas and altair give no usable types here; the pages are checked by tests/test_dashboard.py)
"""Dashboard (Phase 7): every page renders from the saved results, nothing is rerun."""
import ast
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("altair")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "dashboard" / "app.py"
DATA = ROOT / "dashboard" / "data.py"
PAGES = ["Overview", "Scaling", "Throughput", "Latency", "Memory", "Liquidation", "Concentration",
         "Fairness", "Correctness", "Run-1 incident", "Workload and raw repeats", "Why A is slow"]


@pytest.fixture(scope="module")
def app():
    return AppTest.from_file(str(APP), default_timeout=120).run()


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_without_error(app, page):
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception, [str(e.value) for e in app.exception]
    assert app.title, f"page {page} has no title"


def test_the_pages_of_the_assignment_are_all_there(app):
    assert list(app.sidebar.radio[0].options) == PAGES


def _imports(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize("path", [APP, DATA])
def test_dashboard_never_imports_the_engines_or_the_benchmarks(path):
    banned = {"lob", "bench", "generate_orders", "subprocess", "multiprocessing", "tools"}
    assert not (_imports(path) & banned)


def test_dashboard_only_reads_files_in_results():
    text = DATA.read_text() + APP.read_text()
    assert "RESULTS" in text and "data/generated" not in text and "write_text" not in text
    assert ".to_csv" not in text and "open(" not in text.replace("with open", "x")


def test_code_shown_on_the_bottleneck_page_is_in_version_a():
    """The snippets on the page are copies; they must still be what lob/version_a.py contains."""
    source = (ROOT / "lob" / "version_a.py").read_text()
    for line in ("def _is_live(self, order_id: str) -> bool:",
                 "return (any(r[ID] == order_id for r in self._bids)",
                 "or any(r[ID] == order_id for r in self._asks))",
                 "def _best_index(side: list[list], is_bid: bool) -> int:",
                 "for i in range(1, len(side)):",
                 "i = self._best_index(side, side_is_bid)",
                 "side.pop(i)"):
        assert line in source, line


def test_scan_is_live_counts_equal_n_times_n_minus_1_over_2_on_buildup_and_crowded():
    from dashboard import data
    c = data.csv("counters.csv")
    a = c[(c["version"] == "A") & (c["scenario"].isin(["buildup", "crowded"]))
          & (c["status"] == "ok")]
    assert len(a) == 4
    assert (a["scan_is_live"] == a["events"] * (a["events"] - 1) // 2).all()


def test_stopped_and_not_run_runs_are_marked_not_dropped():
    from dashboard import data
    r = data.marker_column(data.runs(data.csv("time_raw.csv")))
    assert {"measured (median)", "stopped at the 600 s limit", "not run (no value)"} <= set(r["marker"])
    assert r[r["status"] == "stopped"]["median_seconds"].isna().all()     # never a number invented
