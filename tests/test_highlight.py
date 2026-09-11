"""Transcript quote highlighting — no LLM."""

from ui.highlight import highlight_quotes_html


def test_highlight_wraps_known_quote():
    html = highlight_quotes_html(
        "Анна: релиз в пятницу.\nБорис: Я против пятницы, инфра не выдержит.",
        ["Я против пятницы, инфра не выдержит"],
    )
    assert "<mark>" in html
    assert "Я против пятницы, инфра не выдержит" in html
    assert html.count("<mark>") == 1


def test_highlight_escapes_html_and_skips_missing_quotes():
    html = highlight_quotes_html(
        "Катя: риск <script>alert(1)</script> в платежах.",
        ["этой цитаты нет в тексте"],
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<mark>" not in html
