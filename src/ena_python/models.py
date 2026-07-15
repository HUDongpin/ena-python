from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_value(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        missing = False
    if isinstance(missing, (bool, np.bool_)) and missing:
        return None
    return value


def _df_to_records(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    if df is None:
        return []
    safe = df.astype(object).where(pd.notna(df), None)
    return [
        {str(key): _json_value(value) for key, value in record.items()}
        for record in safe.to_dict(orient="records")
    ]


def _series_to_dict(series: pd.Series | None) -> dict[str, Any]:
    if series is None:
        return {}
    return {str(key): _json_value(value) for key, value in series.to_dict().items()}


@dataclass(slots=True)
class ENAData:
    """Accumulated ENA data.

    Attributes mirror the central rENA `ENAdata`/`ena.set` fields but use explicit
    Python names and serializable DataFrames.
    """

    raw: pd.DataFrame
    units: list[str]
    conversation: list[str]
    codes: list[str]
    metadata: list[str] = field(default_factory=list)
    model_type: str = "EndPoint"
    window_type: str = "MovingStanzaWindow"
    weight_by: str = "binary"
    connection_counts: pd.DataFrame = field(default_factory=pd.DataFrame)
    row_connection_counts: pd.DataFrame = field(default_factory=pd.DataFrame)
    meta_data: pd.DataFrame = field(default_factory=pd.DataFrame)
    trajectories: pd.DataFrame = field(default_factory=pd.DataFrame)
    adjacency_names: list[str] = field(default_factory=list)
    function_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_raw: bool = False) -> dict[str, Any]:
        """Serialize to JSON-safe records.

        Args:
            include_raw: Also emit `raw` (the complete input dataset, every row and
                metadata column) and `row_connection_counts` (a per-row breakdown).
                Off by default: ENA is routinely run over discourse transcripts that
                carry personal data, and echoing the whole input back inside every
                result -- CLI output, web API responses -- widens the exposure of
                anything stored or transmitted, for payload bloat and no analytic
                gain. Turn it on when you specifically need the input echoed back.
        """

        payload: dict[str, Any] = {
            "units": self.units,
            "conversation": self.conversation,
            "codes": self.codes,
            "metadata": self.metadata,
            "model_type": self.model_type,
            "window_type": self.window_type,
            "weight_by": self.weight_by,
            "adjacency_names": self.adjacency_names,
            "meta_data": _df_to_records(self.meta_data),
            "connection_counts": _df_to_records(self.connection_counts),
            "trajectories": _df_to_records(self.trajectories),
            "function_params": _json_value(self.function_params),
        }
        if include_raw:
            payload["raw"] = _df_to_records(self.raw)
            payload["row_connection_counts"] = _df_to_records(self.row_connection_counts)
        return payload


@dataclass(slots=True)
class ENARotationSet:
    """Rotation information used to project line weights into ENA dimensions."""

    rotation: pd.DataFrame
    codes: list[str]
    eigenvalues: np.ndarray
    node_positions: pd.DataFrame | None = None
    center_vec: np.ndarray | None = None
    full_rotation: pd.DataFrame | None = None
    """Untruncated rotation across every dimension.

    `rotation` is sliced to the requested `dimensions`, but rENA derives variance
    from the complete projection (`ena.make.set.R:332-335`). Keeping the full
    matrix lets `make_set` reproduce that denominator exactly.
    """

    @property
    def rotation_matrix(self) -> pd.DataFrame:
        """rENA-compatible alias for the rotation loading matrix."""

        return self.rotation

    @property
    def nodes(self) -> pd.DataFrame | None:
        """rENA-compatible alias for node positions."""

        return self.node_positions

    def to_dict(self) -> dict[str, Any]:
        rotation_records = _df_to_records(self.rotation.reset_index(names="codes"))
        return {
            "rotation": rotation_records,
            "rotation_matrix": rotation_records,
            "codes": self.codes,
            "eigenvalues": self.eigenvalues.tolist(),
            "node_positions": _df_to_records(self.node_positions)
            if self.node_positions is not None
            else [],
            "nodes": _df_to_records(self.node_positions) if self.node_positions is not None else [],
            "center_vec": _json_value(self.center_vec) if self.center_vec is not None else None,
        }


@dataclass(slots=True)
class ENASet:
    """Modeled ENA set with line weights, rotation, points, and metadata."""

    data: ENAData
    line_weights: pd.DataFrame
    points_for_projection: pd.DataFrame
    rotation: ENARotationSet
    points: pd.DataFrame
    dimensions: int = 2
    nodes: pd.DataFrame | None = None
    centroids: pd.DataFrame | None = None
    variance: pd.Series = field(default_factory=pd.Series)
    function_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_raw: bool = False) -> dict[str, Any]:
        """Serialize to JSON-safe records.

        Args:
            include_raw: Forwarded to `ENAData.to_dict`; see there for why the input
                dataset is not echoed by default.
        """

        return {
            "data": self.data.to_dict(include_raw=include_raw),
            "dimensions": self.dimensions,
            "line_weights": _df_to_records(self.line_weights),
            "points_for_projection": _df_to_records(self.points_for_projection),
            "rotation": self.rotation.to_dict(),
            "points": _df_to_records(self.points),
            "nodes": _df_to_records(self.nodes) if self.nodes is not None else [],
            "centroids": _df_to_records(self.centroids) if self.centroids is not None else [],
            "variance": _series_to_dict(self.variance),
            "function_params": _json_value(self.function_params),
        }
