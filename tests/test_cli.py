from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def sample_csv(tmp_path: Path) -> Path:
    path = tmp_path / "sample.csv"
    pd.DataFrame(
        {
            "unit": ["u1", "u1", "u2", "u2", "u3", "u3", "u4", "u4"],
            "conv": ["c1", "c1", "c1", "c1", "c1", "c1", "c1", "c1"],
            "group": ["a", "a", "b", "b", "a", "a", "b", "b"],
            "score": [1, 1, 2, 2, 3, 3, 4, 4],
            "A": [1, 0, 1, 0, 1, 1, 0, 0],
            "B": [0, 1, 1, 0, 1, 0, 1, 0],
            "C": [0, 1, 0, 1, 0, 1, 1, 1],
        }
    ).to_csv(path, index=False)
    return path


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}"
    return subprocess.run(
        [sys.executable, "-m", "pyena.cli", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def run_validation_script(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}"
    return subprocess.run(
        [sys.executable, "scripts/validate_cli_release.py", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def common_args(path: Path) -> list[str]:
    return [
        str(path),
        "--units",
        "unit",
        "--conversation",
        "conv",
        "--codes",
        "A",
        "B",
        "C",
        "--metadata",
        "group",
        "score",
        "--window-size-back",
        "2",
    ]


def test_cli_help_and_version() -> None:
    help_result = run_cli("--help")
    version_result = run_cli("version")

    assert help_result.returncode == 0
    assert "accumulate" in help_result.stdout
    assert "inspect" in help_result.stdout
    assert version_result.returncode == 0
    assert version_result.stdout.startswith("pyENA ")


def test_cli_inspect_reports_schema(tmp_path: Path) -> None:
    input_path = sample_csv(tmp_path)

    result = run_cli("inspect", str(input_path))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["rows"] == 8
    assert payload["columns"] == ["unit", "conv", "group", "score", "A", "B", "C"]
    assert len(payload["preview"]) == 5


@pytest.mark.parametrize(
    ("command", "expected_key"),
    [("accumulate", "connection_counts"), ("model", "points"), ("ena", "rotation")],
)
def test_cli_analysis_commands_write_json(tmp_path: Path, command: str, expected_key: str) -> None:
    input_path = sample_csv(tmp_path)
    output_path = tmp_path / f"{command}.json"

    result = run_cli(command, *common_args(input_path), "--output", str(output_path))

    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert expected_key in payload


def test_cli_prints_json_to_stdout_when_output_is_omitted(tmp_path: Path) -> None:
    input_path = sample_csv(tmp_path)

    result = run_cli("accumulate", *common_args(input_path))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "connection_counts" in payload


def test_cli_plot_writes_html(tmp_path: Path) -> None:
    pytest.importorskip("plotly")
    input_path = sample_csv(tmp_path)
    output_path = tmp_path / "plot.html"

    result = run_cli("plot", *common_args(input_path), "--output", str(output_path))

    assert result.returncode == 0, result.stderr
    html = output_path.read_text(encoding="utf-8")
    assert "Plotly.newPlot" in html


def test_cli_errors_for_missing_columns_and_bad_paths(tmp_path: Path) -> None:
    input_path = sample_csv(tmp_path)
    missing_column = run_cli(
        "accumulate",
        str(input_path),
        "--units",
        "missing",
        "--conversation",
        "conv",
        "--codes",
        "A",
        "B",
        "C",
    )
    missing_file = run_cli("accumulate", *common_args(tmp_path / "missing.csv"))

    assert missing_column.returncode == 2
    assert "Missing input columns" in missing_column.stderr
    assert "Available columns:" in missing_column.stderr
    assert "pyena inspect" in missing_column.stderr
    assert missing_file.returncode == 2
    assert "Input file does not exist" in missing_file.stderr


def test_cli_errors_for_empty_file_and_bad_output_directory(tmp_path: Path) -> None:
    empty_path = tmp_path / "empty.csv"
    empty_path.write_text("", encoding="utf-8")
    bad_output = tmp_path / "missing_dir" / "out.json"

    empty_result = run_cli("inspect", str(empty_path))
    output_result = run_cli(
        "accumulate", *common_args(sample_csv(tmp_path)), "--output", str(bad_output)
    )

    assert empty_result.returncode == 2
    assert "Input file is empty or has no readable columns" in empty_result.stderr
    assert output_result.returncode == 2
    assert "Output directory does not exist" in output_result.stderr


def test_cli_plot_rejects_unknown_output_extension(tmp_path: Path) -> None:
    pytest.importorskip("plotly")
    input_path = sample_csv(tmp_path)

    result = run_cli("plot", *common_args(input_path), "--output", str(tmp_path / "plot.txt"))

    assert result.returncode == 2
    assert "Plot output must end with .html or .json" in result.stderr


def test_release_validation_script_writes_summary(tmp_path: Path) -> None:
    pytest.importorskip("plotly")
    input_path = sample_csv(tmp_path)
    output_dir = tmp_path / "acceptance"

    result = run_validation_script(
        str(input_path),
        "--units",
        "unit",
        "--conversation",
        "conv",
        "--codes",
        "A",
        "B",
        "C",
        "--metadata",
        "group",
        "score",
        "--window-size-back",
        "2",
        "--output-dir",
        str(output_dir),
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["ok"] is True
    assert summary["rows"] == 8
    assert {item["command"] for item in summary["commands"]} == {
        "accumulate",
        "model",
        "ena",
        "plot",
    }
