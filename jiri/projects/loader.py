"""Load per-project configuration from projects/{project_id}/project.yaml."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("jiri.projects.loader")


@dataclass(frozen=True)
class RepoEntry:
    full_name: str          # owner/repo on GitHub
    clone_url: str          # https clone URL
    role: str = ""          # free-form label (frontend, backend-api, gitops-config, …)
    branch: str = ""        # preferred branch; empty = auto (tries main then master)


@dataclass(frozen=True)
class ProjectConfig:
    project_id: str
    name: str
    description: str
    deploy_strategy: str            # gitops-k8s | docker-compose | manual
    repos: tuple[RepoEntry, ...]
    issue_repo: str                 # owner/repo where Jiri files issues; empty = use triggered repo
    environments: dict[str, str]    # env_name → url
    architecture_notes: str         # injected into LLM prompts
    agents_md: str                  # contents of AGENTS.md; injected into LLM prompts


def _parse_repos(raw: list[Any]) -> tuple[RepoEntry, ...]:
    entries: list[RepoEntry] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        full_name = str(item.get("full_name") or "").strip()
        clone_url = str(item.get("clone_url") or "").strip()
        if not full_name or not clone_url:
            logger.warning("Skipping repo entry missing full_name or clone_url: %s", item)
            continue
        entries.append(
            RepoEntry(
                full_name=full_name,
                clone_url=clone_url,
                role=str(item.get("role") or "").strip(),
                branch=str(item.get("branch") or "").strip(),
            )
        )
    return tuple(entries)


def _parse_environments(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, str] = {}
    for env_name, env_val in raw.items():
        if isinstance(env_val, dict):
            result[str(env_name)] = str(env_val.get("url") or "")
        elif isinstance(env_val, str):
            result[str(env_name)] = env_val
    return result


def load_project(projects_dir: Path, project_id: str) -> ProjectConfig:
    """
    Load projects/{project_id}/project.yaml.

    Raises FileNotFoundError if the directory or YAML does not exist.
    Raises ValueError if required fields are missing or project_id mismatches.
    """
    project_id = project_id.strip()
    if not project_id:
        raise ValueError("project_id must not be empty")

    project_dir = projects_dir / project_id
    yaml_path = project_dir / "project.yaml"

    if not yaml_path.is_file():
        raise FileNotFoundError(f"Project config not found: {yaml_path}")

    raw_yaml = yaml_path.read_text(encoding="utf-8")
    data: dict[str, Any] = yaml.safe_load(raw_yaml) or {}

    # Validate project_id matches directory name
    yaml_id = str(data.get("project_id") or "").strip()
    if yaml_id and yaml_id != project_id:
        raise ValueError(
            f"project_id mismatch: directory={project_id!r} but yaml says {yaml_id!r}"
        )

    repos = _parse_repos(data.get("repos") or [])
    if not repos:
        raise ValueError(f"Project {project_id!r} has no valid repos defined")

    # Load optional AGENTS.md
    agents_md_path = project_dir / "AGENTS.md"
    agents_md = agents_md_path.read_text(encoding="utf-8") if agents_md_path.is_file() else ""

    return ProjectConfig(
        project_id=project_id,
        name=str(data.get("name") or project_id),
        description=str(data.get("description") or ""),
        deploy_strategy=str(data.get("deploy_strategy") or "manual"),
        repos=repos,
        issue_repo=str(data.get("issue_repo") or "").strip(),
        environments=_parse_environments(data.get("environments")),
        architecture_notes=str(data.get("architecture_notes") or ""),
        agents_md=agents_md,
    )


def list_projects(projects_dir: Path) -> list[str]:
    """Return sorted list of project_id slugs found under projects_dir."""
    if not projects_dir.is_dir():
        return []
    return sorted(
        d.name
        for d in projects_dir.iterdir()
        if d.is_dir() and (d / "project.yaml").is_file()
    )
