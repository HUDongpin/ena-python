from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def read_table(path: str | Path, **kwargs: Any) -> pd.DataFrame:
    """Read CSV/TSV/Parquet data for ENA workflows.

    Parquet needs an engine (``pyarrow``), which is an optional extra so that the
    core install stays light enough for browser/Pyodide use. CSV and TSV need
    nothing beyond pandas.
    """

    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".parquet":
        try:
            return pd.read_parquet(p, **kwargs)
        except ImportError as exc:
            raise ImportError(
                "Reading .parquet files requires a Parquet engine, which is not part of "
                "the pyENA core install. Install it with: pip install 'pyENA[parquet]' "
                "(or pip install pyarrow). CSV and TSV inputs need no extra packages."
            ) from exc
    if suffix in {".tsv", ".tab"}:
        return pd.read_csv(p, sep="\t", **kwargs)
    return pd.read_csv(p, **kwargs)
