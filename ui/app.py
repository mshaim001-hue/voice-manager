"""Streamlit UI — один экран: файл/текст → протокол → скачать."""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from asr import DEFAULT_WHISPER_MODEL, ASRError, transcribe
from asr.diarize import DiarizationError, models_ready
from ingest.turns import is_dialogue, parse_speaker_turns
from llm.rag import answer_meeting_question, build_index
from ui.chat import meeting_chat_html
import export as export_mod

export_mod = importlib.reload(export_mod)
export_all = export_mod.export_all
from llm.client import DEFAULT_MODEL, OllamaError
from llm.pipeline import polish_transcript, text_to_protocol
from ui.highlight import highlight_quotes_html
from ui.i18n import LANG_LABELS, UI_LANGS, normalize_ui_lang, t

AUDIO_TYPES = ["wav", "mp3", "m4a", "webm", "ogg", "flac"]

_RISK_STYLE = {
    "disagreement": ("#FFF6E8", "#FFA421"),
    "disputed": ("#F7F0FB", "#8E44AD"),
    "technical": ("#FFF1E6", "#E67E22"),
    "blocker": ("#FDECEC", "#E74C3C"),
}


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _risk_card_html(item: dict, ui: str) -> str:
    kind = str(item.get("kind") or "")
    bg, accent = _RISK_STYLE.get(kind, ("#F0F2F6", "#808495"))
    label = t(ui, f"risk_kind_{kind}") if kind else kind
    desc = _esc(str(item.get("description") or ""))
    speaker = item.get("speaker")
    severity = str(item.get("severity") or "unknown")
    quote = item.get("quote")
    meta = " · ".join(
        part
        for part in (
            _esc(label),
            _esc(severity),
            _esc(str(speaker)) if speaker else "",
        )
        if part
    )
    quote_html = (
        f'<div style="margin-top:6px;font-style:italic;color:#555">«{_esc(str(quote))}»</div>'
        if quote
        else ""
    )
    return (
        f'<div style="border-left:4px solid {accent};background:{bg};'
        f'padding:10px 12px;border-radius:6px;margin-bottom:8px">'
        f'<div style="font-size:12px;color:{accent};font-weight:700">{meta}</div>'
        f'<div style="margin-top:4px">{desc}</div>{quote_html}</div>'
    )


def _init_state() -> None:
    defaults = {
        "protocol": None,
        "transcript": None,
        "transcript_raw": None,
        "error": None,
        "timing": None,
        "exports": None,
        "ui_lang": "ru",
        "turns": None,
        "rag_index": None,
        "chat_qa": None,
        "is_dialogue": False,
        "diarized": False,
        "result_view": "protocol",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _run_pipeline(
    *,
    transcript: str | None,
    audio_path: Path | None,
    llm_model: str,
    whisper_model: str,
    language: str,
    diarize_speakers: bool,
    num_speakers: int,
    polish: bool,
    output_lang: str,
    ui: str,
) -> None:
    st.session_state.error = None
    st.session_state.protocol = None
    st.session_state.exports = None
    st.session_state.transcript_raw = None
    wall0 = time.perf_counter()
    asr_s = 0.0
    polish_s = 0.0

    progress = st.progress(0, text=t(ui, "progress_start"))
    status = st.empty()

    try:
        if audio_path is not None:
            status.info(
                t(ui, "status_asr")
                + (
                    t(ui, "status_asr_diarize")
                    if diarize_speakers
                    else t(ui, "status_asr_whisper")
                )
            )
            progress.progress(12, text=t(ui, "progress_asr"))
            t0 = time.perf_counter()
            transcript = transcribe(
                audio_path,
                model_size=whisper_model,
                language=language,
                diarize_speakers=diarize_speakers,
                num_speakers=num_speakers,
            )
            asr_s = time.perf_counter() - t0
            progress.progress(35, text=t(ui, "progress_asr_done", s=asr_s))
        else:
            progress.progress(20, text=t(ui, "progress_text_ok"))

        if not transcript or not transcript.strip():
            raise ValueError(t(ui, "err_empty"))

        st.session_state.transcript_raw = transcript

        if polish:
            status.info(t(ui, "status_polish"))
            progress.progress(50, text=t(ui, "progress_polish"))
            t_p = time.perf_counter()
            transcript = polish_transcript(
                transcript, model=llm_model, output_lang=output_lang
            )
            polish_s = time.perf_counter() - t_p
            progress.progress(65, text=t(ui, "progress_polish_done", s=polish_s))

        st.session_state.transcript = transcript
        status.info(t(ui, "status_protocol"))
        progress.progress(70, text=t(ui, "progress_protocol"))
        t1 = time.perf_counter()
        protocol = text_to_protocol(
            transcript, model=llm_model, output_lang=output_lang
        )
        llm_s = time.perf_counter() - t1
        payload = protocol.model_dump(mode="json")

        progress.progress(90, text=t(ui, "progress_export"))
        export_dir = ROOT / "output" / "ui_export"
        paths = export_all(payload, export_dir, stem="protocol", lang=ui)
        exports = {k: p.read_bytes() for k, p in paths.items()}

        progress.progress(100, text=t(ui, "progress_done"))
        total = time.perf_counter() - wall0
        turns = parse_speaker_turns(transcript)
        if not is_dialogue(turns):
            raw_turns = parse_speaker_turns(st.session_state.transcript_raw or "")
            if is_dialogue(raw_turns):
                turns = raw_turns
        st.session_state.turns = turns
        st.session_state.is_dialogue = is_dialogue(turns)
        st.session_state.diarized = bool(diarize_speakers) or st.session_state.is_dialogue
        st.session_state.rag_index = build_index(transcript, payload, turns)
        st.session_state.chat_qa = []
        st.session_state.result_view = (
            "chat" if st.session_state.diarized else "protocol"
        )
        st.session_state.protocol = payload
        st.session_state.exports = exports
        st.session_state.timing = {
            "asr_s": round(asr_s, 1),
            "polish_s": round(polish_s, 1),
            "llm_s": round(llm_s, 1),
            "total_s": round(total, 1),
        }
        status.success(
            t(
                ui,
                "status_ok",
                total=total,
                asr=asr_s,
                polish=polish_s,
                llm=llm_s,
            )
        )
    except (ASRError, DiarizationError, OllamaError, ValueError) as e:
        st.session_state.error = str(e)
        status.error(t(ui, "status_err", e=e))
        progress.progress(0, text=t(ui, "progress_err"))
    except Exception as e:
        msg = str(e)
        if "Format not recognised" in msg or "Error opening" in msg:
            msg = f"{msg}{t(ui, 'err_format_hint')}"
        st.session_state.error = msg
        status.error(t(ui, "status_err", e=msg))
        progress.progress(0, text=t(ui, "progress_err"))


def _ask_meeting(question: str, *, llm_model: str, ui: str) -> None:
    q = question.strip()
    if not q:
        return
    if st.session_state.chat_qa is None:
        st.session_state.chat_qa = []
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.chat_qa
        if m.get("role") in {"user", "assistant"} and m.get("content")
    ]
    st.session_state.chat_qa.append({"role": "user", "content": q})
    index = st.session_state.rag_index
    if index is None:
        index = build_index(
            st.session_state.transcript,
            st.session_state.protocol,
            st.session_state.turns,
        )
        st.session_state.rag_index = index
    try:
        with st.spinner(t(ui, "chat_spinner")):
            result = answer_meeting_question(
                q,
                index=index,
                protocol=st.session_state.protocol,
                history=history,
                model=llm_model,
                output_lang=ui,
            )
        st.session_state.chat_qa.append(
            {
                "role": "assistant",
                "content": result["answer"],
                "sources": result.get("sources") or [],
            }
        )
    except Exception as e:
        st.session_state.chat_qa.append(
            {"role": "assistant", "content": str(e), "sources": []}
        )


def main() -> None:
    _init_state()
    ui = normalize_ui_lang(st.session_state.get("ui_lang", "ru"))

    st.set_page_config(
        page_title="Voice Manager",
        page_icon="📝",
        layout="centered",
    )

    with st.sidebar:
        lang_choice = st.selectbox(
            t(ui, "ui_lang"),
            options=list(UI_LANGS),
            index=list(UI_LANGS).index(ui),
            format_func=lambda c: f"{LANG_LABELS[c]} ({c})",
            help=t(ui, "ui_lang_help"),
        )
        if lang_choice != ui:
            st.session_state.ui_lang = lang_choice
            st.rerun()
        ui = normalize_ui_lang(st.session_state.ui_lang)

        llm_model = DEFAULT_MODEL
        whisper_model = DEFAULT_WHISPER_MODEL
        st.subheader(t(ui, "sidebar_models"))
        st.caption(
            t(ui, "sidebar_models_fixed", llm=llm_model, whisper=whisper_model)
        )
        language = st.selectbox(
            t(ui, "audio_lang"),
            options=["auto", "ru", "en", "kk"],
            index=1,
            help=t(ui, "audio_lang_help"),
        )
        diarize_on = st.checkbox(
            t(ui, "diarize"),
            value=False,
            help=t(ui, "diarize_help"),
        )
        num_speakers = st.number_input(
            t(ui, "num_speakers"),
            min_value=0,
            max_value=8,
            value=2 if diarize_on else 0,
            disabled=not diarize_on,
        )
        if diarize_on and not models_ready():
            st.warning(t(ui, "diarize_missing"))
        polish_on = st.checkbox(
            t(ui, "polish"),
            value=True,
            help=t(ui, "polish_help"),
        )
        st.markdown("---")
        st.caption(t(ui, "sidebar_note_kk"))
        st.caption(t(ui, "sidebar_note_ollama"))

    st.title("Voice Manager")
    st.caption(t(ui, "caption"))

    tab_file, tab_text = st.tabs([t(ui, "tab_file"), t(ui, "tab_text")])

    audio_file = None
    text_value = ""
    with tab_file:
        audio_file = st.file_uploader(
            t(ui, "upload"),
            type=AUDIO_TYPES,
            help=t(ui, "upload_help"),
        )
    with tab_text:
        text_value = st.text_area(
            t(ui, "paste"),
            height=220,
            placeholder=t(ui, "paste_ph"),
        )

    col_run, col_clear = st.columns([2, 1])
    with col_run:
        run = st.button(t(ui, "run"), type="primary", use_container_width=True)
    with col_clear:
        if st.button(t(ui, "clear"), use_container_width=True):
            for k in (
                "protocol",
                "transcript",
                "transcript_raw",
                "error",
                "timing",
                "exports",
                "turns",
                "rag_index",
                "chat_qa",
            ):
                st.session_state[k] = None
            st.session_state.is_dialogue = False
            st.session_state.diarized = False
            st.session_state.result_view = "protocol"
            st.rerun()

    if run:
        tmp_path: Path | None = None
        try:
            if audio_file is not None:
                suffix = Path(audio_file.name).suffix.lower() or ".wav"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(audio_file.getvalue())
                    tmp_path = Path(tmp.name)
                _run_pipeline(
                    transcript=None,
                    audio_path=tmp_path,
                    llm_model=llm_model,
                    whisper_model=whisper_model,
                    language=language,
                    diarize_speakers=diarize_on,
                    num_speakers=int(num_speakers) if num_speakers else -1,
                    polish=polish_on,
                    output_lang=ui,
                    ui=ui,
                )
            elif text_value.strip():
                _run_pipeline(
                    transcript=text_value,
                    audio_path=None,
                    llm_model=llm_model,
                    whisper_model=whisper_model,
                    language=language,
                    diarize_speakers=False,
                    num_speakers=-1,
                    polish=polish_on,
                    output_lang=ui,
                    ui=ui,
                )
            else:
                st.warning(t(ui, "need_input"))
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    if st.session_state.error and not st.session_state.protocol:
        st.error(st.session_state.error)

    protocol = st.session_state.protocol
    if protocol:
        st.markdown("---")
        st.subheader(protocol.get("title") or t(ui, "protocol_fallback"))

        if st.session_state.timing:
            timing = st.session_state.timing
            polish_part = (
                t(ui, "timing_polish", s=timing["polish_s"])
                if timing.get("polish_s")
                else ""
            )
            st.caption(
                t(
                    ui,
                    "timing",
                    asr=timing["asr_s"],
                    polish=polish_part,
                    llm=timing["llm_s"],
                    total=timing["total_s"],
                )
            )

        view = st.radio(
            "result_view",
            options=["protocol", "chat"],
            format_func=lambda k: t(ui, f"view_{k}"),
            horizontal=True,
            label_visibility="collapsed",
            key="result_view",
        )

        if view == "chat":
            turns = st.session_state.turns or []
            show_turns = (
                turns if (st.session_state.diarized or is_dialogue(turns)) else []
            )
            if not show_turns:
                st.caption(t(ui, "chat_no_dialogue"))
            qa = st.session_state.chat_qa or []
            st.markdown(
                meeting_chat_html(show_turns, qa, ui_lang=ui),
                unsafe_allow_html=True,
            )
            if not qa:
                st.caption(t(ui, "chat_empty"))
            prompt = st.chat_input(t(ui, "chat_input"))
            if prompt:
                _ask_meeting(prompt, llm_model=llm_model, ui=ui)
                st.rerun()
        else:
            st.markdown(f"**{t(ui, 'summary')}**")
            for line in protocol.get("executive_summary") or []:
                st.write(f"- {line}")

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**{t(ui, 'decisions')}**")
                for d in protocol.get("decisions") or []:
                    st.write(f"- {d}")
                st.markdown(f"**{t(ui, 'topics')}**")
                for topic in protocol.get("topics") or []:
                    st.write(f"- {topic}")
            with c2:
                st.markdown(f"**{t(ui, 'open_questions')}**")
                qs = protocol.get("open_questions") or []
                if qs:
                    for q in qs:
                        st.write(f"- {q}")
                else:
                    st.write(t(ui, "empty"))

            st.markdown(f"**{t(ui, 'risks')}**")
            risks = protocol.get("risks") or []
            if risks:
                cards = "".join(_risk_card_html(item, ui) for item in risks)
                st.markdown(cards, unsafe_allow_html=True)
            else:
                st.write(t(ui, "empty"))

            st.markdown(f"**{t(ui, 'actions')}**")
            items = protocol.get("action_items") or []
            if items:
                st.dataframe(items, use_container_width=True, hide_index=True)
            else:
                st.write(t(ui, "empty"))

            exports = st.session_state.exports or {}
            st.markdown(f"**{t(ui, 'download')}**")
            d1, d2, d3 = st.columns(3)
            with d1:
                st.download_button(
                    "JSON",
                    data=exports.get("json")
                    or json.dumps(protocol, ensure_ascii=False, indent=2).encode(
                        "utf-8"
                    ),
                    file_name="protocol.json",
                    mime="application/json",
                    use_container_width=True,
                )
            with d2:
                st.download_button(
                    "CSV",
                    data=exports.get("csv") or b"",
                    file_name="protocol.csv",
                    mime="text/csv",
                    use_container_width=True,
                    disabled="csv" not in exports,
                )
            with d3:
                st.download_button(
                    "PDF",
                    data=exports.get("pdf") or b"",
                    file_name="protocol.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    disabled="pdf" not in exports,
                )

            with st.expander(
                t(ui, "transcript"), expanded=not st.session_state.diarized
            ):
                st.caption(t(ui, "transcript_cap"))
                quotes = [
                    str(item.get("quote"))
                    for item in protocol.get("risks") or []
                    if item.get("quote")
                ]
                transcript_text = st.session_state.transcript or ""
                if quotes:
                    st.caption(t(ui, "transcript_marks"))
                    st.markdown(
                        highlight_quotes_html(transcript_text, quotes),
                        unsafe_allow_html=True,
                    )
                else:
                    st.text(transcript_text)
                raw = st.session_state.transcript_raw
                polished = st.session_state.transcript
                if raw and polished and raw.strip() != (polished or "").strip():
                    with st.expander(t(ui, "transcript_raw")):
                        st.text(raw)


if __name__ == "__main__":
    main()
