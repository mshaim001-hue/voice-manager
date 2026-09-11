"""Text transcript → optional polish → validated MeetingProtocol."""

from __future__ import annotations

from pydantic import ValidationError

from llm.client import DEFAULT_MODEL, OllamaError, chat, chat_json
from llm.prompt import (
    RETRY_HINT,
    build_polish_prompt,
    build_polish_system,
    build_system_prompt,
    build_user_prompt,
    normalize_output_lang,
)
from schema.protocol import MeetingProtocol


def polish_transcript(
    transcript: str,
    *,
    model: str = DEFAULT_MODEL,
    output_lang: str = "ru",
) -> str:
    """LLM cleanup (+ optional rewrite into output_lang) — no invented facts."""
    if not transcript or not transcript.strip():
        raise ValueError("Пустой транскрипт")

    lang = normalize_output_lang(output_lang)
    messages = [
        {"role": "system", "content": build_polish_system(lang)},
        {"role": "user", "content": build_polish_prompt(transcript, lang)},
    ]
    raw = chat(
        messages,
        model=model,
        json_mode=False,
        temperature=0.1,
        num_predict=4096,
    )
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    for prefix in (
        "Исправленный транскрипт:",
        "Исправленный текст:",
        "Вот исправленный транскрипт:",
        "Corrected transcript:",
        "Polished transcript:",
    ):
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix) :].lstrip(" \n:")
            break
    if not cleaned:
        raise OllamaError("Пустой ответ при правке транскрипта")
    return cleaned


def text_to_protocol(
    transcript: str,
    *,
    model: str = DEFAULT_MODEL,
    output_lang: str = "ru",
) -> MeetingProtocol:
    if not transcript or not transcript.strip():
        raise ValueError("Пустой транскрипт")

    lang = normalize_output_lang(output_lang)
    messages = [
        {"role": "system", "content": build_system_prompt(lang)},
        {"role": "user", "content": build_user_prompt(transcript, lang)},
    ]

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            data = chat_json(messages, model=model)
            return MeetingProtocol.model_validate(data)
        except (OllamaError, ValidationError, ValueError) as e:
            last_error = e
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": f"{RETRY_HINT}{e}",
                    }
                )
                continue
            break

    raise OllamaError(f"Не удалось получить валидный протокол после retry: {last_error}")
