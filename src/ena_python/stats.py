from __future__ import annotations

from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from ena_python.exceptions import ValidationError
from ena_python.models import ENASet


def cohens_d(
    x: pd.Series | np.ndarray | list[float], y: pd.Series | np.ndarray | list[float]
) -> float:
    """Calculate Cohen's d for two samples, matching rENA `fun_cohens.d`.

    The result is **absolute**: rENA takes `md <- abs(mean(x) - mean(y))`
    (`R/cohens.d.R`), so d(x, y) == d(y, x) and the effect carries no direction. That
    is rENA's behaviour rather than a simplification here -- verified against the
    installed package on mirrored inputs. If you need the direction of a group
    difference, compare the group means yourself.
    """

    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    lx = len(x_arr) - 1
    ly = len(y_arr) - 1
    pooled = ((lx * x_arr.var(ddof=1)) + (ly * y_arr.var(ddof=1))) / (lx + ly)
    pooled_sd = float(np.sqrt(pooled))
    return float(abs(x_arr.mean() - y_arr.mean()) / pooled_sd)


def ena_correlation(
    points: pd.DataFrame | np.ndarray,
    centroids: pd.DataFrame | np.ndarray,
    *,
    conf_level: float = 0.95,
) -> pd.DataFrame:
    """Compute rENA Rcpp `ena_correlation` output for point/centroid differences."""

    point_arr = (
        points.to_numpy(dtype=float)
        if isinstance(points, pd.DataFrame)
        else np.asarray(points, dtype=float)
    )
    centroid_arr = (
        centroids.to_numpy(dtype=float)
        if isinstance(centroids, pd.DataFrame)
        else np.asarray(centroids, dtype=float)
    )
    pairs = list(combinations(range(point_arr.shape[0]), 2))
    if len(pairs) < 4:
        raise ValueError("At least 4 pairwise differences are required for confidence intervals")
    point_diff = np.vstack([point_arr[i] - point_arr[j] for i, j in pairs])
    centroid_diff = np.vstack([centroid_arr[i] - centroid_arr[j] for i, j in pairs])
    q = float(scipy_stats.norm.ppf((1 + conf_level) / 2))
    rows: list[dict[str, float]] = []
    for dim in range(point_arr.shape[1]):
        r = float(np.corrcoef(point_diff[:, dim], centroid_diff[:, dim])[0, 1])
        z = np.arctanh(r)
        sigma = 1 / np.sqrt(len(pairs) - 3)
        rows.append(
            {
                "r": r,
                "ci_lower": float(np.tanh(z - sigma * q)),
                "ci_upper": float(np.tanh(z + sigma * q)),
            }
        )
    return pd.DataFrame(rows)


def ena_correlations(enaset: ENASet, dims: list[str] | None = None) -> pd.DataFrame:
    """Compute Pearson and Spearman correlations between points and centroids.

    Ports rENA `ena.correlations`, which correlates the pairwise differences between
    unit points against the same differences between their centroids -- a goodness-of-fit
    measure for the projection.

    `dims` names the dimensions (default: the first two). Unlike rENA, which takes
    positional indices, any subset works here: rENA's `dims` is used both to slice the
    difference matrix and to index the slice, so anything other than `1:n` raises
    "subscript out of bounds" upstream. See docs/rena-upstream-issues.md.

    Note that a dimension can only be correlated if the model retains it: `make_set(...,
    dimensions=2)` projects points onto two dimensions, so asking for `SVD3` requires
    `dimensions=3`. rENA keeps every dimension in `points` and so never hits this.
    """

    if enaset.centroids is None:
        raise ValueError("ENASet has no centroids")
    dimension_names = (
        dims or [col for col in enaset.points.columns if col in enaset.variance.index][:2]
    )
    available = [col for col in dimension_names if col in enaset.points.columns]
    missing = [col for col in dimension_names if col not in enaset.points.columns]
    if missing:
        retained = [col for col in enaset.points.columns if col in enaset.variance.index]
        raise ValidationError(
            f"Dimension(s) {', '.join(missing)} are not in this model's points, which "
            f"retain {', '.join(retained) or 'none'}. `dimensions` in make_set() controls "
            f"how many are projected -- rebuild with make_set(data, dimensions="
            f"{max(len(dimension_names), len(retained) + 1)}) to correlate them."
        )
    missing_centroids = [col for col in available if col not in enaset.centroids.columns]
    if missing_centroids:
        raise ValidationError(
            f"Dimension(s) {', '.join(missing_centroids)} are missing from the centroids"
        )

    points = enaset.points.loc[:, dimension_names].to_numpy(dtype=float)
    centroids = enaset.centroids.loc[:, dimension_names].to_numpy(dtype=float)
    pairs = list(combinations(range(points.shape[0]), 2))
    point_diff = np.vstack([points[i] - points[j] for i, j in pairs])
    centroid_diff = np.vstack([centroids[i] - centroids[j] for i, j in pairs])
    rows: list[dict[str, Any]] = []
    for index, dim in enumerate(dimension_names):
        rows.append(
            {
                "dimension": dim,
                "pearson": float(
                    scipy_stats.pearsonr(point_diff[:, index], centroid_diff[:, index]).statistic
                ),
                "spearman": float(
                    scipy_stats.spearmanr(point_diff[:, index], centroid_diff[:, index]).statistic
                ),
            }
        )
    return pd.DataFrame(rows)


# rENA-compatible aliases
fun_cohens_d = cohens_d
fun_cohens_dot_d = cohens_d
