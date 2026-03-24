"""Optional Playwright UI smoke tests."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jiri.agents.state import JiriState
from jiri.config import Settings

logger = logging.getLogger("jiri.ui_tester")


def run_ui_tests(settings: Settings, state: JiriState) -> dict[str, Any]:
    """Run basic navigation smoke tests; store screenshots on failure under workspaces/.jiri_ui/."""
    if state.get("skip_graph"):
        return {}
    if not settings.ui_test_enabled:
        return {"ui_test_results": "(UI tests disabled)", "ui_test_passed": True}

    if settings.webhook_dry_run:
        return {"ui_test_results": "[dry-run] UI tests skipped", "ui_test_passed": True}

    repo = state.get("repo_local_path") or ""
    if not repo:
        return {"ui_test_results": "no repo", "ui_test_passed": False}

    base = settings.ui_test_base_url.rstrip("/")
    paths = settings.parsed_ui_paths()
    out_dir = Path(settings.workspaces_dir) / ".jiri_ui"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        logger.warning("Playwright not available: %s", e)
        return {
            "ui_test_results": "Playwright not installed (pip install playwright && playwright install chromium)",
            "ui_test_passed": False,
        }

    lines: list[str] = []
    all_ok = True
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(settings.ui_test_timeout_ms)
        for i, path in enumerate(paths):
            url = f"{base}{path if path.startswith('/') else '/' + path}"
            try:
                page.goto(url, wait_until="domcontentloaded")
                title = page.title()
                lines.append(f"OK {url} title={title!r}")
            except Exception as ex:
                all_ok = False
                shot = out_dir / f"fail_{state.get('thread_id', 'run')}_{i}.png"
                try:
                    page.screenshot(path=str(shot))
                    lines.append(f"FAIL {url}: {ex} (screenshot {shot})")
                except Exception as e2:
                    lines.append(f"FAIL {url}: {ex} (screenshot failed: {e2})")
        context.close()
        browser.close()

    return {
        "ui_test_results": "\n".join(lines)[:20_000],
        "ui_test_passed": all_ok,
    }
