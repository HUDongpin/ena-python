from __future__ import annotations

import numpy as np
import pandas as pd


def _preserve_type(
    original: pd.DataFrame | np.ndarray, values: np.ndarray
) -> pd.DataFrame | np.ndarray:
    if isinstance(original, pd.DataFrame):
        return pd.DataFrame(values, index=original.index, columns=original.columns)
    return values


def sphere_norm(
    x: pd.DataFrame | np.ndarray, *, add_meta: bool = True
) -> pd.DataFrame | np.ndarray:
    """Row-wise L2 normalization matching rENA `fun_sphere_norm`.

    Zero rows remain zero. `add_meta` is accepted for API compatibility; callers
    should remove metadata before normalization.
    """

    del add_meta
    arr = x.to_numpy(dtype=float) if isinstance(x, pd.DataFrame) else np.asarray(x, dtype=float)
    norms = np.linalg.norm(arr, axis=1)
    out = np.zeros_like(arr, dtype=float)
    non_zero = norms > 0
    out[non_zero] = arr[non_zero] / norms[non_zero, None]
    return _preserve_type(x, out)


def skip_sphere_norm(
    x: pd.DataFrame | np.ndarray, *, add_meta: bool = True
) -> pd.DataFrame | np.ndarray:
    """Row-wise max-norm scaling matching rENA `fun_skip_sphere_norm` intent."""

    del add_meta
    arr = x.to_numpy(dtype=float) if isinstance(x, pd.DataFrame) else np.asarray(x, dtype=float)
    norms = np.linalg.norm(arr, axis=1)
    max_norm = norms.max(initial=0)
    out = arr.copy().astype(float) if max_norm == 0 else arr / max_norm
    return _preserve_type(x, out)


# rENA-compatible aliases
fun_sphere_norm = sphere_norm
fun_skip_sphere_norm = skip_sphere_norm
