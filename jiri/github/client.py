"""PyGithub helpers for issues, comments, and PR diffs."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("jiri.github")


def get_repo_full_name(payload: dict[str, Any], default_repo: str) -> str:
    repo = payload.get("repository") or {}
    full = (repo.get("full_name") or "").strip()
    if full:
        return full
    return default_repo.strip() or "unknown/unknown"


def create_issue(
    token: str,
    repo_full_name: str,
    title: str,
    body: str,
) -> str:
    """Create an issue; return html_url."""
    from github import Auth, Github
    from github import GithubException

    owner, name = repo_full_name.split("/", 1)
    auth = Auth.Token(token)
    g = Github(auth=auth)
    try:
        repo = g.get_repo(f"{owner}/{name}")
        issue = repo.create_issue(title=title, body=body)
        return issue.html_url
    except GithubException as e:
        logger.exception("create_issue failed: %s", e)
        raise


def create_issue_comment(
    token: str,
    repo_full_name: str,
    issue_number: int,
    body: str,
) -> str:
    """Comment on an issue or PR. Return comment html_url if available."""
    from github import Auth, Github
    from github import GithubException

    owner, name = repo_full_name.split("/", 1)
    auth = Auth.Token(token)
    g = Github(auth=auth)
    try:
        repo = g.get_repo(f"{owner}/{name}")
        issue = repo.get_issue(issue_number)
        c = issue.create_comment(body)
        return getattr(c, "html_url", "") or ""
    except GithubException as e:
        logger.exception("create_issue_comment failed: %s", e)
        raise


def get_pull_request_diff(token: str, repo_full_name: str, pull_number: int) -> str:
    """Return PR unified diff text (truncated if huge)."""
    owner, name = repo_full_name.split("/", 1)
    api = f"https://api.github.com/repos/{owner}/{name}/pulls/{pull_number}"
    try:
        r = httpx.get(
            api,
            headers={
                "Accept": "application/vnd.github.v3.diff",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=60.0,
        )
        r.raise_for_status()
        text = r.text
        return text[:50_000] if len(text) > 50_000 else text
    except Exception as e:
        logger.warning("get_pull_request_diff failed: %s", e)
        return ""


def issue_number_from_payload(payload: dict[str, Any]) -> int | None:
    issue = payload.get("issue") or {}
    num = issue.get("number")
    if isinstance(num, int):
        return num
    pr = payload.get("pull_request") or {}
    num = pr.get("number")
    if isinstance(num, int):
        return num
    return None
