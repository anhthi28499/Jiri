"""LangGraph orchestration for Jiri."""

from __future__ import annotations

import logging
import os
from typing import Any

from langgraph.graph import END, START, StateGraph

from jiri.agents.analyzer import analyze
from jiri.agents.negotiator import negotiate
from jiri.agents.notifier import notify_escalation
from jiri.agents.planner import plan
from jiri.agents.repo_manager import ensure_repo
from jiri.agents.reporter import report, report_from_negotiation
from jiri.agents.state import JiriState
from jiri.agents.test_runner import run_tests
from jiri.agents.ui_tester import run_ui_tests
from jiri.config import Settings, get_settings

logger = logging.getLogger("jiri.graph")

_compiled: Any = None


def _apply_langsmith_env(settings: Settings) -> None:
    if settings.langchain_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    os.environ["LANGCHAIN_TRACING_V2"] = "true" if settings.langchain_tracing_v2 else "false"


def _planner_node(state: JiriState) -> dict[str, Any]:
    settings = get_settings()
    _apply_langsmith_env(settings)
    return plan(settings, state)


def _repo_node(state: JiriState) -> dict[str, Any]:
    settings = get_settings()
    return ensure_repo(settings, state)


def _route_after_repo(state: JiriState) -> str:
    if state.get("error") or not state.get("repo_ready"):
        return END
    return "test_runner"


def _test_runner_node(state: JiriState) -> dict[str, Any]:
    settings = get_settings()
    return run_tests(settings, state)


def _ui_tester_node(state: JiriState) -> dict[str, Any]:
    settings = get_settings()
    return run_ui_tests(settings, state)


def _analyzer_node(state: JiriState) -> dict[str, Any]:
    settings = get_settings()
    return analyze(settings, state)


def _route_after_analyzer(state: JiriState) -> str:
    if state.get("skip_graph"):
        return END
    action = state.get("analysis_action") or "pass"
    if action == "pass":
        return END
    if action == "create_issue":
        return "reporter"
    if action == "negotiate":
        return "negotiator"
    if action == "escalate":
        return "notifier"
    return END


def _reporter_node(state: JiriState) -> dict[str, Any]:
    settings = get_settings()
    return report(settings, state)


def _reporter_neg_node(state: JiriState) -> dict[str, Any]:
    settings = get_settings()
    return report_from_negotiation(settings, state)


def _negotiator_node(state: JiriState) -> dict[str, Any]:
    settings = get_settings()
    return negotiate(settings, state)


def _route_after_negotiator(state: JiriState) -> str:
    r = state.get("negotiation_result") or ""
    if r == "agreed_fix":
        return "reporter_neg"
    if r == "agreed_ignore":
        return END
    if r == "escalated":
        return "notifier"
    return "notifier"


def _notifier_node(state: JiriState) -> dict[str, Any]:
    settings = get_settings()
    return notify_escalation(settings, state)


def _build_graph() -> Any:
    import sqlite3

    settings = get_settings()
    _apply_langsmith_env(settings)

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        db = settings.checkpoint_db_path.resolve()
        db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db), check_same_thread=False)
        checkpointer = SqliteSaver(conn)
    except Exception as e:
        logger.warning("SqliteSaver unavailable (%s); using MemorySaver", e)
        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()

    g = StateGraph(JiriState)
    g.add_node("planner", _planner_node)
    g.add_node("repo_manager", _repo_node)
    g.add_node("test_runner", _test_runner_node)
    g.add_node("ui_tester", _ui_tester_node)
    g.add_node("analyzer", _analyzer_node)
    g.add_node("reporter", _reporter_node)
    g.add_node("reporter_neg", _reporter_neg_node)
    g.add_node("negotiator", _negotiator_node)
    g.add_node("notifier", _notifier_node)

    g.add_edge(START, "planner")
    g.add_edge("planner", "repo_manager")
    g.add_conditional_edges("repo_manager", _route_after_repo)
    g.add_edge("test_runner", "ui_tester")
    g.add_edge("ui_tester", "analyzer")
    g.add_conditional_edges("analyzer", _route_after_analyzer)
    g.add_edge("reporter", END)
    g.add_edge("reporter_neg", END)
    g.add_conditional_edges("negotiator", _route_after_negotiator)
    g.add_edge("notifier", END)

    return g.compile(checkpointer=checkpointer)


def get_compiled_graph() -> Any:
    global _compiled
    if _compiled is None:
        _compiled = _build_graph()
    return _compiled
