"""Local lexical RAG over meeting turns + protocol — no extra models."""

from llm.rag import answer_meeting_question, build_index, protocol_chunks


TRANSCRIPT = """Анна: Нужно выкатить онбординг в пятницу. Это финальная дата для демо.
Борис: Я против пятницы, инфра не выдержит. На пике API ляжет.
Анна: Борис, мы обещали пятницу жюри.
Катя: Changelog кто-то должен обновить, ответственного нет.
"""

PROTOCOL = {
    "title": "Онбординг",
    "executive_summary": ["Спор про релиз в пятницу."],
    "decisions": [],
    "topics": ["онбординг", "инфра"],
    "open_questions": ["Нужна ли анимация лоадера?"],
    "action_items": [
        {
            "task": "План смягчения нагрузки",
            "assignee": "Борис",
            "deadline": "среда",
            "priority": "high",
        }
    ],
    "risks": [
        {
            "kind": "disagreement",
            "description": "Борис против релиза в пятницу из-за инфры",
            "speaker": "Борис",
            "quote": "Я против пятницы, инфра не выдержит",
        }
    ],
}


def test_retrieve_speaker_who_disagreed():
    index = build_index(TRANSCRIPT, PROTOCOL)
    hits = index.retrieve("кто против пятницы и почему инфра", k=3)
    blob = " ".join(h.text for h in hits)
    assert "против пятницы" in blob
    assert any(h.speaker == "Борис" for h in hits)


def test_retrieve_action_item_from_protocol():
    index = build_index(TRANSCRIPT, PROTOCOL)
    hits = index.retrieve("план смягчения нагрузки к среде", k=4)
    blob = " ".join(h.text.lower() for h in hits)
    assert "смягчения" in blob or "борис" in blob


def test_protocol_chunks_include_risks_and_actions():
    chunks = protocol_chunks(PROTOCOL)
    kinds = {c.source for c in chunks}
    assert "risk" in kinds
    assert "action" in kinds
    assert "summary" in kinds


def test_answer_uses_retrieved_context_not_invention(monkeypatch):
    index = build_index(TRANSCRIPT, PROTOCOL)
    captured: dict = {}

    def fake_chat(messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return "Борис был против пятницы из-за инфры."

    result = answer_meeting_question(
        "Кто был против релиза в пятницу?",
        index=index,
        protocol=PROTOCOL,
        history=[],
        output_lang="ru",
        chat_fn=fake_chat,
    )
    prompt = "\n".join(m["content"] for m in captured["messages"])
    assert "против пятницы" in prompt
    assert captured["kwargs"].get("json_mode") is False
    assert result["answer"].startswith("Борис")
    assert result["sources"]
    assert any("Борис" in (s.speaker or "") or "против" in s.text for s in result["sources"])
