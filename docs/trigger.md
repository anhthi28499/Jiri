# Jiri Trigger Protocol

This document describes how to trigger Jiri to analyze a problem and create a GitHub issue.

> **Note on crash safety**: `repository_dispatch` events are stored by GitHub for 30 days.
> If Jiri crashes mid-job, the SQLite checkpoint (`workspaces/.jiri_state.db`) allows the
> LangGraph to resume from where it left off on the next invocation with the same `thread_id`.

---

## Overview

```
Any CI / test runner  ──trigger──▶  Jiri /webhook or /api/test-request
                                         │
                                         ▼ planner reads project_id
                                         ▼ loads projects/{id}/project.yaml
                                         ▼ clones/pulls ALL repos in the project
                                         ▼ analyzes root cause
                                         ▼ creates GitHub issue on issue_repo
```

Jiri runs as a **persistent FastAPI worker** on port 8766. Triggers reach it via:

| Path | When to use |
|------|-------------|
| `POST /webhook` | GitHub webhook events (repository_dispatch, push, PR, etc.) |
| `POST /api/test-request` | Direct HTTP from CI, scripts, or other agents |

---

## Trigger 1 — UI Automation Test Failure via GitHub Actions

Use the reusable workflow `.github/workflows/ui-test-trigger.yml`.

### From the same repo (manual)

```bash
gh workflow run ui-test-trigger.yml \
  -f project_id=acme-k8s \
  -f test_name=checkout-flow \
  -f description="Checkout button unresponsive on mobile" \
  -f screenshot_url="https://storage.example.com/s/run-42.png" \
  -f environment=staging
```

### From another repo's workflow (calling as reusable workflow)

```yaml
jobs:
  run-ui-tests:
    runs-on: ubuntu-latest
    steps:
      - name: Run Playwright tests
        id: playwright
        run: npx playwright test
        continue-on-error: true

      - name: Notify Jiri on failure
        if: failure()
        uses: your-org/jiri/.github/workflows/ui-test-trigger.yml@main
        with:
          project_id: acme-k8s
          test_name: playwright-suite
          description: "UI test suite failed on staging"
          environment: staging
        secrets:
          JIRI_DISPATCH_TOKEN: ${{ secrets.JIRI_DISPATCH_TOKEN }}
          JIRI_INBOUND_SECRET: ${{ secrets.JIRI_INBOUND_SECRET }}
```

### Required secrets/variables

| Name | Type | Description |
|------|------|-------------|
| `JIRI_DISPATCH_TOKEN` | Secret | GitHub PAT with `repo` scope — used to send `repository_dispatch` to Jiri's repo |
| `JIRI_INBOUND_SECRET` | Secret | Optional; must match `JIRI_INBOUND_SECRET` env var on the Jiri server |
| `JIRI_URL` | Variable (not secret) | Base URL of Jiri server (e.g. `https://jiri.example.com`). When set, also POSTs directly as fallback. |

---

## Payload Protocol

### Via `repository_dispatch` → `/webhook`

GitHub sends this as `X-GitHub-Event: repository_dispatch` (HMAC verified by Jiri).
The planner reads `payload["client_payload"]["project_id"]`.

```json
{
  "event_type": "jiri-ui-test-failure",
  "client_payload": {
    "project_id": "acme-k8s",
    "trigger_type": "ui_test_failure",
    "test_name": "checkout-flow",
    "description": "Checkout button unresponsive on mobile viewport",
    "screenshot_url": "https://storage.example.com/screenshots/run-42.png",
    "environment": "staging",
    "triggered_by": "github-actions",
    "run_id": "12345678",
    "run_url": "https://github.com/acme-org/frontend/actions/runs/12345678"
  }
}
```

### Via direct POST `/api/test-request`

The planner reads `payload["project_id"]`.

```json
{
  "project_id": "acme-k8s",
  "repo_full_name": "acme-org/frontend",
  "repo_clone_url": "https://github.com/acme-org/frontend.git",
  "trigger_type": "ui_test_failure",
  "test_name": "checkout-flow",
  "description": "Checkout button unresponsive on mobile viewport",
  "screenshot_url": "https://storage.example.com/screenshots/run-42.png",
  "environment": "staging"
}
```

> `repo_full_name` and `repo_clone_url` are required for `/api/test-request` (existing contract).
> When `project_id` is present, Jiri also pulls all additional repos from the project config.

### Payload field reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `project_id` | string | optional | Slug matching a directory under `projects/`. When set, loads project config and pulls all repos. |
| `trigger_type` | string | optional | `ui_test_failure`, `ci_failure`, `manual` |
| `test_name` | string | optional | Name of the failing test or test suite |
| `description` | string | optional | Human-readable description of the problem |
| `screenshot_url` | string | optional | URL to failure screenshot or artifact |
| `environment` | string | optional | `staging`, `production`, etc. |
| `repo_full_name` | string | required (direct POST) | `owner/repo` |
| `repo_clone_url` | string | required (direct POST) | HTTPS clone URL |
| `thread_id` | string | optional | Idempotency key; auto-generated if absent |

---

## Project Configuration

Each project Jiri supports needs two files under `projects/{project-id}/`:

### `project.yaml`

```yaml
project_id: acme-k8s              # must match directory name
name: "Acme Platform (K8s)"
description: |
  Short description of the platform for the agent.

deploy_strategy: gitops-k8s       # gitops-k8s | docker-compose | manual

repos:
  - full_name: acme-org/frontend   # owner/repo on GitHub
    clone_url: https://github.com/acme-org/frontend.git
    role: frontend                 # free-form label
    branch: main                   # optional; empty = auto (main/master)
  - full_name: acme-org/backend-api
    clone_url: https://github.com/acme-org/backend-api.git
    role: backend-api
  - full_name: acme-org/k8s-manifests
    clone_url: https://github.com/acme-org/k8s-manifests.git
    role: gitops-config

issue_repo: acme-org/frontend      # GitHub issues are filed here

environments:
  staging:
    url: https://staging.acme.example.com
  production:
    url: https://acme.example.com

architecture_notes: |
  Injected into the LLM prompt. Describe deployment pipeline,
  service communication, and key files to check on failure.
```

### `AGENTS.md`

Free-text guide for the agent. Describe:
- How to diagnose failures specific to this project
- Which files to look at first
- What NOT to do (e.g. no kubectl commands)

See `projects/acme-k8s/AGENTS.md` and `projects/acme-compose/AGENTS.md` for examples.

---

## Sample Projects

Two sample project configurations are included:

| Project ID | Deploy Strategy | Repos |
|------------|----------------|-------|
| `acme-k8s` | GitOps / ArgoCD / Kubernetes | `acme-org/frontend`, `acme-org/backend-api`, `acme-org/k8s-manifests` |
| `acme-compose` | Docker Compose | `acme-org/app`, `acme-org/infra` |

Reference directory structures: `samples/acme-k8s/`, `samples/acme-compose/`

---

## Backward Compatibility

All changes are additive. Existing triggers that do not include `project_id` continue
to work identically — Jiri clones the single repo from the payload and analyzes it.

---

## Adding More Triggers

The `project_id` protocol works with any trigger source:

- **Slack bot** → POST to `/api/test-request` with `project_id`
- **Monitoring alert** → webhook → Jiri `/webhook` as `repository_dispatch`
- **Another agent** → POST to `/api/test-request` with `X-Jiri-Secret`
- **Scheduled check** → cron → POST to `/api/test-request`
