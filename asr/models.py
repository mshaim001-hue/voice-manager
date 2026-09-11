"""Whisper model aliases (Kazakh quality → large-v3-turbo int8)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

KAZAKH_HF_DIR = ROOT / "models" / "whisper" / "_hf_src"

# Aliases that should use faster-whisper "turbo" (large-v3-turbo) — fits 8GB @ int8
KAZAKH_ALIASES = {
    "kazakh-turbo",
    "kazakh-whisper-large-v3-turbo",
    "kk-turbo",
    "large-v3-turbo",
}


def is_kazakh_turbo(name: str) -> bool:
    """Legacy name: used to route to HF fine-tune. Now prefer faster-whisper turbo."""
    return name.strip().lower() in {"kazakh-turbo", "kazakh-whisper-large-v3-turbo", "kk-turbo"}


def kazakh_turbo_ready() -> bool:
    """Always ready: faster-whisper downloads 'turbo' on first use.
    HF fine-tune (shyngys879) is optional experiment under models/whisper/_hf_src.
    """
    return True


def kazakh_hf_ready() -> bool:
    return (KAZAKH_HF_DIR / "model.safetensors").is_file()


def resolve_whisper_model(name: str) -> str:
    """Return size/path for WhisperModel(...)."""
    key = name.strip()
    lower = key.lower()
    # Map Kazakh alias → official large-v3-turbo (CT2 via faster-whisper)
    if lower in KAZAKH_ALIASES or lower == "turbo":
        return "turbo"
    p = Path(key).expanduser()
    if p.is_dir() and ((p / "model.bin").is_file() or any(p.glob("*.bin"))):
        return str(p.resolve())
    return key


def whisper_ui_options() -> list[str]:
    opts = ["tiny", "base", "small", "turbo", "kazakh-turbo"]
    return opts
