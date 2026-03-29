# Jiri — Setup Guide

This guide covers everything needed to get Jiri running and connected to a GitHub repository.

---

## Prerequisites

- Python 3.11+
- A server or tunnel with a **public HTTPS URL** (Jiri must be reachable by GitHub)
- A GitHub account with permission to add webhooks to the target repository
- A GitHub Personal Access Token (PAT)

---

## Step 1 — Clone and install

```bash
git clone <your-jiri-repo-url>
cd Jiri

python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Optional — Playwright for UI smoke tests:

```bash
playwright install chromium
```

---

## Step 2 — Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in the required values:

### Required

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub PAT with `repo` scope (or `issues: write` for fine-grained tokens) |
| `WEBHOOK_SECRET` | Any random string — must match the secret you set in the GitHub webhook |

To generate a random webhook secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

To create a GitHub PAT: **GitHub → Settings → Developer settings → Personal access tokens**
- Classic token: enable `repo` scope
- Fine-grained token: enable **Issues → Read and write** for the target repository

### Optional but recommended

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Enables LLM-based issue triage and test analysis. Without this, Jiri uses keyword heuristics. |
| `OPENAI_MODEL` | Model to use (default: `gpt-4o`) |
| `GITHUB_DEFAULT_REPO` | Fallback `owner/repo` when the webhook payload doesn't include repository info |

### Issue triage

| Variable | Default | Description |
|----------|---------|-------------|
| `ISSUE_TRIAGE_ENABLED` | `true` | When `true`, Jiri posts a comment on new issues that are missing required information (steps to reproduce, expected/actual behavior, etc.) |

### Other services (optional)

| Variable | Description |
|----------|-------------|
| `JANNUS_API_URL` | Base URL of the Jannus coding agent (e.g. `http://jannus-host:8765`) |
| `JANNUS_API_SECRET` | Shared secret sent as `X-Jiri-Secret` to Jannus |
| `JIRI_TELEGRAM_BOT_TOKEN` | Telegram bot token for escalation notifications |
| `JIRI_TELEGRAM_CHAT_ID` | Telegram chat or group ID to receive notifications |
| `UI_TEST_ENABLED` | `true` to run Playwright smoke tests on every trigger |

---

## Step 3 — Expose Jiri to the internet

GitHub needs to send webhook events to Jiri's HTTP endpoint. Jiri must have a public URL.

### Option A — ngrok (quickest for local dev/testing)

```bash
# Install: https://ngrok.com/download
ngrok http 8766
# → Forwarding: https://abc123.ngrok.io → localhost:8766
```

Use `https://abc123.ngrok.io` as your base URL (changes every restart unless you have a paid plan).

### Option B — Cloudflare Tunnel (free, stable)

```bash
# Install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
cloudflared tunnel --url http://localhost:8766
# → https://your-subdomain.trycloudflare.com
```

### Option C — VPS with reverse proxy (recommended for production)

Run Jiri on a VPS and put it behind nginx or Caddy with a real domain and TLS certificate.

Example Caddy config:

```
jiri.yourdomain.com {
    reverse_proxy localhost:8766
}
```

---

## Step 4 — Start Jiri

```bash
python -m jiri
# → INFO: Uvicorn running on http://0.0.0.0:8766
```

Verify it's running:

```bash
curl http://localhost:8766/health
# → {"status":"ok"}
```

---

## Step 5 — Register the GitHub webhook

Go to the GitHub repository you want Jiri to monitor:

**Repository → Settings → Webhooks → Add webhook**

| Field | Value |
|-------|-------|
| Payload URL | `https://your-jiri-url/webhook` |
| Content type | `application/json` |
| Secret | Same value as `WEBHOOK_SECRET` in your `.env` |

Under **"Which events would you like to trigger this webhook?"**, select **"Let me select individual events"** and enable:

- **Issues** — triggers issue triage (Jiri comments when info is missing)
- **Issue comments** — triggers tests when a comment contains `/test` or `@jiri`
- **Pull requests** — triggers tests on PR open/sync
- **Pushes** — triggers tests on every push
- **Workflow runs** — triggers analysis when a GitHub Actions workflow fails

Click **Add webhook**. GitHub will send a `ping` event — Jiri will respond with `200 OK`.

---

## How issue triage works

When someone opens an issue on the monitored repository:

1. GitHub sends an `issues` event to Jiri
2. Jiri reads the issue title and body
3. If the issue is missing required information (steps to reproduce, expected behavior, error output), Jiri posts a comment asking for the missing details and stops
4. If the issue has sufficient information, Jiri proceeds with the normal test/analysis flow

Example comment Jiri will post:

```
Hi! Thanks for opening this issue. 👋

To help investigate efficiently, could you please provide the following information?

- steps to reproduce
- expected behavior
- actual behavior or error output

Once you've added these details, Jiri will automatically re-analyze the issue.
```

Without `OPENAI_API_KEY`, Jiri uses keyword heuristics to detect missing fields.
With `OPENAI_API_KEY`, Jiri uses GPT to distinguish bug reports from feature requests and questions, and asks more targeted follow-up questions.

To disable issue triage, set `ISSUE_TRIAGE_ENABLED=false` in `.env`.

---

## Verifying the setup

1. Create a test issue in the monitored repository with a minimal body (e.g. just "test")
2. Jiri should post a comment within a few seconds asking for more information
3. Check Jiri logs for `issue_triager: issue #N is missing [...]`

To check logs when running locally:

```bash
python -m jiri 2>&1 | grep -E "issue_triager|webhook|trigger"
```

---

## Troubleshooting

**Jiri is not receiving webhooks**
- Confirm the public URL is reachable: `curl https://your-url/health`
- Check the webhook delivery log in GitHub: **Repository → Settings → Webhooks → (your webhook) → Recent Deliveries**
- Verify `WEBHOOK_SECRET` matches exactly between `.env` and the GitHub webhook settings

**Jiri receives the event but does not post a comment**
- Check that `GITHUB_TOKEN` is set and has `issues: write` permission on the target repo
- Check that `ISSUE_TRIAGE_ENABLED` is not set to `false`
- Look for errors in Jiri logs: `issue_triager failed to post comment`

**Issue triage comment is not smart enough**
- Add `OPENAI_API_KEY` to `.env` to enable LLM-based analysis

**Jiri posts a comment even though the issue has enough info**
- This can happen with the heuristic mode. Adding `OPENAI_API_KEY` fixes most false positives.
- You can also set `ISSUE_TRIAGE_ENABLED=false` to disable the feature entirely.
