"""Triage GitHub issues: post a comment if required information is missing."""

from __future__ import annotations

import json
import logging
from typing import Any

from jiri.agents.state import JiriState
from jiri.config import Settings
from jiri.github import client as gh

logger = logging.getLogger("jiri.issue_triager")

_BUG_KEYWORDS = (
    "bug", "error", "fail", "broken", "crash", "exception",
    "not work", "wrong", "incorrect", "unexpected",
)
_MIN_BODY_LEN = 30


def _looks_like_bug_report(title: str, body: str) -> bool:
    text = (title + " " + body).lower()
    return any(kw in text for kw in _BUG_KEYWORDS)


def _heuristic_missing(title: str, body: str) -> list[str]:
    missing: list[str] = []
    if not body or len(body) < _MIN_BODY_LEN:
        missing.append("a description of the problem")
        return missing  # No point checking further if body is empty
    if _looks_like_bug_report(title, body):
        lower = body.lower()
        if not any(kw in lower for kw in ("step", "repro", "how to", "reproduce")):
            missing.append("steps to reproduce")
        if not any(kw in lower for kw in ("expect", "should", "want")):
            missing.append("expected behavior")
        if not any(kw in lower for kw in ("actual", "instead", "got", "error", "traceback", "log", "output")):
            missing.append("actual behavior or error output")
    return missing


def _llm_missing(settings: Settings, title: str, body: str) -> list[str]:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    model = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key or None,
        temperature=0.1,
    )
    sys = SystemMessage(
        content=(
            "You are a GitHub issue triage assistant. Analyze the issue title and body. "
            "If the issue is missing information needed to investigate it, return JSON: "
            '{"missing": ["item1", "item2"]}. '
            "If it has sufficient information, return {\"missing\": []}. "
            "For bug reports, flag missing: steps to reproduce, expected behavior, "
            "actual behavior or error output, environment (only if relevant). "
            "Be lenient for feature requests and questions — only flag if truly unclear. "
            "Reply with JSON only."
        )
    )
    human = HumanMessage(content=f"title: {title}\n\nbody:\n{body[:4000]}")
    resp = model.invoke([sys, human])
    text = getattr(resp, "content", str(resp))
    try:
        data = json.loads(text[text.find("{") : text.rfind("}") + 1])
        items = data.get("missing") or []
        return [str(i) for i in items if i]
    except (json.JSONDecodeError, ValueError):
        return _heuristic_missing(title, body)


def _build_comment(missing: list[str]) -> str:
    items = "\n".join(f"- {m}" for m in missing)
    return (
        "Hi! Thanks for opening this issue. :wave:\n\n"
        "To help investigate efficiently, could you please provide the following information?\n\n"
        f"{items}\n\n"
        "Once you've added these details, Jiri will automatically re-analyze the issue "
        "(you can also re-trigger by adding the `reopened` action or commenting `/test`).\n\n"
        "----\n"
        "*This comment was posted automatically by Jiri.*"
    )


def triage_issue(settings: Settings, state: JiriState) -> dict[str, Any]:
    """If a new issue lacks required info, post a comment and skip the test graph."""
    if not settings.issue_triage_enabled:
        return {}

    event = state.get("event") or ""
    payload = state.get("payload") or {}

    if event != "issues":
        return {}
    action = payload.get("action") or ""
    if action not in ("opened", "reopened"):
        return {}

    issue = payload.get("issue") or {}
    title = (issue.get("title") or "").strip()
    body = (issue.get("body") or "").strip()
    issue_number = issue.get("number")

    token = settings.github_token
    repo = gh.get_repo_full_name(payload, settings.github_default_repo)

    if not token or not issue_number:
        logger.warning("issue_triager: no GITHUB_TOKEN or issue_number, skipping triage")
        return {}

    if settings.openai_api_key:
        try:
            missing = _llm_missing(settings, title, body)
        except Exception as e:
            logger.exception("issue_triager LLM failed, falling back to heuristic: %s", e)
            missing = _heuristic_missing(title, body)
    else:
        missing = _heuristic_missing(title, body)

    if not missing:
        logger.info("issue_triager: issue #%s has sufficient info, proceeding", issue_number)
        return {}

    logger.info("issue_triager: issue #%s is missing %s — posting comment", issue_number, missing)
    comment = _build_comment(missing)
    try:
        url = gh.create_issue_comment(token, repo, issue_number, comment)
        return {"skip_graph": True, "github_comment_url": url or ""}
    except Exception as e:
        logger.exception("issue_triager failed to post comment: %s", e)
        return {}
