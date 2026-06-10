# DTX-AI Documentation Site

Built with [Docusaurus](https://docusaurus.io/).

Current docs release: `v2.0`

## Local Development

```bash
npm install
npm start
```

Opens at http://localhost:3000/DTX-AI/

## Build

```bash
npm run build
```

## Deploy to GitHub Pages

### Option 1 — Automatic (GitHub Actions)
Merge your PR into `main`. The `.github/workflows/deploy.yml` workflow will build `docweb/` and publish it automatically.

### Option 2 — Manual
```bash
GIT_USER=YKesX npm run deploy
```

## Repo Setup (one-time)
1. Go to your repo → **Settings → Pages**
2. Set **Source** to `GitHub Actions`
3. Merge the PR into `main`
4. Wait for the **Deploy Docs to GitHub Pages** workflow to finish
5. Site will be live at: `https://YKesX.github.io/DTX-AI/`
