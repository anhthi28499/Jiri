# Jiri Agent Context — acme-compose

## Project Summary

Two-repo Docker Compose deployment:
| Repo | Role |
|------|------|
| `acme-org/app` | Monorepo: `frontend/` (React + Vite) + `backend/` (Python FastAPI) |
| `acme-org/infra` | Docker Compose files, Nginx config, `.env` template |

## Deployment Flow

```
push to acme-org/app
    → GitHub Actions builds frontend + backend Docker images → GHCR
    → Deploy script: SSH → docker compose pull → docker compose up -d
```

## Diagnosing a UI Test Failure

1. **Frontend regression** — check `app/frontend/src/` for component changes.
   Key files: `components/CheckoutForm.tsx`, `api/client.ts`.

2. **API break** — check `app/backend/routers/` for changed endpoints or
   `app/backend/models/schemas.py` for schema drift. A renamed field in a
   Pydantic model often breaks the frontend silently.

3. **Nginx misconfiguration** — check `infra/nginx/nginx.conf`.
   A missing trailing slash on `/api/` proxy_pass is a common culprit.

4. **Wrong image tag / missing env var** — check `infra/docker-compose.prod.yml`
   and `infra/.env.example`. A deployment that ran with an old image or a missing
   `SECRET_KEY` / `DATABASE_URL` will fail in ways that look like frontend bugs.

5. **CORS issue** — check `app/backend/main.py` for FastAPI CORS middleware config.
   Staging domain must be in `allow_origins`.

## Issue Filing

- Target repo: `acme-org/app`
- Apply labels: `bug`, `jiri-reported`
- Include the failing test name, environment, and relevant file paths
- Tag `@jannus` or include `/fix` so the fix agent picks it up

## Constraints

- Read-only analysis only. Do NOT run `docker compose` commands on any host.
- Do NOT modify infra/ configs directly — flag for human review.
- Do NOT merge PRs or push commits.
