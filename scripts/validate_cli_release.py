from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from pyena.io import read_table

DEFAULT_OUTPUT_DIR = Path("data/local/pyena_cli_acceptance")


def _add_schema_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input", help="Real or sample CSV, TSV, or Parquet file")
    parser.add_argument("--units", nargs="+", required=True, help="Unit column names")
    parser.add_argument(
        "--conversation", nargs="+", required=True, help="Conversation column names"
    )
    parser.add_argument("--codes", nargs="+", required=True, help="Code column names")
    parser.add_argument("--metadata", nargs="+", help="Optional metadata column names")
    parser.add_argument("--model", default="EndPoint", help="ENA model type")
    parser.add_argument("--window", default="MovingStanzaWindow", help="Window type")
    parser.add_argument("--window-size-back", default="1", help="Moving stanza back window")
    parser.add_argument("--window-size-forward", default="0", help="Moving stanza forward window")
    parser.add_argument("--weight-by", default="binary", help="Weighting mode")
    parser.add_argument("--dimensions", default="2", help="Number of model dimensions")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a pyENA CLI release against a local tabular file."
    )
    _add_schema_args(parser)
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for generated acceptance outputs",
    )
    parser.add_argument(
        "--skip-plot",
        action="store_true",
        help="Skip plot validation when pyENA[plot] is not installed",
    )
    return parser


def _schema_args(args: argparse.Namespace) -> list[str]:
    values = [
        "--units",
        *args.units,
        "--conversation",
        *args.conversation,
        "--codes",
        *args.codes,
    ]
    if args.metadata:
        values.extend(["--metadata", *args.metadata])
    values.extend(
        [
            "--model",
            args.model,
            "--window",
            args.window,
            "--window-size-back",
            args.window_size_back,
            "--window-size-forward",
            args.window_size_forward,
            "--weight-by",
            args.weight_by,
            "--dimensions",
            args.dimensions,
        ]
    )
    return values


def _run_pyena(command: str, args: argparse.Namespace, output: Path) -> dict[str, Any]:
    command_args = [
        sys.executable,
        "-m",
        "pyena.cli",
        command,
        args.input,
        *_schema_args(args),
        "--output",
        str(output),
    ]
    start = time.perf_counter()
    result = subprocess.run(command_args, text=True, capture_output=True, check=False)
    elapsed = time.perf_counter() - start
    return {
        "command": command,
        "elapsed_sec": elapsed,
        "exit_code": result.returncode,
        "output": str(output),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = read_table(args.input)
    commands = [
        ("accumulate", output_dir / "accumulate.json"),
        ("model", output_dir / "model.json"),
        ("ena", output_dir / "ena.json"),
    ]
    if not args.skip_plot:
        commands.append(("plot", output_dir / "plot.html"))

    results = [_run_pyena(command, args, output) for command, output in commands]
    summary = {
        "input": str(Path(args.input)),
        "rows": len(df),
        "columns": [str(column) for column in df.columns],
        "output_dir": str(output_dir),
        "commands": results,
        "ok": all(item["exit_code"] == 0 for item in results),
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(summary_path)
    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
