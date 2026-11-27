"""Reproduce LiuHaina's cross-Python fixed-seed validation failure."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


def load_generator(target: Path):
    spec = importlib.util.spec_from_file_location(
        "audited_generate_data", target / "generate_data.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load audited generate_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "LiuHaina",
        help="Path to the pinned Submissions/LiuHaina directory",
    )
    args = parser.parse_args()
    target = args.target.resolve()
    saved = json.loads((target / "data" / "inputs.json").read_text(encoding="utf-8"))
    generator = load_generator(target)
    regenerated = generator.build_dataset(
        saved["generator"]["base_seed"],
        saved["generator"]["include_empty_queries"],
    )

    saved_version = saved["generator"]["python_version"]
    current_version = regenerated["generator"]["python_version"]
    print(f"saved_python_version={saved_version}")
    print(f"current_python_version={current_version}")
    print(f"whole_dataset_equal={saved == regenerated}")

    saved_without_environment = copy.deepcopy(saved)
    regenerated_without_environment = copy.deepcopy(regenerated)
    saved_without_environment["generator"].pop("python_version")
    regenerated_without_environment["generator"].pop("python_version")
    equal_without_version = saved_without_environment == regenerated_without_environment
    print(f"equal_without_python_version={equal_without_version}")

    if current_version != saved_version:
        completed = subprocess.run(
            [sys.executable, "-B", "validate_data.py"],
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        )
        print(f"validator_exit_code={completed.returncode}")
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="")
        if completed.returncode == 0:
            raise AssertionError("Expected validator to fail across Python versions")
    else:
        print("validator_not_run: current Python matches the saved metadata version")

    # Demonstrate the faulty comparison deterministically on any Python version.
    simulated = copy.deepcopy(regenerated)
    simulated["generator"]["python_version"] = "different-audit-version"
    if simulated == regenerated:
        raise AssertionError("Changing environment metadata should change whole equality")
    simulated["generator"].pop("python_version")
    baseline = copy.deepcopy(regenerated)
    baseline["generator"].pop("python_version")
    if simulated != baseline or not equal_without_version:
        raise AssertionError("Difference was not isolated to python_version")

    print("BUG REPRODUCED: environment metadata breaks fixed-seed equality")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
