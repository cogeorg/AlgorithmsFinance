"""Run the full test suite and save one row per test case.

Usage (from Assignment1/):
    python 04_benchmarks/export_test_results.py

Writes 05_results/tests_by_case.csv with columns
    test, case, source, version, result
- test:    test function name (without parameters)
- case:    the test's other parameters (pytest id without the version), or
           empty for a test with no other parameters
- source:  the test's @pytest.mark.source label (where expected values come from)
- version: a / b_sorted / b_heap for tests that run one engine; "all" for a
           test marked cross_version (compares every version); "none" for
           tests that need no engine
- result:  pass / fail (a setup error counts as fail)
and 05_results/tests_by_case_run.json: the commit and code state the tests
ran on (git commit, uncommitted code files, source fingerprint), the time,
the Python and pytest versions, and the counts.
Exit code: pytest's exit code.
"""

import csv
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bench_common import git_info, source_fingerprint

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "05_results" / "tests_by_case.csv"
RUN = ROOT / "05_results" / "tests_by_case_run.json"


class Collector:
    def __init__(self):
        self.info = {}      # nodeid -> (test, case, source, version)
        self.result = {}    # nodeid -> pass / fail

    def pytest_collection_modifyitems(self, items):
        for item in items:
            marker = item.get_closest_marker("source")
            source = marker.args[0] if marker else "unlabelled"
            params = getattr(item, "callspec", None)
            module = params.params.get("lob") if params else None
            if module:
                version = module.removeprefix("lob_")
            elif item.get_closest_marker("cross_version"):
                version = "all"      # one test comparing every version
            else:
                version = "none"     # needs no engine
            ids = params.id.split("-") if params else []
            case = "-".join(i for i in ids if i != module)
            self.info[item.nodeid] = (item.originalname, case, source, version)

    def pytest_runtest_logreport(self, report):
        if report.failed:
            self.result[report.nodeid] = "fail"
        elif report.when == "call" and report.nodeid not in self.result:
            self.result[report.nodeid] = "pass"


def main():
    git = git_info()                   # the code state the tests run on
    fingerprint = source_fingerprint()["sha256"]
    collector = Collector()
    code = pytest.main(["-q", "-p", "no:cacheprovider", str(ROOT / "02_tests")],
                       plugins=[collector])
    results = []
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["test", "case", "source", "version", "result"])
        for nodeid, (test, case, source, version) in collector.info.items():
            result = collector.result.get(nodeid, "not run")
            results.append(result)
            writer.writerow([test, case, source, version, result])
    prefix = "Submissions/BonackerMaurice/Assignment1/"
    run = {
        "command": "python 04_benchmarks/export_test_results.py",
        "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": git.get("commit"),
        "branch": git.get("branch"),
        "code_clean": git.get("code_clean"),
        "code_paths": git.get("code_paths"),
        "uncommitted_code_files": [f.removeprefix(prefix)
                                   for f in git.get("dirty_code_files") or []],
        "source_sha256": fingerprint,
        "python": platform.python_version(),
        "pytest": pytest.__version__,
        "exit_code": int(code),
        "cases": len(results),
        "counts": {k: results.count(k) for k in sorted(set(results))},
    }
    RUN.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT).as_posix()} and {RUN.relative_to(ROOT).as_posix()}")
    return int(code)


if __name__ == "__main__":
    sys.exit(main())
