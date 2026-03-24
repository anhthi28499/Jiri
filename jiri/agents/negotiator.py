"""HTTP negotiation with Jannus (separate VPS)."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import httpx

from jiri.agents.state import JiriState
from jiri.config import Settings

logger = logging.getLogger("jiri.negotiator")


def _next_counter_payload(settings: Settings, state: JiriState, jannus_reply: dict[str, Any]) -> dict[str, Any]:
    """Build next round payload; optional LLM."""
    jp = jannus_reply.get("payload") or {}
    if settings.openai_api_key:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_openai import ChatOpenAI

            model = ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key or None,
                temperature=0.2,
            )
            sys = SystemMessage(
                content=(
                    "You are Jiri (test agent). Jannus replied to a negotiation. "
                    "Reply JSON only: {\"summary\":\"...\",\"severity\":\"low|medium|high|critical\","
                    "\"proposed_action\":\"fix|ignore|defer|human_review\",\"details\":\"...\",\"trade_offs\":\"...\"}"
                )
            )
            human = HumanMessage(
                content=(
                    f"test context:\n{(state.get('test_output') or '')[:8000]}\n\n"
                    f"jannus_reply:\n{json.dumps(jannus_reply, default=str)[:8000]}\n"
                )
            )
            resp = model.invoke([sys, human])
            text = getattr(resp, "content", str(resp))
            data = json.loads(text[text.find("{") : text.rfind("}") + 1])
            return {
                "summary": data.get("summary") or "Counter",
                "severity": data.get("severity") or "medium",
                "proposed_action": data.get("proposed_action") or "fix",
                "details": data.get("details") or "",
                "trade_offs": data.get("trade_offs") or "",
            }
        except Exception as e:
            logger.warning("negotiator LLM counter failed: %s", e)

    return {
        "summary": "Counter: still believe fix is needed based on failing tests.",
        "severity": "high",
        "proposed_action": "fix",
        "details": (state.get("analysis_summary") or "")[:2000],
        "trade_offs": str(jp.get("trade_offs") or ""),
    }


def negotiate(settings: Settings, state: JiriState) -> dict[str, Any]:
    """Call Jannus synchronously for up to N rounds."""
    negotiation_id = state.get("negotiation_id") or str(uuid.uuid4())
    history: list[dict[str, Any]] = list(state.get("negotiation_history") or [])

    base = (settings.jannus_api_url or "").strip().rstrip("/")
    if not base:
        logger.warning("JANNUS_API_URL not set; escalating to human (Jiri bot)")
        return {
            "negotiation_id": negotiation_id,
            "negotiation_history": history
            + [{"error": "JANNUS_API_URL not configured — cannot negotiate with Jannus"}],
            "negotiation_result": "escalated",
            "escalation_sender": "jiri",
        }

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.jannus_api_secret:
        headers["X-Jiri-Secret"] = settings.jannus_api_secret

    max_r = settings.negotiation_max_rounds
    current_payload: dict[str, Any] = {
        "summary": state.get("analysis_summary") or "Tests failed",
        "severity": "high" if not state.get("test_passed", True) else "medium",
        "proposed_action": "fix",
        "details": ((state.get("test_output") or "") + "\n" + (state.get("ui_test_results") or ""))[:12000],
        "trade_offs": "",
    }

    for round_no in range(1, max_r + 1):
        msg: dict[str, Any] = {
            "negotiation_id": negotiation_id,
            "from_agent": "jiri",
            "type": "bug_report" if round_no == 1 else "counter",
            "round": round_no,
            "max_rounds": max_r,
            "thread_id": state.get("thread_id"),
            "jiri_public_base_url": settings.jiri_public_base_url,
            "payload": current_payload,
            "history": history[-10:],
        }
        url = f"{base}/api/fix-request" if round_no == 1 else f"{base}/api/negotiate"
        try:
            r = httpx.post(url, json=msg, headers=headers, timeout=120.0)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.exception("negotiation HTTP failed: %s", e)
            return {
                "negotiation_id": negotiation_id,
                "negotiation_history": history + [{"error": str(e)}],
                "negotiation_result": "escalated",
                "escalation_sender": "jiri",
            }

        history.append({"jiri_sent": msg, "jannus_reply": data})

        jtype = str(data.get("type") or "")
        jp = data.get("payload") if isinstance(data.get("payload"), dict) else {}
        proposed = str(jp.get("proposed_action") or "")

        if jtype == "agree" or proposed in ("fix", "ignore"):
            if proposed == "ignore":
                return {
                    "negotiation_id": negotiation_id,
                    "negotiation_history": history,
                    "negotiation_result": "agreed_ignore",
                }
            return {
                "negotiation_id": negotiation_id,
                "negotiation_history": history,
                "negotiation_result": "agreed_fix",
            }

        if jtype == "escalate":
            sender = str(jp.get("escalation_sender") or data.get("escalation_sender") or "jiri")
            if sender not in ("jiri", "jannus"):
                sender = "jiri"
            return {
                "negotiation_id": negotiation_id,
                "negotiation_history": history,
                "negotiation_result": "escalated",
                "escalation_sender": sender,
            }

        # Continue negotiation
        current_payload = _next_counter_payload(settings, state, data)

    return {
        "negotiation_id": negotiation_id,
        "negotiation_history": history,
        "negotiation_result": "escalated",
        "escalation_sender": "jiri",
    }
