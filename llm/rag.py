"""Local RAG over a meeting: BM25 retrieval + existing Ollama LLM. No extra models."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from ingest.turns import Turn, parse_speaker_turns
from llm.client import DEFAULT_MODEL, chat
from llm.prompt import build_rag_system, build_rag_user, normalize_output_lang

_WORD = re.compile(r"[a-zа-яёәіңғүұқөһ0-9]+", re.IGNORECASE)
_BM25_K1 = 1.5
_BM25_B = 0.75


@dataclass
class Chunk:
    chunk_id: str
    text: str
    source: str
    speaker: str | None = None


@dataclass
class MeetingIndex:
    chunks: list[Chunk]
    _avgdl: float = 1.0
    _df: dict[str, int] = field(default_factory=dict)
    _tf: list[dict[str, int]] = field(default_factory=list)
    _dl: list[int] = field(default_factory=list)

    def retrieve(self, query: str, k: int = 6) -> list[Chunk]:
        tokens = tokenize(query)
        if not tokens or not self.chunks:
            return []
        n = len(self.chunks)
        scores: list[tuple[float, int]] = []
        for i, tf in enumerate(self._tf):
            score = 0.0
            dl = self._dl[i] or 1
            for term in set(tokens):
                freq = tf.get(term, 0)
                if not freq:
                    continue
                df = self._df.get(term, 0)
                idf = math.log((n - df + 0.5) / (df + 0.5) + 1.0)
                denom = freq + _BM25_K1 * (1.0 - _BM25_B + _BM25_B * dl / self._avgdl)
                score += idf * (freq * (_BM25_K1 + 1.0)) / denom
            if score > 0:
                scores.append((score, i))
        scores.sort(reverse=True)
        seen: set[str] = set()
        hits: list[Chunk] = []
        for _, i in scores:
            chunk = self.chunks[i]
            key = f"{chunk.speaker or ''}|{chunk.text}"
            if key in seen:
                continue
            seen.add(key)
            hits.append(chunk)
            if len(hits) >= k:
                break
        return hits


def tokenize(text: str) -> list[str]:
    raw = (text or "").lower()
    words = _WORD.findall(raw)
    compact = _WORD.sub(lambda m: m.group(0), raw)
    compact = re.sub(r"[^a-zа-яёәіңғүұқөһ0-9]+", "", compact.lower())
    grams = [compact[i : i + 3] for i in range(max(0, len(compact) - 2))]
    return words + grams


def _fit_index(chunks: list[Chunk]) -> MeetingIndex:
    tfs: list[dict[str, int]] = []
    df: dict[str, int] = {}
    dl: list[int] = []
    for chunk in chunks:
        tokens = tokenize(chunk.text)
        tf: dict[str, int] = {}
        for tok in tokens:
            tf[tok] = tf.get(tok, 0) + 1
        tfs.append(tf)
        dl.append(max(len(tokens), 1))
        for tok in tf:
            df[tok] = df.get(tok, 0) + 1
    avgdl = (sum(dl) / len(dl)) if dl else 1.0
    return MeetingIndex(chunks=chunks, _avgdl=avgdl, _df=df, _tf=tfs, _dl=dl)


def _plain_chunks(text: str, size: int = 500, overlap: int = 80) -> list[str]:
    body = (text or "").strip()
    if not body:
        return []
    if len(body) <= size:
        return [body]
    parts: list[str] = []
    i = 0
    while i < len(body):
        end = min(len(body), i + size)
        if end < len(body):
            cut = body.rfind(". ", i + size // 2, end)
            if cut != -1:
                end = cut + 1
        piece = body[i:end].strip()
        if piece:
            parts.append(piece)
        if end >= len(body):
            break
        i = max(end - overlap, i + 1)
    return parts


def protocol_chunks(protocol: dict[str, Any] | None) -> list[Chunk]:
    if not protocol:
        return []
    chunks: list[Chunk] = []

    title = str(protocol.get("title") or "").strip()
    if title:
        chunks.append(Chunk("title-0", f"Название встречи: {title}", "title"))

    for i, line in enumerate(protocol.get("executive_summary") or []):
        text = str(line).strip()
        if text:
            chunks.append(Chunk(f"summary-{i}", f"Выжимка: {text}", "summary"))

    for i, line in enumerate(protocol.get("decisions") or []):
        text = str(line).strip()
        if text:
            chunks.append(Chunk(f"decision-{i}", f"Решение: {text}", "decision"))

    for i, line in enumerate(protocol.get("topics") or []):
        text = str(line).strip()
        if text:
            chunks.append(Chunk(f"topic-{i}", f"Тема: {text}", "topic"))

    for i, line in enumerate(protocol.get("open_questions") or []):
        text = str(line).strip()
        if text:
            chunks.append(Chunk(f"open-{i}", f"Открытый вопрос: {text}", "open"))

    for i, item in enumerate(protocol.get("action_items") or []):
        if not isinstance(item, dict):
            continue
        bits = [
            str(item.get("task") or "").strip(),
            f"ответственный {item['assignee']}" if item.get("assignee") else "",
            f"срок {item['deadline']}" if item.get("deadline") else "",
            f"спикер {item['speaker']}" if item.get("speaker") else "",
        ]
        text = "Поручение: " + "; ".join(b for b in bits if b)
        if str(item.get("task") or "").strip():
            chunks.append(
                Chunk(
                    f"action-{i}",
                    text,
                    "action",
                    speaker=str(item["speaker"]) if item.get("speaker") else None,
                )
            )

    for i, item in enumerate(protocol.get("risks") or []):
        if not isinstance(item, dict):
            continue
        bits = [
            str(item.get("kind") or "").strip(),
            str(item.get("description") or "").strip(),
            f"цитата: {item['quote']}" if item.get("quote") else "",
        ]
        text = "Риск: " + "; ".join(b for b in bits if b)
        if str(item.get("description") or "").strip():
            chunks.append(
                Chunk(
                    f"risk-{i}",
                    text,
                    "risk",
                    speaker=str(item["speaker"]) if item.get("speaker") else None,
                )
            )

    return chunks


def build_index(
    transcript: str | None,
    protocol: dict[str, Any] | None = None,
    turns: list[Turn] | None = None,
) -> MeetingIndex:
    chunks: list[Chunk] = []
    parsed = turns if turns is not None else parse_speaker_turns(transcript or "")
    if parsed:
        for turn in parsed:
            chunks.append(
                Chunk(
                    f"turn-{turn.index}",
                    turn.text,
                    "turn",
                    speaker=turn.speaker,
                )
            )
        for i, (a, b) in enumerate(zip(parsed, parsed[1:])):
            chunks.append(
                Chunk(
                    f"window-{i}",
                    f"{a.speaker}: {a.text}\n{b.speaker}: {b.text}",
                    "window",
                )
            )
    else:
        for i, piece in enumerate(_plain_chunks(transcript or "")):
            chunks.append(Chunk(f"plain-{i}", piece, "transcript"))
    chunks.extend(protocol_chunks(protocol))
    return _fit_index(chunks)


ChatFn = Callable[..., str]


def answer_meeting_question(
    question: str,
    *,
    index: MeetingIndex,
    protocol: dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
    model: str = DEFAULT_MODEL,
    output_lang: str = "ru",
    chat_fn: ChatFn | None = None,
    k: int = 6,
) -> dict[str, Any]:
    q = (question or "").strip()
    if not q:
        raise ValueError("Пустой вопрос")

    hits = index.retrieve(q, k=k)
    lang = normalize_output_lang(output_lang)
    prior = [
        item
        for item in (history or [])
        if item.get("role") in {"user", "assistant"} and item.get("content")
    ][-6:]
    messages = [
        {"role": "system", "content": build_rag_system(lang)},
        {
            "role": "user",
            "content": build_rag_user(
                question=q,
                protocol=protocol,
                hits=hits,
                history=prior,
                output_lang=lang,
            ),
        },
    ]
    fn = chat_fn or chat
    raw = fn(
        messages,
        model=model,
        json_mode=False,
        temperature=0.1,
        num_predict=1024,
    )
    answer = (raw or "").strip()
    if not answer:
        raise ValueError("Пустой ответ модели")
    return {"answer": answer, "sources": hits}
