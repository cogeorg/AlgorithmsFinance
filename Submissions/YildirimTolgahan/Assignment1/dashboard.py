"""Build the offline dashboard from saved results. Runs no experiment.

    python dashboard.py
    python dashboard.py --results results/smoke/measurements.json --output results/smoke/dashboard.html
"""
import argparse
import html
import json
import os
from pathlib import Path
import re

from benchmark import HIST_MIN_LOG10_NS, HIST_PER_DECADE

HERE = Path(__file__).resolve().parent


def test_summary(path):
    """Counts from a saved unittest transcript, or None if the file is absent."""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    ran = sum(int(n) for n in re.findall(r"^Ran (\d+) tests? in", text, flags=re.M))
    problems = sum(int(n) for n in re.findall(r"(?:failures|errors)=(\d+)", text))
    failed_runs = len(re.findall(r"^FAILED", text, flags=re.M))
    return {"ran": ran, "problems": problems, "passed": ran if not failed_runs else None,
            "files": sorted(set(re.findall(r"\((test_\w+)\.", text)))}


def load(source):
    data = json.loads(source.read_text(encoding="utf-8"))
    if not data.get("replay"):
        raise ValueError("No saved measurements to display")
    folder = source.parent
    data["metadata_hist"] = {"per_decade": HIST_PER_DECADE, "min_log10": HIST_MIN_LOG10_NS}
    data["tests"] = {"before": test_summary(folder / "test_before.txt"), "after": test_summary(folder / "test_after.txt")}
    for name in ("profile", "tuning"):               # optional diagnostic results
        extra = folder / f"{name}.json"
        if extra.exists():
            data[name] = json.loads(extra.read_text(encoding="utf-8"))
    return data


def build(source, output):
    data = load(source)
    payload = json.dumps(data, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    link = Path(os.path.relpath(source, output.parent)).as_posix()
    template = (HERE / "dashboard_template.html").read_text(encoding="utf-8")
    page = template.replace("__JSON_LINK__", html.escape(link, quote=True)).replace("__DATA__", payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8", newline="\n")
    print(f"Dashboard: {output.resolve()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", type=Path, default=HERE / "results" / "measurements.json")
    parser.add_argument("--output", type=Path, default=HERE / "results" / "dashboard.html")
    args = parser.parse_args()
    build(args.results, args.output)


if __name__ == "__main__":
    main()
