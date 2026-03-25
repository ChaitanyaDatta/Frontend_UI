from __future__ import annotations

import html
from typing import Iterable

import streamlit as st


def _format_message(
    message: dict[str, str],
    theme: str,
    grouped: bool = False,
) -> str:
    role = message.get("role", "assistant")
    content = html.escape(message.get("content", ""))
    timestamp = html.escape(message.get("timestamp", ""))
    role_class = "user" if role == "user" else "assistant"
    avatar = "YOU" if role == "user" else f"BOT {theme.upper()}"
    role_label = "You" if role == "user" else "Assistant"
    grouped_class = " grouped" if grouped else ""
    return (
        f'<div class="message-row {role_class}{grouped_class}">'
        f'  <div class="avatar-pill {theme}">{avatar}</div>'
        f'  <div class="message-bubble-wrap">'
        f'    <div class="message-meta {role_class}">{role_label}{" • " + timestamp if timestamp else ""}</div>'
        f'    <div class="message-bubble {role_class}">{content}</div>'
        f"  </div>"
        f"</div>"
    )


def render_chat_panel(
    title: str,
    model_label: str,
    theme: str,
    history: Iterable[dict[str, str]],
    show_typing: bool = False,
) -> None:
    history_list = list(history)
    messages: list[str] = []
    previous_role = ""
    for message in history_list:
        role = str(message.get("role", "assistant"))
        grouped = role == previous_role
        messages.append(_format_message(message, theme, grouped=grouped))
        previous_role = role

    if show_typing:
        messages.append(
            f'<div class="message-row assistant grouped">'
            f'  <div class="avatar-pill {theme}">BOT {theme.upper()}</div>'
            f'  <div class="message-bubble-wrap">'
            f'    <div class="message-meta assistant">Assistant • typing...</div>'
            f'    <div class="message-bubble assistant typing-indicator"><span></span><span></span><span></span></div>'
            f'  </div>'
            f"</div>"
        )

    if not messages:
        messages.append('<div class="chat-empty">Start a conversation to see responses here.</div>')

    messages_html = "".join(messages)
    panel_html = (
        f'<div class="chat-panel">'
        f'  <div class="chat-header {theme}">{html.escape(title)} ({html.escape(model_label)})</div>'
        f'  <div class="chat-body">{messages_html}</div>'
        f"</div>"
    )
    st.markdown(panel_html, unsafe_allow_html=True)
