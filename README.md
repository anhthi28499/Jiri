# Jiri — Autonomous Tester Agent

Jiri is a **separate** service from [Jannus](../Jannus) (the coding/fix agent). It runs tests on cloned repositories, can open GitHub issues or comments that mention `@jannus` / `/fix`, negotiates with Jannus over **HTTP** (no shared Python imports), and notifies you via a **dedicated Telegram bot**.

## Features

- **GitHub webhooks** — `push`, `pull_request`, `workflow_run`, `issue_comment` (with keywords), etc.
- **Clone/pull** repos under `workspaces/` (same idea as Jannus).
- **Test runner** — auto-detects `pytest`, `npm test`, `make test`, `go test`, `cargo test`, or `TEST_COMMANDS`.
- **Optional UI smoke tests** — Playwright (`UI_TEST_ENABLED=true`).
- **Analyzer** — OpenAI-based triage (or heuristics without `OPENAI_API_KEY`).
- **GitHub reporter** — creates issues or comments with trigger phrases for Jannus.
- **Negotiation** — synchronous HTTP to Jannus `POST /api/fix-request` and `POST /api/negotiate`.
- **Escalation** — Telegram via **Jiri’s bot**; when negotiation assigns `escalation_sender: jannus`, Jiri skips its bot and you should rely on Jannus notifications (or extend Jannus to mirror the message).

## Quick start

```bash
cd Jiri
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — at minimum: WEBHOOK_SECRET (if using GitHub), GITHUB_TOKEN, JANNUS_API_URL
```

Run the server (default port **8766**):

```bash
python -m jiri
```

Health check: `GET http://127.0.0.1:8766/health`

### Playwright (optional)

```bash
playwright install chromium
```

## Environment variables

See `.env.example` for the full list. Important ones:

| Variable | Purpose |
|----------|---------|
| `PORT` | Listen port (default `8766`) |
| `WEBHOOK_SECRET` | GitHub webhook HMAC secret |
| `GITHUB_TOKEN` | PAT for creating issues/comments |
| `GITHUB_DEFAULT_REPO` | Fallback `owner/repo` when payload has no repository |
| `JANNUS_API_URL` | Base URL of Jannus (e.g. `http://jannus-vps:8765`) |
| `JANNUS_API_SECRET` | Sent as `X-Jiri-Secret` to Jannus; must match Jannus `JIRI_PEER_SECRET` |
| `JIRI_INBOUND_SECRET` | If set, incoming `POST /api/test-request` and `POST /api/negotiate` require `X-Jiri-Secret` |
| `JIRI_TELEGRAM_BOT_TOKEN` / `JIRI_TELEGRAM_CHAT_ID` | Jiri’s **own** Telegram bot |
| `OPENAI_API_KEY` | Planner/analyzer/negotiation (optional) |
| `UI_TEST_ENABLED` | `true` to run Playwright smoke tests |

## HTTP API

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness |
| `POST /webhook` | GitHub webhooks (HMAC) |
| `POST /api/test-request` | Jannus (or automation) asks Jiri to test a repo (`repo_full_name`, `repo_clone_url`, optional `thread_id`) |
| `POST /api/negotiate` | Inbound from Jannus (async/observability; logs payload; optional `JIRI_INBOUND_SECRET`) |
| `POST /callback` | Human-in-the-loop resume (LangGraph `Command(resume=...)`) |

## Deploying on a separate VPS

1. Clone **this** repo (`Jiri` only) on the tester VPS.
2. Set env vars; use a **public URL** for `JIRI_PUBLIC_BASE_URL` if you add async callbacks later.
3. Run behind a reverse proxy (TLS) and register GitHub webhooks pointing to `https://your-jiri/webhook`.
4. Open firewall between Jiri and Jannus so Jiri can `POST` to Jannus (`JANNUS_API_URL`).

Jannus (on another VPS) should set:

- `JIRI_API_URL` — base URL of this Jiri instance (optional, for `notify_jiri_optional` helpers).
- `JIRI_PEER_SECRET` — same string as Jiri’s `JANNUS_API_SECRET` (Jiri sends it when calling Jannus).

## Coordination with Jannus

- **No shared code** — only REST + GitHub + Telegram.
- **Sync negotiation** — Jiri’s `negotiator` calls Jannus and reads JSON in the HTTP response.
- **GitHub** — Jiri can open issues/comments containing `/fix` or `@jannus` so Jannus’s existing GitHub triggers can run fixes.

## Repo layout

```
Jiri/
├── jiri/              # Python package
│   ├── agents/        # LangGraph nodes
│   ├── trigger/       # FastAPI app
│   └── github/        # PyGithub helpers
├── workspaces/        # Clones + checkpoints (gitignored contents)
├── requirements.txt
└── .env.example
```
