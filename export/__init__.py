"""Export protocol to JSON / CSV (action items) / PDF."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

# Prefer macOS fonts with Cyrillic; fall back if missing.
_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)


def export_json(protocol: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(protocol, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def export_csv_action_items(protocol: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = protocol.get("action_items") or []
    fieldnames = ["task", "assignee", "speaker", "deadline", "priority"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for item in rows:
            writer.writerow(
                {
                    "task": item.get("task") or "",
                    "assignee": item.get("assignee") if item.get("assignee") is not None else "",
                    "speaker": item.get("speaker") if item.get("speaker") is not None else "",
                    "deadline": item.get("deadline") if item.get("deadline") is not None else "",
                    "priority": item.get("priority") or "",
                }
            )
    return path


def _find_font() -> str | None:
    for p in _FONT_CANDIDATES:
        if Path(p).is_file():
            return p
    return None


def export_pdf(protocol: dict[str, Any], path: Path) -> Path:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as e:
        raise RuntimeError("reportlab не установлен: pip install reportlab") from e

    path.parent.mkdir(parents=True, exist_ok=True)
    font_path = _find_font()
    font_name = "Helvetica"
    if font_path:
        font_name = "ProtocolFont"
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
        except Exception:
            font_name = "Helvetica"

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleRU",
        parent=styles["Heading1"],
        fontName=font_name,
        fontSize=16,
        leading=20,
        spaceAfter=8,
    )
    h_style = ParagraphStyle(
        "HeadingRU",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=12,
        leading=16,
        spaceBefore=10,
        spaceAfter=4,
    )
    body = ParagraphStyle(
        "BodyRU",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        leading=14,
        spaceAfter=2,
    )

    def esc(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    story: list[Any] = []
    title = protocol.get("title") or "Протокол встречи"
    story.append(Paragraph(esc(str(title)), title_style))
    story.append(Spacer(1, 4 * mm))

    def section(heading: str, items: list[Any], numbered: bool = True) -> None:
        story.append(Paragraph(esc(heading), h_style))
        if not items:
            story.append(Paragraph("—", body))
            return
        for i, item in enumerate(items, 1):
            prefix = f"{i}. " if numbered else "• "
            story.append(Paragraph(esc(f"{prefix}{item}"), body))

    section("Краткая выжимка", list(protocol.get("executive_summary") or []))
    section("Принятые решения", list(protocol.get("decisions") or []))
    section("Темы и тезисы", list(protocol.get("topics") or []))
    section("Открытые вопросы", list(protocol.get("open_questions") or []))

    story.append(Paragraph(esc("Поручения (Action Items)"), h_style))
    actions = protocol.get("action_items") or []
    if not actions:
        story.append(Paragraph("—", body))
    else:
        for i, a in enumerate(actions, 1):
            task = a.get("task") or ""
            assignee = a.get("assignee") or "не назначен"
            deadline = a.get("deadline") or "не указан"
            priority = a.get("priority") or "unknown"
            line = (
                f"{i}. {task} | Ответственный: {assignee} | "
                f"Срок: {deadline} | Приоритет: {priority}"
            )
            story.append(Paragraph(esc(line), body))

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=str(title),
    )
    doc.build(story)
    return path


def export_all(protocol: dict[str, Any], out_dir: Path, *, stem: str = "protocol") -> dict[str, Path]:
    """Write .json / .csv / .pdf into out_dir from one protocol dict."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": export_json(protocol, out_dir / f"{stem}.json"),
        "csv": export_csv_action_items(protocol, out_dir / f"{stem}_action_items.csv"),
        "pdf": export_pdf(protocol, out_dir / f"{stem}.pdf"),
    }
    return paths
