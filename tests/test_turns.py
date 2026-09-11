"""Parse labeled transcript into messenger-style speaker turns."""

from ingest.turns import is_dialogue, parse_speaker_turns


RISKS = """Встреча продуктовой команды, 11 сентября.

Участники: Анна (PM), Борис (backend), Катя (дизайн).

Анна: Нужно выкатить онбординг в пятницу.
Борис: Я против пятницы, инфра не выдержит.
Катя: И ещё спорный момент — светлая или тёмная тема.
"""

DIARIZED = """Спикер 1: Нужно выкатить онбординг в пятницу. Это финальная дата.
Спикер 2: Я против пятницы, инфра не выдержит.
Спикер 1: Мы обещали пятницу жюри.
"""


def test_parse_named_speakers_skips_header():
    turns = parse_speaker_turns(RISKS)
    speakers = [t.speaker for t in turns]
    assert speakers == ["Анна", "Борис", "Катя"]
    assert "пятницу" in turns[0].text
    assert "против" in turns[1].text
    assert all(t.speaker != "Участники" for t in turns)


def test_parse_diarized_speakers():
    turns = parse_speaker_turns(DIARIZED)
    assert [t.speaker for t in turns] == ["Спикер 1", "Спикер 2", "Спикер 1"]
    assert is_dialogue(turns)


def test_parse_english_speaker_labels():
    text = "Speaker 1: Ship on Friday.\nSpeaker 2: Infra will not survive."
    turns = parse_speaker_turns(text)
    assert [t.speaker for t in turns] == ["Speaker 1", "Speaker 2"]
    assert is_dialogue(turns)


def test_continuation_appends_to_previous_speaker():
    text = "Анна: Первая фраза.\nпродолжение мысли.\nБорис: Ответ."
    turns = parse_speaker_turns(text)
    assert len(turns) == 2
    assert "Первая фраза." in turns[0].text
    assert "продолжение" in turns[0].text
    assert turns[1].speaker == "Борис"


def test_unlabeled_transcript_is_not_dialogue():
    turns = parse_speaker_turns("Обсудили релиз. Решение — пятница.")
    assert turns == []
    assert not is_dialogue(turns)


def test_kazakh_participant_header_skipped():
    text = (
        "Қатысушылар: Айгүл (PM), Ерлан (backend).\n"
        "Айгүл: Релиз жұмада.\n"
        "Ерлан: Келісемін."
    )
    turns = parse_speaker_turns(text)
    assert [t.speaker for t in turns] == ["Айгүл", "Ерлан"]
