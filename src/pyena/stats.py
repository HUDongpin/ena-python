from __future__ import annotations

from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from pyena.models import ENASet


def cohens_d(
    x: pd.Series | np.ndarray | list[float], y: pd.Series | np.ndarray | list[float]
) -> float:
    """Calculate rENA-style absolute Cohen's d for two samples."""

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
    """Compute Pearson and Spearman correlations between points and centroids."""

    if enaset.centroids is None:
        raise ValueError("ENASet has no centroids")
    dimension_names = (
        dims or [col for col in enaset.points.columns if col in enaset.variance.index][:2]
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
