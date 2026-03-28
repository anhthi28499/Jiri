# acme-compose — Sample Project Structure

This directory shows the structure of two repos that make up the `acme-compose` project.
In production these are separate GitHub repositories cloned to `workspaces/` by Jiri.

```
acme-compose/
├── app/      github.com/acme-org/app    (monorepo: frontend + backend)
└── infra/    github.com/acme-org/infra  (docker-compose + nginx)
```

Project config: `projects/acme-compose/project.yaml`
Agent guide:    `projects/acme-compose/AGENTS.md`
