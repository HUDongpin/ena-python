# Internal Wheel Release Checklist

Use this checklist before publishing a release or handing a local wheel to another user.

## 1. Prepare The Version

Use `0.0.x` versions for internal alpha releases. Before building, update both:

- `pyproject.toml`: `[project].version`
- `src/ena_python/__init__.py`: `__version__`

The values must match.

## 2. Run Quality Gates

```bash
python -m pytest
python -m ruff check .
python -m ruff format . --check
python -m mypy src/ena_python
```

## 3. Build The Wheel

```bash
rm -rf dist build
python -m build
ls -lh dist
```

Expected outputs:

- `dist/ena_python-<version>-py3-none-any.whl`
- `dist/ena_python-<version>.tar.gz`

## 4. Smoke Test A Fresh Install

```bash
tmpdir=$(mktemp -d /tmp/ena-python-wheel-smoke.XXXXXX)
python -m venv "$tmpdir/venv"
"$tmpdir/venv/bin/python" -m pip install dist/ena_python-*.whl
"$tmpdir/venv/bin/ena-python" --help
"$tmpdir/venv/bin/ena-python" ena examples/cli_sample.csv \
  --units unit \
  --conversation conv \
  --codes A B C \
  --metadata group score \
  --window-size-back 2 \
  --output "$tmpdir/ena.json"
```

## 5. Check Plot Optional Extra

Core installs do not include Plotly. A core-only install should show a clear plot dependency error:

```bash
"$tmpdir/venv/bin/ena-python" plot examples/cli_sample.csv \
  --units unit \
  --conversation conv \
  --codes A B C \
  --output "$tmpdir/plot.html"
```

Install plot support when plot output is needed:

```bash
"$tmpdir/venv/bin/python" -m pip install "dist/ena_python-<version>-py3-none-any.whl[plot]"
"$tmpdir/venv/bin/ena-python" plot examples/cli_sample.csv \
  --units unit \
  --conversation conv \
  --codes A B C \
  --output "$tmpdir/plot.html"
```

## 6. Optional Real CSV Acceptance

Do not commit real data. Put the real CSV under `data/local/`, for example:

```text
data/local/acceptance.csv
```

Then run:

```bash
python scripts/validate_cli_release.py data/local/acceptance.csv \
  --units <unit columns...> \
  --conversation <conversation columns...> \
  --codes <code columns...> \
  --metadata <optional metadata columns...> \
  --window-size-back 2
```

Outputs are written to `data/local/ena_python_cli_acceptance/`, including `summary.json`.

## 7. Handoff

Send the wheel file and the minimal install command:

```bash
python -m pip install ena_python-<version>-py3-none-any.whl
ena-python --help
```

For plot usage, tell users to install the plot extra from the project source or provide an environment with Plotly installed.
