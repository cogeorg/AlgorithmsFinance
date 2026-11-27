"""Smoke tests for the saved-result Streamlit dashboard."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = PROJECT_ROOT / "05_dashboard" / "dashboard_01_app.py"


def test_dashboard_loads_saved_measurements_without_exceptions() -> None:
    app = AppTest.from_file(str(DASHBOARD_PATH)).run(timeout=30)

    assert not app.exception
    assert app.title[0].value == "Algorithms in Finance — Phase 1 Results"
    assert len(app.dataframe) >= 2
    assert [tab.label for tab in app.tabs] == ["Preparation", "Query batch", "Total"]
