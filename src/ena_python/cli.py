from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from ena_python import __version__
from ena_python.accumulation import accumulate_data
from ena_python.api import ena
from ena_python.exceptions import PyENAError
from ena_python.io import read_table
from ena_python.modeling import make_set

MAX_COLUMNS_IN_ERROR = 30
PREVIEW_ROWS = 5


def _columns(values: list[str] | None) -> list[str]:
    return [] if values is None else values


def _load_table(path: str) -> pd.DataFrame:
    input_path = Path(path)
    if not input_path.exists():
        raise ValueError(f"Input file does not exist: {input_path}")
    if not input_path.is_file():
        raise ValueError(f"Input path is not a file: {input_path}")
    try:
        df = read_table(input_path)
    except EmptyDataError as exc:
        raise ValueError(f"Input file is empty or has no readable columns: {input_path}") from exc
    except Exception as exc:
        raise ValueError(f"Unable to read input file {input_path}: {exc}") from exc
    if len(df.columns) == 0:
        raise ValueError(f"Input file has no columns: {input_path}")
    return df


def _column_preview(columns: Sequence[str]) -> str:
    preview = list(columns[:MAX_COLUMNS_IN_ERROR])
    suffix = "" if len(columns) <= MAX_COLUMNS_IN_ERROR else f", ... ({len(columns)} total)"
    return ", ".join(preview) + suffix


def _validate_columns(df: pd.DataFrame, columns: Sequence[str], *, input_path: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        available = _column_preview([str(column) for column in df.columns])
        raise ValueError(
            "Missing input columns: "
            f"{', '.join(missing)}\n"
            f"Available columns: {available}\n"
            f"Tip: run `pyena inspect {input_path}` to preview the file schema."
        )


def _validate_output_path(output: str | None) -> Path | None:
    if output is None:
        return None
    output_path = Path(output)
    parent = output_path.parent
    if str(parent) and not parent.exists():
        raise ValueError(f"Output directory does not exist: {parent}")
    if output_path.exists() and output_path.is_dir():
        raise ValueError(f"Output path is a directory: {output_path}")
    return output_path


def _write_text_or_stdout(text: str, output: Path | None) -> None:
    if output is None:
        print(text)
    else:
        output.write_text(text, encoding="utf-8")


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _inspect_payload(df: pd.DataFrame, path: str) -> dict[str, Any]:
    input_path = Path(path)
    preview = df.head(PREVIEW_ROWS).astype(object).where(pd.notna(df), None)
    return {
        "path": str(input_path),
        "file_type": input_path.suffix.lower().lstrip(".") or "unknown",
        "rows": len(df),
        "columns": [str(column) for column in df.columns],
        "preview": preview.to_dict(orient="records"),
    }


def _accumulation_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "units": args.units,
        "conversation": args.conversation,
        "codes": args.codes,
        "metadata": _columns(args.metadata),
        "model": args.model,
        "window": args.window,
        "window_size_back": args.window_size_back,
        "window_size_forward": args.window_size_forward,
        "weight_by": args.weight_by,
    }


def _load_and_validate(args: argparse.Namespace) -> pd.DataFrame:
    df = _load_table(args.input)
    _validate_columns(
        df,
        [
            *args.units,
            *args.conversation,
            *args.codes,
            *_columns(args.metadata),
        ],
        input_path=args.input,
    )
    return df


def _run_inspect(args: argparse.Namespace) -> int:
    output = _validate_output_path(args.output)
    df = _load_table(args.input)
    _write_text_or_stdout(_json_text(_inspect_payload(df, args.input)), output)
    return 0


def _run_accumulate(args: argparse.Namespace) -> int:
    output = _validate_output_path(args.output)
    df = _load_and_validate(args)
    result = accumulate_data(df, **_accumulation_kwargs(args))
    _write_text_or_stdout(_json_text(result.to_dict(include_raw=args.include_raw)), output)
    return 0


def _run_model(args: argparse.Namespace) -> int:
    output = _validate_output_path(args.output)
    df = _load_and_validate(args)
    data = accumulate_data(df, **_accumulation_kwargs(args))
    result = make_set(data, dimensions=args.dimensions)
    _write_text_or_stdout(_json_text(result.to_dict(include_raw=args.include_raw)), output)
    return 0


def _run_ena(args: argparse.Namespace) -> int:
    output = _validate_output_path(args.output)
    df = _load_and_validate(args)
    result = ena(df, dimensions=args.dimensions, **_accumulation_kwargs(args))
    _write_text_or_stdout(_json_text(result.to_dict(include_raw=args.include_raw)), output)
    return 0


def _run_plot(args: argparse.Namespace) -> int:
    output = _validate_output_path(args.output)
    df = _load_and_validate(args)
    try:
        from ena_python.plotting import add_network, add_nodes, add_points, ena_plot

        set_ = ena(df, dimensions=args.dimensions, **_accumulation_kwargs(args))
        fig = ena_plot(set_)
        add_network(fig)
        add_points(fig)
        add_nodes(fig)
    except RuntimeError as exc:
        raise RuntimeError(
            'Plot support requires Plotly. Install it with: python -m pip install "pyENA[plot]"'
        ) from exc

    if output is None:
        print(fig.to_json())
        return 0

    suffix = output.suffix.lower()
    if suffix == ".html":
        fig.write_html(output)
    elif suffix == ".json":
        output.write_text(fig.to_json(), encoding="utf-8")
    else:
        raise ValueError("Plot output must end with .html or .json")
    return 0


def _run_version(args: argparse.Namespace) -> int:
    del args
    print(f"pyENA {__version__}")
    return 0


def _add_workflow_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input", help="Input CSV, TSV, or Parquet file")
    parser.add_argument("--units", nargs="+", required=True, help="Unit column names")
    parser.add_argument(
        "--conversation", nargs="+", required=True, help="Conversation column names"
    )
    parser.add_argument("--codes", nargs="+", required=True, help="Code column names")
    parser.add_argument("--metadata", nargs="+", help="Optional metadata column names")
    parser.add_argument("--model", default="EndPoint", help="ENA model type")
    parser.add_argument("--window", default="MovingStanzaWindow", help="Window type")
    parser.add_argument("--window-size-back", default=1, help="Moving stanza back window")
    parser.add_argument("--window-size-forward", default=0, help="Moving stanza forward window")
    parser.add_argument("--weight-by", default="binary", help="Weighting mode")
    parser.add_argument("--dimensions", type=int, default=2, help="Number of model dimensions")
    parser.add_argument("--output", help="Output path; prints to stdout when omitted")
    parser.add_argument(
        "--include-raw",
        action="store_true",
        help=(
            "Echo the full input dataset and per-row connection counts into the JSON "
            "output. Omitted by default so results do not carry a copy of possibly "
            "sensitive source data."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the pyENA command-line parser."""

    parser = argparse.ArgumentParser(
        prog="pyena",
        description="Run pyENA accumulation, modeling, and plotting from local files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, description, handler in [
        ("accumulate", "Accumulate coded rows into ENA connection counts", _run_accumulate),
        ("model", "Accumulate and build an ENA model/set", _run_model),
        ("ena", "Run the high-level accumulate + model workflow", _run_ena),
        ("plot", "Run ENA and write a Plotly figure as HTML or JSON", _run_plot),
    ]:
        subparser = subparsers.add_parser(command, help=description, description=description)
        _add_workflow_arguments(subparser)
        subparser.set_defaults(func=handler)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect an input file schema",
        description="Inspect an input CSV, TSV, or Parquet file schema.",
    )
    inspect_parser.add_argument("input", help="Input CSV, TSV, or Parquet file")
    inspect_parser.add_argument("--output", help="Output path; prints to stdout when omitted")
    inspect_parser.set_defaults(func=_run_inspect)

    version_parser = subparsers.add_parser("version", help="Print the pyENA version")
    version_parser.set_defaults(func=_run_version)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the pyENA command-line interface."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (PyENAError, RuntimeError, ValueError) as exc:
        print(f"pyena: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
