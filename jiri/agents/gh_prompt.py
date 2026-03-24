"""Decide whether a GitHub event should trigger the test graph."""

from __future__ import annotations

from typing import Any


def _comment_matches_trigger(body: str, keywords: list[str]) -> bool:
    if not body.strip() or not keywords:
        return False
    lower = body.lower()
    for kw in keywords:
        if kw.lower() in lower:
            return True
    return False


def should_trigger_tests(event: str, payload: dict[str, Any], *, trigger_keywords: list[str]) -> bool:
    """Return True if this webhook should enqueue a test run."""
    if event == "ping":
        return False

    if event == "push":
        return True

    if event == "pull_request":
        action = payload.get("action") or ""
        return action in ("opened", "synchronize", "reopened", "ready_for_review")

    if event == "workflow_run":
        wr = payload.get("workflow_run") or {}
        if wr.get("status") != "completed":
            return False
        conclusion = wr.get("conclusion") or ""
        return conclusion in ("failure", "cancelled", "timed_out", "action_required")

    if event == "issue_comment":
        action = payload.get("action") or ""
        if action != "created":
            return False
        comment = payload.get("comment") or {}
        body = comment.get("body") or ""
        return _comment_matches_trigger(body, trigger_keywords)

    if event == "issues":
        action = payload.get("action") or ""
        return action in ("opened", "reopened", "labeled")

    # Custom / manual triggers may send event=test_request
    if event in ("jiri_test_request", "repository_dispatch"):
        return True

    return False
