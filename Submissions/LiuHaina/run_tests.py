"""Run the unchanged contract suite against original and/or revised algorithms."""

import argparse
import importlib
import unittest

import test_search


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=("original", "revised", "both"), default="both")
    args = parser.parse_args()
    versions = ("original", "revised") if args.version == "both" else (args.version,)
    passed = True
    for version in versions:
        module_name = "search_original" if version == "original" else "search"
        test_search.search = importlib.import_module(module_name)
        print(f"\n=== {version}: {module_name}.py ===", flush=True)
        suite = unittest.defaultTestLoader.loadTestsFromModule(test_search)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        passed = result.wasSuccessful() and passed
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
