from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Iterable


def _csv_value(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    return value


def write_rows(path: str | Path, rows: Iterable[dict[str, Any]]) -> Path:
    target = Path(path)
    materialized = list(rows)
    if not materialized:
        raise ValueError(f"refusing to write empty CSV: {target}")
    fieldnames: list[str] = []
    for row in materialized:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        for row in materialized:
            writer.writerow({key: _csv_value(row.get(key, "")) for key in fieldnames})
    temporary.replace(target)
    return target

