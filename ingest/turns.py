"""Parse a meeting transcript into speaker turns (messenger messages)."""

from __future__ import annotations

import re
from dataclasses import dataclass

HEADER_SPEAKERS = {
    "участники",
    "participants",
    "қатысушылар",
    "катысушылар",
    "дата",
    "date",
    "тема",
    "topic",
    "место",
    "location",
    "agenda",
    "повестка",
    "встреча",
    "meeting",
    "кеңес",
    "кенёс",
    "протокол",
    "protocol",
    "summary",
    "выжимка",
    "time",
    "время",
}

# Optional [HH:MM] / HH:MM:SS then "Name: text"
_LINE = re.compile(
    r"^(?:\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s+)?"
    r"(?P<speaker>[A-Za-zА-Яа-яЁёІіҢңҒғҮүҰұҚқӨөҺһӘә][A-Za-zА-Яа-яЁёІіҢңҒғҮүҰұҚқӨөҺһӘә0-9 ._-]{0,40})"
    r"\s*:\s*(?P<text>.+)$"
)


@dataclass(frozen=True)
class Turn:
    speaker: str
    text: str
    index: int


def _is_header_speaker(name: str) -> bool:
    key = name.strip().lower().rstrip(".")
    return key in HEADER_SPEAKERS


def parse_speaker_turns(transcript: str | None) -> list[Turn]:
    """Split labeled lines like 'Спикер 1: …' / 'Анна: …' into turns."""
    if not transcript or not transcript.strip():
        return []

    turns: list[Turn] = []
    current_speaker: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, current_speaker
        text = " ".join(part.strip() for part in buf if part.strip()).strip()
        if current_speaker and text:
            turns.append(Turn(speaker=current_speaker, text=text, index=len(turns)))
        buf = []

    for raw in transcript.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _LINE.match(line)
        if match:
            speaker = match.group("speaker").strip()
            text = match.group("text").strip()
            if _is_header_speaker(speaker):
                continue
            if current_speaker != speaker:
                flush()
                current_speaker = speaker
            if text:
                buf.append(text)
            continue
        if current_speaker is not None:
            buf.append(line)

    flush()
    return turns


def is_dialogue(turns: list[Turn] | None) -> bool:
    if not turns:
        return False
    speakers = {t.speaker for t in turns}
    return len(turns) >= 2 and len(speakers) >= 2
