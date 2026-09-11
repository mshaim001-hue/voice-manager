"""Kazakh Whisper large-v3-turbo via HuggingFace pipeline (fp16 MPS/CPU)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from asr.diarize import TimedSegment
from asr.models import ROOT

HF_ID = os.environ.get(
    "KAZAKH_WHISPER_HF", "shyngys879/kazakh-whisper-large-v3-turbo"
)
LOCAL_SRC = ROOT / "models" / "whisper" / "_hf_src"


class KazakhASRError(RuntimeError):
    pass


def kazakh_hf_ready() -> bool:
    return (LOCAL_SRC / "model.safetensors").is_file() or (
        LOCAL_SRC / "pytorch_model.bin"
    ).is_file()


@lru_cache(maxsize=1)
def _load_pipeline():
    try:
        import torch
        from transformers import pipeline
    except ImportError as e:
        raise KazakhASRError(
            "Нужны torch+transformers: pip install torch transformers accelerate"
        ) from e

    model_id = str(LOCAL_SRC) if kazakh_hf_ready() else HF_ID
    if torch.backends.mps.is_available():
        device = "mps"
        dtype = torch.float16
    else:
        device = "cpu"
        dtype = torch.float32

    print(f"Kazakh Whisper pipeline: {model_id} device={device} dtype={dtype}")

    # Processor from base turbo — Kazakh checkpoint has incomplete processor_config
    asr = pipeline(
        "automatic-speech-recognition",
        model=model_id,
        tokenizer="openai/whisper-large-v3-turbo",
        feature_extractor="openai/whisper-large-v3-turbo",
        device=device,
        torch_dtype=dtype,
        chunk_length_s=30,
        stride_length_s=5,
        return_timestamps=True,
    )
    return asr


def unload_kazakh_model() -> None:
    _load_pipeline.cache_clear()
    try:
        import gc
        import torch

        gc.collect()
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
    except Exception:
        pass


def transcribe_kazakh_hf(
    wav_path: Path | str,
    *,
    language: str = "kk",
    chunk_length_s: float = 30.0,  # kept for API compat; pipeline uses its own
) -> list[TimedSegment]:
    """Transcribe WAV with Kazakh fine-tuned large-v3-turbo."""
    try:
        import librosa
    except ImportError as e:
        raise KazakhASRError("pip install librosa") from e

    path = Path(wav_path)
    if not path.is_file():
        raise FileNotFoundError(path)

    # Pass ndarray — transformers pipeline needs ffmpeg only for file paths
    audio, sr = librosa.load(str(path), sr=16000, mono=True)

    lang = language if language and language not in ("auto",) else "kk"
    asr = _load_pipeline()

    try:
        result = asr(
            {"array": audio, "sampling_rate": sr},
            generate_kwargs={
                "language": lang,
                "task": "transcribe",
                "num_beams": 1,
                "condition_on_prev_tokens": False,
            },
        )
    except Exception as e:
        raise KazakhASRError(f"Kazakh Whisper inference failed: {e}") from e

    segments: list[TimedSegment] = []
    chunks = result.get("chunks") if isinstance(result, dict) else None
    if chunks:
        for ch in chunks:
            text = (ch.get("text") or "").strip()
            ts = ch.get("timestamp") or (None, None)
            start = float(ts[0] or 0.0)
            end = float(ts[1] if ts[1] is not None else start)
            # filter degenerate garbage (long runs of punctuation)
            if not text or text.count("!") > 20 or "\ufffd" in text:
                continue
            segments.append(TimedSegment(start=start, end=end, text=text))
    else:
        text = (result.get("text") if isinstance(result, dict) else str(result) or "").strip()
        if text and text.count("!") <= 20:
            segments.append(TimedSegment(start=0.0, end=0.0, text=text))

    if not segments:
        raise KazakhASRError(
            "Kazakh Whisper вернул пустой/битый текст. "
            "Попробуй другой файл или language=kk."
        )

    chars = sum(len(s.text) for s in segments)
    print(f"ASR(kazakh-hf): segs={len(segments)} chars={chars}")
    return segments
