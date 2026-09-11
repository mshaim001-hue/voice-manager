"""Schema unit tests — no LLM required."""

from schema.protocol import ActionItem, MeetingProtocol, Priority


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
