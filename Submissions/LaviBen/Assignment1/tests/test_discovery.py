"""Regression test for importing the suite from the repository root."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DiscoveryTests(unittest.TestCase):
    def test_root_discovery_probe_target(self) -> None:
        """Give the filtered child discovery one non-recursive test to run."""

    def test_root_discovery_imports_every_test_module(self) -> None:
        child_environment = os.environ.copy()
        child_environment.pop("PYTHONPATH", None)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-v",
                "-k",
                "test_root_discovery_probe_target",
            ],
            cwd=PROJECT_ROOT,
            env=child_environment,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            completed.returncode,
            0,
            completed.stdout + completed.stderr,
        )


if __name__ == "__main__":
    unittest.main()
