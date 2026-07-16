from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from math import isinf

import numpy as np
import pandas as pd

from ena_python.exceptions import ValidationError


@lru_cache(maxsize=128)
def _ut_indices(n_codes: int) -> tuple[np.ndarray, np.ndarray]:
    """Cached column indices for the upper-triangle pair order.

    `(left, right)` such that `matrix[:, left] * matrix[:, right]` yields the code-pair
    products in rENA's order. Cached because the hot paths ask for the same handful of
    code counts over and over, and rebuilding a list of tuples per row was a large part
    of the old cost.

    The arrays are returned read-only: they are shared across every caller, so a mutation
    would corrupt unrelated results.
    """

    if n_codes < 0:
        raise ValidationError("n_codes must be non-negative")
    left = np.fromiter((j for i in range(1, n_codes) for j in range(i)), dtype=np.intp, count=-1)
    right = np.fromiter((i for i in range(1, n_codes) for _ in range(i)), dtype=np.intp, count=-1)
    left.flags.writeable = False
    right.flags.writeable = False
    return left, right


def _batch_to_ut(matrix: np.ndarray) -> np.ndarray:
    """Vectorized `vector_to_ut` over every row at once: (n, codes) -> (n, pairs)."""

    left, right = _ut_indices(matrix.shape[1])
    return matrix[:, left] * matrix[:, right]


def adjacency_pairs(n_codes: int) -> list[tuple[int, int]]:
    """Return rENA upper-triangle pair order for `n_codes`.

    rENA order is `(0, 1), (0, 2), (1, 2), (0, 3), ...`, matching
    `svector_to_ut` and `vector_to_ut` in `src/ena.cpp`.
    """

    left, right = _ut_indices(n_codes)
    return [(int(j), int(i)) for j, i in zip(left, right, strict=True)]


def adjacency_names(codes: Sequence[str], sep: str = " & ") -> list[str]:
    """Create rENA-style adjacency names from code names."""

    code_list = list(codes)
    return [f"{code_list[j]}{sep}{code_list[i]}" for j, i in adjacency_pairs(len(code_list))]


def names_to_adjacency_key(codes: Sequence[str], upper_triangle: bool = True) -> pd.DataFrame:
    """Return an adjacency-key table similar to rENA `namesToAdjacencyKey`."""

    code_list = list(codes)
    rows: list[dict[str, object]] = []
    for edge_id, (source_idx, target_idx) in enumerate(adjacency_pairs(len(code_list)), start=1):
        rows.append(
            {
                "edge_id": edge_id,
                "source": code_list[source_idx],
                "target": code_list[target_idx],
                "source_index": source_idx,
                "target_index": target_idx,
                "name": f"{code_list[source_idx]} & {code_list[target_idx]}",
            }
        )
        if not upper_triangle:
            rows.append(
                {
                    "edge_id": edge_id,
                    "source": code_list[target_idx],
                    "target": code_list[source_idx],
                    "source_index": target_idx,
                    "target_index": source_idx,
                    "name": f"{code_list[target_idx]} & {code_list[source_idx]}",
                }
            )
    return pd.DataFrame(rows)


def vector_to_ut(vector: Sequence[float] | np.ndarray) -> np.ndarray:
    """Convert one code vector to rENA's upper-triangle co-occurrence vector."""

    arr = np.asarray(vector, dtype=float).reshape(-1)
    left, right = _ut_indices(arr.size)
    return arr[left] * arr[right]


def rows_to_co_occurrences(
    rows: pd.DataFrame | np.ndarray,
    *,
    binary: bool = True,
    columns: Sequence[str] | None = None,
) -> pd.DataFrame | np.ndarray:
    """Convert code rows to co-occurrence rows.

    If a DataFrame is provided, a DataFrame with rENA-style adjacency columns is
    returned. If an ndarray is provided, an ndarray is returned.
    """

    if isinstance(rows, pd.DataFrame):
        matrix = rows.to_numpy(dtype=float)
    else:
        matrix = np.asarray(rows, dtype=float)
    if matrix.ndim != 2:
        raise ValidationError("rows must be a 2D matrix or DataFrame")

    out = _batch_to_ut(matrix)
    if binary:
        out = (out > 0).astype(float)

    if isinstance(rows, pd.DataFrame):
        names = adjacency_names(list(rows.columns) if columns is None else list(columns))
        return pd.DataFrame(out, index=rows.index, columns=names)
    return out


def _coerce_window(value: int | float | str) -> float:
    if isinstance(value, str):
        if "inf" in value.lower() or value.lower() == "conversation":
            return float("inf")
        return float(value)
    return float(value)


def ref_window_matrix(
    rows: pd.DataFrame | np.ndarray,
    *,
    window_size_back: int | float | str = 1,
    window_size_forward: int | float | str = 0,
    binary: bool = True,
    columns: Sequence[str] | None = None,
) -> pd.DataFrame | np.ndarray:
    """Compute rENA moving-stanza co-occurrences for one conversation.

    This mirrors the `ref_window_df` algorithm from rENA's Rcpp source. The
    function assumes `rows` belongs to a single conversation; callers should
    group by conversation before invoking it.
    """

    if isinstance(rows, pd.DataFrame):
        matrix = rows.to_numpy(dtype=float)
    else:
        matrix = np.asarray(rows, dtype=float)
    if matrix.ndim != 2:
        raise ValidationError("rows must be a 2D matrix or DataFrame")

    n_rows, n_codes = matrix.shape
    back = _coerce_window(window_size_back)
    forward = _coerce_window(window_size_forward)

    if n_rows == 0:
        out = np.zeros((0, len(_ut_indices(n_codes)[0])), dtype=float)
    else:
        # Every quantity rENA needs per row -- the window, its head, its tail -- is the
        # sum of a *contiguous* run of rows. Prefix sums turn each of those into one
        # subtraction, `prefix[stop] - prefix[start]`, so the whole thing becomes array
        # arithmetic and the per-row Python loop disappears.
        #
        # Exactness: code columns are 0/1, so these sums are small integers held exactly
        # in float64 and `prefix[stop] - prefix[start]` equals a fresh sum bit-for-bit.
        # tests/test_matrix.py pins the kernel against rENA's compiled ref_window_df.
        prefix = np.zeros((n_rows + 1, n_codes), dtype=float)
        np.cumsum(matrix, axis=0, out=prefix[1:])

        rows_idx = np.arange(n_rows, dtype=np.intp)
        if isinf(back):
            earliest = np.zeros(n_rows, dtype=np.intp)
        elif back == 0:
            earliest = rows_idx.copy()
        else:
            earliest = np.maximum(0, rows_idx - (int(back) - 1))

        if isinf(forward):
            last = np.full(n_rows, n_rows - 1, dtype=np.intp)
        else:
            last = np.minimum(n_rows - 1, rows_idx + int(forward))

        window_sum = prefix[last + 1] - prefix[earliest]
        n_window_rows = last - earliest + 1

        # Head subtraction. rENA clamps an infinite forward window to the row count
        # rather than 0 (ena.cpp:236), which drives `headRows` <= 0 and skips the
        # subtraction entirely (ena.cpp:274-276); substituting 0 would remove a head
        # rENA keeps.
        effective_forward = float(n_rows) if isinf(forward) else forward
        head_rows = (n_window_rows - 1 - effective_forward).astype(np.intp)
        head_active = (n_window_rows > 0) & (back > 1) & (rows_idx >= 1) & (head_rows > 0)
        # Zeroing the inactive rows makes their slice empty, so the sum is 0 and the
        # subtraction below is a no-op -- no branch needed.
        head_rows = np.where(head_active, head_rows, 0)
        head_sum = prefix[earliest + head_rows] - prefix[earliest]

        tail_rows = last - rows_idx
        tail_active = (n_window_rows > 0) & (forward > 0) & (last <= n_rows - 1) & (tail_rows > 0)
        tail_rows = np.where(tail_active, tail_rows, 0)
        tail_sum = prefix[last + 1] - prefix[last + 1 - tail_rows]

        out = _batch_to_ut(window_sum) - _batch_to_ut(head_sum) - _batch_to_ut(tail_sum)

    if binary:
        out = (out > 0).astype(float)

    if isinstance(rows, pd.DataFrame):
        names = adjacency_names(list(rows.columns) if columns is None else list(columns))
        return pd.DataFrame(out, index=rows.index, columns=names)
    return out


def connection_matrix(vector: Sequence[float] | pd.Series, codes: Sequence[str]) -> pd.DataFrame:
    """Convert an adjacency vector into a symmetric square connection matrix."""

    values = np.asarray(vector, dtype=float).reshape(-1)
    code_list = list(codes)
    pairs = adjacency_pairs(len(code_list))
    if len(values) != len(pairs):
        raise ValidationError(
            f"Expected {len(pairs)} values for {len(code_list)} codes, got {len(values)}"
        )
    mat = np.zeros((len(code_list), len(code_list)), dtype=float)
    for value, (j, i) in zip(values, pairs, strict=True):
        mat[j, i] = value
        mat[i, j] = value
    return pd.DataFrame(mat, index=code_list, columns=code_list)


# rENA-compatible aliases
svector_to_ut = adjacency_names
namesToAdjacencyKey = names_to_adjacency_key
