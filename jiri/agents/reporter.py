"""Create GitHub issues/comments that trigger Jannus."""

from __future__ import annotations

import logging
from typing import Any

from jiri.agents.state import JiriState
from jiri.config import Settings
from jiri.github import client as gh

logger = logging.getLogger("jiri.reporter")


def _jannus_trigger_body(extra: str) -> str:
    return (
        f"{extra}\n\n"
        "----\n"
        "Jiri detected failing tests or UI checks.\n"
        "Please fix: `/fix` or `@jannus`\n"
    )


def report(settings: Settings, state: JiriState) -> dict[str, Any]:
    """Create issue or comment with Jannus trigger keywords."""
    if state.get("skip_graph"):
        return {}

    token = settings.github_token
    payload = state.get("payload") or {}
    repo = gh.get_repo_full_name(payload, settings.github_default_repo)
    summary = state.get("analysis_summary") or state.get("planner_summary") or "Test failure"

    if not token:
        logger.warning("GITHUB_TOKEN not set; skipping GitHub reporter")
        return {
            "github_issue_url": "",
            "error": (state.get("error") or "") + "; GITHUB_TOKEN missing",
        }

    title = f"[Jiri] Tests failed — {repo} ({state.get('thread_id', '')[:8]})"
    body = _jannus_trigger_body(summary[:12000])

    issue_num = gh.issue_number_from_payload(payload)
    try:
        if issue_num is not None:
            url = gh.create_issue_comment(token, repo, issue_num, body)
            return {"github_comment_url": url or "", "github_issue_url": ""}
        url = gh.create_issue(token, repo, title, body)
        return {"github_issue_url": url, "github_comment_url": ""}
    except Exception as e:
        logger.exception("reporter failed: %s", e)
        return {"error": f"github reporter: {e}"}


def report_from_negotiation(settings: Settings, state: JiriState) -> dict[str, Any]:
    """After agreed_fix, open issue/comment with negotiation context."""
    extra = (
        f"Negotiation ID: `{state.get('negotiation_id')}`\n"
        f"Result: {state.get('negotiation_result')}\n\n"
        f"{state.get('analysis_summary') or ''}"
    )
    merged: JiriState = {**state, "analysis_summary": extra}
    return report(settings, merged)
