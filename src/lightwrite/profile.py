"""Optional lightweight profiling for Lightwrite.

Enable with LIGHTWRITE_PROFILE=1 (or =all). Prints ms totals on exit /
when dump() is called. Zero cost when disabled.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager

_ENABLED = os.environ.get("LIGHTWRITE_PROFILE", "").strip().lower() in (
    "1", "true", "yes", "all",
)

_totals: dict[str, float] = {}
_counts: dict[str, int] = {}


def enabled() -> bool:
    return _ENABLED


@contextmanager
def span(name: str):
    if not _ENABLED:
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        dt = time.perf_counter() - t0
        _totals[name] = _totals.get(name, 0.0) + dt
        _counts[name] = _counts.get(name, 0) + 1


def dump(stream=None):
    if not _ENABLED or not _totals:
        return
    import sys
    out = stream or sys.stderr
    out.write("LIGHTWRITE_PROFILE (ms total / calls / avg ms):\n")
    for name in sorted(_totals, key=lambda k: -_totals[k]):
        total = _totals[name] * 1000.0
        n = _counts[name]
        out.write(f"  {name:24s}  {total:10.2f}  {n:6d}  {total / n:8.3f}\n")
    out.flush()


def reset():
    _totals.clear()
    _counts.clear()
