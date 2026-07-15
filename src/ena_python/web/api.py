"""Optional FastAPI service for ena-python.

**Intended for localhost / trusted-network use.** The endpoints run unbounded
linear algebra over caller-supplied data and have no authentication. `max_rows`
caps the obvious algorithmic-DoS path, but binding this app to a public
interface is not a supported configuration -- put it behind your own
authentication and request limits first.
"""

# NOTE: deliberately no `from __future__ import annotations` here.
# `ENARequest` is defined inside create_app(), so PEP 563 string annotations would
# be resolved by FastAPI against this module's globals, where that local class does
# not exist -- FastAPI then silently demotes the body model to a query parameter and
# every endpoint answers 422. The union syntax below needs no future import on 3.10+.

import os
from typing import Any

import pandas as pd

from ena_python import __version__
from ena_python.accumulation import accumulate_data
from ena_python.api import ena
from ena_python.modeling import make_set
from ena_python.models import ENAData
from ena_python.plotting import add_network, add_nodes, add_points, ena_plot

DEFAULT_MAX_ROWS = 100_000
"""Rows accepted per request unless overridden.

Accumulation is a Python-level loop over rows x code-pairs, so an unbounded
request body is a cheap way to exhaust CPU/memory. Override via `create_app(
max_rows=...)` or the ENA_PYTHON_WEB_MAX_ROWS environment variable.
"""


def _resolve_max_rows(max_rows: int | None) -> int:
    if max_rows is not None:
        return max_rows
    configured = os.environ.get("ENA_PYTHON_WEB_MAX_ROWS")
    if configured:
        try:
            return int(configured)
        except ValueError as exc:
            raise ValueError(
                f"ENA_PYTHON_WEB_MAX_ROWS must be an integer, got {configured!r}"
            ) from exc
    return DEFAULT_MAX_ROWS


def create_app(*, max_rows: int | None = None) -> Any:
    """Create a FastAPI app for ENA accumulation, modeling, and plotting.

    Args:
        max_rows: Reject requests carrying more than this many rows with HTTP 413.
            Defaults to ENA_PYTHON_WEB_MAX_ROWS, else DEFAULT_MAX_ROWS.
    """

    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel, Field
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install ena-python[web] to use the FastAPI app") from exc

    row_limit = _resolve_max_rows(max_rows)

    class ENARequest(BaseModel):
        rows: list[dict[str, Any]]
        codes: list[str]
        units: list[str]
        conversation: list[str]
        metadata: list[str] = Field(default_factory=list)
        model: str = "EndPoint"
        window: str = "MovingStanzaWindow"
        window_size_back: int | float | str = 1
        window_size_forward: int | float | str = 0
        weight_by: str = "binary"
        dimensions: int = 2

    app = FastAPI(title="ena-python API", version=__version__)

    def check_size(req: ENARequest) -> None:
        if len(req.rows) > row_limit:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Request carries {len(req.rows)} rows, above the {row_limit}-row limit. "
                    "Raise it with ENA_PYTHON_WEB_MAX_ROWS or create_app(max_rows=...)."
                ),
            )

    def accumulate_request(req: ENARequest) -> ENAData:
        check_size(req)
        return accumulate_data(
            pd.DataFrame(req.rows),
            codes=req.codes,
            units=req.units,
            conversation=req.conversation,
            metadata=req.metadata,
            model=req.model,
            window=req.window,
            window_size_back=req.window_size_back,
            window_size_forward=req.window_size_forward,
            weight_by=req.weight_by,
        )

    @app.post("/accumulate")
    def run_accumulate(req: ENARequest) -> dict[str, Any]:
        return accumulate_request(req).to_dict()

    @app.post("/model")
    def run_model(req: ENARequest) -> dict[str, Any]:
        return make_set(accumulate_request(req), dimensions=req.dimensions).to_dict()

    @app.post("/ena")
    def run_ena(req: ENARequest) -> dict[str, Any]:
        check_size(req)
        result = ena(
            pd.DataFrame(req.rows),
            codes=req.codes,
            units=req.units,
            conversation=req.conversation,
            metadata=req.metadata,
            model=req.model,
            window=req.window,
            window_size_back=req.window_size_back,
            window_size_forward=req.window_size_forward,
            weight_by=req.weight_by,
            dimensions=req.dimensions,
        )
        return result.to_dict()

    @app.post("/plot")
    def run_plot(req: ENARequest) -> dict[str, Any]:
        set_ = make_set(accumulate_request(req), dimensions=req.dimensions)
        fig = ena_plot(set_)
        add_network(fig)
        add_points(fig)
        add_nodes(fig)
        return fig.to_dict()

    return app


_app: Any = None


def __getattr__(name: str) -> Any:
    """Build the module-level `app` on first access rather than at import.

    `uvicorn ena_python.web.api:app` still works, because uvicorn resolves the
    attribute. But merely importing this module -- which a test collector or a
    documentation tool may do -- no longer constructs a FastAPI instance, and no
    longer hard-requires the [web] extra to be installed.
    """

    if name == "app":
        global _app
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
