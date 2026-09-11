"""Messenger-style HTML for diarized turns + RAG Q&A."""

from __future__ import annotations

import html
import re
from typing import Any, Iterable

from ingest.turns import Turn
from ui.i18n import t

_PALETTE = [
    ("#1B6B9A", "#E7F2FA"),
    ("#2E7D4F", "#E7F6EE"),
    ("#C45C12", "#FFF1E4"),
    ("#6B3FA0", "#F3EAFB"),
    ("#B42318", "#FDECEC"),
    ("#3D4A8F", "#ECEFFA"),
]

_SPEAKER_NUM = re.compile(r"(\d+)")


def _speaker_sides(turns: Iterable[Turn]) -> dict[str, bool]:
    """Two-speaker chats sit left/right like a messenger; groups stay left."""
    ordered: list[str] = []
    for turn in turns:
        if turn.speaker not in ordered:
            ordered.append(turn.speaker)
    if len(ordered) == 2:
        return {ordered[0]: False, ordered[1]: True}
    return {name: False for name in ordered}


def _esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def _color_for(name: str) -> tuple[str, str]:
    acc = 0
    for ch in name:
        acc = (acc * 31 + ord(ch)) & 0xFFFFFFFF
    return _PALETTE[acc % len(_PALETTE)]


def _initials(name: str) -> str:
    num = _SPEAKER_NUM.search(name or "")
    if num:
        return num.group(1)
    token = (name or "?").strip()
    return token[0].upper() if token else "?"


def _css() -> str:
    return """
<style>
.vm-chat{background:linear-gradient(180deg,#d7e3ef 0%,#eef3f8 100%);
  border:1px solid #d3dde8;border-radius:16px;padding:14px 12px 18px;
  max-height:640px;overflow-y:auto;}
.vm-sep{display:flex;align-items:center;gap:10px;margin:14px 8px 12px;
  color:#6b7789;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;}
.vm-sep:before,.vm-sep:after{content:"";flex:1;height:1px;background:#c5d0dc;}
.vm-row{display:flex;gap:8px;align-items:flex-end;margin:8px 0;max-width:86%;}
.vm-row.right{margin-left:auto;flex-direction:row-reverse;}
.vm-av{width:32px;height:32px;border-radius:50%;color:#fff;display:flex;
  align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0;}
.vm-col{min-width:0;}
.vm-name{font-size:11px;font-weight:700;margin:0 4px 3px;}
.vm-bubble{border-radius:16px;padding:8px 12px;box-shadow:0 1px 1px rgba(16,24,40,.06);
  font-size:14px;line-height:1.45;white-space:pre-wrap;word-wrap:break-word;color:#1a2433;}
.vm-row.right .vm-bubble{border-bottom-right-radius:4px;}
.vm-row:not(.right) .vm-bubble{border-bottom-left-radius:4px;}
.vm-src{margin-top:6px;font-size:11px;color:#5b6777;font-style:italic;}
</style>
"""


def _bubble(
    *,
    name: str,
    text: str,
    accent: str,
    fill: str,
    right: bool = False,
    sources: Iterable[str] | None = None,
) -> str:
    side = " right" if right else ""
    src_html = ""
    quotes = [s for s in (sources or []) if s]
    if quotes:
        src_html = "".join(
            f'<div class="vm-src">{_esc(q)}</div>' for q in quotes[:2]
        )
    return (
        f'<div class="vm-row{side}">'
        f'<div class="vm-av" style="background:{accent}">{_esc(_initials(name))}</div>'
        f'<div class="vm-col">'
        f'<div class="vm-name" style="color:{accent}">{_esc(name)}</div>'
        f'<div class="vm-bubble" style="background:{fill}">{_esc(text)}{src_html}</div>'
        f"</div></div>"
    )


def meeting_chat_html(
    turns: list[Turn] | None,
    qa: list[dict[str, Any]] | None,
    ui_lang: str = "ru",
    you_label: str | None = None,
    assistant_label: str | None = None,
) -> str:
    you = you_label or t(ui_lang, "chat_you")
    assistant = assistant_label or t(ui_lang, "chat_assistant")
    parts = [_css(), '<div class="vm-chat">']
    if turns:
        sides = _speaker_sides(turns)
        parts.append(f'<div class="vm-sep">{_esc(t(ui_lang, "chat_meeting_log"))}</div>')
        for turn in turns:
            accent, fill = _color_for(turn.speaker)
            parts.append(
                _bubble(
                    name=turn.speaker,
                    text=turn.text,
                    accent=accent,
                    fill=fill,
                    right=sides.get(turn.speaker, False),
                )
            )
    if qa:
        parts.append(f'<div class="vm-sep">{_esc(t(ui_lang, "chat_ask_section"))}</div>')
        for item in qa:
            role = item.get("role")
            text = str(item.get("content") or "")
            if role == "user":
                parts.append(
                    _bubble(
                        name=you,
                        text=text,
                        accent="#0A6CFF",
                        fill="#D6E9FF",
                        right=True,
                    )
                )
                continue
            sources: list[str] = []
            for src in item.get("sources") or []:
                if hasattr(src, "text"):
                    speaker = getattr(src, "speaker", None)
                    snippet = str(getattr(src, "text", "")).strip()
                elif isinstance(src, dict):
                    speaker = src.get("speaker")
                    snippet = str(src.get("text") or "").strip()
                else:
                    speaker, snippet = None, str(src)
                if not snippet:
                    continue
                short = snippet if len(snippet) <= 140 else snippet[:137] + "…"
                sources.append(f"«{short}»" if not speaker else f"{speaker}: «{short}»")
            parts.append(
                _bubble(
                    name=assistant,
                    text=text,
                    accent="#5B3FA0",
                    fill="#F4EEFB",
                    sources=sources,
                )
            )
    parts.append("</div>")
    return "".join(parts)
