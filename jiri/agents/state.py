"""Shared LangGraph state for Jiri runs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, TypedDict

if TYPE_CHECKING:
    from jiri.projects.loader import ProjectConfig


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

    # Multi-project support
    project_id: str                     # set from trigger payload when present
    project_config: "ProjectConfig | None"  # loaded by planner; None = single-repo mode
    additional_repo_paths: list[str]    # local paths of secondary repos from project_config
