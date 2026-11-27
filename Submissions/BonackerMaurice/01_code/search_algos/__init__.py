"""LinearSearch, BinarySearch and hash-set membership over integer ID arrays.

Usage::

    from search_algos import get_method
    get_method("binary")([7, 11, 7], [11, 9, 7])   # -> [True, False, True]
"""
from . import binary, hashset, linear
from .registry import CURRENT, METHODS, Method, current_methods, get_method

__all__ = ["CURRENT", "METHODS", "Method", "binary", "current_methods", "get_method",
           "hashset", "linear"]
