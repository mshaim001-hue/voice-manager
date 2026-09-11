"""Export round-trip checks — no LLM."""

import csv
import json
from pathlib import Path

from export import export_all


def test_export_fields_match(tmp_path: Path):
    protocol = {
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
    }
    paths = export_all(protocol, tmp_path, stem="protocol")
    assert paths["json"].is_file()
    assert paths["csv"].is_file()
    assert paths["pdf"].is_file()
    assert paths["pdf"].stat().st_size > 500

    loaded = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert loaded["title"] == protocol["title"]
    assert loaded["action_items"] == protocol["action_items"]

    with paths["csv"].open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["task"] == "Сделать X"
    assert rows[0]["assignee"] == "Анна"
    assert rows[0]["speaker"] == "Спикер 1"
    assert rows[0]["deadline"] == "пятница"
    assert rows[1]["assignee"] == ""
    assert rows[1]["speaker"] == ""
    assert rows[1]["deadline"] == ""
