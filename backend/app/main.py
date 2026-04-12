from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(listings.router)
app.include_router(price_history.router)
app.include_router(notifications.router)


@app.get("/healthz", tags=["meta"])
def health():
    return {"status": "ok"}
