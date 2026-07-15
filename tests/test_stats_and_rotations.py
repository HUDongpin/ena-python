from __future__ import annotations

import numpy as np
import pandas as pd

from pyena import accumulate, make_set
from pyena.rotation import (
    rotate_by_generalized,
    rotate_by_regression,
    rotate_by_regression_2,
    rotation_h,
)
from pyena.stats import cohens_d, ena_correlation, ena_correlations


def sample_rotation_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "unit": ["u1", "u1", "u2", "u2", "u3", "u3", "u4", "u4"],
            "conv": ["c1", "c1", "c1", "c1", "c1", "c1", "c1", "c1"],
            "group": ["a", "a", "b", "b", "a", "a", "b", "b"],
            "score": [1, 1, 2, 2, 3, 3, 4, 4],
            "A": [1, 0, 1, 0, 1, 1, 0, 0],
            "B": [0, 1, 1, 0, 1, 0, 1, 0],
            "C": [0, 1, 0, 1, 0, 1, 1, 1],
        }
    )


def sample_accumulation():
    return accumulate(
        sample_rotation_df(),
        units="unit",
        conversation="conv",
        metadata=["group", "score"],
        codes=["A", "B", "C"],
        window_size_back=2,
    )


def test_cohens_d_matches_r_formula() -> None:
    assert cohens_d([1, 2, 3], [2, 3, 4]) == 1.0


def test_ena_correlation_outputs_confidence_intervals() -> None:
    points = np.array([[0.0, 0.0], [1.0, 2.0], [2.0, 1.0], [3.0, 3.0]])
    centroids = np.array([[0.0, 0.0], [0.8, 2.2], [2.2, 1.1], [2.9, 3.2]])

    got = ena_correlation(points, centroids)

    assert list(got.columns) == ["r", "ci_lower", "ci_upper"]
    assert got.shape == (2, 3)
    assert np.isfinite(got.to_numpy(dtype=float)).all()


def test_ena_correlations_accepts_enaset() -> None:
    got = ena_correlations(make_set(sample_accumulation()))

    assert list(got.columns) == ["dimension", "pearson", "spearman"]
    assert got["dimension"].tolist() == ["SVD1", "SVD2"]


def test_advanced_rotation_families_are_callable() -> None:
    accum = sample_accumulation()

    generalized = make_set(
        accum,
        rotation_by=rotate_by_generalized,
        rotation_params={"x_var": "group"},
    )
    regression = make_set(
        accum,
        rotation_by=rotate_by_regression,
        rotation_params={"x_var": "V ~ score"},
    )
    regression_2 = make_set(
        accum,
        rotation_by=rotate_by_regression_2,
        rotation_params={"x_var": "score ~ V"},
    )
    hena = make_set(
        accum,
        rotation_by=rotation_h,
        rotation_params={"x_var": "score"},
    )

    assert list(generalized.rotation.rotation.columns) == ["RR1", "SVD2"]
    assert next(iter(regression.rotation.rotation.columns)) == "score_reg"
    assert next(iter(regression_2.rotation.rotation.columns)) == "score_reg"
    assert next(iter(hena.rotation.rotation.columns)) == "x_score"
