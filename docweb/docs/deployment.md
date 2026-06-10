---
id: deployment
title: Deployment
sidebar_position: 12
---

# Deployment

## Current State

The application runtime is still designed for **local development first**. There is no committed production container or infrastructure setup for the API/dashboard stack yet, but the repo does already ship GitHub Actions for CI and for docs deployment.

**What is in the repo today:**
- Two background processes from `run_dev.sh`
- SQLite database at `apps/api/api/dtx_ai.db`
- CORS hardcoded to `allow_origins=["*"]`
- `.github/workflows/ci.yml` for Python tests/lint and dashboard lint
- `.github/workflows/deploy.yml` for Docusaurus GitHub Pages deploys

---

## GitHub Pages (This Site)

This documentation is deployed via GitHub Pages using Docusaurus.

```bash
# From the docweb/ folder in the repo
npm run build
npm run deploy   # pushes to gh-pages branch automatically
```

GitHub Actions deployment on push to `main` is already configured in `.github/workflows/deploy.yml`.

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
      - DTX_ACTIVE_MODEL=lightgbm
  dashboard:
    build: ./apps/dashboard
    ports: ["5173:5173"]
```

---

## CI/CD

Two workflows are already committed:

- `ci.yml` runs Python tests plus optional linting and dashboard lint on pushes/PRs.
- `deploy.yml` builds and publishes `docweb/` to GitHub Pages on pushes to `main`.

If you want stricter CI later, the next useful upgrade would be failing the job on lint errors and adding a docs build check to pull requests.
