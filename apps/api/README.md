# apps/api — FastAPI backend for DTX-AI

## Responsibilities
- Accept warehouse events via `POST /events`
- Pass events to the AI pipeline (services/ai)
- Broadcast results over WebSocket `/ws/events`
- Persist events + alerts to SQLite
- Serve alert history via `GET /alerts`

## Running locally

```bash
cd apps/api
python -m uvicorn main:app --reload --port 8000
```

Or use the root convenience script:

```bash
bash scripts/run_dev.sh
```

## Environment variables

Copy `.env.example` to `.env` and adjust:

```bash
cp .env.example .env
```

## API Reference

See [docs/api_contract.md](../../docs/api_contract.md) or the interactive
Swagger UI at http://localhost:8000/docs once the server is running.
