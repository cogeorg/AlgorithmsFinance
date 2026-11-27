"""Shared input validation, applied identically to every method.

Rejects anything that is not a sequence of integer IDs, so that all methods
fail the same way on bad input instead of diverging (for example, ``sorted``
raising on ``None`` while a linear scan silently returns ``False``).
Runs in O(len(values)); it is called from ``Method.__call__`` only, never
inside the timed ``prepare``/``query`` functions.

Only Python ``int`` (and subclasses) are accepted, not ``bool``. NumPy integers
are rejected on purpose: comparisons on them return ``numpy.bool_``, which would
leak into the output of some methods; convert with ``array.tolist()`` first.
"""
from collections.abc import Sequence


def check_ids(values, name):
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(
            f"{name} must be a sequence of integers (list, tuple or range), "
            f"got {type(values).__name__}; for NumPy arrays pass array.tolist()")
    for i, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(
                f"{name}[{i}] must be a Python int ID, got {type(value).__name__}: {value!r}")
