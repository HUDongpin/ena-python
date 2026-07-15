# ena-python CLI Usage

The `ena-python` command is a command-line interface for running the core ENA workflow on local tabular files.

## Install From A Local Wheel

```bash
python -m pip install -e ".[dev,plot,web]"
python -m build
python -m pip install dist/ena_python-*.whl
ena-python --help
```

## Input Files

`ena-python` reads CSV, TSV, and Parquet files through the same table reader used by the Python API. Column names are passed explicitly.

```bash
ena-python ena examples/cli_sample.csv \
  --units unit \
  --conversation conv \
  --codes A B C \
  --metadata group score \
  --window-size-back 2 \
  --output ena.json
```

## Commands

```bash
ena-python accumulate INPUT.csv --units unit --conversation conv --codes A B C --output data.json
ena-python model INPUT.csv --units unit --conversation conv --codes A B C --output model.json
ena-python ena INPUT.csv --units unit --conversation conv --codes A B C --output ena.json
ena-python plot INPUT.csv --units unit --conversation conv --codes A B C --output plot.html
ena-python inspect INPUT.csv
ena-python version
```

All analysis commands support:

- `--metadata`: optional metadata columns
- `--model`: `EndPoint`, `AccumulatedTrajectory`, or `SeparateTrajectory`
- `--window`: `MovingStanzaWindow` or `Conversation`
- `--window-size-back` and `--window-size-forward`
- `--weight-by`: defaults to `binary`
- `--dimensions`: defaults to `2`

## Output

`accumulate`, `model`, and `ena` write JSON generated from ena-python `to_dict()` methods. If `--output` is omitted, JSON is printed to stdout.

`plot` writes either:

- `.html`: standalone Plotly HTML
- `.json`: Plotly figure JSON

If `plot` is run without `--output`, it prints Plotly figure JSON to stdout.

`inspect` writes JSON with the input path, file type, row count, columns, and the first five rows as a preview.

## Exit Codes

- `0`: command completed successfully
- `2`: invalid input, missing columns, bad output path, or unsupported plot output extension

Plot commands require the plot extra:

```bash
python -m pip install "ena-python[plot]"
# or, for a local wheel:
python -m pip install "$(ls dist/ena_python-*-py3-none-any.whl)[plot]"
```

## Real CSV Acceptance

Keep real data out of git. Put real CSV files under `data/local/`, then run the release validation helper:

```bash
python scripts/validate_cli_release.py data/local/acceptance.csv \
  --units unit \
  --conversation conv \
  --codes A B C \
  --metadata group score \
  --window-size-back 2
```

The helper writes outputs and `summary.json` to `data/local/ena_python_cli_acceptance/`.
