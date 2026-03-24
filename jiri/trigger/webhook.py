"""FastAPI webhook and peer-agent APIs for Jiri."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from typing import Any

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response

from jiri.agents.gh_prompt import should_trigger_tests
from jiri.agents.graph import get_compiled_graph
from jiri.agents.state import JiriState
from jiri.config import get_settings, load_settings
from jiri.trigger.security import verify_github_signature, verify_jiri_secret

logger = logging.getLogger("jiri.trigger")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

_graph_lock = threading.Lock()

# Optional async hook: last inbound message from Jannus (for observability / future resume)
_last_inbound_negotiation: dict[str, Any] = {}

app = FastAPI(
    title="Jiri",
    version="0.1.0",
    description="GitHub webhook → LangGraph → tests → GitHub/Telegram/Jannus",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _run_graph_job(event: str, payload: dict[str, Any], thread_id: str) -> None:
    settings = get_settings()
    initial: JiriState = {
        "event": event,
        "payload": payload,
        "thread_id": thread_id,
        "negotiation_history": [],
    }
    graph = get_compiled_graph()
    cfg: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    try:
        with _graph_lock:
            graph.invoke(initial, config=cfg)
    except Exception:
        logger.exception("Graph invoke failed for thread_id=%s", thread_id)


def _check_inbound_secret(request: Request) -> None:
    settings = get_settings()
    sec = settings.jiri_inbound_secret
    if not sec:
        return
    hdr = request.headers.get("X-Jiri-Secret") or request.headers.get("x-jiri-secret")
    if not verify_jiri_secret(sec, hdr):
        raise HTTPException(status_code=401, detail="Invalid inbound secret")


@app.post("/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    settings = get_settings()
    raw = await request.body()
    sig = request.headers.get("X-Hub-Signature-256")
    if not verify_github_signature(raw, settings.webhook_secret, sig):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event = (request.headers.get("X-GitHub-Event") or "").strip().lower()
    if not event:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Event")

    if event == "ping":
        return Response(content=json.dumps({"ok": True, "ping": True}), media_type="application/json")

    allow_events = settings.parsed_event_allowlist()
    if allow_events and event not in allow_events:
        return Response(
            content=json.dumps({"ok": True, "skipped": True, "reason": "event not in allowlist"}),
            media_type="application/json",
        )

    try:
        payload: dict[str, Any] = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e

    repo = (payload.get("repository") or {}).get("full_name") or ""
    allow_repos = settings.parsed_repo_allowlist()
    if allow_repos and repo.lower() not in allow_repos:
        return Response(
            content=json.dumps({"ok": True, "skipped": True, "reason": "repo not in allowlist"}),
            media_type="application/json",
        )

    kws = settings.parsed_trigger_keywords()
    if not should_trigger_tests(event, payload, trigger_keywords=kws):
        return Response(
            content=json.dumps({"ok": True, "skipped": True, "reason": "event not configured for tests"}),
            media_type="application/json",
        )

    delivery = request.headers.get("X-GitHub-Delivery", "") or str(uuid.uuid4())
    logger.info(
        "Queue graph job event=%s delivery=%s repo=%s",
        event,
        delivery,
        repo or "?",
    )
    background_tasks.add_task(_run_graph_job, event, payload, delivery)

    return Response(
        content=json.dumps(
            {
                "ok": True,
                "accepted": True,
                "event": event,
                "thread_id": delivery,
            }
        ),
        media_type="application/json",
        status_code=202,
    )


@app.post("/api/test-request")
async def test_request(request: Request, background_tasks: BackgroundTasks) -> Response:
    """Jannus (or CI) asks Jiri to run tests on a repository."""
    _check_inbound_secret(request)
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON") from e

    thread_id = body.get("thread_id") or str(uuid.uuid4())
    repo_full = (body.get("repo_full_name") or "").strip()
    clone_url = (body.get("repo_clone_url") or "").strip()
    if not repo_full or not clone_url:
        raise HTTPException(status_code=400, detail="repo_full_name and repo_clone_url required")

    owner, name = repo_full.split("/", 1) if "/" in repo_full else ("", "")
    payload: dict[str, Any] = {
        "repository": {
            "full_name": repo_full,
            "clone_url": clone_url,
            "html_url": body.get("html_url") or f"https://github.com/{repo_full}",
            "owner": {"login": owner},
            "name": name,
        },
        "jiri_test_request": True,
        "requested_by": body.get("requested_by") or "jannus",
    }
    if body.get("issue_number") is not None:
        payload["issue"] = {"number": int(body["issue_number"])}
    if body.get("pull_request") is not None:
        payload["pull_request"] = body["pull_request"]

    background_tasks.add_task(_run_graph_job, "jiri_test_request", payload, thread_id)
    return Response(
        content=json.dumps({"ok": True, "accepted": True, "thread_id": thread_id}),
        media_type="application/json",
        status_code=202,
    )


@app.post("/api/negotiate")
async def negotiate_inbound(request: Request) -> Response:
    """Inbound message from Jannus (async / observability). Sync negotiation uses Jiri→Jannus HTTP."""
    _check_inbound_secret(request)
    global _last_inbound_negotiation
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON") from e

    _last_inbound_negotiation = body
    logger.info("Inbound negotiation from Jannus: keys=%s", list(body.keys()))
    return Response(
        content=json.dumps({"ok": True, "received": True}),
        media_type="application/json",
    )


@app.post("/callback")
async def human_callback(request: Request) -> Response:
    """Resume graph after human input (optional; same pattern as Jannus)."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    thread_id = body.get("thread_id")
    message = body.get("message", "")
    if not thread_id:
        raise HTTPException(status_code=400, detail="thread_id required")

    from langgraph.types import Command

    graph = get_compiled_graph()
    cfg: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    try:
        with _graph_lock:
            graph.invoke(Command(resume=message), config=cfg)
    except Exception:
        logger.exception("Callback resume failed thread_id=%s", thread_id)
        raise HTTPException(status_code=500, detail="Resume failed") from None

    return Response(
        content=json.dumps({"ok": True, "resumed": True, "thread_id": thread_id}),
        media_type="application/json",
    )


def run() -> None:
    settings = load_settings()
    uvicorn.run(
        "jiri.trigger.webhook:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
