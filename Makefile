.PHONY: install test lint format typecheck all benchmark

install:
	python -m pip install -e ".[dev,plot,web]"

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy src/pyena

all: lint typecheck test

benchmark:
	pytest -m benchmark --benchmark-only
