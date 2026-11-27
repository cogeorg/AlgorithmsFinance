"""Declared before long measurements, 2026-11-22: A is only a baseline."""

BASELINE_PROTOCOL = "single-large"


def timing_plan(version, size):
    """Return warm-ups, measured trials and the reporting label."""
    if version == "A" and size >= 100000:
        return 0, 1, "A: single trial"
    return 1, 5, "warm-up + 5 repeats"
