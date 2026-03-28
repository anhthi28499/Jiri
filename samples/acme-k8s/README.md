# acme-k8s — Sample Project Structure

This directory shows the structure of three repos that make up the `acme-k8s` project.
In production these are separate GitHub repositories cloned to `workspaces/` by Jiri.

```
acme-k8s/
├── frontend/           github.com/acme-org/frontend
├── backend-api/        github.com/acme-org/backend-api
└── k8s-manifests/      github.com/acme-org/k8s-manifests
```

Project config: `projects/acme-k8s/project.yaml`
Agent guide:    `projects/acme-k8s/AGENTS.md`
