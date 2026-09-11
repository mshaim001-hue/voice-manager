"""Highlight risk quotes inside a meeting transcript."""

from __future__ import annotations

import html


def highlight_quotes_html(transcript: str, quotes: list[str] | None) -> str:
    """Escape transcript HTML and wrap the first match of each quote in <mark>."""
    escaped = html.escape(transcript or "")
    seen: set[str] = set()
    for raw in quotes or []:
        quote = (raw or "").strip()
        if not quote:
            continue
        needle = html.escape(quote)
        if not needle or needle in seen:
            continue
        seen.add(needle)
        if needle in escaped:
            escaped = escaped.replace(needle, f"<mark>{needle}</mark>", 1)
    html_body = escaped.replace("\n", "<br/>\n")
    return (
        "<style>mark{background:#FFE082;padding:0 3px;border-radius:2px;}</style>"
        + html_body
    )
