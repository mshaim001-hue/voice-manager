"""Schema unit tests — no LLM required."""

import pytest
from pydantic import ValidationError

from schema.protocol import ActionItem, MeetingProtocol, Priority, RiskItem, RiskKind


def test_empty_deadline_and_assignee_become_null():
    item = ActionItem(
        task="Обновить changelog",
        assignee="",
        deadline="null",
        priority=Priority.unknown,
    )
    assert item.assignee is None
    assert item.deadline is None


def test_protocol_accepts_minimal_valid():
    p = MeetingProtocol(
        title="Тест",
        executive_summary=["Коротко о встрече.", "Второе предложение.", "Третье."],
        decisions=["Релиз в пятницу"],
        topics=["Релиз", "Баги"],
        open_questions=["Анимация лоадера?"],
        action_items=[
            ActionItem(task="Починить токены", assignee="Борис", deadline="среда", priority=Priority.high),
            ActionItem(task="Changelog", assignee=None, deadline=None),
        ],
    )
    assert p.action_items[1].assignee is None
    assert p.action_items[1].deadline is None
    assert p.risks == []


def test_risk_empty_speaker_and_quote_become_null():
    item = RiskItem(
        kind=RiskKind.blocker,
        description="Миграция БД не готова",
        speaker="",
        quote="null",
        severity=Priority.high,
    )
    assert item.speaker is None
    assert item.quote is None


def test_protocol_accepts_risks_and_blockers():
    p = MeetingProtocol(
        title="Тест",
        executive_summary=["Коротко о встрече."],
        risks=[
            RiskItem(
                kind=RiskKind.disagreement,
                description="Борис против релиза в пятницу",
                speaker="Борис",
                quote="Я против пятницы, инфра не выдержит",
                severity=Priority.high,
            ),
            RiskItem(
                kind=RiskKind.technical,
                description="Нагрузка на API при пике онбординга",
                severity=Priority.medium,
            ),
        ],
    )
    assert p.risks[0].kind is RiskKind.disagreement
    assert p.risks[1].kind is RiskKind.technical
    dumped = p.model_dump(mode="json")
    assert dumped["risks"][0]["kind"] == "disagreement"


def test_risk_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        RiskItem(kind="politics", description="Спор о приоритетах")
