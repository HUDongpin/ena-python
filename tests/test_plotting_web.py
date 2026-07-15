from __future__ import annotations

import json

import pandas as pd
import pytest

from pyena import accumulate, make_set
from pyena.plotting import add_group, add_network, add_nodes, add_points, ena_plot, with_trajectory


def sample_df() -> pd.DataFrame:
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


def sample_payload() -> dict[str, object]:
    return {
        "rows": sample_df().to_dict(orient="records"),
        "codes": ["A", "B", "C"],
        "units": ["unit"],
        "conversation": ["conv"],
        "metadata": ["group", "score"],
        "window_size_back": 2,
    }


def sample_set():
    accum = accumulate(
        sample_df(),
        units="unit",
        conversation="conv",
        metadata=["group", "score"],
        codes=["A", "B", "C"],
        window_size_back=2,
    )
    return make_set(accum)


def test_plotly_helpers_build_json_serializable_figure() -> None:
    pytest.importorskip("plotly")
    set_ = sample_set()

    fig = ena_plot(set_)
    add_network(fig)
    add_points(fig, group_by="group")
    add_group(fig, label="all")
    with_trajectory(fig)
    add_nodes(fig)

    assert len(fig.data) >= 6
    json.dumps(fig.to_dict())


def test_fastapi_endpoints_return_json() -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("plotly")
    from fastapi.testclient import TestClient

    from pyena.web.api import create_app

    client = TestClient(create_app())
    payload = sample_payload()

    for path in ["/accumulate", "/model", "/ena", "/plot"]:
        response = client.post(path, json=payload)
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, dict)
        assert body

    assert "connection_counts" in client.post("/accumulate", json=payload).json()
    assert "points" in client.post("/model", json=payload).json()
    assert "data" in client.post("/plot", json=payload).json()


def test_importing_web_api_does_not_build_app() -> None:
    """The app must be built on access, not at import.

    Importing the module used to call create_app(), which both raised when the
    [web] extra was absent and constructed a server object as a side effect of an
    import.
    """

    import importlib

    module = importlib.import_module("pyena.web.api")
    importlib.reload(module)
    assert module._app is None, "importing pyena.web.api constructed the FastAPI app"

    with pytest.raises(AttributeError):
        _ = module.does_not_exist


def test_web_requests_over_row_limit_are_rejected() -> None:
    """Guards F-6: an unbounded request body is an algorithmic-DoS path."""

    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from pyena.web.api import create_app

    client = TestClient(create_app(max_rows=4))
    payload = sample_payload()  # 8 rows, above the limit of 4

    for path in ["/accumulate", "/model", "/ena"]:
        response = client.post(path, json=payload)
        assert response.status_code == 413, f"{path} accepted an over-limit request"
        assert "row limit" in response.json()["detail"]

    # A request within the limit still succeeds.
    small = dict(payload, rows=payload["rows"][:4])
    assert client.post("/accumulate", json=small).status_code == 200


def test_max_rows_env_override() -> None:
    from pyena.web.api import DEFAULT_MAX_ROWS, _resolve_max_rows

    assert _resolve_max_rows(None) == DEFAULT_MAX_ROWS
    assert _resolve_max_rows(7) == 7

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PYENA_WEB_MAX_ROWS", "11")
        assert _resolve_max_rows(None) == 11
        assert _resolve_max_rows(7) == 7, "explicit argument must win over the env var"

        mp.setenv("PYENA_WEB_MAX_ROWS", "not-an-int")
        with pytest.raises(ValueError, match="must be an integer"):
            _resolve_max_rows(None)


def test_plot_labels_are_escaped() -> None:
    """Guards F-6: dataset labels flow into Plotly text fields.

    Plotly interprets a limited HTML subset in text/hovertext, so markup in a unit
    or code name would otherwise be live in exported HTML.
    """

    pytest.importorskip("plotly")
    from pyena.plotting import escape_label

    assert escape_label("<img src=x onerror=alert(1)>") == "&lt;img src=x onerror=alert(1)&gt;"
    assert escape_label("plain unit") == "plain unit"
    assert escape_label(42) == 42, "non-strings must pass through unchanged"

    hostile = sample_df().assign(unit=lambda d: d["unit"] + "<script>alert(1)</script>")
    set_ = make_set(
        accumulate(
            hostile,
            units="unit",
            conversation="conv",
            metadata=["group", "score"],
            codes=["A", "B", "C"],
            window_size_back=2,
        )
    )
    fig = ena_plot(set_)
    add_points(fig)
    add_nodes(fig)

    payload = json.dumps(fig.to_dict())
    assert "<script>" not in payload, "raw markup reached the figure payload"
    assert "&lt;script&gt;" in payload, "expected escaped unit label in the figure"
