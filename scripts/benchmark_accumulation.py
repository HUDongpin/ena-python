"""Time the ENA pipeline on a real dataset.

Reports accumulation *and* modeling. An earlier version timed a single unwarmed
accumulate() call and printed it to six decimal places -- more precision than one
cache-cold, GC-exposed sample can support -- and left the whole SVD/rotation/node
path unmeasured.

This takes `--repeats` samples after `--warmup` discarded ones and reports the median
with the observed range, so a number can be compared against another machine honestly.

For regression *guards* rather than measurements, see tests/test_benchmarks.py: those
assert on how cost grows with input size, which is independent of the host.
"""

from __future__ import annotations

import argparse
import statistics
import time
from collections.abc import Callable
from typing import Any

from ena_python import accumulate, make_set
from ena_python.io import read_table


def _time_repeatedly(
    fn: Callable[[], Any], *, repeats: int, warmup: int
) -> tuple[Any, list[float]]:
    """Run `fn` `warmup + repeats` times; return its last result and the timed samples."""

    result: Any = None
    for _ in range(warmup):
        result = fn()

    timings: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn()
        timings.append(time.perf_counter() - start)
    return result, timings


def _report(label: str, timings: list[float]) -> None:
    median = statistics.median(timings)
    spread = ""
    if len(timings) > 1:
        # The range, not a standard deviation: with a handful of samples, min/max says
        # more about the noise than an sd computed from those same few points.
        spread = f"  (min {min(timings):.4f}s, max {max(timings):.4f}s, n={len(timings)})"
    print(f"  {label:<11} median {median:.4f}s{spread}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark ENA accumulation and modeling on a tabular file."
    )
    parser.add_argument("file")
    parser.add_argument("--units", nargs="+", required=True)
    parser.add_argument("--conversation", nargs="+", required=True)
    parser.add_argument("--codes", nargs="+", required=True)
    parser.add_argument("--metadata", nargs="+", default=None)
    parser.add_argument("--window-size-back", default=1)
    parser.add_argument("--dimensions", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=5, help="Timed samples (default: 5)")
    parser.add_argument("--warmup", type=int, default=1, help="Untimed runs first (default: 1)")
    args = parser.parse_args()

    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1")
    if args.warmup < 0:
        raise SystemExit("--warmup cannot be negative")

    df = read_table(args.file)

    accumulated, accumulate_timings = _time_repeatedly(
        lambda: accumulate(
            df,
            units=args.units,
            conversation=args.conversation,
            codes=args.codes,
            metadata=args.metadata,
            window_size_back=args.window_size_back,
        ),
        repeats=args.repeats,
        warmup=args.warmup,
    )
    modeled, make_set_timings = _time_repeatedly(
        lambda: make_set(accumulated, dimensions=args.dimensions),
        repeats=args.repeats,
        warmup=args.warmup,
    )

    total = statistics.median(accumulate_timings) + statistics.median(make_set_timings)
    print(
        f"rows={len(df)} units={len(accumulated.connection_counts)} "
        f"codes={len(args.codes)} pairs={len(accumulated.adjacency_names)} "
        f"dimensions={modeled.dimensions}"
    )
    _report("accumulate", accumulate_timings)
    _report("make_set", make_set_timings)
    print(f"  {'total':<11} median {total:.4f}s")


if __name__ == "__main__":
    main()
