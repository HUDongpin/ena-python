from __future__ import annotations

from collections.abc import Sequence
from math import isinf

import numpy as np
import pandas as pd

from pyena.exceptions import ValidationError


def adjacency_pairs(n_codes: int) -> list[tuple[int, int]]:
    """Return rENA upper-triangle pair order for `n_codes`.

    rENA order is `(0, 1), (0, 2), (1, 2), (0, 3), ...`, matching
    `svector_to_ut` and `vector_to_ut` in `src/ena.cpp`.
    """

    if n_codes < 0:
        raise ValidationError("n_codes must be non-negative")
    return [(j, i) for i in range(1, n_codes) for j in range(i)]


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
    result = np.empty(len(adjacency_pairs(arr.size)), dtype=float)
    for pos, (j, i) in enumerate(adjacency_pairs(arr.size)):
        result[pos] = arr[j] * arr[i]
    return result


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

    pairs = adjacency_pairs(matrix.shape[1])
    out = np.empty((matrix.shape[0], len(pairs)), dtype=float)
    for pos, (j, i) in enumerate(pairs):
        out[:, pos] = matrix[:, j] * matrix[:, i]
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
    pairs = adjacency_pairs(n_codes)
    out = np.zeros((n_rows, len(pairs)), dtype=float)
    back = _coerce_window(window_size_back)
    forward = _coerce_window(window_size_forward)

    for row in range(n_rows):
        if isinf(back):
            earliest = 0
        elif back == 0:
            earliest = row
        else:
            earliest = max(0, row - (int(back) - 1))

        last = n_rows - 1 if isinf(forward) else min(n_rows - 1, row + int(forward))
        current_window = matrix[earliest : last + 1, :]
        summed = current_window.sum(axis=0)
        cooc = vector_to_ut(summed)

        n_window_rows = current_window.shape[0]
        if n_window_rows > 0 and back > 1 and row - 1 >= 0:
            # rENA clamps an infinite forward window to the row count rather than 0
            # (ena.cpp:236), which drives `headRows` <= 0 and skips head subtraction
            # entirely (ena.cpp:274-276). Substituting 0 would subtract a head that
            # rENA never removes.
            effective_forward = n_rows if isinf(forward) else forward
            head_rows = int(n_window_rows - 1 - effective_forward)
            if head_rows > 0:
                cooc -= vector_to_ut(current_window[:head_rows, :].sum(axis=0))

        if n_window_rows > 0 and forward > 0 and last <= n_rows - 1:
            tail_rows = last - row
            if tail_rows > 0:
                cooc -= vector_to_ut(current_window[-tail_rows:, :].sum(axis=0))

        out[row, :] = cooc

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
