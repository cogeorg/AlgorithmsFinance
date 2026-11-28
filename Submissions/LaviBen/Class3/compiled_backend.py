"""Compiled O(N)-memory backend for the exact American put recurrence."""

from __future__ import annotations

import ctypes
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

from american_put import PricingResult, _validate_inputs


SOURCE = Path(__file__).with_name("american_put_kernel.c")
_LOCK = threading.Lock()
_LIBRARY = None
_LIBRARY_PATH = None


def _target_path() -> Path:
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()[:16]
    suffix = ".dylib" if sys.platform == "darwin" else ".dll" if os.name == "nt" else ".so"
    return Path(tempfile.gettempdir()) / f"class3_american_put_{digest}{suffix}"


def ensure_compiled() -> Path:
    global _LIBRARY_PATH
    target = _target_path()
    with _LOCK:
        if not target.exists():
            compiler = os.environ.get("CC", "cc")
            temporary = target.with_suffix(target.suffix + f".{os.getpid()}.tmp")
            command = [
                compiler, "-O3", "-std=c11", "-fPIC", "-shared",
                str(SOURCE), "-o", str(temporary), "-lm",
            ]
            completed = subprocess.run(command, text=True, capture_output=True)
            if completed.returncode != 0:
                raise RuntimeError(
                    "failed to compile American put kernel:\n"
                    + completed.stdout + completed.stderr
                )
            os.replace(temporary, target)
        _LIBRARY_PATH = target
    return target


def _load_library():
    global _LIBRARY
    if _LIBRARY is not None:
        return _LIBRARY
    path = ensure_compiled()
    library = ctypes.CDLL(str(path))
    function = library.american_put_kernel
    function.argtypes = [
        ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
        ctypes.c_double, ctypes.c_int64, ctypes.c_int, ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_uint64),
    ]
    function.restype = ctypes.c_int
    _LIBRARY = library
    return library


def compiler_metadata() -> dict[str, str]:
    path = ensure_compiled()
    compiler = os.environ.get("CC", "cc")
    completed = subprocess.run(
        [compiler, "--version"], text=True, capture_output=True, check=False
    )
    return {
        "source": str(SOURCE),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "library": str(path),
        "library_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "compiler": compiler,
        "compiler_version": (completed.stdout or completed.stderr).splitlines()[0],
        "flags": "-O3 -std=c11 -fPIC -shared -lm",
    }


def _price(spot, strike, up, down, gross_rate, steps, *, keep_boundary):
    spot, strike, up, down, gross_rate, steps = _validate_inputs(
        spot, strike, up, down, gross_rate, steps
    )
    library = _load_library()
    out_value = ctypes.c_double()
    out_updates = ctypes.c_uint64()
    boundary_storage = (
        (ctypes.c_int64 * (steps + 1))() if keep_boundary else None
    )
    boundary_pointer = (
        boundary_storage
        if boundary_storage is not None
        else ctypes.POINTER(ctypes.c_int64)()
    )
    status = library.american_put_kernel(
        spot, strike, up, down, gross_rate, steps, int(keep_boundary),
        ctypes.byref(out_value), boundary_pointer, ctypes.byref(out_updates)
    )
    if status != 0:
        raise ArithmeticError(f"compiled American put kernel failed with status {status}")
    if keep_boundary:
        boundary = tuple(
            None
            if boundary_storage[t] < 0
            else spot
            * up ** boundary_storage[t]
            * down ** (t - boundary_storage[t])
            for t in range(steps + 1)
        )
    else:
        boundary = ()
    return PricingResult(out_value.value, boundary, int(out_updates.value))


def price_american_put_compiled(spot, strike, up, down, gross_rate, steps) -> float:
    return _price(
        spot, strike, up, down, gross_rate, steps, keep_boundary=False
    ).value


def price_american_put_with_boundary_compiled(
    spot, strike, up, down, gross_rate, steps
) -> PricingResult:
    return _price(
        spot, strike, up, down, gross_rate, steps, keep_boundary=True
    )
