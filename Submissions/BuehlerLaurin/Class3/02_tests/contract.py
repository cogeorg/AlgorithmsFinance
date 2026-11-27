"""Named contract checks: check_<rule>(impl) -> None, raise AssertionError on violation.

Used by 02_tests/test_contract.py (real versions) and 02_tests/test_mutants.py (mutants).
Imported as `import contract` (02_tests is on pythonpath, not a package).
"""
