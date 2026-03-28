"""Clone or update persistent workspaces under WORKSPACES_DIR."""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jiri.agents.state import JiriState
from jiri.config import Settings

logger = logging.getLogger("jiri.repo_manager")


def _sanitize_repo_dir(full_name: str) -> str:
    return full_name.replace("/", "--").lower()


def _load_registry(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"repos": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"repos": {}}


def _save_registry(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _run_git(args: list[str], cwd: str, timeout: int = 300) -> tuple[int, str, str]:
    proc = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _ensure_single_repo(
    settings: Settings,
    full_name: str,
    clone_url: str,
) -> tuple[str, str]:
    """
    Clone or pull a single repo. Returns (local_path, error).
    local_path is empty string on failure.
    """
    base = settings.workspaces_dir.resolve()
    base.mkdir(parents=True, exist_ok=True)
    local_name = _sanitize_repo_dir(full_name)
    repo_path = base / local_name
    registry_path = settings.registry_path
    reg = _load_registry(registry_path)

    if not repo_path.is_dir() or not (repo_path / ".git").is_dir():
        logger.info("Cloning %s -> %s", clone_url, repo_path)
        code, out, err = _run_git(
            ["git", "clone", clone_url, str(repo_path)],
            cwd=str(base),
            timeout=600,
        )
        if code != 0:
            logger.error("git clone failed for %s: %s %s", full_name, out, err)
            return "", f"git clone failed: {err or out}"
        reg.setdefault("repos", {})[full_name] = {
            "path": str(repo_path),
            "clone_url": clone_url,
            "cloned_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        logger.info("Updating existing clone at %s", repo_path)
        for branch in ("main", "master"):
            c, _, _ = _run_git(["git", "checkout", branch], cwd=str(repo_path), timeout=60)
            if c == 0:
                break
        code, out, err = _run_git(
            ["git", "pull", "--ff-only"],
            cwd=str(repo_path),
            timeout=120,
        )
        if code != 0:
            logger.error("git pull failed for %s: %s %s", full_name, out, err)
            return "", f"git pull failed: {err or out}"

    reg.setdefault("repos", {})[full_name] = {
        **reg.get("repos", {}).get(full_name, {}),
        "path": str(repo_path),
        "clone_url": clone_url,
        "last_pull": datetime.now(timezone.utc).isoformat(),
    }
    _save_registry(registry_path, reg)
    return str(repo_path), ""


def ensure_repo(settings: Settings, state: JiriState) -> dict[str, Any]:
    """Clone if missing, else fetch + pull. Updates registry."""
    if settings.webhook_dry_run:
        return {
            "repo_local_path": str(settings.workspaces_dir / "dry-run"),
            "repo_ready": True,
            "error": "",
        }

    full_name = state.get("repo_full_name") or ""
    clone_url = state.get("repo_clone_url") or ""
    if not full_name or full_name == "unknown/unknown" or not clone_url:
        return {"repo_ready": False, "error": "missing repo_full_name or repo_clone_url"}

    repo_path_str, err = _ensure_single_repo(settings, full_name, clone_url)
    if err:
        return {"repo_ready": False, "error": err}

    repo_path = Path(repo_path_str)

    # Align working tree with PR head when applicable
    event = state.get("event") or ""
    payload = state.get("payload") or {}
    if event == "pull_request":
        pr = payload.get("pull_request") or {}
        head = pr.get("head") or {}
        sha = head.get("sha")
        if isinstance(sha, str) and len(sha) > 6:
            fc, fo, fe = _run_git(["git", "fetch", "origin", sha], cwd=str(repo_path), timeout=120)
            if fc == 0:
                co, _, ce = _run_git(["git", "checkout", "--detach", sha], cwd=str(repo_path), timeout=60)
                if co != 0:
                    logger.warning("checkout PR head failed: %s", ce)
            else:
                logger.warning("fetch PR head failed: %s", fe)
    elif event == "push":
        after = payload.get("after")
        if isinstance(after, str) and len(after) > 6:
            fc, _, fe = _run_git(["git", "fetch", "origin", after], cwd=str(repo_path), timeout=120)
            if fc == 0:
                _run_git(["git", "checkout", "--detach", after], cwd=str(repo_path), timeout=60)
            else:
                logger.warning("fetch push head failed: %s", fe)

    return {"repo_local_path": repo_path_str, "repo_ready": True, "error": ""}


def ensure_all_repos(settings: Settings, state: JiriState) -> dict[str, Any]:
    """
    If project_config is set, clone/pull ALL repos listed in it.
    First repo → repo_local_path (primary). Remaining → additional_repo_paths.
    Falls back to ensure_repo() when no project_config is present.
    """
    if settings.webhook_dry_run:
        return {
            "repo_local_path": str(settings.workspaces_dir / "dry-run"),
            "repo_ready": True,
            "additional_repo_paths": [],
            "error": "",
        }

    project_config = state.get("project_config")
    if not project_config or not project_config.repos:
        return ensure_repo(settings, state)

    primary_path = ""
    additional_paths: list[str] = []
    errors: list[str] = []

    for i, repo_entry in enumerate(project_config.repos):
        local_path, err = _ensure_single_repo(settings, repo_entry.full_name, repo_entry.clone_url)
        if err:
            errors.append(f"{repo_entry.full_name}: {err}")
            continue
        if i == 0:
            primary_path = local_path
        else:
            additional_paths.append(local_path)

    if not primary_path:
        return {
            "repo_ready": False,
            "error": "; ".join(errors) or "Primary repo failed",
            "additional_repo_paths": [],
        }

    return {
        "repo_local_path": primary_path,
        "repo_ready": True,
        "additional_repo_paths": additional_paths,
        "error": "; ".join(errors) if errors else "",
    }
