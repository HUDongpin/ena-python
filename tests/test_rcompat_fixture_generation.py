from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.rcompat
def test_rcompat_fixture_generation_smoke() -> None:
    if os.environ.get("ENA_PYTHON_RUN_RCOMPAT") != "1":
        pytest.skip("Set ENA_PYTHON_RUN_RCOMPAT=1 to regenerate R oracle fixtures")
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not installed")

    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/generate_r_oracle.py"],
        check=True,
        capture_output=True,
        cwd=repo_root,
        text=True,
    )
    out_file = Path(completed.stdout.strip())
    assert out_file.exists()
    assert out_file.name == "rena_parity_model.json"
