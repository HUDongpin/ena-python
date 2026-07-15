# Agent instructions for ena-python

This repository is meant for AI-assisted porting from rENA to Python.

Read `CODEX_PROMPT.md` first. Then inspect the R reference files under `reference/rENA/` before changing Python code.

## Development commands

```bash
python -m pip install -e ".[dev,plot,web]"
pytest
ruff check .
ruff format .
mypy src/ena_python
```

## Ground rules

- Implement behavior from R tests before inventing new behavior.
- Use `tests/fixtures/r_oracle/` for generated compatibility fixtures.
- Mark R-dependent tests with `@pytest.mark.rcompat`.
- Keep production code independent of R.
- Use snake_case APIs, but add compatibility aliases when they reduce migration friction.
- Do not commit huge generated datasets. Put large local datasets under `data/local/`, which is gitignored.
