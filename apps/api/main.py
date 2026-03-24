"""
DTX-AI — FastAPI stub entry point.

Start with:
    uvicorn main:app --reload --port 8000
or:
    python main.py
"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.events import router as events_router

load_dotenv()

app = FastAPI(
    title="DTX-AI API",
    description="Smart Warehouse XAI Digital Twin — stub backend",
    version="0.1.0",
)

# Allow all origins in development; tighten this for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events_router, tags=["events"])


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=True,
    )
