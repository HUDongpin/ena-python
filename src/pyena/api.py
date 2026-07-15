from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import pandas as pd

from pyena.accumulation import accumulate_data
from pyena.modeling import make_set
from pyena.models import ENASet
from pyena.normalize import sphere_norm
from pyena.rotation import svd_rotation


def ena(
    data: pd.DataFrame,
    codes: Sequence[str] | str,
    units: Sequence[str] | str,
    conversation: Sequence[str] | str,
    metadata: Sequence[str] | str | None = None,
    model: str = "EndPoint",
    weight_by: str = "binary",
    window: str = "MovingStanzaWindow",
    window_size_back: int | float | str = 1,
    window_size_forward: int | float | str = 0,
    include_meta: bool = True,
    dimensions: int = 2,
    norm_by: Callable[[pd.DataFrame], pd.DataFrame | np.ndarray] = sphere_norm,
    rotation_by: Callable[..., Any] | None = svd_rotation,
    rotation_params: Any = None,
    rotation_set: Any = None,
    center_align_to_origin: bool = True,
    **kwargs: Any,
) -> ENASet:
    """High-level ENA workflow wrapper.

    This mirrors rENA's `ena(...)` convenience function while returning a Python
    `ENASet` dataclass.
    """

    enadata = accumulate_data(
        data,
        units=units,
        conversation=conversation,
        codes=codes,
        metadata=metadata,
        model=model,
        weight_by=weight_by,
        window=window,
        window_size_back=window_size_back,
        window_size_forward=window_size_forward,
        include_meta=include_meta,
        **kwargs,
    )
    return make_set(
        enadata,
        dimensions=dimensions,
        norm_by=norm_by,
        rotation_by=rotation_by,
        rotation_params=rotation_params,
        rotation_set=rotation_set,
        center_align_to_origin=center_align_to_origin,
    )
