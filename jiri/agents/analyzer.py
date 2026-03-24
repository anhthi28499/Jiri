"""Analyze test output and decide next action."""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from jiri.agents.state import JiriState
from jiri.config import Settings

logger = logging.getLogger("jiri.analyzer")

AnalysisAction = Literal["pass", "create_issue", "negotiate", "escalate"]


def _heuristic(state: JiriState) -> tuple[AnalysisAction, str]:
    test_ok = bool(state.get("test_passed"))
    ui_ok = bool(state.get("ui_test_passed", True))
    if test_ok and ui_ok:
        return "pass", "All checks passed (heuristic)."
    out = (state.get("test_output") or "")[:4000]
    ui = (state.get("ui_test_results") or "")[:2000]
    summary = f"Tests failed or UI smoke failed.\n\nstdout/stderr:\n{out}\n\nUI:\n{ui}"
    # Escalate if output suggests flaky infra / ambiguity
    ambiguous = any(
        x in out.lower()
        for x in ("network", "timeout", "econnrefused", "rate limit", "429", "503")
    )
    if ambiguous:
        return "negotiate", summary + "\n\n(Heuristic: possible infra ambiguity — negotiate with Jannus.)"
    return "create_issue", summary


def _llm_analyze(settings: Settings, state: JiriState) -> tuple[AnalysisAction, str]:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    model = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key or None,
        temperature=0.1,
    )
    sys = SystemMessage(
        content=(
            "You are a test triage agent. Given unit/UI test output, reply with JSON only: "
            '{"action":"pass"|"create_issue"|"negotiate"|"escalate","summary":"..."} '
            "Use pass if everything succeeded. "
            "Use create_issue for clear product bugs. "
            "Use negotiate when coordination with a fixer agent (Jannus) is needed or trade-offs are unclear. "
            "Use escalate for human-only decisions (large trade-offs, policy)."
        )
    )
    human = HumanMessage(
        content=(
            f"repo={state.get('repo_full_name')}\n"
            f"planner={state.get('planner_summary')}\n\n"
            f"test_passed={state.get('test_passed')}\n"
            f"test_exit_code={state.get('test_exit_code')}\n"
            f"test_output:\n{(state.get('test_output') or '')[:20000]}\n\n"
            f"ui_test_passed={state.get('ui_test_passed')}\n"
            f"ui_test_results:\n{(state.get('ui_test_results') or '')[:8000]}\n"
        )
    )
    resp = model.invoke([sys, human])
    text = getattr(resp, "content", str(resp))
    try:
        data = json.loads(text[text.find("{") : text.rfind("}") + 1])
    except (json.JSONDecodeError, ValueError):
        return _heuristic(state)
    action = data.get("action", "create_issue")
    if action not in ("pass", "create_issue", "negotiate", "escalate"):
        action = "create_issue"
    return action, data.get("summary") or ""


def analyze(settings: Settings, state: JiriState) -> dict[str, Any]:
    if state.get("skip_graph"):
        return {}
    if settings.openai_api_key:
        try:
            action, summary = _llm_analyze(settings, state)
        except Exception as e:
            logger.exception("Analyzer LLM failed: %s", e)
            action, summary = _heuristic(state)
    else:
        action, summary = _heuristic(state)

    out: dict[str, Any] = {
        "analysis_action": action,
        "analysis_summary": summary,
    }
    if action == "escalate":
        out["escalation_sender"] = "jiri"
    return out
