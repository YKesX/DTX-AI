# Contributing to DTX-AI

## Branch Naming

```
<type>/<short-description>

feat/event-ingestion-api
fix/ws-reconnect-loop
task/setup-ci
docs/architecture-diagram
```

## Commit Messages (Conventional Commits)

```
feat(api): add POST /events endpoint
fix(ai): correct anomaly score normalisation
docs(arch): update sequence diagram
test(smoke): add schema validation tests
chore(deps): bump pydantic to 2.7
```

## Pull Requests

1. Branch from `main`.
2. Open a PR and fill in the template.
3. At least 1 approval required.
4. Squash-merge preferred.

## Running Tests

```bash
source .venv/bin/activate
pytest tests/smoke/ -v
pytest tests/integration/ -v   # requires httpx
```

## Code Style

- Python: ruff (`pip install ruff && ruff check .`)
- JavaScript: ESLint (`cd apps/dashboard && npm run lint`)
