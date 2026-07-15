from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from ena_python.exceptions import ValidationError
from ena_python.models import ENAData, ENASet
from ena_python.normalize import sphere_norm
from ena_python.rotation import (
    project,
    rotate_by_generalized,
    rotate_by_mean,
    rotate_by_regression,
    rotate_by_regression_2,
    rotation_h,
    svd_rotation,
)


def _numeric_line_weights(
    enadata: ENAData,
    norm_by: Callable[[pd.DataFrame], pd.DataFrame | np.ndarray],
) -> pd.DataFrame:
    numeric_counts = enadata.connection_counts.loc[:, enadata.adjacency_names].astype(float)
    line_weights = norm_by(numeric_counts)
    if isinstance(line_weights, np.ndarray):
        line_weights = pd.DataFrame(
            line_weights, index=numeric_counts.index, columns=numeric_counts.columns
        )
    return line_weights.astype(float)


def _center_line_weights(
    line_weights: pd.DataFrame,
    *,
    center_align_to_origin: bool,
    rotation_center_vec: np.ndarray | None = None,
) -> tuple[pd.DataFrame, np.ndarray]:
    non_zero = line_weights.sum(axis=1) != 0
    if rotation_center_vec is not None:
        center_vec = np.asarray(rotation_center_vec, dtype=float)
        if center_vec.size != line_weights.shape[1]:
            raise ValidationError("Supplied rotation.set center vector has the wrong length")
    elif center_align_to_origin:
        if not non_zero.any():
            raise ValidationError(
                "There were no co-occurrences of codes for any of the units within the model as defined."
            )
        center_vec = line_weights.loc[non_zero].mean(axis=0).to_numpy()
    else:
        center_vec = line_weights.mean(axis=0).to_numpy()

    if center_align_to_origin:
        centered = line_weights.copy()
        centered.loc[non_zero, :] = centered.loc[non_zero, :] - center_vec
    else:
        centered = line_weights - center_vec
    return centered, center_vec


def _node_weights(line_weights: pd.DataFrame) -> np.ndarray:
    weights_arr = line_weights.to_numpy(dtype=float)
    upper_tri_size = weights_arr.shape[1]
    num_nodes = int(np.ceil(np.sqrt(2 * upper_tri_size)) ** 2 - (2 * upper_tri_size))
    weights = np.zeros((weights_arr.shape[0], num_nodes), dtype=float)
    for row_index, row in enumerate(weights_arr):
        edge_index = 0
        for target_minus_one in range(num_nodes - 1):
            for source in range(target_minus_one + 1):
                weight = 0.5 * row[edge_index]
                weights[row_index, target_minus_one + 1] += weight
                weights[row_index, source] += weight
                edge_index += 1

    lengths = np.abs(weights).sum(axis=1)
    lengths[lengths < 0.0001] = 0.0001
    return weights / lengths[:, None]


def lws_lsq_positions(
    line_weights: pd.DataFrame,
    points: pd.DataFrame,
    *,
    codes: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Least-squares node positions matching rENA `lws_lsq_positions`."""

    weights = _node_weights(line_weights)
    points_arr = points.to_numpy(dtype=float)
    ss_a = weights.T @ weights
    node_axes = np.zeros((points_arr.shape[1], weights.shape[1]), dtype=float)
    for dim in range(points_arr.shape[1]):
        ss_b = weights.T @ points_arr[:, dim]
        try:
            node_axes[dim, :] = np.linalg.solve(ss_a, ss_b)
        except np.linalg.LinAlgError:
            node_axes[dim, :] = np.linalg.lstsq(ss_a, ss_b, rcond=None)[0]

    nodes_numeric = node_axes.T
    centroids_numeric = (node_axes @ weights.T).T
    nodes = pd.DataFrame(nodes_numeric, columns=list(points.columns))
    nodes.insert(0, "code", codes)
    centroids = pd.DataFrame(centroids_numeric, columns=list(points.columns))
    return nodes, centroids


def _centroids_from_nodes(
    line_weights: pd.DataFrame,
    nodes: pd.DataFrame,
    *,
    unit_labels: pd.Series,
) -> pd.DataFrame:
    weights = _node_weights(line_weights)
    node_numeric = nodes.drop(columns=["code"], errors="ignore").to_numpy(dtype=float)
    values = weights @ node_numeric
    centroids = pd.DataFrame(
        values, columns=list(nodes.drop(columns=["code"], errors="ignore").columns)
    )
    centroids.insert(0, "unit", unit_labels.reset_index(drop=True))
    return centroids


def _point_labels(enadata: ENAData) -> pd.DataFrame:
    """Identifier columns to prepend to projected points.

    rENA binds the trajectory frame for Trajectory models and the metadata frame
    otherwise (`ena.make.set.R:257-262`). Trajectory points are one row per
    unit-and-step, so without the conversation column there is no way to tell the
    steps apart or order them -- which is the whole point of a trajectory.

    pyENA keeps any extra metadata columns alongside the trajectory columns. rENA
    drops them here; carrying them is a superset, so every rENA column is still
    present with the same values, and callers can still group or color points by
    metadata.
    """

    meta = enadata.meta_data.reset_index(drop=True)
    if "Trajectory" not in (enadata.model_type or "") or enadata.trajectories is None:
        return meta

    trajectories = enadata.trajectories.reset_index(drop=True)
    extra = [col for col in meta.columns if col not in trajectories.columns]
    if not extra:
        return trajectories
    return pd.concat([trajectories, meta.loc[:, extra]], axis=1)


def make_set(
    enadata: ENAData,
    *,
    dimensions: int = 2,
    norm_by: Callable[[pd.DataFrame], pd.DataFrame | np.ndarray] = sphere_norm,
    rotation_by: Callable[..., Any] | None = svd_rotation,
    rotation_params: Any = None,
    center_align_to_origin: bool = True,
    rotation_set: Any = None,
    **kwargs: Any,
) -> ENASet:
    """Create an ENA model/set from accumulated data.

    This ports the central path of rENA `ena.make.set`: normalize line weights,
    center, compute SVD rotation, and project points. Rotation reuse, mean
    rotation, regression rotation, and node optimization are left as explicit
    future porting tasks.
    """

    line_weights_numeric = _numeric_line_weights(enadata, norm_by)
    line_weights = pd.concat(
        [enadata.meta_data.reset_index(drop=True), line_weights_numeric], axis=1
    )

    supplied_rotation = rotation_set is not None
    if supplied_rotation:
        if not hasattr(rotation_set, "rotation") or not hasattr(rotation_set, "center_vec"):
            raise ValidationError("Supplied rotation.set is not an instance of ENARotationSet")
        if rotation_set.center_vec is None:
            raise ValidationError("Supplied rotation.set does not have a center vector")
        if getattr(rotation_set, "node_positions", None) is None:
            raise ValidationError(
                "Unable to determine the node positions from the supplied rotation.set"
            )

    centered_numeric, center_vec = _center_line_weights(
        line_weights_numeric,
        center_align_to_origin=center_align_to_origin,
        rotation_center_vec=rotation_set.center_vec if supplied_rotation else None,
    )
    points_for_projection = pd.concat(
        [enadata.meta_data.reset_index(drop=True), centered_numeric], axis=1
    )

    if supplied_rotation:
        rotation = rotation_set
    elif rotation_by is None:
        raise ValidationError("Unable to find or create a rotation set")
    elif rotation_by is rotate_by_mean:
        rotation = rotate_by_mean(
            centered_numeric,
            groups=rotation_params,
            unit_labels=enadata.meta_data["ENA_UNIT"].astype(str).tolist(),
            line_weight_columns=enadata.adjacency_names,
            codes=enadata.codes,
            dimensions=dimensions,
        )
    elif rotation_by in {
        rotate_by_generalized,
        rotate_by_regression,
        rotate_by_regression_2,
        rotation_h,
    }:
        rotation = rotation_by(
            centered_numeric,
            params=rotation_params,
            meta_data=enadata.meta_data.reset_index(drop=True),
            codes=enadata.codes,
            dimensions=dimensions,
        )
    else:
        rotation = rotation_by(centered_numeric, codes=enadata.codes, dimensions=dimensions)
    rotation.center_vec = center_vec

    projected = project(centered_numeric, rotation)
    points = pd.concat([_point_labels(enadata), projected.reset_index(drop=True)], axis=1)

    if supplied_rotation:
        nodes = rotation.node_positions.copy()
        centroids = _centroids_from_nodes(
            line_weights_numeric,
            nodes,
            unit_labels=enadata.meta_data["ENA_UNIT"].astype(str),
        )
    else:
        nodes, centroid_values = lws_lsq_positions(
            line_weights_numeric,
            projected,
            codes=enadata.codes,
        )
        centroids = centroid_values.copy()
        centroids.insert(
            0, "unit", enadata.meta_data["ENA_UNIT"].astype(str).reset_index(drop=True)
        )
        rotation.node_positions = nodes

    # rENA projects onto the complete rotation and normalizes each dimension's
    # variance by the total across *all* dimensions (ena.make.set.R:332-335).
    # Normalizing over only the retained dimensions would overstate every
    # retained share whenever rank(points) > dimensions.
    full_rotation = (
        rotation.full_rotation if rotation.full_rotation is not None else rotation.rotation
    )
    full_projected = project(centered_numeric, full_rotation)
    full_var = full_projected.var(axis=0, ddof=1)
    total_var = full_var.sum()
    variance = full_var / total_var if total_var != 0 else full_var

    return ENASet(
        data=enadata,
        line_weights=line_weights,
        points_for_projection=points_for_projection,
        rotation=rotation,
        points=points,
        dimensions=dimensions,
        nodes=nodes,
        centroids=centroids,
        variance=variance,
        function_params={
            "dimensions": dimensions,
            "center_align_to_origin": center_align_to_origin,
            "rotation_by": getattr(rotation_by, "__name__", None)
            if rotation_by is not None
            else None,
            **kwargs,
        },
    )


def model(enadata: ENAData, **kwargs: Any) -> ENASet:
    """Pipeline alias for `make_set`."""

    return make_set(enadata, **kwargs)


# rENA-compatible alias
ena_make_set = make_set
