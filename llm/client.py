"""Minimal Ollama HTTP client (localhost only)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

DEFAULT_BASE_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
# Default: gemma3:12b — JSON + multilingual on M4 24GB; override via OLLAMA_MODEL
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:12b")
CANDIDATE_MODELS = (
    "gemma3:12b",
    "qwen3:14b",
    "qwen2.5:14b",
)


class OllamaError(RuntimeError):
    pass


def _extract_json(text: str) -> str:
    """Strip markdown fences and isolate the first JSON object."""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise OllamaError("Ответ модели не содержит JSON-объект")
    return cleaned[start : end + 1]


def _wants_no_think(model: str) -> bool:
    """Qwen3 thinking mode often breaks JSON — disable it."""
    name = model.lower()
    return name.startswith("qwen3") or ":qwen3" in name


def chat(
    messages: list[dict[str, str]],
    *,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    temperature: float = 0.0,
    timeout: float = 300.0,
    json_mode: bool = True,
    num_predict: int = 2048,
) -> str:
    url = f"{base_url.rstrip('/')}/api/chat"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }
    if json_mode:
        payload["format"] = "json"
    if _wants_no_think(model):
        payload["think"] = False

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.ConnectError as e:
        raise OllamaError(
            f"Ollama недоступна на {base_url}. Запусти: ollama serve && ollama pull {model}"
        ) from e
    except httpx.HTTPError as e:
        raise OllamaError(f"Ошибка Ollama HTTP: {e}") from e

    content = (data.get("message") or {}).get("content")
    if not content:
        raise OllamaError(f"Пустой ответ Ollama: {data!r}")
    return content


def chat_json(
    messages: list[dict[str, str]],
    *,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
) -> dict[str, Any]:
    raw = chat(messages, model=model, base_url=base_url)
    try:
        return json.loads(_extract_json(raw))
    except json.JSONDecodeError as e:
        raise OllamaError(f"Невалидный JSON от модели: {e}\n---\n{raw[:800]}") from e
