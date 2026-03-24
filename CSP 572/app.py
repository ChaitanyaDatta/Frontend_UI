from __future__ import annotations

import csv
import json
import os
import re
from datetime import date
from datetime import datetime
from pathlib import Path
import time
from typing import Any

import requests
import streamlit as st

from components.chat_panel import render_chat_panel
from components.layout import load_css, render_footer_actions, render_title_block


def _init_state() -> None:
    if "history_a" not in st.session_state:
        st.session_state.history_a = [
            {"role": "assistant", "content": "Ask a question to compare model responses."}
        ]
    if "history_b" not in st.session_state:
        st.session_state.history_b = [
            {"role": "assistant", "content": "Ask a question to compare model responses."}
        ]
    if "is_generating" not in st.session_state:
        st.session_state.is_generating = False
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = ""


def _timestamp_now() -> str:
    return datetime.now().strftime("%I:%M %p").lstrip("0")


def _append_message(history_key: str, role: str, content: str) -> None:
    st.session_state[history_key].append(
        {"role": role, "content": content, "timestamp": _timestamp_now()}
    )


def _chunk_dirs() -> list[Path]:
    root = Path(__file__).parent
    return [
        root / "ALL Stuff" / "Chunks",
        root / "Chunks",
        root / "Data" / "Chunks",
    ]


def _find_chunk_file(filename: str) -> Path | None:
    for directory in _chunk_dirs():
        candidate = directory / filename
        if candidate.exists():
            return candidate
    return None


@st.cache_data(show_spinner=False)
def _load_tuition_data() -> list[dict[str, Any]]:
    path = _find_chunk_file("tuition_data.json")
    if not path:
        return []
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload if isinstance(payload, list) else []


@st.cache_data(show_spinner=False)
def _load_calendar_data() -> list[dict[str, Any]]:
    path = _find_chunk_file("calendar_chunks.json")
    if not path:
        return []
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload if isinstance(payload, list) else []


@st.cache_data(show_spinner=False)
def _load_directory_data() -> list[dict[str, str]]:
    path = _find_chunk_file("Contacts data.csv")
    if not path:
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@st.cache_data(show_spinner=False)
def _load_handbook_data() -> list[dict[str, Any]]:
    filenames = [
        "Student handbook.json",
        "Coterminal student handbook.json",
        "Coterminal handbook.json",
        "Unstructured chunks.json",
        "Structured chunks.json",
    ]
    rows: list[dict[str, Any]] = []
    for name in filenames:
        path = _find_chunk_file(name)
        if not path:
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        rows.append(item)
        except Exception:
            continue
    return rows


def _extract_keywords(prompt: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9]+", prompt.lower())
    skip = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "about",
        "that",
        "this",
        "what",
        "when",
        "where",
        "which",
        "please",
        "show",
        "give",
        "tell",
        "need",
        "help",
        "academic",
        "calendar",
        "iit",
        "tech",
        "illinois",
    }
    return [w for w in words if len(w) > 2 and w not in skip and not w.isdigit()]


def _autocorrect_prompt(prompt: str) -> str:
    substitutions = {
        r"\btuitiion\b": "tuition",
        r"\btuituin\b": "tuition",
        r"\baademic\b": "academic",
        r"\bcalender\b": "calendar",
        r"\bdirctory\b": "directory",
        r"\bpolcies\b": "policies",
        r"\bhandbok\b": "handbook",
    }
    corrected = prompt
    for wrong, right in substitutions.items():
        corrected = re.sub(wrong, right, corrected, flags=re.IGNORECASE)
    return corrected


def _is_tuition_query(prompt: str) -> bool:
    p = prompt.lower()
    return any(token in p for token in ("tuition", "tuiti", "tuituin", "fees", "fee", "cost"))


def _is_calendar_query(prompt: str) -> bool:
    p = prompt.lower()
    return any(token in p for token in ("calendar", "academic", "deadline", "semester", "term", "exam", "spring", "fall"))


def _is_directory_query(prompt: str) -> bool:
    p = prompt.lower()
    return any(token in p for token in ("directory", "contact", "department", "phone", "email", "office"))


def _is_policy_query(prompt: str) -> bool:
    p = prompt.lower()
    return any(
        token in p
        for token in (
            "policy",
            "policies",
            "handbook",
            "student handbook",
            "academic integrity",
            "attendance",
            "withdraw",
            "probation",
            "conduct",
            "grade appeal",
        )
    )


def _top_matches(items: list[dict[str, Any]], prompt: str, fields: tuple[str, ...], limit: int = 3) -> list[dict[str, Any]]:
    keywords = _extract_keywords(prompt)
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in items:
        haystack = " ".join(str(item.get(field, "")).lower() for field in fields)
        score = sum(1 for kw in keywords if kw in haystack)
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:limit]]


def _format_money(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"${value:,.0f}"
    return "N/A"


def _tuition_response(prompt: str, variant: str) -> str:
    rows = _load_tuition_data()
    matches = _top_matches(rows, prompt, ("school", "section", "fee_name", "program", "content"), limit=3)
    matches.sort(
        key=lambda r: 0 if "tuition" in str(r.get("fee_name", "")).lower() else 1
    )
    if not matches:
        return (
            "Great question. I can help with Illinois Tech tuition, but I need one more detail.\n\n"
            "Could you share your school/program (for example: Mies graduate, Stuart, or Chicago-Kent) and whether you want full-time or per-credit rates?"
        )
    lines = []
    for row in matches:
        school = row.get("school", "Illinois Tech")
        section = row.get("section", "Tuition")
        fee_name = row.get("fee_name") or "Tuition"
        amount = _format_money(row.get("amount_value"))
        unit = (row.get("unit") or "").replace("_", " ")
        source = row.get("source_url", "")
        detail = f"- {school}: {section} - {fee_name}: {amount}"
        if unit:
            detail += f" ({unit})"
        if source:
            detail += f"\n  Source: {source}"
        lines.append(detail)

    if variant == "A":
        intro = "Absolutely - here are the closest tuition details I found:"
        outro = "If you share your exact program and term, I can narrow this to one precise amount."
    else:
        intro = "Sure, I checked the tuition data and found these likely matches:"
        outro = "Want me to filter this by your degree level and semester so it reads like a single estimate?"
    return f"{intro}\n\n" + "\n".join(lines) + f"\n\n{outro}"


def _calendar_response(prompt: str, variant: str) -> str:
    rows = _load_calendar_data()
    lower_prompt = prompt.lower()
    term_hint = ""
    for season in ("spring", "summer", "fall", "winter"):
        if season in lower_prompt:
            term_hint = season
            break

    if term_hint:
        filtered_rows = [r for r in rows if term_hint in str(r.get("term", "")).lower()]
    else:
        filtered_rows = rows

    matches = _top_matches(filtered_rows, prompt, ("term", "event_name"), limit=4)

    if not matches:
        today = date.today().isoformat()
        upcoming = [
            r for r in rows if isinstance(r.get("start_date"), str) and r.get("start_date") >= today
        ][:4]
    else:
        upcoming = matches

    if not upcoming:
        return "I could not find calendar entries right now. Please try again with a term like Spring 2026 or Fall 2026."

    lines = []
    for row in upcoming:
        term = row.get("term", "Academic Calendar")
        event_name = row.get("event_name", "Event")
        start_date = row.get("start_date", "")
        source_urls = row.get("source_urls") or []
        source = source_urls[0] if source_urls else ""
        detail = f"- {start_date}: {event_name} ({term})"
        if source:
            detail += f"\n  Source: {source}"
        lines.append(detail)

    lead = (
        "Happy to help - here are the most relevant academic calendar events:"
        if variant == "A"
        else "Here are the calendar events that best match your question:"
    )
    follow_up = (
        "Tell me your term and I can give you add/drop, withdrawal, and final exam milestones only."
        if variant == "A"
        else "If you want, I can organize these into a week-by-week checklist for your semester."
    )
    return f"{lead}\n\n" + "\n".join(lines) + f"\n\n{follow_up}"


def _directory_response(prompt: str, variant: str) -> str:
    rows = _load_directory_data()
    matches = _top_matches(rows, prompt, ("Name", "Department", "Description", "Email", "Phone"), limit=4)
    if not matches:
        matches = rows[:4]

    if not matches:
        return "I could not read the directory data file. Please check that the contacts file is available."

    lines = []
    for row in matches:
        name = row.get("Name") or row.get("\ufeffName") or row.get("Department") or "Department"
        dept = row.get("Department", "")
        phone = row.get("Phone", "N/A")
        email = row.get("Email", "N/A")
        building = row.get("Building", "N/A")
        detail = f"- {name} ({dept})\n  Phone: {phone} | Email: {email} | Building: {building}"
        lines.append(detail)

    intro = (
        "Sure - here are the directory contacts that look most relevant:"
        if variant == "A"
        else "Got it. I found these likely contacts from the Illinois Tech directory:"
    )
    next_step = (
        "If you tell me the exact office or person, I can return one best contact."
        if variant == "A"
        else "Share who you're trying to reach and I will narrow this down to the best single contact."
    )
    return f"{intro}\n\n" + "\n".join(lines) + f"\n\n{next_step}"


def _policy_response(prompt: str, variant: str) -> str:
    rows = _load_handbook_data()
    matches = _top_matches(
        rows,
        prompt,
        ("title", "section", "content", "chunk_text", "text", "source", "source_url"),
        limit=3,
    )
    if not matches:
        return (
            "I can help with handbook and policy topics, but I need your specific policy area.\n\n"
            "Try asking: attendance policy, academic integrity, withdrawal rules, grade appeals, or probation."
        )

    lines = []
    for row in matches:
        text = str(
            row.get("content")
            or row.get("chunk_text")
            or row.get("text")
            or "Policy detail found."
        ).strip()
        snippet = text[:260] + ("..." if len(text) > 260 else "")
        title = str(row.get("title") or row.get("section") or "Policy")
        source = str(row.get("source_url") or row.get("source") or "").strip()
        detail = f"- {title}: {snippet}"
        if source:
            detail += f"\n  Source: {source}"
        lines.append(detail)

    intro = (
        "Absolutely - here are the closest handbook/policy details I found:"
        if variant == "A"
        else "Sure, here are policy and handbook details relevant to your question:"
    )
    outro = (
        "If you tell me your exact program and situation, I can give a more precise policy interpretation."
        if variant == "A"
        else "Share your exact scenario and I can narrow this down to the most applicable policy."
    )
    return f"{intro}\n\n" + "\n".join(lines) + f"\n\n{outro}"


def _general_conversation_response(prompt: str, variant: str) -> str:
    if variant == "A":
        return (
            f"Thanks for your question: \"{prompt.strip()}\".\n\n"
            "I can help best with Illinois Tech tuition, academic calendar, and directory information. "
            "Tell me which one you want, and I will respond with specific details and source links."
        )
    return (
        f"Great question. You asked: \"{prompt.strip()}\".\n\n"
        "I am currently tuned for Illinois Tech topics like tuition, academic calendar, and directory contacts. "
        "Pick one area and I will give you a clear, conversational answer."
    )


def _mock_response(prompt: str, variant: str) -> str:
    corrected_prompt = _autocorrect_prompt(prompt)
    if _is_tuition_query(corrected_prompt):
        return _tuition_response(corrected_prompt, variant)
    if _is_calendar_query(corrected_prompt):
        return _calendar_response(corrected_prompt, variant)
    if _is_directory_query(corrected_prompt):
        return _directory_response(corrected_prompt, variant)
    if _is_policy_query(corrected_prompt):
        return _policy_response(corrected_prompt, variant)
    return _general_conversation_response(corrected_prompt, variant)


def _fetch_api_response(prompt: str, endpoint: str, fallback_variant: str) -> str:
    try:
        response = requests.post(endpoint, json={"prompt": prompt}, timeout=20)
        response.raise_for_status()
        payload = response.json()
        for key in ("response", "answer", "content", "text"):
            if key in payload and isinstance(payload[key], str):
                return payload[key]
        return str(payload)
    except Exception:
        return _mock_response(prompt, fallback_variant)


def get_model_a_response(prompt: str, use_api_mode: bool) -> str:
    if use_api_mode:
        endpoint = os.getenv("MODEL_A_ENDPOINT", "").strip()
        if endpoint:
            return _fetch_api_response(prompt, endpoint, "A")
    return _mock_response(prompt, "A")


def get_model_b_response(prompt: str, use_api_mode: bool) -> str:
    if use_api_mode:
        endpoint = os.getenv("MODEL_B_ENDPOINT", "").strip()
        if endpoint:
            return _fetch_api_response(prompt, endpoint, "B")
    return _mock_response(prompt, "B")


def main() -> None:
    st.set_page_config(page_title="Chatbot Comparison", page_icon=":speech_balloon:", layout="wide")
    css_path = Path(__file__).parent / "assets" / "styles.css"
    load_css(css_path)
    _init_state()

    with st.sidebar:
        st.markdown("### Settings")
        response_mode = st.radio("Response mode", ["Mock", "API-ready"], index=0, horizontal=True)
        logo_position = st.radio("Logo position", ["Center Top", "Left Top"], index=0)
        if response_mode == "API-ready":
            st.caption("Set MODEL_A_ENDPOINT and MODEL_B_ENDPOINT environment variables to enable live calls.")
        if st.button("Clear conversation", use_container_width=True):
            st.session_state.pop("history_a", None)
            st.session_state.pop("history_b", None)
            st.rerun()

    st.markdown('<div class="app-shell">', unsafe_allow_html=True)
    render_title_block("center" if logo_position == "Center Top" else "left")
    show_typing_a = st.session_state.is_generating
    show_typing_b = st.session_state.is_generating

    col_a, col_b = st.columns(2, gap="large")
    with col_a:
        render_chat_panel("CHATBOT A", "MODEL 1", "a", st.session_state.history_a, show_typing=show_typing_a)
    with col_b:
        render_chat_panel("CHATBOT B", "MODEL 2", "b", st.session_state.history_b, show_typing=show_typing_b)

    with st.form("send_form", clear_on_submit=True):
        input_col, button_col = st.columns([6, 1])
        with input_col:
            prompt = st.text_input(
                "Compare prompt",
                placeholder="Type your message to compare...",
                label_visibility="collapsed",
                disabled=st.session_state.is_generating,
            )
            st.caption("Press Enter or click SEND")
        with button_col:
            submitted = st.form_submit_button(
                "SEND",
                use_container_width=True,
                type="primary",
                disabled=st.session_state.is_generating,
            )

    if submitted and prompt.strip() and not st.session_state.is_generating:
        user_prompt = prompt.strip()
        _append_message("history_a", "user", user_prompt)
        _append_message("history_b", "user", user_prompt)
        st.session_state.pending_prompt = user_prompt
        st.session_state.is_generating = True
        st.rerun()

    if st.session_state.is_generating and st.session_state.pending_prompt:
        user_prompt = st.session_state.pending_prompt.strip()
        use_api_mode = response_mode == "API-ready"
        time.sleep(0.45)
        response_a = get_model_a_response(user_prompt, use_api_mode)
        response_b = get_model_b_response(user_prompt, use_api_mode)
        _append_message("history_a", "assistant", response_a)
        _append_message("history_b", "assistant", response_b)

        st.session_state.pending_prompt = ""
        st.session_state.is_generating = False
        st.rerun()

    render_footer_actions()
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
