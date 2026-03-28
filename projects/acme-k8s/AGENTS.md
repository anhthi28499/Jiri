# Jiri Agent Context — acme-k8s

## Project Summary

Three-repo Kubernetes/GitOps platform:
| Repo | Role |
|------|------|
| `acme-org/frontend` | React + Vite SPA, served by Nginx inside K8s |
| `acme-org/backend-api` | Node.js/Express REST API |
| `acme-org/k8s-manifests` | ArgoCD Application YAMLs + Kustomize overlays |

## Deployment Flow

```
push to frontend/backend-api
    → GitHub Actions builds Docker image → GHCR
    → CI bot commits new image tag to k8s-manifests
    → ArgoCD syncs Deployment in cluster
```

## Diagnosing a UI Test Failure

1. **Frontend regression** — check recent commits in `frontend/src/` for component
   or routing changes. Pay attention to `pages/Checkout.tsx` and `api/client.ts`.

2. **API contract break** — check `backend-api/src/routes/` for endpoint signature
   changes that the frontend didn't track. Look at request/response schemas.

3. **Bad image tag or missing env var** — check
   `k8s-manifests/base/frontend/deployment.yaml` and
   `k8s-manifests/base/backend-api/configmap.yaml`.
   A CI bot commit that bumped the image tag to a broken build is a common root cause.

4. **Staging-only issue** — compare
   `k8s-manifests/overlays/staging/kustomization.yaml` vs `overlays/production/`
   for config drift.

## Issue Filing

- Target repo: `acme-org/frontend`
- Apply labels: `bug`, `jiri-reported`
- Mention the relevant file path(s) in the issue body
- Tag `@jannus` or include `/fix` so the fix agent picks it up

## Constraints

- Read-only analysis only. Do NOT run `kubectl`, `argocd`, or `helm` commands.
- Do NOT modify k8s-manifests directly — flag for human review.
- Do NOT merge PRs or push commits.
