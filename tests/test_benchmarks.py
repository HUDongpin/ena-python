"""Performance benchmarks and regression guards.

Two kinds of test live here.

The `@pytest.mark.benchmark` ones *measure* -- absolute wall-clock times via
pytest-benchmark. They are excluded from the default suite (`pyproject.toml` sets
`-m "not benchmark"`) because they are slow and host-dependent. Run them with:

    make benchmark          # pytest -m benchmark

The `test_*_scales_*` guards *compare timings against each other*, so they hold on any
host and run in the normal suite, where they can actually catch a regression in CI.

**On budgets.** Wall-clock ceilings are machine-dependent, so the ones here are
deliberately loose -- roughly 20-30x the measured time on a 2026 laptop. They exist to
catch a catastrophic regression (an accidental O(n^2), a per-row DataFrame copy), not to
police a 20% drift, which on a shared CI runner would only produce flakes. The
`test_*_scales_*` guards below are the sharper instrument: they compare timings against
each other, so they are independent of how fast the host is.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from ena_python import accumulate, ena, make_set
from ena_python.matrix import ref_window_matrix

N_CODES = 6
CODES = [f"code{i}" for i in range(N_CODES)]


def synthetic(n_units: int, per_unit: int = 80, *, seed: int = 0) -> pd.DataFrame:
    """A dataset shaped like real ENA input: units x conversations x binary codes."""

    rng = np.random.default_rng(seed)
    n_rows = n_units * per_unit
    return pd.DataFrame(
        {
            "unit": np.repeat([f"U{i}" for i in range(n_units)], per_unit),
            "conv": np.tile(np.repeat(["c1", "c2", "c3", "c4"], per_unit // 4), n_units),
            **{code: rng.integers(0, 2, n_rows) for code in CODES},
        }
    )


def _accumulate(df: pd.DataFrame):
    return accumulate(df, units=["unit"], conversation=["conv"], codes=CODES, window_size_back=4)


# --- Benchmarks -------------------------------------------------------------
# The reference workload is ~3840 rows / 48 units / 6 codes, matching the scale
# docs/performance_strategy.md records for rENA's RS.data (3824 rows, 48 units).


@pytest.mark.benchmark
def test_benchmark_accumulate(benchmark) -> None:
    """Accumulation: the dominant cost, and a Python-level loop over rows x code pairs."""

    df = synthetic(48)
    result = benchmark(_accumulate, df)

    assert len(result.connection_counts) == 48
    assert benchmark.stats["median"] < 2.0, (
        f"accumulate of {len(df)} rows took {benchmark.stats['median']:.3f}s (budget 2.0s); "
        "~0.06s is normal, so this is a >30x regression, not noise"
    )


@pytest.mark.benchmark
def test_benchmark_make_set(benchmark) -> None:
    """Modeling: normalize -> center -> SVD -> project -> node positions.

    Scales with units and code pairs rather than rows, so it stays cheap next to
    accumulation. Benchmarked separately because the review noted the old script timed
    only accumulation and left the whole SVD/rotation path unmeasured.
    """

    accumulated = _accumulate(synthetic(48))
    result = benchmark(make_set, accumulated, dimensions=2)

    assert len(result.points) == 48
    assert benchmark.stats["median"] < 1.0, (
        f"make_set took {benchmark.stats['median']:.3f}s (budget 1.0s); ~0.002s is normal"
    )


@pytest.mark.benchmark
def test_benchmark_ena_end_to_end(benchmark) -> None:
    """The full public entry point, which is what most callers actually time."""

    df = synthetic(48)
    result = benchmark(
        ena, data=df, codes=CODES, units=["unit"], conversation=["conv"], window_size_back=4
    )

    assert len(result.points) == 48
    assert benchmark.stats["median"] < 3.0, (
        f"ena() took {benchmark.stats['median']:.3f}s (budget 3.0s)"
    )


@pytest.mark.benchmark
def test_benchmark_window_kernel(benchmark) -> None:
    """The moving-stanza window in isolation -- the hot loop inside accumulation."""

    rng = np.random.default_rng(0)
    rows = pd.DataFrame({code: rng.integers(0, 2, 2000) for code in CODES})
    result = benchmark(ref_window_matrix, rows, window_size_back=4, binary=True)

    assert len(result) == 2000
    assert benchmark.stats["median"] < 2.0, (
        f"window kernel took {benchmark.stats['median']:.3f}s (budget 2.0s)"
    )


# --- Complexity guards ------------------------------------------------------
# These fit the observed cost to t = c * n^k and assert on the exponent, so they say
# nothing about how fast the host is -- only about how the cost *grows*. That makes them
# safe to run on a shared CI runner, unlike a wall-clock ceiling.
#
# Calibrated by injecting real regressions into ref_window_matrix and re-measuring:
#
#     baseline (as shipped) .................. k = 1.01 - 1.03
#     one numpy full-scan per row ............ k = 1.25
#     a python-loop scan per row (true O(n^2)) k = 1.97
#
# Hence LINEAR_EXPONENT_LIMIT = 1.5: ~50% headroom over the real baseline, while still
# failing on a genuine quadratic. It is deliberately blind to constant-factor slowdowns
# (the 1.25 case passes) -- catching those reliably would need a stable machine and a
# committed baseline, which CI does not offer.

LINEAR_EXPONENT_LIMIT = 1.5
SIZES = (500, 1000, 2000, 4000)


def _median_seconds(fn, *args, repeats: int = 5, warmup: int = 1) -> float:
    for _ in range(warmup):
        fn(*args)
    timings = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn(*args)
        timings.append(time.perf_counter() - start)
    return float(np.median(timings))


def _cost_exponent(fn, make_input, sizes=SIZES) -> float:
    """Fit k in `time = c * size**k` by least squares on the log-log timings."""

    times = [_median_seconds(fn, make_input(size)) for size in sizes]
    assert all(t > 0 for t in times), f"timings must be positive, got {times}"
    return float(np.polyfit(np.log(sizes), np.log(times), 1)[0])


def _code_frame(n_rows: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({code: rng.integers(0, 2, n_rows) for code in CODES})


def test_window_kernel_cost_is_linear_in_rows() -> None:
    """The moving-stanza window must stay O(rows), not O(rows^2).

    It is a Python-level loop over rows, so it is the most likely place for an
    accidental quadratic -- e.g. rescanning the whole frame per row.
    """

    exponent = _cost_exponent(ref_window_matrix, _code_frame)
    assert exponent < LINEAR_EXPONENT_LIMIT, (
        f"ref_window_matrix cost grows as rows^{exponent:.2f}; linear is ~1.0 and the "
        f"limit is {LINEAR_EXPONENT_LIMIT}. Something became super-linear in rows."
    )


def test_accumulate_cost_is_linear_in_rows() -> None:
    """Accumulation is O(rows x code_pairs) and must stay linear in rows."""

    def make(n_rows: int) -> pd.DataFrame:
        frame = _code_frame(n_rows)
        frame.insert(0, "conv", np.tile(["c1", "c2"], n_rows // 2))
        frame.insert(0, "unit", np.repeat([f"U{i}" for i in range(10)], n_rows // 10))
        return frame

    exponent = _cost_exponent(_accumulate, make)
    assert exponent < LINEAR_EXPONENT_LIMIT, (
        f"accumulate cost grows as rows^{exponent:.2f}; linear is ~1.0 and the limit is "
        f"{LINEAR_EXPONENT_LIMIT}"
    )


def test_make_set_cost_is_driven_by_units_not_rows() -> None:
    """More rows per unit must not make modeling slower.

    make_set consumes the accumulated units x code-pairs matrix, so its cost depends on
    the unit count. If this fails, something started scanning raw rows.
    """

    few_rows = _accumulate(synthetic(48, per_unit=20))
    many_rows = _accumulate(synthetic(48, per_unit=80))  # 4x rows, same 48 units
    assert len(few_rows.connection_counts) == len(many_rows.connection_counts) == 48

    few_time = _median_seconds(make_set, few_rows)
    many_time = _median_seconds(make_set, many_rows)

    ratio = many_time / max(few_time, 1e-9)
    assert ratio < 4.0, (
        f"4x the rows made make_set {ratio:.1f}x slower ({few_time:.4f}s -> "
        f"{many_time:.4f}s); it should depend on units, not rows"
    )
