"""Pydantic schema for the meeting protocol (must-have fields)."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Priority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    unknown = "unknown"


class ActionItem(BaseModel):
    task: str = Field(..., min_length=1, description="Суть поручения")
    assignee: Optional[str] = Field(
        default=None,
        description="Ответственный. null, если в тексте не назван явно",
    )
    speaker: Optional[str] = Field(
        default=None,
        description="Спикер из диаризации (Спикер 1/2…), если есть в транскрипте",
    )
    deadline: Optional[str] = Field(
        default=None,
        description="Срок, только если озвучен. Иначе null. Не выдумывать.",
    )
    priority: Priority = Field(
        default=Priority.unknown,
        description="Приоритет, если следует из текста; иначе unknown",
    )

    @field_validator("assignee", "deadline", "speaker", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str) and v.strip().lower() in {
            "",
            "null",
            "none",
            "n/a",
            "-",
            "не указан",
            "не указано",
        }:
            return None
        return v


class MeetingProtocol(BaseModel):
    title: str = Field(default="Протокол встречи", description="Краткое название встречи")
    executive_summary: list[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="3–5 ключевых предложений для руководителя",
    )
    decisions: list[str] = Field(
        default_factory=list,
        description="Принятые решения",
    )
    topics: list[str] = Field(
        default_factory=list,
        description="Темы и тезисы (смысловые блоки)",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Открытые вопросы без финального решения",
    )
    action_items: list[ActionItem] = Field(
        default_factory=list,
        description="Таблица поручений",
    )

    @field_validator("executive_summary", mode="before")
    @classmethod
    def coerce_summary(cls, v: object) -> object:
        if isinstance(v, str):
            parts = [p.strip() for p in v.replace("\n", " ").split(".") if p.strip()]
            return [p if p.endswith(".") else f"{p}." for p in parts[:5]] or [v]
        return v