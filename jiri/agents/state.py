"""Shared LangGraph state for Jiri runs."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class JiriState(TypedDict, total=False):
    """State passed between graph nodes; nodes return partial updates."""

    event: str
    payload: dict[str, Any]
    thread_id: str

    repo_full_name: str
    repo_clone_url: str
    repo_local_path: str
    repo_ready: bool
    planner_summary: str
    task_type: str

    test_command: str
    test_output: str
    test_exit_code: int
    test_passed: bool

    ui_test_results: str
    ui_test_passed: bool

    analysis_summary: str
    analysis_action: Literal["pass", "create_issue", "negotiate", "escalate"]

    negotiation_id: str
    negotiation_history: list[dict[str, Any]]
    negotiation_result: Literal["agreed_fix", "agreed_ignore", "escalated", "pending"]
    escalation_sender: Literal["jiri", "jannus", ""]

    github_issue_url: str
    github_comment_url: str

    human_response: str | None
    error: str
    skip_graph: bool
