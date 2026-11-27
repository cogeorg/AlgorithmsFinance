"""Bug 5 (robustness): the dashboard crashes with a raw traceback if one results file is missing.

Example: `docker run -p 8501:8501 -v "$(pwd)/results:/app/results" ...` on a checkout whose
results/ folder does not yet contain breakeven_curve.csv. The page should say which script
creates the missing file. This test copies the audited folder to a temporary directory
(the original is not touched), deletes one results file and runs the dashboard headless.
It FAILS on the audited commit. Needs streamlit (in Bastian's requirements.txt).

Run from Submissions/BundschuhBastian/:
    .venv/bin/python -m pytest -q audit_HuangJiaxin/reproducers/repro_5_dashboard_missing_file.py
"""
import shutil

import pytest

from _target import TARGET

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def test_dashboard_reports_missing_file(tmp_path, monkeypatch):
    copy = tmp_path / "HuangJiaxin"
    shutil.copytree(TARGET, copy)
    (copy / "results" / "breakeven_curve.csv").unlink()
    monkeypatch.chdir(copy)
    at = AppTest.from_file(str(copy / "dashboard.py"), default_timeout=60).run()
    errors = [e.message for e in at.exception]
    assert not errors, f"dashboard crashed instead of showing a message: {errors[0][:120]}"
