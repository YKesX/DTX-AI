# Kanban Workflow — DTX-AI

## Columns

| Column | Meaning |
|--------|---------|
| **Backlog** | Accepted but not yet scheduled |
| **Sprint Ready** | Prioritised for the current sprint; fully specified |
| **In Progress** | Actively being worked on (max 2 cards per developer) |
| **In Review** | Pull request open; waiting for code review |
| **Done** | Merged and verified |

## Labels

| Label | Colour | Usage |
|-------|--------|-------|
| `feature` | Blue | New functionality |
| `bug` | Red | Something broken |
| `task` | Grey | Chore, setup, docs |
| `ai` | Purple | AI / ML pipeline work |
| `frontend` | Teal | Dashboard work |
| `backend` | Orange | API work |
| `sim` | Yellow | Isaac Sim / digital twin |
| `infra` | Dark grey | CI, Docker, scripts |
| `priority: high` | Bright red | Must ship this sprint |
| `priority: low` | Light grey | Nice to have |
| `good first issue` | Green | Suitable for onboarding |
| `blocked` | Black | Blocked on dependency |

## Branch Naming Convention

```
<type>/<short-description>

Examples:
  feature/event-ingestion-api
  fix/ws-reconnect-loop
  task/setup-ci-pipeline
  docs/update-architecture-diagram
```

## Commit Message Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

Types: feat, fix, docs, chore, refactor, test, ci
Scope: api, ai, dashboard, sim, shared, scripts, data

Examples:
  feat(api): add POST /events endpoint
  fix(ai): correct anomaly score normalisation
  docs(architecture): add sequence diagram
  test(smoke): add schema validation tests
```

## Review Process

1. Open a PR from your feature branch to `main`.
2. Fill in the PR template (linked checklist items to Kanban cards).
3. At least 1 approval required before merging.
4. Squash-merge to keep `main` history clean.
