from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from ena_python.models import ENARotationSet


def center(
    x: pd.DataFrame | np.ndarray, *, center_vec: np.ndarray | None = None
) -> pd.DataFrame | np.ndarray:
    """Column-center a numeric matrix, preserving DataFrame metadata."""

    arr = x.to_numpy(dtype=float) if isinstance(x, pd.DataFrame) else np.asarray(x, dtype=float)
    vec = arr.mean(axis=0) if center_vec is None else np.asarray(center_vec, dtype=float)
    out = arr - vec
    if isinstance(x, pd.DataFrame):
        return pd.DataFrame(out, index=x.index, columns=x.columns)
    return out


def svd_rotation(
    points_for_projection: pd.DataFrame | np.ndarray,
    *,
    codes: list[str] | None = None,
    dimensions: int = 2,
) -> ENARotationSet:
    """Compute an SVD/PCA rotation compatible with rENA `ena.svd`.

    rENA calls `prcomp(..., center = FALSE, scale = FALSE)` after centering has
    already happened upstream. This function therefore does not center input.
    """

    arr = (
        points_for_projection.to_numpy(dtype=float)
        if isinstance(points_for_projection, pd.DataFrame)
        else np.asarray(points_for_projection, dtype=float)
    )
    _, singular_values, vt = np.linalg.svd(arr, full_matrices=False)
    index = (
        points_for_projection.columns if isinstance(points_for_projection, pd.DataFrame) else None
    )
    full_columns = [f"SVD{i}" for i in range(1, vt.shape[0] + 1)]
    full_rotation = pd.DataFrame(vt.T, index=index, columns=full_columns)

    dims = min(dimensions, vt.shape[0])
    rotation = full_rotation.iloc[:, :dims].copy()

    # rENA stores `prcomp(...)$sdev^2` for every dimension (ena.svd.R:57). R's
    # prcomp defines sdev = singular_value / sqrt(n - 1), so squaring gives
    # s^2 / (n - 1) -- not the raw s^2, and never truncated to `dimensions`.
    n_rows = arr.shape[0]
    eigenvalues = singular_values**2 / max(n_rows - 1, 1)

    return ENARotationSet(
        rotation=rotation,
        codes=list(codes or (index if index is not None else [])),
        eigenvalues=eigenvalues,
        full_rotation=full_rotation,
    )


def project(
    x: pd.DataFrame | np.ndarray,
    rotation: ENARotationSet | pd.DataFrame | np.ndarray,
) -> pd.DataFrame:
    """Project rows through a rotation matrix."""

    arr = x.to_numpy(dtype=float) if isinstance(x, pd.DataFrame) else np.asarray(x, dtype=float)
    rot_df = rotation.rotation if isinstance(rotation, ENARotationSet) else rotation
    rot = (
        rot_df.to_numpy(dtype=float)
        if isinstance(rot_df, pd.DataFrame)
        else np.asarray(rot_df, dtype=float)
    )
    values = arr @ rot
    columns = (
        list(rot_df.columns)
        if isinstance(rot_df, pd.DataFrame)
        else [f"Dim{i + 1}" for i in range(rot.shape[1])]
    )
    index = x.index if isinstance(x, pd.DataFrame) else None
    return pd.DataFrame(values, index=index, columns=columns)


def qr_ortho(weights: pd.DataFrame | np.ndarray) -> np.ndarray:
    """Return a complete QR orthonormal basis matching rENA `qr.Q(qr(A), complete=TRUE)`."""

    arr = np.asarray(weights, dtype=float)
    return np.linalg.qr(arr, mode="complete")[0]


def orthogonal_svd(
    data: pd.DataFrame | np.ndarray, weights: pd.DataFrame | np.ndarray
) -> np.ndarray:
    """Find an orthogonal SVD basis constrained to include `weights` first.

    This ports rENA's internal `orthogonal_svd` helper used by
    `ena.rotate.by.mean`.
    """

    data_arr = np.asarray(data, dtype=float)
    weights_arr = np.asarray(weights, dtype=float)
    if weights_arr.ndim != 2 or weights_arr.shape[1] < 1:
        raise ValueError("weights must be a 2D matrix with at least one column")

    q = qr_ortho(weights_arr)
    n_weight_cols = weights_arr.shape[1]
    x_bar = data_arr @ q[:, n_weight_cols:]
    _, _, vt = np.linalg.svd(x_bar, full_matrices=False)
    remainder = q[:, n_weight_cols:] @ vt.T
    return np.column_stack([q[:, :n_weight_cols], remainder])


def _as_numeric_series(values: pd.Series) -> np.ndarray:
    if pd.api.types.is_numeric_dtype(values):
        return values.to_numpy(dtype=float)
    codes, _ = pd.factorize(values.astype(str), sort=False)
    return codes.astype(float)


def _design_matrix(meta_data: pd.DataFrame, terms: Sequence[str]) -> tuple[np.ndarray, list[str]]:
    columns = [np.ones(len(meta_data), dtype=float)]
    names = ["Intercept"]
    for term in terms:
        clean = term.strip()
        if not clean or clean == "1":
            continue
        if clean not in meta_data.columns:
            raise ValueError(f"Metadata column {clean!r} was not found")
        columns.append(_as_numeric_series(meta_data[clean]))
        names.append(clean)
    return np.column_stack(columns), names


def _parse_formula(formula: str) -> tuple[str, list[str]]:
    if "~" not in formula:
        raise ValueError("Regression rotation formulas must contain '~'")
    lhs, rhs = formula.split("~", 1)
    terms = [term.strip() for term in rhs.replace(":", "+").split("+") if term.strip()]
    return lhs.strip(), terms


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    arr = np.asarray(vector, dtype=float).reshape(-1)
    norm = np.linalg.norm(arr)
    return arr if norm == 0 else arr / norm


def _svd_remainder(deflated: np.ndarray, existing: np.ndarray) -> np.ndarray:
    _, _, vt = np.linalg.svd(deflated, full_matrices=False)
    svd_v = vt.T
    count = existing.shape[1]
    if count >= svd_v.shape[1]:
        return existing
    return np.column_stack([existing, svd_v[:, : svd_v.shape[1] - count]])


def _rotation_set_from_values(
    values: np.ndarray,
    *,
    columns: Sequence[str],
    feature_index: Sequence[str] | None,
    codes: list[str] | None,
    dimensions: int,
    eigenvalues: np.ndarray | None = None,
) -> ENARotationSet:
    dims = min(dimensions, values.shape[1])
    full_rotation = pd.DataFrame(
        values, index=list(feature_index or []) or None, columns=list(columns)
    )
    rotation = full_rotation.iloc[:, :dims].copy()
    return ENARotationSet(
        rotation=rotation,
        codes=list(codes or []),
        eigenvalues=np.asarray([] if eigenvalues is None else eigenvalues, dtype=float),
        full_rotation=full_rotation,
    )


def _linear_coefficients(y: np.ndarray, design: np.ndarray) -> np.ndarray:
    coefs = np.linalg.lstsq(design, y, rcond=None)[0]
    return np.asarray(coefs, dtype=float)


def compute_sb(points: pd.DataFrame | np.ndarray, groups: Sequence[Any] | np.ndarray) -> np.ndarray:
    """Compute rENA's between-group scatter matrix helper."""

    arr = np.asarray(points, dtype=float)
    labels = np.asarray(groups)
    total_mean = arr.mean(axis=0)
    out = np.zeros((arr.shape[1], arr.shape[1]), dtype=float)
    for label in pd.unique(labels):
        group_values = arr[labels == label]
        if len(group_values) == 0:
            continue
        diff = (group_values.mean(axis=0) - total_mean).reshape(-1, 1)
        out += len(group_values) * (diff @ diff.T)
    return out


def gmr(
    points: pd.DataFrame | np.ndarray, predictors: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generalized means rotation core.

    Returns `(rotation_vector, fitted_main_effect, target_values)`.
    """

    arr = np.asarray(points, dtype=float)
    if predictors.empty:
        raise ValueError("predictors must contain at least one column")
    target = predictors.iloc[:, 0]
    x = np.column_stack([np.ones(len(target)), _as_numeric_series(target)])
    fitted = x @ _linear_coefficients(arr, x)
    if pd.api.types.is_numeric_dtype(target):
        vector = _linear_coefficients(arr, x)[1, :]
    else:
        vector = np.linalg.svd(
            compute_sb(fitted, target.astype(str).to_numpy()), full_matrices=True
        )[2].T[:, 0]
    return _normalize_vector(vector), fitted, target.to_numpy()


def _as_group_contrasts(groups: Sequence[Any] | None) -> list[tuple[Any, Any]]:
    if groups is None:
        raise ValueError("Unable to rotate without 2 groups.")
    group_list = list(groups)
    if len(group_list) < 1:
        raise ValueError("Unable to rotate without 2 groups.")

    first = group_list[0]
    if isinstance(first, (list, tuple)) and len(first) == 2:
        return [(contrast[0], contrast[1]) for contrast in group_list]
    if len(group_list) == 2:
        return [(group_list[0], group_list[1])]
    raise ValueError("Mean rotation groups must be a pair or a sequence of pairs")


def _resolve_group_mask(mask_or_units: Any, unit_labels: Sequence[str], n_rows: int) -> np.ndarray:
    values = np.asarray(mask_or_units)
    if values.dtype == bool:
        mask = values.astype(bool).reshape(-1)
        if mask.size != n_rows:
            raise ValueError("Mean rotation group masks must match the number of rows")
        return mask

    allowed_units = {str(value) for value in values.reshape(-1)}
    return np.asarray([str(unit) in allowed_units for unit in unit_labels], dtype=bool)


def _rena_col_means(selected: np.ndarray) -> np.ndarray | float:
    if selected.shape[0] == 1:
        return float(selected.reshape(-1).mean())
    return selected.mean(axis=0)


def rotate_by_mean(
    points_for_projection: pd.DataFrame | np.ndarray,
    *,
    groups: Sequence[Any] | None,
    unit_labels: Sequence[str],
    line_weight_columns: Sequence[str] | None = None,
    codes: list[str] | None = None,
    dimensions: int = 2,
) -> ENARotationSet:
    """Compute rENA `ena.rotate.by.mean` rotation vectors.

    `groups` is either a pair of boolean masks/unit-name sequences or a sequence
    of such pairs. The first rotation dimension for each pair is the normalized
    difference between group means; remaining dimensions are filled by SVD of
    the deflated data.
    """

    arr = (
        points_for_projection.to_numpy(dtype=float)
        if isinstance(points_for_projection, pd.DataFrame)
        else np.asarray(points_for_projection, dtype=float)
    )
    if arr.ndim != 2:
        raise ValueError("points_for_projection must be a 2D matrix")
    data = arr - arr.mean(axis=0)
    deflated = data.copy()
    contrasts = _as_group_contrasts(groups)
    weights = np.zeros((data.shape[1], len(contrasts)), dtype=float)

    for contrast_index, (first_group, second_group) in enumerate(contrasts):
        first_mask = _resolve_group_mask(first_group, unit_labels, data.shape[0])
        second_mask = _resolve_group_mask(second_group, unit_labels, data.shape[0])
        if not first_mask.any() or not second_mask.any():
            raise ValueError("Mean rotation groups must each select at least one row")

        mean_diff = np.asarray(
            _rena_col_means(deflated[first_mask]) - _rena_col_means(deflated[second_mask]),
            dtype=float,
        )
        if mean_diff.ndim == 0:
            mean_diff = np.repeat(float(mean_diff.item()), data.shape[1])
        norm = np.linalg.norm(mean_diff)
        if norm == 0:
            raise ValueError("Mean rotation groups have identical means")
        mean_vector = mean_diff / norm
        deflated = deflated - (deflated @ mean_vector[:, None]) @ mean_vector[None, :]
        weights[:, contrast_index] = mean_vector

    rotation_values = orthogonal_svd(deflated, weights)
    dims = min(dimensions, rotation_values.shape[1])
    full_columns = [f"MR{i}" for i in range(1, len(contrasts) + 1)]
    full_columns.extend(f"SVD{i}" for i in range(len(contrasts) + 1, rotation_values.shape[1] + 1))
    feature_index = (
        list(points_for_projection.columns)
        if isinstance(points_for_projection, pd.DataFrame)
        else list(line_weight_columns or [])
    )
    full_rotation = pd.DataFrame(rotation_values, index=feature_index or None, columns=full_columns)
    rotation = full_rotation.iloc[:, :dims].copy()
    return ENARotationSet(
        rotation=rotation,
        codes=list(codes or []),
        eigenvalues=np.array([]),
        full_rotation=full_rotation,
    )


def rotate_by_generalized(
    points_for_projection: pd.DataFrame | np.ndarray,
    *,
    params: dict[str, Any] | None,
    meta_data: pd.DataFrame,
    codes: list[str] | None = None,
    dimensions: int = 2,
) -> ENARotationSet:
    """Port rENA generalized means rotation for the common x/y variable path."""

    if not isinstance(params, dict) or "x_var" not in params:
        raise ValueError("params must provide x_var")
    arr = (
        points_for_projection.to_numpy(dtype=float)
        if isinstance(points_for_projection, pd.DataFrame)
        else np.asarray(points_for_projection, dtype=float)
    )
    feature_index = (
        list(points_for_projection.columns)
        if isinstance(points_for_projection, pd.DataFrame)
        else []
    )

    def resolve_frame(value: Any) -> pd.DataFrame:
        if isinstance(value, pd.DataFrame):
            return value.reset_index(drop=True)
        if isinstance(value, str):
            return meta_data[[value]].reset_index(drop=True)
        return meta_data[list(value)].reset_index(drop=True)

    x_vector, vx1, target = gmr(arr, resolve_frame(params["x_var"]))
    deflated = arr - (arr @ x_vector[:, None]) @ x_vector[None, :]

    x1 = None
    selected = params.get("select_2_groups")
    if selected is not None and len(selected) == 2:
        first = deflated[np.asarray(target) == selected[0]]
        second = deflated[np.asarray(target) == selected[1]]
        if len(first) and len(second):
            candidate = first.mean(axis=0) - second.mean(axis=0)
            if np.linalg.norm(candidate) > 1e-10:
                x1 = _normalize_vector(candidate)
    if x1 is None:
        x1 = np.linalg.svd(vx1, full_matrices=False)[2].T[:, 0]
    projection = float(x1.T @ x_vector)
    if abs(projection) < 0.99:
        x1 = _normalize_vector(x1 - projection * x_vector)
        deflated = deflated - (deflated @ x1[:, None]) @ x1[None, :]

    if params.get("y_var") is not None:
        y_vector, _, _ = gmr(deflated, resolve_frame(params["y_var"]))
        y_name = "RR2"
    else:
        y_vector = np.linalg.svd(deflated, full_matrices=False)[2].T[:, 0]
        y_name = "SVD2"

    base = np.column_stack([x_vector, y_vector])
    deflated = (
        arr
        - (arr @ x_vector[:, None]) @ x_vector[None, :]
        - (arr @ y_vector[:, None]) @ y_vector[None, :]
    )
    combined = _svd_remainder(deflated, base)
    columns = ["RR1", y_name, *[f"SVD{i}" for i in range(3, combined.shape[1] + 1)]]
    return _rotation_set_from_values(
        combined,
        columns=columns,
        feature_index=feature_index,
        codes=codes,
        dimensions=dimensions,
    )


def rotate_by_regression(
    points_for_projection: pd.DataFrame | np.ndarray,
    *,
    params: dict[str, Any] | None,
    meta_data: pd.DataFrame,
    codes: list[str] | None = None,
    dimensions: int = 2,
) -> ENARotationSet:
    """Port rENA hENA regression rotation where formulas have `V` as outcome.

    Formulas are plain strings such as ``"V ~ score"``, where ``V`` stands for the ENA
    points. (rENA's own docstring shows ``"lm(formula=V ~ ...)"``, but its code calls
    ``formula(params$x_var)``, which only accepts the plain form.)

    The x vector matches rENA exactly. **The y vector deliberately does not**, when
    both ``x_var`` and ``y_var`` are given:

    rENA intends to regress y on the x-deflated points -- ``ena.rotate.by.regression.R``
    sets ``V <- defA`` before the call. That assignment has no effect: the
    ``with.ena.matrix`` helper rebinds ``V`` to the raw ``points.for.projection``
    unless a ``V =`` argument is passed (``ena.rotate.by.regression.2.R:18-29``), and a
    refactor dropped that argument -- the commented-out line above the call still shows
    it. rENA therefore regresses y on undeflated points and returns x/y axes that are
    strongly collinear (cosine ~0.8-0.97), so its "2D" projection is close to
    one-dimensional. Its sibling `rotate_by_generalized` deflates correctly on the same
    data, which is what marks this as a defect rather than a design choice.

    ena-python deflates, yielding orthogonal axes. Anyone comparing a two-formula regression
    rotation against rENA will therefore see a different y axis; that is intended. See
    `tests/test_r_oracle_parity.py::test_regression_xy_axes_are_orthogonal_unlike_rena`.
    """

    if not isinstance(params, dict) or "x_var" not in params:
        raise ValueError("params must provide x_var")
    arr = (
        points_for_projection.to_numpy(dtype=float)
        if isinstance(points_for_projection, pd.DataFrame)
        else np.asarray(points_for_projection, dtype=float)
    )
    feature_index = (
        list(points_for_projection.columns)
        if isinstance(points_for_projection, pd.DataFrame)
        else []
    )

    def vector_from_formula(formula: str, data: np.ndarray) -> tuple[np.ndarray, str]:
        _, terms = _parse_formula(formula)
        if not terms:
            raise ValueError("Regression formula must include a predictor")
        design, names = _design_matrix(meta_data, terms)
        vector = _normalize_vector(_linear_coefficients(data, design)[1, :])
        return vector, f"{names[1]}_reg"

    v1, x_name = vector_from_formula(str(params["x_var"]), arr)
    base = v1.reshape(-1, 1)
    deflated = arr - (arr @ v1[:, None]) @ v1[None, :]
    names = [x_name]
    if params.get("y_var") is not None:
        v2, y_name = vector_from_formula(str(params["y_var"]), deflated)
        base = np.column_stack([v1, v2])
        deflated = deflated - (deflated @ v2[:, None]) @ v2[None, :]
        names.append(y_name)
    combined = _svd_remainder(deflated, base)
    columns = [*names, *[f"SVD{i}" for i in range(len(names) + 1, combined.shape[1] + 1)]]
    return _rotation_set_from_values(
        combined,
        columns=columns,
        feature_index=feature_index,
        codes=codes,
        dimensions=dimensions,
    )


def rotate_by_regression_2(
    points_for_projection: pd.DataFrame | np.ndarray,
    *,
    params: dict[str, Any] | None,
    meta_data: pd.DataFrame,
    codes: list[str] | None = None,
    dimensions: int = 2,
) -> ENARotationSet:
    """Port rENA regression_2 where `V` appears on the predictor side."""

    if not isinstance(params, dict) or "x_var" not in params:
        raise ValueError("params must provide x_var")
    arr = (
        points_for_projection.to_numpy(dtype=float)
        if isinstance(points_for_projection, pd.DataFrame)
        else np.asarray(points_for_projection, dtype=float)
    )
    feature_index = (
        list(points_for_projection.columns)
        if isinstance(points_for_projection, pd.DataFrame)
        else []
    )

    def vector_from_formula(formula: str) -> tuple[np.ndarray, str]:
        lhs, terms = _parse_formula(formula)
        if lhs not in meta_data.columns:
            raise ValueError(f"Metadata column {lhs!r} was not found")
        y = _as_numeric_series(meta_data[lhs])
        extra_terms = [term for term in terms if term != "V"]
        extra, _ = _design_matrix(meta_data, extra_terms)
        design = np.column_stack([extra, arr])
        coefs = _linear_coefficients(y, design)
        vector = _normalize_vector(coefs[-arr.shape[1] :])
        return vector, f"{lhs}_reg"

    v1, x_name = vector_from_formula(str(params["x_var"]))
    base = v1.reshape(-1, 1)
    deflated = arr - (arr @ v1[:, None]) @ v1[None, :]
    names = [x_name]
    if params.get("y_var") is not None:
        v2, y_name = vector_from_formula(str(params["y_var"]))
        base = np.column_stack([v1, v2])
        deflated = deflated - (deflated @ v2[:, None]) @ v2[None, :]
        names.append(y_name)
    combined = _svd_remainder(deflated, base)
    columns = [*names, *[f"SVD{i}" for i in range(len(names) + 1, combined.shape[1] + 1)]]
    return _rotation_set_from_values(
        combined,
        columns=columns,
        feature_index=feature_index,
        codes=codes,
        dimensions=dimensions,
    )


def rotation_h(
    points_for_projection: pd.DataFrame | np.ndarray,
    *,
    params: dict[str, Any] | None,
    meta_data: pd.DataFrame,
    codes: list[str] | None = None,
    dimensions: int = 2,
) -> ENARotationSet:
    """Port the hENA regression-style rotation helper."""

    if not isinstance(params, dict) or "x_var" not in params:
        raise ValueError("params must provide x_var")
    arr = (
        points_for_projection.to_numpy(dtype=float)
        if isinstance(points_for_projection, pd.DataFrame)
        else np.asarray(points_for_projection, dtype=float)
    )
    feature_index = (
        list(points_for_projection.columns)
        if isinstance(points_for_projection, pd.DataFrame)
        else []
    )
    centered = arr - arr.mean(axis=0)

    terms = [str(params["x_var"])]
    if params.get("y_var") is not None:
        terms.append(str(params["y_var"]))
    terms.extend(params.get("control_vars") or [])
    design_meta = meta_data.copy()
    for term in terms:
        if term not in design_meta.columns:
            raise ValueError(f"Metadata column {term!r} was not found")
    if params.get("centering", True):
        for term in terms:
            design_meta[term] = (
                _as_numeric_series(design_meta[term]) - _as_numeric_series(design_meta[term]).mean()
            )

    design, names = _design_matrix(design_meta, terms)
    coefs = _linear_coefficients(centered, design)[1 : 1 + len(terms), :]
    v1 = _normalize_vector(coefs[0, :])
    base = v1.reshape(-1, 1)
    deflated = centered - (centered @ v1[:, None]) @ v1[None, :]
    columns = [f"x_{names[1]}"]
    if params.get("y_var") is not None and coefs.shape[0] > 1:
        v2 = coefs[1, :]
        v2 = _normalize_vector(v2 - float(v2.T @ v1) * v1)
        base = np.column_stack([v1, v2])
        deflated = deflated - (deflated @ v2[:, None]) @ v2[None, :]
        columns.append(f"y_{names[2]}")
    _, singular_values, _ = np.linalg.svd(deflated, full_matrices=False)
    combined = _svd_remainder(deflated, base)
    columns = [*columns, *[f"SVD{i}" for i in range(len(columns) + 1, combined.shape[1] + 1)]]
    return _rotation_set_from_values(
        combined,
        columns=columns,
        feature_index=feature_index,
        codes=codes,
        dimensions=dimensions,
        eigenvalues=singular_values**2,
    )


def rotate_by_regression_not_ported(*args: Any, **kwargs: Any) -> ENARotationSet:
    """Deprecated compatibility placeholder."""

    del args, kwargs
    raise NotImplementedError("rotate_by_regression has not been ported yet")


# rENA-compatible aliases
center_data_c = center
ena_svd = svd_rotation
ena_rotate_by_mean = rotate_by_mean
ena_rotate_by_generalized = rotate_by_generalized
ena_rotate_by_hena_regression = rotate_by_regression
ena_rotate_by_hena_regression_2 = rotate_by_regression_2
ena_rotation_h = rotation_h
