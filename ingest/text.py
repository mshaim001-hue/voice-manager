from __future__ import annotations

from pathlib import Path


def load_text(path: str | Path) -> str:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Файл не найден: {p}")
    return p.read_text(encoding="utf-8")