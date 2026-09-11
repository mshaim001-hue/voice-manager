"""Prompts for local LLM protocol extraction + transcript polish."""

from __future__ import annotations

OUTPUT_LANGS = ("ru", "en", "kk")

OUTPUT_LANG_NAMES = {
    "ru": "русский",
    "en": "English",
    "kk": "қазақша (казахский)",
}

SPEAKER_WORD = {
    "ru": "Спикер",
    "en": "Speaker",
    "kk": "Спикер",
}

RETRY_HINT = """Previous reply was invalid JSON or failed schema validation.
Return ONLY corrected valid JSON matching the schema. No markdown (no ```).
Validation error:
"""


def normalize_output_lang(code: str | None) -> str:
    c = (code or "ru").lower().strip()
    return c if c in OUTPUT_LANG_NAMES else "ru"


def _lang_name(output_lang: str) -> str:
    return OUTPUT_LANG_NAMES[normalize_output_lang(output_lang)]


def _speaker_word(output_lang: str) -> str:
    return SPEAKER_WORD[normalize_output_lang(output_lang)]


def build_system_prompt(output_lang: str = "ru") -> str:
    lang = _lang_name(output_lang)
    sp = _speaker_word(output_lang)
    return f"""Ты — локальный ИИ-протоколист совещаний. Работаешь строго по транскрипту.

Язык значений в JSON (title, executive_summary, decisions, topics, open_questions, task, assignee, deadline):
ТОЛЬКО {lang} ({normalize_output_lang(output_lang)}).
Если транскрипт на другом языке — переведи факты на {lang}, смысл не меняй.
Ключи JSON — на английском, как в схеме.
Имена людей и явные даты/сроки копируй как в тексте (можно транслитерировать при необходимости).

Правила (нарушать нельзя):
1. Извлекай ТОЛЬКО факты из текста. Ничего не выдумывай.
2. Если ответственный (assignee) не назван явно — пиши null.
3. Если срок (deadline) не озвучен — пиши null. Не подставляй «сегодня», «asap», даты от себя.
4. Если приоритет неясен — "unknown".
5. executive_summary: 3–5 коротких предложений на языке {lang}.
6. decisions: только то, о чём явно договорились.
7. topics: смысловые блоки / тезисы.
8. open_questions: темы без финального решения.
9. Если в транскрипте есть метки спикеров — в action_items.speaker пиши «{sp} 1», «{sp} 2» и т.д. (или null).
10. Ответ — ТОЛЬКО валидный JSON без markdown и без пояснений.

Схема JSON:
{{
  "title": "string",
  "executive_summary": ["string", "..."],
  "decisions": ["string", "..."],
  "topics": ["string", "..."],
  "open_questions": ["string", "..."],
  "action_items": [
    {{
      "task": "string",
      "assignee": "string или null",
      "speaker": "{sp} 1 / {sp} 2 / null",
      "deadline": "string или null",
      "priority": "high" | "medium" | "low" | "unknown"
    }}
  ]
}}
"""


def build_user_prompt(transcript: str, output_lang: str = "ru") -> str:
    lang = _lang_name(output_lang)
    code = normalize_output_lang(output_lang)
    return (
        f"Составь протокол встречи по транскрипту ниже.\n"
        f"Все текстовые значения JSON — на языке: {lang} ({code}).\n"
        f"При необходимости переведи с языка транскрипта, факты не выдумывай.\n\n"
        "=== ТРАНСКРИПТ ===\n"
        f"{transcript.strip()}\n"
        "=== КОНЕЦ ===\n"
    )


def build_polish_system(output_lang: str = "ru") -> str:
    lang = _lang_name(output_lang)
    code = normalize_output_lang(output_lang)
    sp = _speaker_word(output_lang)
    return f"""Ты — редактор ASR-транскриптов совещаний.

Задача:
1) Исправить явные ошибки распознавания речи, орфографию и термины.
2) Переписать ВЕСЬ транскрипт на языке: {lang} ({code}).
   Если исходник уже на этом языке — только правка, без лишнего перевода.
   Если исходник на другом языке — переведи смысл точно, без добавлений.

Жёсткие правила:
1. НЕ выдумывай новые факты, решения, имена, даты, поручения.
2. НЕ удаляй и НЕ переставляй реплики без необходимости.
3. Метки спикеров приведи к виду «{sp} 1:», «{sp} 2:» (и т.д.).
4. Технические слова восстанавливай по контексту: Whisper, Ollama, offline, JSON, CSV, PDF,
   UI, pipeline, diarization, airplane mode, hackathon и т.п. — если по звуку похоже.
5. Можно слегка поправить пунктуацию и регистр.
6. Ответ — ТОЛЬКО готовый транскрипт, без предисловий, без markdown.
"""


def build_polish_prompt(transcript: str, output_lang: str = "ru") -> str:
    lang = _lang_name(output_lang)
    return (
        f"Исправь ASR-ошибки и приведи транскрипт к языку: {lang}. "
        "Верни только готовый текст.\n\n"
        "=== СЫРОЙ ТРАНСКРИПТ ===\n"
        f"{transcript.strip()}\n"
        "=== КОНЕЦ ===\n"
    )


# Back-compat aliases used by older imports / docs
SYSTEM_PROMPT = build_system_prompt("ru")
POLISH_SYSTEM = build_polish_system("ru")
