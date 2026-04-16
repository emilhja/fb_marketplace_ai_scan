import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import ensure_dashboard_schema
from .routers import listings, notifications, price_history


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Apply dashboard-only schema additions on API startup."""
    ensure_dashboard_schema()
    yield


app = FastAPI(
    title="FB Marketplace Dashboard API",
    description="Read-only dashboard over the ai-marketplace-monitor PostgreSQL cache.",
    version="1.0.0",
    lifespan=lifespan,
)

_frontend_port = os.environ.get("DASHBOARD_FRONTEND_PORT", "5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://127.0.0.1:{_frontend_port}",
        f"http://localhost:{_frontend_port}",
        # allow production preview build served on the same host
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_methods=["GET", "PATCH", "POST"],
    allow_headers=["*"],
)

app.include_router(listings.router)
app.include_router(price_history.router)
app.include_router(notifications.router)


@app.get("/healthz", tags=["meta"])
def health() -> dict[str, str]:
    """Return a minimal liveness payload for local tooling and CI smoke tests."""
    return {"status": "ok"}
