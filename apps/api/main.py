"""
DTX-AI — FastAPI entry point.

Start with:
    uvicorn main:app --reload --port 8000
or:
    python main.py
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import init_db
from api.routes.alerts import router as alerts_router
from api.routes.events import router as events_router
from api.routes.health import router as health_router
from api.routes.websocket import router as ws_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the database on startup."""
    await init_db()
    yield


app = FastAPI(
    title="DTX-AI API",
    description="Smart Warehouse XAI Digital Twin backend",
    version="0.2.0",
    lifespan=lifespan,
)

# Allow all origins in development; tighten this for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, tags=["health"])
app.include_router(events_router, prefix="/events", tags=["events"])
app.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
app.include_router(ws_router, tags=["websocket"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=True,
    )
