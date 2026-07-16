from __future__ import annotations

import warnings
from collections.abc import Sequence
from math import isinf
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ena_python.exceptions import ValidationError
from ena_python.matrix import adjacency_names, ref_window_matrix, rows_to_co_occurrences
from ena_python.models import ENAData
from ena_python.types import ModelType, WindowType

_MODEL_ALIASES: dict[str, ModelType] = {
    "E": "EndPoint",
    "endpoint": "EndPoint",
    "EndPoint": "EndPoint",
    "A": "AccumulatedTrajectory",
    "accumulatedtrajectory": "AccumulatedTrajectory",
    "AccumulatedTrajectory": "AccumulatedTrajectory",
    "S": "SeparateTrajectory",
    "separatetrajectory": "SeparateTrajectory",
    "seperatetrajectory": "SeparateTrajectory",
    "SeparateTrajectory": "SeparateTrajectory",
    "SeperateTrajectory": "SeparateTrajectory",
}

_WINDOW_ALIASES: dict[str, WindowType] = {
    "MSW": "MovingStanzaWindow",
    "MS": "MovingStanzaWindow",
    "movingstanzawindow": "MovingStanzaWindow",
    "MovingStanzaWindow": "MovingStanzaWindow",
    "Moving Stanza": "MovingStanzaWindow",
    "C": "Conversation",
    "conversation": "Conversation",
    "Conversation": "Conversation",
}


def _as_columns(value: Sequence[str] | str | None, *, name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    cols = list(value)
    if not all(isinstance(col, str) for col in cols):
        raise ValidationError(f"{name} must be a string or sequence of strings")
    return cols


def _as_frame(value: pd.DataFrame | pd.Series | None, *, name: str) -> pd.DataFrame:
    if value is None:
        raise ValidationError(
            f"Accumulation requires: units, conversation, and codes; missing {name}"
        )
    if isinstance(value, pd.Series):
        frame = value.to_frame()
    elif isinstance(value, pd.DataFrame):
        frame = value.copy()
    else:
        raise ValidationError(f"{name} must be a pandas DataFrame or Series when data is omitted")
    if any(pd.isna(frame.columns)):
        raise ValidationError(f"{name} columns must be named")
    return frame


def _prepare_accumulation_frame(
    data: pd.DataFrame | None,
    *,
    units: pd.DataFrame | pd.Series | Sequence[str] | str,
    conversation: pd.DataFrame | pd.Series | Sequence[str] | str,
    codes: pd.DataFrame | pd.Series | Sequence[str] | str,
    metadata: pd.DataFrame | pd.Series | Sequence[str] | str | None,
) -> tuple[pd.DataFrame, list[str], list[str], list[str], list[str]]:
    if data is not None:
        return (
            data.copy(),
            _as_columns(units, name="units"),  # type: ignore[arg-type]
            _as_columns(conversation, name="conversation"),  # type: ignore[arg-type]
            _as_columns(codes, name="codes"),  # type: ignore[arg-type]
            _as_columns(metadata, name="metadata"),  # type: ignore[arg-type]
        )

    unit_frame = _as_frame(
        units if isinstance(units, pd.DataFrame | pd.Series) else None, name="units"
    )
    conversation_frame = _as_frame(
        conversation if isinstance(conversation, pd.DataFrame | pd.Series) else None,
        name="conversation",
    )
    code_frame = _as_frame(
        codes if isinstance(codes, pd.DataFrame | pd.Series) else None, name="codes"
    )
    metadata_frame = None
    if metadata is not None:
        metadata_frame = _as_frame(
            metadata if isinstance(metadata, pd.DataFrame | pd.Series) else None,
            name="metadata",
        )

    n_rows = len(unit_frame)
    frames = [unit_frame, conversation_frame, code_frame]
    if metadata_frame is not None:
        frames.append(metadata_frame)
    if any(len(frame) != n_rows for frame in frames):
        raise ValidationError("Data Frames do not have the same number of rows")

    all_columns = [str(col) for frame in frames for col in frame.columns]
    if len(all_columns) != len(set(all_columns)):
        raise ValidationError(
            "Combined units, conversation, codes, and metadata columns must be unique"
        )

    df = pd.concat([frame.reset_index(drop=True) for frame in frames], axis=1)
    return (
        df,
        [str(col) for col in unit_frame.columns],
        [str(col) for col in conversation_frame.columns],
        [str(col) for col in code_frame.columns],
        [str(col) for col in metadata_frame.columns] if metadata_frame is not None else [],
    )


def _merge_columns(df: pd.DataFrame, cols: Sequence[str], sep: str = "::") -> pd.Series:
    """Join key columns into rENA-style `a::b` unit/conversation labels.

    Vectorized deliberately. The obvious `.agg(sep.join, axis=1)` walks the frame row by
    row in Python and, on a realistic dataset (rENA's RS.data: 3824 rows, 87 small
    conversations), cost ~73% of the whole accumulation -- far more than the
    moving-stanza window it is usually blamed on. `Series.str.cat` does the same
    concatenation in one pass.

    Missing keys become the literal "nan", which is what `.astype(str)` + `sep.join`
    produced under pandas 2. Pandas 3 changed `.astype(str)` to leave NaN as NaN rather
    than stringifying it, which made the old row-wise join raise
    `TypeError: sequence item 0: expected str instance, float found` -- a latent
    incompatibility no test covered, because none used a NaN key. Filling explicitly
    keeps one behaviour across both.

    A NaN unit or conversation key is still questionable input; it survives here only to
    avoid changing labels for anyone already relying on it. See
    docs/porting-notes for the wider NaN policy question.
    """

    if not cols:
        raise ValidationError("Cannot merge zero columns")
    frame = df.loc[:, list(cols)].astype(str).fillna("nan")
    first = frame.iloc[:, 0]
    if frame.shape[1] == 1:
        # `str.cat` with no `others` would concatenate the column into a single string.
        return first.rename(None)
    # Pass the remaining columns as a frame rather than a list of Series: same result,
    # and it is the shape pandas-stubs actually declares.
    return first.str.cat(frame.iloc[:, 1:], sep=sep).rename(None)


def _canonical_model(model: str) -> ModelType:
    try:
        return _MODEL_ALIASES[model]
    except KeyError:
        key = model.replace("_", "").replace(" ", "").lower()
        if key in _MODEL_ALIASES:
            return _MODEL_ALIASES[key]  # type: ignore[return-value]
        raise ValidationError(f"Unknown model: {model!r}") from None


def _canonical_window(window: str) -> WindowType:
    try:
        return _WINDOW_ALIASES[window]
    except KeyError:
        key = window.replace("_", "").replace(" ", "").lower()
        if key in _WINDOW_ALIASES:
            return _WINDOW_ALIASES[key]  # type: ignore[return-value]
        raise ValidationError(f"Unknown window: {window!r}") from None


def _coerce_inf(value: int | float | str) -> int | float | str:
    if isinstance(value, str) and "inf" in value.lower():
        return float("inf")
    return value


def _validate_columns(df: pd.DataFrame, columns: Sequence[str], *, role: str) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValidationError(f"Missing {role} columns: {missing}")


def _apply_mask(
    counts: pd.DataFrame, mask: pd.DataFrame | np.ndarray | None, codes: list[str]
) -> pd.DataFrame:
    if mask is None:
        return counts
    mask_arr = (
        mask.to_numpy(dtype=float)
        if isinstance(mask, pd.DataFrame)
        else np.asarray(mask, dtype=float)
    )
    if mask_arr.shape != (len(codes), len(codes)):
        raise ValidationError(f"mask must have shape {(len(codes), len(codes))}")
    # Preserve only pair-level masks. A connection is enabled when the upper-triangle pair is non-zero.
    pairs = [(j, i) for i in range(1, len(codes)) for j in range(i)]
    mask_vec = np.asarray([mask_arr[j, i] for j, i in pairs], dtype=float)
    return counts.mul(mask_vec, axis=1)


def _conversation_window_rows(
    df: pd.DataFrame,
    *,
    conversation_cols: list[str],
    unit_cols: list[str],
    code_cols: list[str],
    binary: bool,
) -> pd.DataFrame:
    group_cols = list(dict.fromkeys([*conversation_cols, *unit_cols]))
    pieces: list[pd.DataFrame] = []
    adj_names = adjacency_names(code_cols)
    for _, group in df.groupby(group_cols, sort=False, dropna=False):
        summed = group[code_cols].sum(axis=0).to_frame().T
        cooc = rows_to_co_occurrences(summed, binary=binary, columns=code_cols)
        assert isinstance(cooc, pd.DataFrame)
        group_values = group[["ENA_UNIT", *group_cols]].iloc[[0]].reset_index(drop=True)
        pieces.append(pd.concat([group_values, cooc.reset_index(drop=True)], axis=1))
    if not pieces:
        return pd.DataFrame(columns=["ENA_UNIT", *group_cols, *adj_names])
    return pd.concat(pieces, ignore_index=True)


def _moving_stanza_windows(
    df: pd.DataFrame,
    *,
    conversation_cols: list[str],
    code_cols: list[str],
    window_size_back: int | float | str,
    window_size_forward: int | float | str,
    binary: bool,
) -> pd.DataFrame:
    adj_names = adjacency_names(code_cols)
    if df.empty:
        return pd.DataFrame(columns=adj_names, index=df.index)

    # Slice the codes once and hand each conversation a plain ndarray. Building a
    # DataFrame per conversation (and concatenating them afterwards) cost more than the
    # windowing itself on data with many short conversations -- rENA's RS.data has 87 --
    # because every group paid for a fresh Index and block manager.
    codes_matrix = df.loc[:, code_cols].to_numpy(dtype=float)
    out = np.empty((len(df), len(adj_names)), dtype=float)

    grouped = df.groupby(conversation_cols, sort=False, dropna=False)
    for positions in grouped.indices.values():
        # `indices` gives positions in original row order, which is what the moving
        # stanza window depends on -- it is order-sensitive by definition.
        block = ref_window_matrix(
            codes_matrix[positions],
            window_size_back=window_size_back,
            window_size_forward=window_size_forward,
            binary=binary,
        )
        out[positions] = block

    # Writing at original positions and then sorting reproduces the previous
    # `pd.concat(pieces).sort_index()` exactly: same rows, same index labels, same sort.
    return pd.DataFrame(out, index=df.index, columns=adj_names).sort_index()


def _metadata_for_units(
    df: pd.DataFrame,
    *,
    unit_cols: list[str],
    metadata_cols: list[str],
    include_meta: bool,
) -> pd.DataFrame:
    base_cols = ["ENA_UNIT", *unit_cols]
    meta = df.drop_duplicates("ENA_UNIT", keep="first").loc[:, base_cols].reset_index(drop=True)
    if not include_meta or not metadata_cols:
        return meta

    grouped = df.groupby("ENA_UNIT", sort=False, dropna=False)
    stable_cols = [col for col in metadata_cols if (grouped[col].nunique(dropna=False) <= 1).all()]

    # A metadata column that varies within a unit has no single unit-level value, so
    # it is dropped rather than silently reduced to one arbitrary row's value. Warn:
    # dropping a requested column without a word is the kind of thing a caller only
    # notices much later, when it is missing from a plot or an export.
    dropped = [col for col in metadata_cols if col not in stable_cols]
    if dropped:
        warnings.warn(
            f"Dropped metadata column(s) {', '.join(map(str, dropped))}: values vary "
            "within a unit, so there is no unit-level value to keep. Aggregate them "
            "to one value per unit beforehand if you need them retained.",
            UserWarning,
            stacklevel=3,
        )

    if stable_cols:
        stable = grouped[stable_cols].first().reset_index(drop=True)
        meta = pd.concat([meta, stable], axis=1)
    return meta


def accumulate_data(
    data: pd.DataFrame | None = None,
    *,
    units: pd.DataFrame | pd.Series | Sequence[str] | str,
    conversation: pd.DataFrame | pd.Series | Sequence[str] | str,
    codes: pd.DataFrame | pd.Series | Sequence[str] | str,
    metadata: pd.DataFrame | pd.Series | Sequence[str] | str | None = None,
    model: str = "EndPoint",
    weight_by: str = "binary",
    window: str = "MovingStanzaWindow",
    window_size_back: int | float | str = 1,
    window_size_forward: int | float | str = 0,
    mask: pd.DataFrame | np.ndarray | None = None,
    include_meta: bool = True,
    **kwargs: Any,
) -> ENAData:
    """Accumulate coded rows into ENA co-occurrence vectors.

    This is the Python counterpart of rENA `ena.accumulate.data`. The template
    includes core endpoint and trajectory behavior; parity work should continue
    against the rENA tests in `reference/rENA/tests/testthat`.
    """

    if data is not None and len(data) == 0:
        raise ValidationError("The provided data is NULL or empty")

    df, unit_cols, conversation_cols, code_cols, metadata_cols = _prepare_accumulation_frame(
        data,
        units=units,
        conversation=conversation,
        codes=codes,
        metadata=metadata,
    )
    if len(df) == 0:
        raise ValidationError("The provided data is NULL or empty")
    _validate_columns(df, unit_cols, role="unit")
    _validate_columns(df, conversation_cols, role="conversation")
    _validate_columns(df, code_cols, role="code")
    _validate_columns(df, metadata_cols, role="metadata")

    model_type = _canonical_model(model)
    window_type = _canonical_window(window)
    binary = weight_by == "binary"
    window_size_back = _coerce_inf(window_size_back)
    window_size_forward = _coerce_inf(window_size_forward)

    df["ENA_UNIT"] = _merge_columns(df, unit_cols, sep="::")
    adj_names = adjacency_names(code_cols)

    if window_type == "Conversation":
        row_level = _conversation_window_rows(
            df,
            conversation_cols=conversation_cols,
            unit_cols=unit_cols,
            code_cols=code_cols,
            binary=binary,
        )
    else:
        row_cooc = _moving_stanza_windows(
            df,
            conversation_cols=conversation_cols,
            code_cols=code_cols,
            window_size_back=window_size_back,
            window_size_forward=window_size_forward,
            binary=binary,
        )
        row_metadata_cols = ["ENA_UNIT", *list(dict.fromkeys([*unit_cols, *conversation_cols]))]
        row_level = pd.concat([df[row_metadata_cols], row_cooc], axis=1)

    row_level.loc[:, adj_names] = _apply_mask(row_level.loc[:, adj_names], mask, code_cols)

    if model_type == "EndPoint":
        connection_counts = row_level.groupby("ENA_UNIT", sort=False, dropna=False)[adj_names].sum()
        connection_counts = connection_counts.reset_index(drop=True)
        meta_data = _metadata_for_units(
            df,
            unit_cols=unit_cols,
            metadata_cols=metadata_cols,
            include_meta=include_meta,
        )
        trajectories = pd.DataFrame()
    else:
        trajectory_cols = ["ENA_UNIT", *list(dict.fromkeys([*unit_cols, *conversation_cols]))]
        grouped = row_level.groupby(["ENA_UNIT", *conversation_cols], sort=False, dropna=False)
        connection_counts = grouped[adj_names].sum().reset_index(drop=True)
        trajectories = grouped[trajectory_cols].first().reset_index(drop=True)
        meta_data = trajectories[["ENA_UNIT", *unit_cols]].copy()
        if include_meta and metadata_cols:
            first_meta = (
                df.groupby(["ENA_UNIT", *conversation_cols], sort=False, dropna=False)[
                    metadata_cols
                ]
                .first()
                .reset_index(drop=True)
            )
            meta_data = pd.concat([meta_data, first_meta], axis=1)
        if model_type == "AccumulatedTrajectory":
            connection_counts = connection_counts.groupby(
                meta_data["ENA_UNIT"], sort=False
            ).cumsum()

    return ENAData(
        raw=df,
        units=unit_cols,
        conversation=conversation_cols,
        codes=code_cols,
        metadata=metadata_cols,
        model_type=model_type,
        window_type=window_type,
        weight_by=weight_by,
        connection_counts=connection_counts.reset_index(drop=True),
        row_connection_counts=row_level.reset_index(drop=True),
        meta_data=meta_data.reset_index(drop=True),
        trajectories=trajectories.reset_index(drop=True),
        adjacency_names=adj_names,
        function_params={
            "model": model_type,
            "weight_by": weight_by,
            "window": window_type,
            "window_size_back": "Inf"
            if isinstance(window_size_back, float) and isinf(window_size_back)
            else window_size_back,
            "window_size_forward": "Inf"
            if isinstance(window_size_forward, float) and isinf(window_size_forward)
            else window_size_forward,
            "include_meta": include_meta,
            **kwargs,
        },
    )


def accumulate(
    data: pd.DataFrame,
    units: Sequence[str] | str,
    codes: Sequence[str] | str,
    conversation: Sequence[str] | str,
    **kwargs: Any,
) -> ENAData:
    """Composable pipeline alias for `accumulate_data`.

    The argument order mirrors rENA's pipe-friendly `accumulate(x, units, codes,
    horizon)` rather than the legacy `ena.accumulate.data` order.
    """

    return accumulate_data(data, units=units, conversation=conversation, codes=codes, **kwargs)


def ena_accumulate_data(
    *,
    units: pd.DataFrame | pd.Series,
    conversation: pd.DataFrame | pd.Series,
    codes: pd.DataFrame | pd.Series,
    metadata: pd.DataFrame | pd.Series | None = None,
    **kwargs: Any,
) -> ENAData:
    """rENA-compatible separate-frame wrapper for `ena.accumulate.data`.

    Examples
    --------
    >>> units = pd.DataFrame({"unit": ["u1", "u1"]})
    >>> conversation = pd.DataFrame({"conversation": ["c1", "c1"]})
    >>> codes = pd.DataFrame({"A": [1, 0], "B": [0, 1]})
    >>> ena_accumulate_data(units=units, conversation=conversation, codes=codes).connection_counts.iloc[0, 0]
    np.float64(0.0)
    """

    return accumulate_data(
        None,
        units=units,
        conversation=conversation,
        codes=codes,
        metadata=metadata,
        **kwargs,
    )


def ena_accumulate_data_file(
    file: str | Path | pd.DataFrame,
    *,
    units_by: Sequence[str] | str | None = None,
    conversations_by: Sequence[str] | str | None = None,
    codes: Sequence[str] | str | None = None,
    metadata: Sequence[str] | str | None = None,
    units_used: Sequence[str] | str | None = None,
    conversations_used: Sequence[str] | str | None = None,
    model: str = "EndPoint",
    window: str = "MovingStanzaWindow",
    window_size_back: int | float | str = 1,
    window_size_forward: int | float | str = 0,
    weight_by: str = "binary",
    binary_stanzas: bool = False,
    mask: pd.DataFrame | np.ndarray | None = None,
    include_meta: bool = True,
    **kwargs: Any,
) -> ENAData:
    """rENA-compatible CSV/data-frame wrapper for `ena.accumulate.data.file`.

    Parameters use Python snake_case equivalents of rENA's `units.by`,
    `conversations.by`, `window.size.back`, and related arguments. `units_used`,
    `conversations_used`, and `binary_stanzas` are accepted for migration
    compatibility; filtering behavior should be done by callers before passing
    data when exact rENA R6 file-processing semantics are needed.
    """

    del units_used, conversations_used, binary_stanzas
    if file is None or units_by is None or conversations_by is None or codes is None:
        raise ValidationError("Accumulation: file, units_by, conversations_by, and codes")
    data = file.copy() if isinstance(file, pd.DataFrame) else pd.read_csv(file)
    return accumulate_data(
        data,
        units=units_by,
        conversation=conversations_by,
        codes=codes,
        metadata=metadata,
        model=model,
        window=window,
        window_size_back=window_size_back,
        window_size_forward=window_size_forward,
        weight_by=weight_by,
        mask=mask,
        include_meta=include_meta,
        **kwargs,
    )
