"""Messenger HTML for diarized turns — no Streamlit."""

from ui.chat import meeting_chat_html
from ingest.turns import parse_speaker_turns


def test_speaker_bubbles_look_like_messages():
    turns = parse_speaker_turns(
        "Спикер 1: Нужно выкатить онбординг.\nСпикер 2: Я против пятницы."
    )
    html = meeting_chat_html(turns, qa=[], ui_lang="ru")
    assert "Спикер 1" in html
    assert "Спикер 2" in html
    assert "Нужно выкатить онбординг." in html
    assert "vm-bubble" in html
    assert "vm-row" in html
    s1 = html.find("Нужно выкатить онбординг.")
    s2 = html.find("Я против пятницы.")
    left_row = html.rfind("class=\"vm-row", 0, s1)
    right_row = html.rfind("class=\"vm-row", 0, s2)
    assert html[left_row : left_row + 24].startswith('class="vm-row"')
    assert 'class="vm-row right"' in html[right_row : right_row + 24]


def test_user_messages_align_right_and_escape_html():
    html = meeting_chat_html(
        [],
        qa=[
            {"role": "user", "content": "<script>alert(1)</script>"},
            {"role": "assistant", "content": "Ответ про <релиз>"},
        ],
        ui_lang="ru",
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "vm-row right" in html
    assert "&lt;релиз&gt;" in html
