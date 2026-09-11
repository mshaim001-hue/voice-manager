#!/usr/bin/env python3
"""CLI: transcript/audio → protocol.json (+ optional csv/pdf export)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from asr import DEFAULT_WHISPER_MODEL, ASRError, transcribe
from asr.diarize import DiarizationError
from export import export_all
from ingest.text import load_text
from llm.client import DEFAULT_MODEL, OllamaError
from llm.pipeline import polish_transcript, text_to_protocol


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="AI Meeting Intelligence — локальный протоколист (offline)",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", type=Path, help="Путь к .txt транскрипту")
    src.add_argument("--audio", type=Path, help="Путь к аудио MP3/WAV/M4A")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("protocol.json"),
        help="Куда сохранить JSON (по умолчанию protocol.json)",
    )
    p.add_argument(
        "--export-dir",
        type=Path,
        default=None,
        help="Если задан — дополнительно csv + pdf (+ json) в эту папку",
    )
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Модель Ollama (по умолчанию {DEFAULT_MODEL})",
    )
    p.add_argument(
        "--whisper-model",
        default=DEFAULT_WHISPER_MODEL,
        help=f"Faster-Whisper size (по умолчанию {DEFAULT_WHISPER_MODEL})",
    )
    p.add_argument(
        "--language",
        default=os.environ.get("WHISPER_LANGUAGE", "auto"),
        help="Язык ASR: auto | ru | en | kk (default: auto — не форсировать русский)",
    )
    p.add_argument(
        "--diarize",
        action="store_true",
        help="Диаризация спикеров (sherpa-onnx) → метки «Спикер 1/2» в транскрипте",
    )
    p.add_argument(
        "--num-speakers",
        type=int,
        default=-1,
        help="Число спикеров (-1 = авто). Для демо с 2 голосами: --num-speakers 2",
    )
    p.add_argument(
        "--save-transcript",
        type=Path,
        default=None,
        help="Опционально сохранить транскрипт (после правки, если --polish)",
    )
    p.add_argument(
        "--polish",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Правка ASR через LLM перед протоколом (по умолчанию вкл.; --no-polish выкл.)",
    )
    p.add_argument(
        "--output-lang",
        choices=["ru", "en", "kk"],
        default=os.environ.get("OUTPUT_LANG", "ru"),
        help="Язык правки транскрипта и значений протокола (ru|en|kk)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    wall0 = time.perf_counter()
    asr_s = 0.0
    polish_s = 0.0

    if args.audio:
        print(f"Аудио: {args.audio}")
        print(
            f"Whisper: {args.whisper_model} language={args.language} "
            f"diarize={args.diarize}"
        )
        t0 = time.perf_counter()
        try:
            transcript = transcribe(
                args.audio,
                model_size=args.whisper_model,
                language=args.language,
                diarize_speakers=args.diarize,
                num_speakers=args.num_speakers,
            )
        except (ASRError, DiarizationError, FileNotFoundError) as e:
            print(f"Ошибка ASR: {e}", file=sys.stderr)
            return 1
        asr_s = time.perf_counter() - t0
        print(f"ASR wall: {asr_s:.1f}s ({len(transcript)} символов)")
    else:
        try:
            transcript = load_text(args.text)
        except FileNotFoundError as e:
            print(e, file=sys.stderr)
            return 1
        print(f"Текст: {args.text} ({len(transcript)} символов)")

    print(f"LLM: {args.model} polish={args.polish} output_lang={args.output_lang}")
    if args.polish:
        t_p = time.perf_counter()
        try:
            transcript = polish_transcript(
                transcript, model=args.model, output_lang=args.output_lang
            )
        except (OllamaError, ValueError) as e:
            print(f"Ошибка правки транскрипта: {e}", file=sys.stderr)
            return 1
        polish_s = time.perf_counter() - t_p
        print(f"Polish wall: {polish_s:.1f}s ({len(transcript)} символов)")

    if args.save_transcript:
        args.save_transcript.parent.mkdir(parents=True, exist_ok=True)
        args.save_transcript.write_text(transcript + "\n", encoding="utf-8")
        print(f"Транскрипт → {args.save_transcript}")

    t1 = time.perf_counter()
    try:
        protocol = text_to_protocol(
            transcript, model=args.model, output_lang=args.output_lang
        )
    except (OllamaError, ValueError) as e:
        print(f"Ошибка LLM: {e}", file=sys.stderr)
        return 1
    llm_s = time.perf_counter() - t1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = protocol.model_dump(mode="json")
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"OK → {args.output}")

    if args.export_dir:
        paths = export_all(payload, args.export_dir, stem=args.output.stem)
        for kind, path in paths.items():
            print(f"export {kind} → {path}")

    total = time.perf_counter() - wall0
    print(
        f"timing: asr={asr_s:.1f}s polish={polish_s:.1f}s llm={llm_s:.1f}s "
        f"total={total:.1f}s | "
        f"summary={len(protocol.executive_summary)} "
        f"decisions={len(protocol.decisions)} "
        f"risks={len(protocol.risks)} "
        f"actions={len(protocol.action_items)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
