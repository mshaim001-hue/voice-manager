#!/usr/bin/env python3
"""Re-export existing protocol.json → json/csv/pdf (no LLM)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from export import export_all


def main() -> int:
    p = argparse.ArgumentParser(description="Export protocol.json to json/csv/pdf")
    p.add_argument("protocol", type=Path, help="Path to protocol JSON")
    p.add_argument(
        "-d",
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: same folder as protocol)",
    )
    p.add_argument("--stem", default="protocol", help="Filename stem")
    args = p.parse_args()

    if not args.protocol.is_file():
        print(f"Файл не найден: {args.protocol}", file=sys.stderr)
        return 1

    data = json.loads(args.protocol.read_text(encoding="utf-8"))
    out_dir = args.out_dir or args.protocol.parent
    paths = export_all(data, out_dir, stem=args.stem)
    for kind, path in paths.items():
        print(f"{kind}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
