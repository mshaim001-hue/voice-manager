"""Normalize uploaded audio to WAV (macOS afconvert — no ffmpeg required)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Formats soundfile/sherpa often fail on without ffmpeg
_NEEDS_CONVERT = {".m4a", ".mp3", ".mp4", ".aac", ".caf", ".aiff", ".aif", ".webm", ".ogg"}


class AudioConvertError(RuntimeError):
    pass


def needs_wav_convert(path: Path) -> bool:
    return path.suffix.lower() in _NEEDS_CONVERT


def convert_to_wav(src: Path, dst: Path) -> Path:
    """Convert src → 16-bit PCM WAV via afconvert (macOS) or ffmpeg."""
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    afconvert = shutil.which("afconvert")
    if afconvert:
        # LEI16 = linear PCM 16-bit little-endian; WAVE container
        cmd = [afconvert, "-f", "WAVE", "-d", "LEI16", str(src), str(dst)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            err = (e.stderr or e.stdout or str(e)).strip()
            raise AudioConvertError(
                f"afconvert не смог открыть {src.suffix}: {err}"
            ) from e
        if not dst.is_file() or dst.stat().st_size < 44:
            raise AudioConvertError(f"Пустой WAV после конвертации: {dst}")
        return dst

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(dst),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            err = (e.stderr or e.stdout or str(e)).strip()[-400:]
            raise AudioConvertError(f"ffmpeg не смог открыть файл: {err}") from e
        return dst

    raise AudioConvertError(
        f"Формат {src.suffix} нуждается в конвертации, но нет afconvert/ffmpeg. "
        "На macOS обычно есть /usr/bin/afconvert."
    )


@contextmanager
def as_wav(path: Path | str) -> Iterator[Path]:
    """Yield a WAV path for processing; convert temp copy for m4a/mp3/…"""
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(f"Аудио не найдено: {src}")

    if not needs_wav_convert(src):
        yield src
        return

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        print(f"Audio: converting {src.suffix} → WAV …")
        convert_to_wav(src, tmp_path)
        yield tmp_path
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
