"""Planner: classify GitHub event and fill repo fields (optional OpenAI)."""

from __future__ import annotations

import json
import logging
from typing import Any

from jiri.agents.state import JiriState
from jiri.config import Settings

logger = logging.getLogger("jiri.planner")


def _heuristic_plan(state: JiriState) -> dict[str, Any]:
    payload = state.get("payload") or {}
    repo = payload.get("repository") or {}
    full_name = repo.get("full_name") or ""
    clone_url = repo.get("clone_url") or ""
    event = state.get("event") or "unknown"

    task_type = "test_webhook"
    if event == "pull_request":
        task_type = "test_pr"
    elif event == "push":
        task_type = "test_push"
    elif event == "workflow_run":
        task_type = "test_workflow_failure"
    elif event == "jiri_test_request":
        task_type = "verify_fix"

    if not full_name and state.get("payload", {}).get("manual_repo"):
        full_name = str(state["payload"]["manual_repo"])

    return {
        "repo_full_name": full_name or "unknown/unknown",
        "repo_clone_url": clone_url,
        "task_type": task_type,
        "planner_summary": f"Run tests for GitHub event `{event}` on repository `{full_name or '?'}`.",
    }


def _llm_plan(settings: Settings, state: JiriState) -> dict[str, Any]:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    payload = state.get("payload") or {}
    model = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key or None,
        temperature=0.2,
    )
    sys = SystemMessage(
        content=(
            "You are a planner for a testing agent. Given a webhook event name and JSON payload, "
            "output a short JSON object with keys: task_type (string), summary (string), "
            "repo_full_name (owner/repo), repo_clone_url (https clone URL from payload.repository.clone_url)."
        )
    )
    human = HumanMessage(
        content=f"event={state.get('event')}\n\npayload=\n{json.dumps(payload, default=str)[:12000]}"
    )
    resp = model.invoke([sys, human])
    text = getattr(resp, "content", str(resp))
    try:
        data = json.loads(text[text.find("{") : text.rfind("}") + 1])
    except (json.JSONDecodeError, ValueError):
        logger.warning("Planner LLM returned non-JSON; using heuristic")
        return _heuristic_plan(state)
    h = _heuristic_plan(state)
    return {
        "repo_full_name": data.get("repo_full_name") or h["repo_full_name"],
        "repo_clone_url": data.get("repo_clone_url") or h["repo_clone_url"],
        "task_type": data.get("task_type") or h["task_type"],
        "planner_summary": data.get("summary") or h["planner_summary"],
    }


def plan(settings: Settings, state: JiriState) -> dict[str, Any]:
    if state.get("skip_graph"):
        return {}
    if settings.openai_api_key:
        try:
            return _llm_plan(settings, state)
        except Exception as e:
            logger.exception("Planner LLM failed: %s", e)
            return _heuristic_plan(state)
    return _heuristic_plan(state)
