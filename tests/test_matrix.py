from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ena_python import accumulate
from ena_python.matrix import (
    adjacency_names,
    connection_matrix,
    ref_window_matrix,
    rows_to_co_occurrences,
    vector_to_ut,
)


def test_adjacency_names_match_rena_order() -> None:
    assert adjacency_names(["A", "B", "C", "D"]) == [
        "A & B",
        "A & C",
        "B & C",
        "A & D",
        "B & D",
        "C & D",
    ]


def test_vector_to_ut() -> None:
    np.testing.assert_array_equal(vector_to_ut([2, 3, 5]), np.array([6, 10, 15]))


def test_rows_to_co_occurrences_binary_dataframe() -> None:
    rows = pd.DataFrame({"A": [1, 0], "B": [1, 1], "C": [0, 1]})
    got = rows_to_co_occurrences(rows, binary=True)
    assert isinstance(got, pd.DataFrame)
    assert got.to_dict(orient="list") == {
        "A & B": [1.0, 0.0],
        "A & C": [0.0, 0.0],
        "B & C": [0.0, 1.0],
    }


def test_ref_window_matrix_simple_back_two() -> None:
    rows = pd.DataFrame({"A": [1, 0, 1], "B": [0, 1, 1]})
    got = ref_window_matrix(rows, window_size_back=2, binary=False)
    assert isinstance(got, pd.DataFrame)
    assert got["A & B"].tolist() == [0.0, 1.0, 2.0]


def test_ref_window_matrix_matches_rena_compiled_kernel() -> None:
    """Pin the moving-stanza window to rENA 0.3.1's compiled `ref_window_df`.

    Expected values were produced by the real Rcpp/Armadillo kernel:
        rENA:::ref_window_df(data.frame(A=..., B=..., C=...), back, forward, FALSE)

    The infinite-forward cases guard a real divergence: rENA clamps an infinite
    forward window to the row count (ena.cpp:236), which drives headRows <= 0 and
    skips head subtraction (ena.cpp:274-276). Using 0 there instead subtracts a
    head rENA never removes.
    """

    rows = pd.DataFrame({"A": [1, 0, 1, 0], "B": [0, 1, 1, 0], "C": [1, 1, 0, 1]})
    cases = {
        (2, 0): [[0, 1, 0], [1, 1, 2], [2, 1, 1], [0, 1, 1]],
        (2, np.inf): [[2, 4, 2], [3, 5, 5], [2, 2, 4], [1, 1, 1]],
        (np.inf, np.inf): [[2, 4, 2], [3, 5, 5], [4, 6, 6], [4, 6, 6]],
        (3, 1): [[1, 2, 1], [3, 3, 4], [3, 4, 4], [2, 2, 3]],
    }
    for (back, forward), expected in cases.items():
        got = ref_window_matrix(
            rows, window_size_back=back, window_size_forward=forward, binary=False
        )
        np.testing.assert_allclose(
            got.to_numpy(dtype=float),
            np.asarray(expected, dtype=float),
            err_msg=f"window back={back} forward={forward} diverges from rENA",
        )


def test_connection_matrix() -> None:
    got = connection_matrix([1, 2, 3], ["A", "B", "C"])
    assert got.loc["A", "B"] == 1
    assert got.loc["A", "C"] == 2
    assert got.loc["B", "C"] == 3
    assert got.loc["C", "B"] == 3


def test_window_matrix_uses_cached_pair_indices() -> None:
    """The upper-triangle indices are cached and shared, so they must be read-only.

    A caller mutating them would silently corrupt every later result for that code count.
    """

    from ena_python.matrix import _ut_indices

    left, right = _ut_indices(4)
    assert not left.flags.writeable and not right.flags.writeable
    assert _ut_indices(4)[0] is left, "indices should be cached, not rebuilt"

    with pytest.raises(ValueError):
        left[0] = 99


def test_accumulation_rows_stay_aligned_with_a_duplicate_index() -> None:
    """Co-occurrences must land on the row they came from, even if index labels repeat.

    The previous implementation built one frame per conversation and stitched them with
    `pd.concat(pieces).sort_index()`. That orders rows group-by-group, and when index
    labels tie the sort cannot restore the original row order -- so a co-occurrence was
    attributed to the wrong row. Here only row 2 has A=1 and B=1, yet the old code put
    the 1 on row 1 (which is all zeros, and in a different conversation).
    """

    df = pd.DataFrame(
        {"conv": ["a", "b", "a"], "A": [0.0, 0.0, 1.0], "B": [0.0, 0.0, 1.0]},
        index=[0, 0, 0],
    )
    got = accumulate(df, units=["conv"], conversation=["conv"], codes=["A", "B"])

    # Row-level counts are what the alignment shows up in.
    per_row = got.row_connection_counts["A & B"].tolist()
    assert per_row == [0.0, 0.0, 1.0], (
        f"co-occurrence landed on the wrong row: {per_row}; only row 2 has A=1 and B=1"
    )
