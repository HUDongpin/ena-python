from __future__ import annotations

import html
from typing import Any

import numpy as np
import pandas as pd

from ena_python.models import ENASet


def escape_label(value: Any) -> Any:
    """Escape a dataset-derived string before it reaches a Plotly text field.

    Plotly renders a limited HTML subset (``<b>``, ``<a href>``, ``<span>``, ...) in
    ``text``/``hovertext``. Unit names, code names, and metadata come from
    user-supplied datasets that may be third-party, so markup in a label would
    otherwise be interpreted when the exported HTML is opened. Escaping keeps such
    labels rendering as the literal text they are.

    Non-string values pass through untouched so numeric axes keep their types.
    """

    if isinstance(value, str):
        return html.escape(value, quote=False)
    return value


def _escape_labels(values: list[Any]) -> list[Any]:
    return [escape_label(value) for value in values]


def _as_float(value: Any) -> float:
    """Coerce a DataFrame cell to float.

    pandas types a `.loc[...]` lookup as a broad scalar union (str, bytes, date, ...),
    so calling `float()` on one fails a strict type check even though node
    coordinates are always numeric.
    """

    return float(value)


def _plotly_go() -> Any:
    try:
        import plotly.graph_objects as go
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install ena-python[plot] to use plotting") from exc
    return go


def _attach_set(fig: Any, enaset: ENASet) -> Any:
    object.__setattr__(fig, "_ena_python_set", enaset)
    return fig


def _get_set(fig: Any, enaset: ENASet | None) -> ENASet:
    if enaset is not None:
        return enaset
    stored = getattr(fig, "_ena_python_set", None)
    if stored is None:
        raise ValueError("Pass enaset=... when the figure was not created by ena_plot")
    return stored


def _json_list(values: Any) -> list[Any]:
    if values is None:
        return []
    raw_values = values.tolist() if isinstance(values, pd.Series | np.ndarray) else list(values)

    out: list[Any] = []
    for value in raw_values:
        if isinstance(value, np.generic):
            value = value.item()
        if pd.isna(value):
            out.append(None)
        else:
            out.append(value)
    return out


def _dimensions(enaset: ENASet, dimensions: tuple[str, str] | None = None) -> tuple[str, str]:
    if dimensions is not None:
        return dimensions
    dims = [col for col in enaset.points.columns if col in enaset.variance.index]
    if len(dims) < 2:
        dims = [
            col for col in enaset.points.columns if col.startswith(("SVD", "MR", "RR", "x_", "y_"))
        ]
    if len(dims) < 2:
        raise ValueError("ENASet must contain at least two plotted dimensions")
    return dims[0], dims[1]


def ena_plot(
    enaset: ENASet,
    *,
    title: str = "ENA Plot",
    dimensions: tuple[str, str] | None = None,
    scale_to: str = "network",
) -> Any:
    """Create an empty Plotly ENA figure with rENA-like axes."""

    go = _plotly_go()
    x_dim, y_dim = _dimensions(enaset, dimensions)
    fig = go.Figure()
    scale_source = (
        enaset.nodes if scale_to == "network" and enaset.nodes is not None else enaset.points
    )
    max_abs = float(
        np.nanmax(np.abs(scale_source.loc[:, [x_dim, y_dim]].to_numpy(dtype=float)))
        if len(scale_source)
        else 1.0
    )
    max_abs = max(max_abs * 1.2, 1e-9)
    fig.update_layout(
        title=title,
        xaxis={"title": x_dim, "range": [-max_abs, max_abs], "zeroline": True},
        yaxis={"title": y_dim, "range": [-max_abs, max_abs], "zeroline": True, "scaleanchor": "x"},
        template="plotly_white",
        showlegend=True,
        meta={"ena_python_dimensions": [x_dim, y_dim]},
    )
    return _attach_set(fig, enaset)


def add_points(
    fig: Any,
    *,
    enaset: ENASet | None = None,
    points: pd.DataFrame | None = None,
    group_by: str | None = None,
    name: str = "points",
    color: str | None = None,
) -> Any:
    """Add ENA points to a Plotly figure."""

    go = _plotly_go()
    set_ = _get_set(fig, enaset)
    x_dim, y_dim = _dimensions(set_)
    pts = set_.points if points is None else points
    if group_by is not None and group_by in pts.columns:
        for group, group_points in pts.groupby(group_by, sort=False, dropna=False):
            fig.add_trace(
                go.Scatter(
                    x=_json_list(group_points[x_dim]),
                    y=_json_list(group_points[y_dim]),
                    mode="markers",
                    name=escape_label(str(group)),
                    text=_escape_labels(_json_list(group_points.get("ENA_UNIT"))),
                    marker={"size": 9},
                )
            )
    else:
        marker: dict[str, Any] = {"size": 9}
        if color is not None:
            marker["color"] = color
        fig.add_trace(
            go.Scatter(
                x=_json_list(pts[x_dim]),
                y=_json_list(pts[y_dim]),
                mode="markers",
                name=name,
                text=_escape_labels(_json_list(pts.get("ENA_UNIT"))),
                marker=marker,
            )
        )
    return fig


def add_group(
    fig: Any,
    *,
    enaset: ENASet | None = None,
    points: pd.DataFrame | None = None,
    label: str = "mean",
    color: str = "black",
) -> Any:
    """Add a centroid/mean marker for a selected set of points."""

    go = _plotly_go()
    set_ = _get_set(fig, enaset)
    x_dim, y_dim = _dimensions(set_)
    pts = set_.points if points is None else points
    fig.add_trace(
        go.Scatter(
            x=[float(pts[x_dim].mean())],
            y=[float(pts[y_dim].mean())],
            mode="markers",
            name=label,
            marker={"symbol": "diamond", "size": 14, "color": color, "line": {"width": 1}},
        )
    )
    return fig


def add_nodes(fig: Any, *, enaset: ENASet | None = None, color: str = "#333333") -> Any:
    """Add code node labels to an ENA Plotly figure."""

    go = _plotly_go()
    set_ = _get_set(fig, enaset)
    if set_.nodes is None:
        raise ValueError("ENASet has no node positions")
    x_dim, y_dim = _dimensions(set_)
    fig.add_trace(
        go.Scatter(
            x=_json_list(set_.nodes[x_dim]),
            y=_json_list(set_.nodes[y_dim]),
            mode="markers+text",
            name="nodes",
            text=_escape_labels(_json_list(set_.nodes["code"])),
            textposition="top center",
            marker={"size": 11, "color": color},
        )
    )
    return fig


def add_network(
    fig: Any,
    *,
    enaset: ENASet | None = None,
    weights: pd.Series | dict[str, float] | None = None,
    name: str = "network",
    color: str = "#888888",
    edge_multiplier: float = 3.0,
) -> Any:
    """Add network edges using the ENA node positions and line weights."""

    go = _plotly_go()
    set_ = _get_set(fig, enaset)
    if set_.nodes is None:
        raise ValueError("ENASet has no node positions")
    x_dim, y_dim = _dimensions(set_)
    node_lookup = set_.nodes.set_index("code")
    if weights is None:
        edge_weights = set_.line_weights.loc[:, set_.data.adjacency_names].mean(axis=0)
    else:
        edge_weights = pd.Series(weights, dtype=float)
    first = True
    for edge_name, weight in edge_weights.items():
        if abs(float(weight)) <= 0:
            continue
        source, target = str(edge_name).split(" & ", 1)
        if source not in node_lookup.index or target not in node_lookup.index:
            continue
        fig.add_trace(
            go.Scatter(
                x=[
                    _as_float(node_lookup.loc[source, x_dim]),
                    _as_float(node_lookup.loc[target, x_dim]),
                ],
                y=[
                    _as_float(node_lookup.loc[source, y_dim]),
                    _as_float(node_lookup.loc[target, y_dim]),
                ],
                mode="lines",
                name=name if first else None,
                showlegend=first,
                line={"color": color, "width": max(abs(float(weight)) * edge_multiplier, 0.5)},
                hovertext=f"{escape_label(str(edge_name))}: {float(weight):.4g}",
            )
        )
        first = False
    return fig


def with_trajectory(
    fig: Any,
    *,
    enaset: ENASet | None = None,
    by: str = "ENA_UNIT",
    color: str = "#555555",
) -> Any:
    """Add trajectory lines grouped by a metadata column."""

    go = _plotly_go()
    set_ = _get_set(fig, enaset)
    x_dim, y_dim = _dimensions(set_)
    for group, pts in set_.points.groupby(by, sort=False, dropna=False):
        fig.add_trace(
            go.Scatter(
                x=_json_list(pts[x_dim]),
                y=_json_list(pts[y_dim]),
                mode="lines",
                name=f"{group} trajectory",
                line={"color": color, "dash": "dot"},
            )
        )
    return fig


def plot_points(enaset: ENASet, *, x: str = "SVD1", y: str = "SVD2", **kwargs: Any) -> Any:
    """Create a Plotly scatter plot of ENA points."""

    fig = ena_plot(enaset, dimensions=(x, y), **{k: v for k, v in kwargs.items() if k in {"title"}})
    return add_points(fig)


# rENA-ish aliases
plot = plot_points
ena_plot_points = add_points
ena_plot_group = add_group
ena_plot_network = add_network
ena_plot_trajectory = with_trajectory
