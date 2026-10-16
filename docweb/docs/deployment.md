---
id: deployment
title: Deployment
sidebar_position: 12
---

# Deployment

## v3.0 Final runtime

The application runtime targets a **local demonstration environment**. The repository includes GitHub Actions for verification and documentation deployment. Production infrastructure is outside the final release.

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

## Verification

The dashboard and documentation have production build commands. The Python
suite covers API, inference, replay, and hardware bridge behavior. See the
[setup guide](/docs/setup) for commands and [release limitations](/docs/known-issues)
for deployment boundaries.
