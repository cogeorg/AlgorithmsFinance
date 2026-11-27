"""Smoke test: the dashboard renders without exceptions for every filter setting."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")


@pytest.fixture(scope="module")
def app():
    return AppTest.from_file(APP, default_timeout=60).run()


def test_renders_all_tabs(app):
    assert not app.exception
    assert [t.label for t in app.tabs] == ["Runtime", "Revisions", "Memory", "Raw data", "Environment"]


@pytest.mark.parametrize("key,value", [("q", 1), ("q", 100), ("scale", "Linear"), ("versions", ["v1"]), ("versions", ["v3"]), ("versions", [])])
def test_filters_do_not_break_the_page(app, key, value):
    app.segmented_control(key=key).set_value(value).run()
    assert not app.exception
