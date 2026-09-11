"""Export protocol to JSON / CSV (full report) / PDF."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

# Prefer macOS fonts with Cyrillic; fall back if missing.
_FONT_REGULAR = (
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
)
_FONT_BOLD = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)

# Streamlit default theme — PDF should feel like the UI.
_UI = {
    "primary": "#FF4B4B",
    "text": "#31333F",
    "muted": "#808495",
    "secondary": "#F0F2F6",
    "border": "#D5D9E0",
    "row_alt": "#FAFBFC",
    "white": "#FFFFFF",
}
_PRIORITY_COLOR = {
    "high": "#FF4B4B",
    "medium": "#FFA421",
    "low": "#09AB3B",
    "unknown": "#808495",
}

LABELS: dict[str, dict[str, str]] = {
    "ru": {
        "brand": "Voice Manager",
        "section": "Раздел",
        "content": "Содержание",
        "assignee": "Ответственный",
        "speaker": "Спикер",
        "deadline": "Срок",
        "priority": "Приоритет",
        "task": "Задача",
        "title": "Название",
        "summary": "Выжимка",
        "decisions": "Решения",
        "topics": "Темы",
        "open_questions": "Открытые вопросы",
        "actions": "Поручения",
        "empty": "—",
    },
    "en": {
        "brand": "Voice Manager",
        "section": "Section",
        "content": "Content",
        "assignee": "Assignee",
        "speaker": "Speaker",
        "deadline": "Deadline",
        "priority": "Priority",
        "task": "Task",
        "title": "Title",
        "summary": "Summary",
        "decisions": "Decisions",
        "topics": "Topics",
        "open_questions": "Open questions",
        "actions": "Action items",
        "empty": "—",
    },
    "kk": {
        "brand": "Voice Manager",
        "section": "Бөлім",
        "content": "Мазмұны",
        "assignee": "Жауапты",
        "speaker": "Спикер",
        "deadline": "Мерзім",
        "priority": "Басымдылық",
        "task": "Тапсырма",
        "title": "Атауы",
        "summary": "Қысқаша қорытынды",
        "decisions": "Шешімдер",
        "topics": "Тақырыптар",
        "open_questions": "Ашық сұрақтар",
        "actions": "Тапсырмалар",
        "empty": "—",
    },
}


def _labels(lang: str | None) -> dict[str, str]:
    code = (lang or "ru").lower().strip()
    return LABELS.get(code, LABELS["ru"])


def export_json(protocol: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(protocol, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _csv_rows(protocol: dict[str, Any], labels: dict[str, str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(
        section: str,
        content: str,
        assignee: str = "",
        speaker: str = "",
        deadline: str = "",
        priority: str = "",
    ) -> None:
        rows.append(
            {
                labels["section"]: section,
                labels["content"]: content,
                labels["assignee"]: assignee,
                labels["speaker"]: speaker,
                labels["deadline"]: deadline,
                labels["priority"]: priority,
            }
        )

    def lines(section_key: str, items: list[Any]) -> None:
        if not items:
            add(labels[section_key], labels["empty"])
            return
        for item in items:
            add(labels[section_key], str(item))

    add(labels["title"], str(protocol.get("title") or labels["empty"]))
    lines("summary", list(protocol.get("executive_summary") or []))
    lines("decisions", list(protocol.get("decisions") or []))
    lines("topics", list(protocol.get("topics") or []))
    lines("open_questions", list(protocol.get("open_questions") or []))

    actions = protocol.get("action_items") or []
    if not actions:
        add(labels["actions"], labels["empty"])
    else:
        for item in actions:
            add(
                labels["actions"],
                str(item.get("task") or ""),
                "" if item.get("assignee") is None else str(item.get("assignee")),
                "" if item.get("speaker") is None else str(item.get("speaker")),
                "" if item.get("deadline") is None else str(item.get("deadline")),
                str(item.get("priority") or ""),
            )
    return rows


def export_csv(
    protocol: dict[str, Any],
    path: Path,
    *,
    lang: str = "ru",
) -> Path:
    """Write the full protocol (all sections + action items) as one CSV table."""
    path.parent.mkdir(parents=True, exist_ok=True)
    labels = _labels(lang)
    fieldnames = [
        labels["section"],
        labels["content"],
        labels["assignee"],
        labels["speaker"],
        labels["deadline"],
        labels["priority"],
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(_csv_rows(protocol, labels))
    return path


export_csv_action_items = export_csv


def _find_font(candidates: tuple[str, ...]) -> str | None:
    for p in candidates:
        if Path(p).is_file():
            return p
    return None


def _register_fonts() -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular_path = _find_font(_FONT_REGULAR)
    bold_path = _find_font(_FONT_BOLD)
    regular_name = "Helvetica"
    bold_name = "Helvetica-Bold"
    registered = set(pdfmetrics.getRegisteredFontNames())
    if regular_path:
        regular_name = "ProtocolFont"
        if regular_name not in registered:
            try:
                pdfmetrics.registerFont(TTFont(regular_name, regular_path))
            except Exception:
                regular_name = "Helvetica"
    if bold_path:
        bold_name = "ProtocolFontBold"
        if bold_name not in registered:
            try:
                pdfmetrics.registerFont(TTFont(bold_name, bold_path))
            except Exception:
                bold_name = regular_name
    elif regular_name != "Helvetica":
        bold_name = regular_name
    return regular_name, bold_name


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _bullet_html(items: list[Any], empty: str) -> str:
    if not items:
        return _esc(empty)
    return "<br/>".join(f"• {_esc(str(item))}" for item in items)


def pdf_story(protocol: dict[str, Any], *, lang: str = "ru") -> list[Any]:
    """Build ReportLab flowables for the protocol (UI-like layout + real table)."""
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import HRFlowable, Paragraph, Spacer, Table, TableStyle

    labels = _labels(lang)
    font_name, font_bold = _register_fonts()
    primary = colors.HexColor(_UI["primary"])
    text_color = colors.HexColor(_UI["text"])
    muted = colors.HexColor(_UI["muted"])
    secondary = colors.HexColor(_UI["secondary"])
    border = colors.HexColor(_UI["border"])
    row_alt = colors.HexColor(_UI["row_alt"])

    styles = getSampleStyleSheet()
    brand_style = ParagraphStyle(
        "Brand",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8,
        leading=11,
        textColor=muted,
        spaceAfter=2,
    )
    title_style = ParagraphStyle(
        "TitleUI",
        parent=styles["Heading1"],
        fontName=font_bold,
        fontSize=18,
        leading=22,
        textColor=text_color,
        spaceAfter=4,
    )
    h_style = ParagraphStyle(
        "HeadingUI",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=11,
        leading=14,
        textColor=text_color,
        spaceBefore=0,
        spaceAfter=4,
    )
    body = ParagraphStyle(
        "BodyUI",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        leading=14,
        textColor=text_color,
        spaceAfter=2,
    )
    cell = ParagraphStyle(
        "CellUI",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8,
        leading=11,
        textColor=text_color,
    )
    cell_header = ParagraphStyle(
        "CellHeaderUI",
        parent=cell,
        fontName=font_bold,
        fontSize=8,
        leading=11,
        textColor=text_color,
    )

    def P(text: str, style: ParagraphStyle = body) -> Paragraph:
        return Paragraph(_esc(text), style)

    story: list[Any] = []
    title = str(protocol.get("title") or labels["title"])
    story.append(P(labels["brand"], brand_style))
    story.append(P(title, title_style))
    story.append(
        HRFlowable(
            width="100%",
            thickness=3,
            color=primary,
            spaceBefore=2,
            spaceAfter=10,
        )
    )

    story.append(P(labels["summary"], h_style))
    story.append(Paragraph(_bullet_html(list(protocol.get("executive_summary") or []), labels["empty"]), body))
    story.append(Spacer(1, 6 * mm))

    left_html = (
        f'<font name="{font_bold}" size="11">{_esc(labels["decisions"])}</font><br/>'
        f'{_bullet_html(list(protocol.get("decisions") or []), labels["empty"])}'
        f'<br/><br/>'
        f'<font name="{font_bold}" size="11">{_esc(labels["topics"])}</font><br/>'
        f'{_bullet_html(list(protocol.get("topics") or []), labels["empty"])}'
    )
    right_html = (
        f'<font name="{font_bold}" size="11">{_esc(labels["open_questions"])}</font><br/>'
        f'{_bullet_html(list(protocol.get("open_questions") or []), labels["empty"])}'
    )
    columns = Table(
        [[Paragraph(left_html, body), Paragraph(right_html, body)]],
        colWidths=[89 * mm, 89 * mm],
    )
    columns.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 8),
                ("LEFTPADDING", (1, 0), (1, 0), 10),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("BACKGROUND", (1, 0), (1, 0), secondary),
                ("BOX", (1, 0), (1, 0), 0.3, border),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(columns)
    story.append(Spacer(1, 7 * mm))

    story.append(P(labels["actions"], h_style))
    actions = protocol.get("action_items") or []
    if not actions:
        story.append(P(labels["empty"], body))
        return story

    header = [
        Paragraph(_esc(labels["task"]), cell_header),
        Paragraph(_esc(labels["assignee"]), cell_header),
        Paragraph(_esc(labels["speaker"]), cell_header),
        Paragraph(_esc(labels["deadline"]), cell_header),
        Paragraph(_esc(labels["priority"]), cell_header),
    ]
    data: list[list[Any]] = [header]
    for item in actions:
        prio = str(item.get("priority") or "unknown")
        prio_hex = _PRIORITY_COLOR.get(prio, _UI["muted"])
        data.append(
            [
                Paragraph(_esc(str(item.get("task") or "")), cell),
                Paragraph(_esc(str(item.get("assignee") or labels["empty"])), cell),
                Paragraph(_esc(str(item.get("speaker") or labels["empty"])), cell),
                Paragraph(_esc(str(item.get("deadline") or labels["empty"])), cell),
                Paragraph(f'<font color="{prio_hex}">{_esc(prio)}</font>', cell),
            ]
        )

    table = Table(
        data,
        colWidths=[62 * mm, 32 * mm, 28 * mm, 30 * mm, 26 * mm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), secondary),
                ("TEXTCOLOR", (0, 0), (-1, -1), text_color),
                ("FONTNAME", (0, 0), (-1, 0), font_bold),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, row_alt]),
                ("GRID", (0, 0), (-1, -1), 0.4, border),
                ("BOX", (0, 0), (-1, -1), 0.7, border),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, primary),
            ]
        )
    )
    story.append(table)
    return story


def export_pdf(
    protocol: dict[str, Any],
    path: Path,
    *,
    lang: str = "ru",
) -> Path:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate
    except ImportError as e:
        raise RuntimeError("reportlab не установлен: pip install reportlab") from e

    path.parent.mkdir(parents=True, exist_ok=True)
    title = str(protocol.get("title") or "Протокол встречи")
    story = pdf_story(protocol, lang=lang)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=title,
        author="Voice Manager",
    )
    doc.build(story)
    return path


def export_all(
    protocol: dict[str, Any],
    out_dir: Path,
    *,
    stem: str = "protocol",
    lang: str = "ru",
) -> dict[str, Path]:
    """Write .json / .csv / .pdf into out_dir from one protocol dict."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": export_json(protocol, out_dir / f"{stem}.json"),
        "csv": export_csv(protocol, out_dir / f"{stem}.csv", lang=lang),
        "pdf": export_pdf(protocol, out_dir / f"{stem}.pdf", lang=lang),
    }
    return paths
