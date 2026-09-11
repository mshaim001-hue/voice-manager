#!/usr/bin/env python3
"""Phase 1 A/B: 3 samples × candidate models → pick winner for gate."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingest.text import load_text
from llm.client import CANDIDATE_MODELS, DEFAULT_MODEL, OllamaError
from llm.pipeline import text_to_protocol

SAMPLES = [
    ROOT / "samples" / "meeting_with_deadline.txt",
    ROOT / "samples" / "meeting_no_deadline.txt",
    ROOT / "samples" / "meeting_no_assignee.txt",
]

# Soft checks for anti-hallucination gate (heuristic on known samples)
EXPECTATIONS = {
    "meeting_no_deadline.txt": {"deadlines_must_be_null": True},
    "meeting_no_assignee.txt": {"assignees_must_be_null": True},
    "meeting_with_deadline.txt": {},
}


def soft_score(sample_name: str, protocol: dict) -> list[str]:
    """Return list of soft-gate warnings (empty = ok)."""
    warns: list[str] = []
    exp = EXPECTATIONS.get(sample_name, {})
    items = protocol.get("action_items") or []
    if exp.get("deadlines_must_be_null"):
        for i, it in enumerate(items):
            if it.get("deadline") not in (None, ""):
                warns.append(f"action_items[{i}].deadline={it.get('deadline')!r} (ожидали null)")
    if exp.get("assignees_must_be_null"):
        for i, it in enumerate(items):
            if it.get("assignee") not in (None, ""):
                warns.append(f"action_items[{i}].assignee={it.get('assignee')!r} (ожидали null)")
    return warns


def main() -> int:
    p = argparse.ArgumentParser(description="A/B models on Phase 1 samples")
    p.add_argument(
        "--models",
        nargs="+",
        default=list(CANDIDATE_MODELS),
        help=f"Models to try (default: {', '.join(CANDIDATE_MODELS)})",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "output" / "ab",
        help="Where to write per-run JSON",
    )
    args = p.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    summary: list[dict] = []
    print(f"Default candidate set; preferred default in code: {DEFAULT_MODEL}\n")

    for model in args.models:
        print(f"=== {model} ===")
        ok = 0
        warn_n = 0
        fail = 0
        times: list[float] = []
        for sample in SAMPLES:
            name = sample.name
            out = args.out_dir / f"{model.replace(':', '_')}__{sample.stem}.json"
            t0 = time.perf_counter()
            try:
                protocol = text_to_protocol(load_text(sample), model=model)
                elapsed = time.perf_counter() - t0
                times.append(elapsed)
                data = protocol.model_dump(mode="json")
                out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                warns = soft_score(name, data)
                if warns:
                    warn_n += 1
                    status = "WARN"
                    detail = "; ".join(warns)
                else:
                    ok += 1
                    status = "OK"
                    detail = (
                        f"actions={len(protocol.action_items)} "
                        f"decisions={len(protocol.decisions)}"
                    )
                print(f"  [{status}] {name}  {elapsed:.1f}s  → {out.name}  {detail}")
            except (OllamaError, ValueError, Exception) as e:
                elapsed = time.perf_counter() - t0
                times.append(elapsed)
                fail += 1
                print(f"  [FAIL] {name}  {elapsed:.1f}s  {e}")
        avg = sum(times) / len(times) if times else 0
        row = {
            "model": model,
            "ok": ok,
            "warn": warn_n,
            "fail": fail,
            "avg_s": round(avg, 1),
            "score": ok * 2 + warn_n,  # prefer clean OK
        }
        summary.append(row)
        print(f"  → ok={ok} warn={warn_n} fail={fail} avg={avg:.1f}s\n")

    summary.sort(key=lambda r: (-r["score"], r["fail"], r["avg_s"]))
    print("=== RANKING ===")
    for i, r in enumerate(summary, 1):
        print(
            f"  {i}. {r['model']}: score={r['score']} "
            f"(ok={r['ok']} warn={r['warn']} fail={r['fail']}) avg={r['avg_s']}s"
        )
    if summary and summary[0]["fail"] == 0 and summary[0]["ok"] + summary[0]["warn"] == 3:
        winner = summary[0]["model"]
        print(f"\nWINNER → export OLLAMA_MODEL={winner}")
        print(f"Or: python run.py --text samples/... --model {winner}")
        return 0
    print("\nNo clean winner yet — fix fails / hallucinations before Phase 2.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
