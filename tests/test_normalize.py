from __future__ import annotations

import numpy as np
import pandas as pd

from ena_python.normalize import skip_sphere_norm, sphere_norm


def test_sphere_norm_zero_rows_remain_zero() -> None:
    data = pd.DataFrame({"x": [3.0, 0.0], "y": [4.0, 0.0]})
    got = sphere_norm(data)
    assert isinstance(got, pd.DataFrame)
    np.testing.assert_allclose(got.to_numpy(), [[0.6, 0.8], [0.0, 0.0]])


def test_skip_sphere_norm_uses_max_row_norm() -> None:
    data = np.array([[3.0, 4.0], [0.0, 10.0]])
    got = skip_sphere_norm(data)
    np.testing.assert_allclose(got, [[0.3, 0.4], [0.0, 1.0]])
