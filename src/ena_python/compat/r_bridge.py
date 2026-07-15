from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class RUnavailableError(RuntimeError):
    """Raised when Rscript is not available."""


def run_r_script(script: str, *, cwd: str | Path | None = None) -> dict[str, Any]:
    """Run a short R script and parse JSON from stdout.

    This is for fixture generation only. Production pyENA must not depend on R.
    """

    if shutil.which("Rscript") is None:
        raise RUnavailableError("Rscript is not installed or not on PATH")
    with tempfile.NamedTemporaryFile("w", suffix=".R", delete=False) as handle:
        handle.write(script)
        script_path = Path(handle.name)
    try:
        completed = subprocess.run(
            ["Rscript", str(script_path)],
            cwd=cwd,
            check=True,
            text=True,
            capture_output=True,
        )
    finally:
        script_path.unlink(missing_ok=True)
    return json.loads(completed.stdout)
