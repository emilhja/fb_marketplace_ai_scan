"""FastAPI application entrypoint for the local dashboard API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import ensure_dashboard_schema
from .routers import listings, notifications, price_history

app = FastAPI(
    title="FB Marketplace Dashboard API",
    description="Read-only dashboard over the ai-marketplace-monitor PostgreSQL cache.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        # allow production build served on the same host
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


@app.on_event("startup")
def startup() -> None:
    """Apply dashboard-only schema additions on API startup."""
    ensure_dashboard_schema()
