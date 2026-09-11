"""Local ASR via Faster-Whisper (offline) + optional diarization + Kazakh HF turbo."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from asr.audio_io import AudioConvertError, as_wav
from asr.diarize import (
    DiarizationError,
    TimedSegment,
    diarize,
    merge_transcript,
    models_ready,
)
from asr.models import (
    is_kazakh_turbo,
    kazakh_hf_ready,
    kazakh_turbo_ready,
    resolve_whisper_model,
)

SUPPORTED_SUFFIXES = {".wav", ".mp3", ".m4a", ".webm", ".ogg", ".flac", ".mp4", ".aac", ".caf"}

DEFAULT_WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")
_DEFAULT_LANG_ENV = os.environ.get("WHISPER_LANGUAGE", "auto").strip().lower()


class ASRError(RuntimeError):
    pass


def resolve_language(language: str | None) -> str | None:
    """Map UI/CLI value to faster-whisper language arg (None = detect)."""
    if language is None:
        return None
    value = language.strip().lower()
    if value in {"", "auto", "detect", "none"}:
        return None
    return value


@lru_cache(maxsize=2)
def _load_model(model_size: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise ASRError(
            "faster-whisper не установлен. pip install faster-whisper"
        ) from e

    resolved = resolve_whisper_model(model_size)
    print(f"Whisper load: {model_size} → {resolved} (int8/cpu)")
    return WhisperModel(resolved, device="cpu", compute_type="int8")


def _transcribe_wav(
    wav_path: Path,
    *,
    model_size: str,
    language: str | None,
) -> list[TimedSegment]:
    # Optional experimental HF fine-tune (often worse on TTS; set WHISPER_KAZAKH_HF=1)
    use_hf = os.environ.get("WHISPER_KAZAKH_HF", "").strip() in {"1", "true", "yes"}
    if use_hf and is_kazakh_turbo(model_size):
        if not kazakh_turbo_ready():
            raise ASRError(
                "Kazakh HF не скачан. bash scripts/setup_kazakh_whisper.sh"
            )
        try:
            from asr.kazakh_hf import KazakhASRError, transcribe_kazakh_hf, unload_kazakh_model
        except ImportError as e:
            raise ASRError(str(e)) from e
        if not kazakh_hf_ready():
            raise ASRError("Нет models/whisper/_hf_src — bash scripts/setup_kazakh_whisper.sh")
        lang = resolve_language(language) or "kk"
        try:
            return transcribe_kazakh_hf(wav_path, language=lang)
        except KazakhASRError as e:
            raise ASRError(str(e)) from e
        finally:
            unload_kazakh_model()

    lang = resolve_language(language)
    # kazakh-turbo alias → faster-whisper "turbo" (large-v3-turbo int8)
    load_name = model_size
    if is_kazakh_turbo(model_size):
        load_name = "turbo"
        if not lang:
            lang = "kk"
        print("Whisper: kazakh-turbo → large-v3-turbo (int8). Для HF fine-tune: WHISPER_KAZAKH_HF=1")

    model = _load_model(load_name)
    try:
        segments_iter, info = model.transcribe(
            str(wav_path),
            language=lang,
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=False,
        )
        segments = [
            TimedSegment(
                start=float(seg.start),
                end=float(seg.end),
                text=seg.text.strip(),
            )
            for seg in segments_iter
            if seg.text and seg.text.strip()
        ]
    except Exception as e:
        msg = str(e)
        if "ffmpeg" in msg.lower() or "format not recognised" in msg.lower():
            raise ASRError(
                f"Не удалось прочитать аудио после конвертации: {e}"
            ) from e
        raise ASRError(f"ASR ошибка: {e}") from e

    if not segments:
        raise ASRError("Пустой транскрипт от Whisper — проверь аудио/язык")

    detected = getattr(info, "language", None) or lang or "?"
    prob = getattr(info, "language_probability", None)
    prob_s = f" p={prob:.2f}" if isinstance(prob, float) else ""
    text_len = sum(len(s.text) for s in segments)
    print(
        f"ASR: model={model_size} lang={detected}{prob_s} "
        f"segs={len(segments)} chars={text_len}"
    )
    return segments


def transcribe_segments(
    audio_path: Path | str,
    *,
    model_size: str = DEFAULT_WHISPER_MODEL,
    language: str | None = _DEFAULT_LANG_ENV,
) -> list[TimedSegment]:
    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(f"Аудио не найдено: {path}")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ASRError(
            f"Формат {path.suffix} не поддержан. Ожидаются: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )

    try:
        with as_wav(path) as wav:
            return _transcribe_wav(wav, model_size=model_size, language=language)
    except AudioConvertError as e:
        raise ASRError(str(e)) from e


def transcribe(
    audio_path: Path | str,
    *,
    model_size: str = DEFAULT_WHISPER_MODEL,
    language: str | None = _DEFAULT_LANG_ENV,
    diarize_speakers: bool = False,
    num_speakers: int = -1,
) -> str:
    """Transcribe audio; optionally label Speakers via sherpa-onnx diarization."""
    path = Path(audio_path)
    try:
        with as_wav(path) as wav:
            segments = _transcribe_wav(
                wav, model_size=model_size, language=language
            )
            if not diarize_speakers:
                return " ".join(s.text for s in segments).strip()

            if not models_ready():
                raise DiarizationError(
                    "Модели диаризации не установлены. bash scripts/setup_diarization.sh"
                )
            turns = diarize(wav, num_speakers=num_speakers)
            labeled = merge_transcript(segments, turns)
            print(f"ASR+diarization: labeled chars={len(labeled)}")
            return labeled
    except AudioConvertError as e:
        raise ASRError(str(e)) from e
