# pyENA architecture

## Package layers

`pyena.matrix` contains low-level vector/matrix operations that correspond mostly to rENA's `src/ena.cpp`. The rENA sources are not vendored here; see [`reference/README.md`](../reference/README.md) to obtain them.

`pyena.accumulation` converts coded rows into ENA co-occurrence vectors. This is the most important performance path for web use.

`pyena.normalize` and `pyena.rotation` implement normalization, centering, SVD projection, and future rotation strategies.

`pyena.modeling` builds an `ENASet` from an `ENAData` object.

`pyena.api` exposes the high-level `ena()` wrapper.

`pyena.plotting` and `pyena.web` are optional layers for frontend/backend integration.

## Data objects

The R package mixes R6 objects, S3 classes, data.table, and matrix subclasses. pyENA uses dataclasses with DataFrame fields:

- `ENAData`: raw data, metadata, connection counts, trajectories, configuration
- `ENARotationSet`: rotation matrix, eigenvalues, center vector, node positions
- `ENASet`: modeled line weights, projected points, nodes, and serialization

These objects should remain JSON-friendly through `.to_dict()` methods.

## Backend strategy

The default backend should be pure NumPy/Pandas. Optional acceleration can be introduced later:

- Numba for moving-window accumulation loops
- Polars for very large CSV/dataframe workflows
- sparse matrices for high-code-count analyses

Keep backend choices behind functions/classes so the public API stays stable.
