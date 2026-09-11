"""Offline speaker diarization via sherpa-onnx (ONNX, no HF token)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODELS_DIR = Path(
    os.environ.get("DIARIZATION_MODELS_DIR", ROOT / "models" / "diarization")
)
SEG_MODEL = DEFAULT_MODELS_DIR / "sherpa-onnx-pyannote-segmentation-3-0" / "model.onnx"
EMB_MODEL = DEFAULT_MODELS_DIR / "nemo_en_titanet_small.onnx"


class DiarizationError(RuntimeError):
    pass


@dataclass
class SpeakerTurn:
    start: float
    end: float
    speaker: int  # 0-based from model


def models_ready(models_dir: Path | None = None) -> bool:
    base = models_dir or DEFAULT_MODELS_DIR
    seg = base / "sherpa-onnx-pyannote-segmentation-3-0" / "model.onnx"
    emb = base / "nemo_en_titanet_small.onnx"
    return seg.is_file() and emb.is_file()


@lru_cache(maxsize=1)
def _load_diarizer(num_speakers: int, threshold: float, models_dir: str):
    try:
        import sherpa_onnx
    except ImportError as e:
        raise DiarizationError(
            "sherpa-onnx не установлен. pip install sherpa-onnx"
        ) from e

    base = Path(models_dir)
    seg = str(base / "sherpa-onnx-pyannote-segmentation-3-0" / "model.onnx")
    emb = str(base / "nemo_en_titanet_small.onnx")
    if not Path(seg).is_file() or not Path(emb).is_file():
        raise DiarizationError(
            f"Модели диаризации не найдены в {base}. "
            "Запусти: bash scripts/setup_diarization.sh"
        )

    # num_clusters=-1 → auto via threshold
    n_clusters = num_speakers if num_speakers and num_speakers > 0 else -1
    kwargs = dict(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=seg,
            ),
        ),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=emb),
        clustering=sherpa_onnx.FastClusteringConfig(
            num_clusters=n_clusters,
            threshold=threshold,
        ),
        min_duration_on=0.3,
        min_duration_off=0.5,
    )
    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(**kwargs)
    if not config.validate():
        raise DiarizationError("Невалидный конфиг sherpa-onnx diarization")
    return sherpa_onnx.OfflineSpeakerDiarization(config)


def diarize(
    audio_path: Path | str,
    *,
    num_speakers: int = -1,
    cluster_threshold: float = 0.6,
    models_dir: Path | None = None,
) -> list[SpeakerTurn]:
    """Return speaker turns (start/end/speaker_id). Offline."""
    try:
        import librosa
        import soundfile as sf
    except ImportError as e:
        raise DiarizationError("Нужны soundfile и librosa") from e

    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(f"Аудио не найдено: {path}")

    base = models_dir or DEFAULT_MODELS_DIR
    sd = _load_diarizer(num_speakers, cluster_threshold, str(base.resolve()))

    audio, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
    audio = audio[:, 0]
    if sample_rate != sd.sample_rate:
        audio = librosa.resample(
            audio, orig_sr=sample_rate, target_sr=sd.sample_rate
        )

    result = sd.process(audio).sort_by_start_time()
    turns = [
        SpeakerTurn(start=float(r.start), end=float(r.end), speaker=int(r.speaker))
        for r in result
    ]
    n_spk = len({t.speaker for t in turns})
    print(f"Diarization: turns={len(turns)} speakers={n_spk}")
    return turns


def speaker_label(speaker_id: int) -> str:
    """0 → Спикер 1 (human-friendly 1-based)."""
    return f"Спикер {speaker_id + 1}"


@dataclass
class TimedSegment:
    start: float
    end: float
    text: str


def assign_speaker(seg: TimedSegment, turns: list[SpeakerTurn]) -> int | None:
    """Pick speaker with max overlap with segment window."""
    if not turns:
        return None
    best_id: int | None = None
    best_overlap = 0.0
    for t in turns:
        overlap = max(0.0, min(seg.end, t.end) - max(seg.start, t.start))
        if overlap > best_overlap:
            best_overlap = overlap
            best_id = t.speaker
    if best_id is None:
        # fallback: nearest turn by midpoint
        mid = (seg.start + seg.end) / 2
        best_id = min(turns, key=lambda t: abs((t.start + t.end) / 2 - mid)).speaker
    return best_id


def merge_transcript(segments: list[TimedSegment], turns: list[SpeakerTurn]) -> str:
    """Build labeled transcript: 'Спикер 1: …' merging consecutive same speaker."""
    if not segments:
        return ""
    if not turns:
        return " ".join(s.text.strip() for s in segments if s.text.strip()).strip()

    lines: list[str] = []
    current_spk: int | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, current_spk
        if not buf or current_spk is None:
            buf = []
            return
        text = " ".join(buf).strip()
        if text:
            lines.append(f"{speaker_label(current_spk)}: {text}")
        buf = []

    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        spk = assign_speaker(seg, turns)
        if spk is None:
            spk = 0
        if current_spk is None:
            current_spk = spk
        if spk != current_spk:
            flush()
            current_spk = spk
        buf.append(text)
    flush()
    return "\n".join(lines)
