---
id: deployment
title: Deployment
sidebar_position: 12
---

# Deployment

## Current State

The project is designed for **local development only**. No production deployment configuration exists in the repository (no Dockerfile, docker-compose.yml, or CI/CD workflows).

**Local dev stack:**
- Two background processes from `run_dev.sh`
- SQLite database at `apps/api/api/dtx_ai.db`
- CORS hardcoded to `allow_origins=["*"]`

---

## GitHub Pages (This Site)

This documentation is deployed via GitHub Pages using Docusaurus.

```bash
# From the website/ folder in the repo
npm run build
npm run deploy   # pushes to gh-pages branch automatically
```

Or set up GitHub Actions to auto-deploy on push to `main`.

---

## Production Recommendations

| Component | Current | Production Path |
|---|---|---|
| API | `uvicorn` direct | Docker + nginx reverse proxy + HTTPS |
| Database | SQLite | PostgreSQL (asyncpg + SQLAlchemy async) |
| Frontend | Vite dev server | `npm run build` → CDN / nginx static |
| AI service | In-process | Extract to microservice behind Redis Streams / NATS |
| CORS | `*` | Set to specific allowed origins |
| Secrets | `.env` file | Vault / AWS Secrets Manager |

### Example Docker Setup (future)

```dockerfile
# apps/api/Dockerfile (not yet committed)
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml (not yet committed)
services:
  api:
    build: ./apps/api
    ports: ["8000:8000"]
    environment:
      - MODEL_NAME=lightgbm
  dashboard:
    build: ./apps/dashboard
    ports: ["5173:5173"]
```

---

## CI/CD

No CI/CD configuration is currently committed. Recommended setup:

```yaml
# .github/workflows/test.yml (suggested)
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r apps/api/requirements.txt -r services/ai/requirements.txt
      - run: pip install -e packages/shared
      - run: pytest tests/
```
