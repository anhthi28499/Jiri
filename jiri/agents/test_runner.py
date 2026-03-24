"""Detect test framework and run tests in the cloned repo."""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any

from jiri.agents.state import JiriState
from jiri.config import Settings

logger = logging.getLogger("jiri.test_runner")


def _has_file(root: Path, name: str) -> bool:
    return (root / name).is_file()


def _read_package_json_scripts(root: Path) -> dict[str, Any]:
    p = root / "package.json"
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("scripts") or {}
    except (json.JSONDecodeError, OSError):
        return {}


def detect_test_command(root: str, explicit: list[str]) -> str | None:
    """Pick a shell command to run tests."""
    if explicit:
        return explicit[0]
    path = Path(root)

    if _has_file(path, "pytest.ini") or _has_file(path, "pyproject.toml") or _has_file(path, "setup.cfg"):
        return "pytest -q"

    scripts = _read_package_json_scripts(path)
    if "test" in scripts:
        return "npm test"
    if _has_file(path, "package.json"):
        return "npm test"

    if _has_file(path, "Makefile"):
        return "make test"

    if _has_file(path, "go.mod"):
        return "go test ./..."

    if _has_file(path, "Cargo.toml"):
        return "cargo test"

    return None


def run_tests(settings: Settings, state: JiriState) -> dict[str, Any]:
    """Run tests; populate test_command, test_output, test_exit_code, test_passed."""
    if state.get("skip_graph"):
        return {}

    if settings.webhook_dry_run:
        return {
            "test_command": "echo dry-run",
            "test_output": "[dry-run] skipped real tests",
            "test_exit_code": 0,
            "test_passed": True,
        }

    repo = state.get("repo_local_path") or ""
    if not repo:
        return {"error": "missing repo_local_path", "test_passed": False, "test_exit_code": 1}

    explicit = settings.parsed_test_commands()
    cmd_str = detect_test_command(repo, explicit)
    if not cmd_str:
        return {
            "test_command": "",
            "test_output": "No test command detected (set TEST_COMMANDS or add pytest/package.json/Makefile).",
            "test_exit_code": 1,
            "test_passed": False,
        }

    logger.info("Running tests: %s in %s", cmd_str, repo)
    proc = subprocess.Popen(
        cmd_str,
        cwd=repo,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + settings.test_timeout
    while proc.poll() is None:
        if time.monotonic() > deadline:
            proc.kill()
            out, err = proc.communicate(timeout=30)
            combined = (out or "") + "\n" + (err or "") + "\n[timeout]"
            return {
                "test_command": cmd_str,
                "test_output": combined[:120_000],
                "test_exit_code": -1,
                "test_passed": False,
            }
        time.sleep(0.5)

    out, err = proc.communicate()
    code = proc.returncode if proc.returncode is not None else -1
    combined = (out or "") + "\n" + (err or "")
    return {
        "test_command": cmd_str,
        "test_output": combined[:120_000],
        "test_exit_code": code,
        "test_passed": code == 0,
    }
