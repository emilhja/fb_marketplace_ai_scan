"""Sanity checks for the dashboard API module."""

from __future__ import annotations

from backend.app.main import health


def test_health_endpoint_payload() -> None:
    assert health() == {"status": "ok"}
