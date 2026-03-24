"""Telegram notifications for Jiri (dedicated bot)."""

from __future__ import annotations

import logging
from typing import Any, Literal

from jiri.agents.state import JiriState
from jiri.config import Settings

logger = logging.getLogger("jiri.notifier")

Sender = Literal["jiri", "jannus"]


def send_telegram(settings: Settings, text: str) -> None:
    if not settings.jiri_telegram_bot_token or not settings.jiri_telegram_chat_id:
        logger.warning("Jiri Telegram not configured; skipping send")
        return
    import httpx

    url = f"https://api.telegram.org/bot{settings.jiri_telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.jiri_telegram_chat_id,
        "text": text[:4000],
        "parse_mode": "HTML",
    }
    try:
        r = httpx.post(url, json=payload, timeout=30.0)
        r.raise_for_status()
    except Exception as e:
        logger.exception("Telegram send failed: %s", e)


def notify_escalation(settings: Settings, state: JiriState) -> dict[str, Any]:
    """Notify human on Jiri Telegram when escalation is needed."""
    tid = state.get("thread_id") or "unknown"
    sender = state.get("escalation_sender") or "jiri"
    summary = state.get("analysis_summary") or ""
    neg = state.get("negotiation_id") or ""
    hist = state.get("negotiation_history") or []
    hist_txt = ""
    if hist:
        import json

        hist_txt = json.dumps(hist[-3:], indent=2, default=str)[:2500]

    body = (
        f"<b>Jiri escalation</b>\n"
        f"thread_id: <code>{tid}</code>\n"
        f"negotiation_id: <code>{neg}</code>\n"
        f"sender_bot: <code>{sender}</code> (jiri=test ambiguity; jannus=code ambiguity)\n\n"
        f"{summary[:2000]}\n\n"
        f"<pre>{hist_txt}</pre>\n"
        "Resume via POST /callback with JSON {\"thread_id\":\"...\",\"message\":\"...\"}"
    )

    # Only Jiri bot sends from this module; Jannus bot is notified via Jannus API separately.
    if sender == "jiri":
        send_telegram(settings, body)
    else:
        logger.info("Escalation sender=jannus — Jiri notifier skipped (Jannus should notify).")
    return {}


def notify_simple(settings: Settings, title: str, detail: str) -> None:
    send_telegram(settings, f"<b>{title}</b>\n{detail[:3500]}")
