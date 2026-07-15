# pyENA

[![CI](https://github.com/HUDongpin/pyENA/actions/workflows/ci.yml/badge.svg)](https://github.com/HUDongpin/pyENA/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-GPL--3.0--only-blue)](LICENSE)

**pyENA** is a Python implementation of [Epistemic Network Analysis](https://www.epistemicnetwork.org/), ported from the R package [rENA](https://gitlab.com/epistemic-analytics/qe-packages/rENA).

It is a standalone library: `import pyena` needs only NumPy, pandas, and SciPy. No R, no Node, no server, and no network access. That keeps it usable in a notebook, in a script, or in browser Python (Pyodide).

> **Status: early release (0.1.0).** The core pipeline — accumulation, the moving-stanza window, normalization, centering, SVD projection, node positioning, and mean rotation — is checked numerically against real rENA 0.3.1. Other parts are not; see [Parity with rENA](#parity-with-rena) for exactly which. The API may still change.

## Install

```bash
pip install git+https://github.com/HUDongpin/pyENA
```

pyENA is not on PyPI: the `pyena` name is already taken by an unrelated project.

Optional extras:

```bash
pip install "pyENA[plot] @ git+https://github.com/HUDongpin/pyENA"    # Plotly figures
pip install "pyENA[web] @ git+https://github.com/HUDongpin/pyENA"     # FastAPI service
pip install "pyENA[parquet] @ git+https://github.com/HUDongpin/pyENA" # .parquet input
```

## Quick start

```python
import pandas as pd
from pyena import ena

rows = pd.DataFrame(
    {
        "UserName": ["u1", "u1", "u2", "u2"],
        "Condition": ["A", "A", "B", "B"],
        "GroupName": ["g1", "g1", "g2", "g2"],
        "Data": [1, 0, 1, 1],
        "Design": [0, 1, 1, 0],
        "Collaboration": [1, 1, 0, 1],
    }
)

set_ = ena(
    data=rows,
    codes=["Data", "Design", "Collaboration"],
    units=["Condition", "UserName"],
    conversation=["Condition", "GroupName"],
)

print(set_.points)      # unit positions in ENA space
print(set_.variance)    # variance explained, per dimension
```

### Step by step

```python
from pyena import accumulate, make_set

data = accumulate(
    rows,
    units=["Condition", "UserName"],
    conversation=["Condition", "GroupName"],
    codes=["Data", "Design", "Collaboration"],
)
set_ = make_set(data, dimensions=2)

payload = set_.to_dict()  # JSON-friendly: NaN -> None, NumPy scalars -> Python scalars
```

`to_dict()` does **not** include your input dataset. ENA is often run over discourse
transcripts that carry personal data, so results do not echo the source back by
default. Pass `to_dict(include_raw=True)` if you want `raw` and
`row_connection_counts` in the payload.

## Input data

One row per coded line. Columns:

| Column kind | Meaning |
|---|---|
| **units** | Who/what the network is about (e.g. `Condition`, `UserName`) |
| **conversation** | Which lines can connect to each other |
| **codes** | Binary 0/1 columns, one per code |
| **metadata** | Optional; carried through to results |

Metadata must be constant within a unit. A metadata column that varies inside a unit has no unit-level value, so it is dropped and a `UserWarning` names it.

## Interpreting the output

- `set_.points` — unit coordinates for the retained `dimensions`.
- `set_.variance` — variance explained for **every** dimension, normalized by the total across all of them (matching rENA). The first two entries sum to less than 1 whenever the data has rank > 2.
- `set_.rotation.eigenvalues` — `prcomp` `sdev²` (`s²/(n−1)`) for every dimension, as in rENA.
- `set_.nodes` — code node positions.

**SVD signs are not canonical.** As in any SVD, an axis may be mirrored relative to rENA or across platforms. Compare sign-aligned (see `_sign_align` in `tests/test_r_oracle_parity.py`).

## Plotting and serving

```python
from pyena.plotting import add_network, add_nodes, add_points, ena_plot

fig = ena_plot(set_)
add_network(fig)
add_points(fig)
add_nodes(fig)
fig.to_json()
```

```bash
uvicorn pyena.web.api:app --reload   # /accumulate, /model, /ena, /plot
```

The web app is for **localhost/trusted use**: no authentication, and a row cap
(`PYENA_WEB_MAX_ROWS`, default 100000) is its only DoS guard. Put your own auth and
limits in front of it before exposing it.

## CLI

```bash
pyena inspect examples/cli_sample.csv

pyena ena examples/cli_sample.csv \
  --units unit --conversation conv --codes A B C \
  --metadata group score --window-size-back 2 \
  --output ena.json
```

Reads CSV, TSV, and Parquet (Parquet needs `pyENA[parquet]`). `--include-raw` echoes the input into the JSON. See [`docs/cli_usage.md`](docs/cli_usage.md).

## Parity with rENA

Golden fixtures are generated from **real, compiled rENA 0.3.1** and stamped with provenance; the test suite refuses a fixture built from anything less authoritative. Be aware of what is and isn't covered:

| Area | Checked against rENA? |
|---|---|
| EndPoint accumulation, moving-stanza window | **Yes** — incl. infinite windows vs the compiled C++ kernel |
| Conversation window | **Yes** — accumulation and full model |
| AccumulatedTrajectory / SeparateTrajectory | **Yes** — accumulation and full model |
| Sphere/skip normalization, centering | **Yes** |
| SVD rotation, points, node positions, centroids | **Yes** (sign-aligned) |
| `variance`, `eigenvalues` | **Yes** — incl. a rank-3 case where a truncated denominator is wrong |
| Generalized rotation (`gmr`) | **Yes** — numeric and categorical targets, and x+y |
| hENA regression / regression_2 | **Yes** for the x axis; y axis diverges by design (see below) |
| hENA `rotation_h` | **Yes** — incl. control variables |
| Mean rotation | Partly — `MR1`/`SVD2` only |
| Cohen's d, `ena_correlations` | **No** |

### Known divergence: two-formula regression rotation

Given both `x_var` and `y_var`, `rotate_by_regression` returns a **different y axis than rENA** — deliberately.

rENA means to regress y on the x-deflated points (`ena.rotate.by.regression.R` sets `V <- defA` first), but that assignment never takes effect: its `with.ena.matrix` helper rebinds `V` to the raw points unless passed a `V =` argument, and a refactor dropped it. rENA therefore regresses y on undeflated points and returns axes that are strongly collinear (cosine ~0.8–0.97 on our fixtures), making its "2D" projection nearly one-dimensional. Its sibling `ena.rotate.by.generalized` deflates correctly on the same data.

pyENA deflates, so its axes are orthogonal. The x axis matches rENA exactly. If rENA fixes this, pyENA will match it column-for-column.

pyENA also names regression axes after the predictor (`score_reg`) where rENA names them after the first edge (`A & B_reg`) — an rENA naming bug from the same string/formula confusion. Names are cosmetic; the vectors match.

See [`docs/testing_strategy.md`](docs/testing_strategy.md) and [`reference/README.md`](reference/README.md).

## Development

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev,plot,web]"
pytest
```

```bash
ruff check . && ruff format --check . && mypy src/pyena && pytest
```

Regenerating fixtures needs R with rENA installed (`install.packages("rENA")`) — see [`reference/README.md`](reference/README.md). Everyday development does not need R.

## Relationship to rENA, and citation

pyENA is an independent port. It is **not** affiliated with or endorsed by the rENA authors. All credit for the ENA method and the reference implementation belongs to the [Epistemic Analytics](https://www.epistemicnetwork.org/) group. If you use pyENA in research, cite the original ENA literature and rENA; see [`docs/migration_guide.md`](docs/migration_guide.md) for the R-to-Python API map.

There is a separate, unrelated `pyena` package on PyPI by another author. This project is not it.

## License

GPL-3.0-only, matching rENA (GPL-3), since pyENA is a derivative port. See [LICENSE](LICENSE).
