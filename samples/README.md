# Sample Project Structures

These directories are **read-only reference stubs** showing what a real project's
repository structure looks like alongside its Jiri `project.yaml` config.

> The actual project configs used by Jiri at runtime are in `projects/`.
> Real repos are cloned to `workspaces/` when a trigger fires.

| Sample | Deploy Strategy | Repos |
|--------|----------------|-------|
| [acme-k8s](acme-k8s/) | GitOps / ArgoCD / Kubernetes | `frontend`, `backend-api`, `k8s-manifests` |
| [acme-compose](acme-compose/) | Docker Compose | `app` (monorepo), `infra` |

## How to add a new project

1. Create `projects/<your-project-id>/project.yaml` (see existing examples for schema).
2. Create `projects/<your-project-id>/AGENTS.md` with architecture notes for the agent.
3. Optionally add a stub tree under `samples/<your-project-id>/` for reference.
4. Trigger Jiri with `project_id: <your-project-id>` in the payload.
