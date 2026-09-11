"""Export round-trip checks — no LLM."""

import csv
import json
from pathlib import Path

from reportlab.platypus import Table

from export import export_all, pdf_story


SAMPLE = {
    "title": "Тест",
    "executive_summary": ["Раз.", "Два."],
    "decisions": ["Решение A"],
    "topics": ["Тема"],
    "open_questions": ["Вопрос?"],
    "action_items": [
        {
            "task": "Сделать X",
            "assignee": "Анна",
            "speaker": "Спикер 1",
            "deadline": "пятница",
            "priority": "high",
        },
        {
            "task": "Changelog",
            "assignee": None,
            "speaker": None,
            "deadline": None,
            "priority": "unknown",
        },
    ],
    "risks": [
        {
            "kind": "disagreement",
            "description": "Борис против релиза в пятницу",
            "speaker": "Борис",
            "quote": "Я против пятницы, инфра не выдержит",
            "severity": "high",
        },
        {
            "kind": "technical",
            "description": "Пиковая нагрузка на API",
            "speaker": None,
            "quote": None,
            "severity": "medium",
        },
    ],
}


def _cell_text(cell) -> str:
    text = getattr(cell, "text", None)
    if text is not None:
        return str(text)
    return str(cell)


def test_export_fields_match(tmp_path: Path):
    paths = export_all(SAMPLE, tmp_path, stem="protocol")
    assert paths["json"].is_file()
    assert paths["csv"].is_file()
    assert paths["pdf"].is_file()
    assert paths["pdf"].stat().st_size > 500
    assert paths["csv"].name == "protocol.csv"

    loaded = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert loaded["title"] == SAMPLE["title"]
    assert loaded["action_items"] == SAMPLE["action_items"]
    assert loaded["executive_summary"] == SAMPLE["executive_summary"]
    assert loaded["decisions"] == SAMPLE["decisions"]


def test_csv_contains_full_protocol(tmp_path: Path):
    paths = export_all(SAMPLE, tmp_path, stem="protocol")
    with paths["csv"].open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    sections = [r["Раздел"] for r in rows]
    assert "Название" in sections
    assert "Выжимка" in sections
    assert "Решения" in sections
    assert "Темы" in sections
    assert "Открытые вопросы" in sections
    assert "Риски и блокеры" in sections
    assert "Поручения" in sections

    title_row = next(r for r in rows if r["Раздел"] == "Название")
    assert title_row["Содержание"] == "Тест"

    summaries = [r["Содержание"] for r in rows if r["Раздел"] == "Выжимка"]
    assert summaries == ["Раз.", "Два."]
    assert any(r["Содержание"] == "Решение A" for r in rows if r["Раздел"] == "Решения")
    assert any(r["Содержание"] == "Тема" for r in rows if r["Раздел"] == "Темы")
    assert any(r["Содержание"] == "Вопрос?" for r in rows if r["Раздел"] == "Открытые вопросы")

    risk = next(
        r
        for r in rows
        if r["Раздел"] == "Риски и блокеры"
        and "Борис против релиза" in r["Содержание"]
    )
    assert "несогласие" in risk["Содержание"].lower() or "disagreement" in risk["Содержание"].lower()
    assert risk["Спикер"] == "Борис"
    assert risk["Приоритет"] == "high"

    action = next(
        r
        for r in rows
        if r["Раздел"] == "Поручения" and r["Содержание"] == "Сделать X"
    )
    assert action["Ответственный"] == "Анна"
    assert action["Спикер"] == "Спикер 1"
    assert action["Срок"] == "пятница"
    assert action["Приоритет"] == "high"

    empty = next(
        r
        for r in rows
        if r["Раздел"] == "Поручения" and r["Содержание"] == "Changelog"
    )
    assert empty["Ответственный"] == ""
    assert empty["Спикер"] == ""
    assert empty["Срок"] == ""


def test_pdf_action_items_are_table():
    story = pdf_story(SAMPLE)
    tables = [item for item in story if isinstance(item, Table)]
    action_tables = [tbl for tbl in tables if tbl._cellvalues and len(tbl._cellvalues[0]) == 5]
    assert action_tables, "поручения в PDF должны быть таблицей, а не строками текста"

    data = action_tables[0]._cellvalues
    header = [_cell_text(c) for c in data[0]]
    assert header == ["Задача", "Ответственный", "Спикер", "Срок", "Приоритет"]
    assert "Сделать X" in _cell_text(data[1][0])
    assert "Анна" in _cell_text(data[1][1])
    assert "Спикер 1" in _cell_text(data[1][2])
    assert "пятница" in _cell_text(data[1][3])
    assert "high" in _cell_text(data[1][4])
    assert "Changelog" in _cell_text(data[2][0])


def test_pdf_contains_risks_section():
    story = pdf_story(SAMPLE)
    texts = []
    for item in story:
        text = getattr(item, "text", None)
        if text:
            texts.append(str(text))
        elif isinstance(item, Table):
            for row in item._cellvalues:
                for cell in row:
                    texts.append(_cell_text(cell))
    blob = "\n".join(texts)
    assert "Риски и блокеры" in blob
    assert "Борис против релиза в пятницу" in blob
    assert "Пиковая нагрузка на API" in blob
