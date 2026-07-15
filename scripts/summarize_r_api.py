from __future__ import annotations

import json
import re
from pathlib import Path


def main() -> None:
    root = Path("reference/rENA")
    records = []
    for path in sorted((root / "R").glob("*.R")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r"(?m)^\s*([A-Za-z0-9_.]+)\s*<-\s*function\s*\(", text):
            records.append({"name": match.group(1), "source": str(path)})
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
