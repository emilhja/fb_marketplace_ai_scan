#!/usr/bin/env python3
"""Worker for processing queued listing reruns from the dashboard."""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from backend.app.db import SessionLocal, configure_session_local, ensure_dashboard_schema
from backend.app.models import ListingRerunQueue
from backend.app.services.rerun_listings import rerun_listings

logger = logging.getLogger("rerun_queue")
DEFAULT_STALE_TIMEOUT_MINUTES = 30


def utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


def claim_next_job() -> tuple[int, int] | None:
    """Atomically claim the next pending rerun job, if one exists."""
    with SessionLocal() as db:
        job = db.execute(
            select(ListingRerunQueue)
            .where(ListingRerunQueue.status == "pending")
            .order_by(ListingRerunQueue.requested_at.asc(), ListingRerunQueue.id.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        ).scalar_one_or_none()
        if job is None:
            return None

        job.status = "running"
        job.started_at = utcnow()
        job.finished_at = None
        job.error_message = None
        db.commit()
        return job.id, job.listing_id


def finish_job(job_id: int, success: bool, message: str) -> None:
    """Persist the final status of a rerun job."""
    with SessionLocal() as db:
        job = db.get(ListingRerunQueue, job_id)
        if job is None:
            return

        job.status = "completed" if success else "failed"
        job.finished_at = utcnow()
        job.error_message = None if success else message
        db.commit()


def recover_stale_running_jobs(stale_timeout_minutes: int) -> int:
    """Move abandoned running jobs back to pending so they can be retried."""
    cutoff = utcnow() - timedelta(minutes=stale_timeout_minutes)
    with SessionLocal() as db:
        jobs = (
            db.execute(
                select(ListingRerunQueue)
                .where(
                    ListingRerunQueue.status == "running",
                    ListingRerunQueue.started_at.is_not(None),
                    ListingRerunQueue.started_at < cutoff,
                )
                .order_by(ListingRerunQueue.started_at.asc(), ListingRerunQueue.id.asc())
            )
            .scalars()
            .all()
        )

        for job in jobs:
            job.status = "pending"
            job.started_at = None
            job.finished_at = None
            job.error_message = (
                f"Recovered stale running job after exceeding {stale_timeout_minutes} minutes"
            )

        if jobs:
            db.commit()

        return len(jobs)


def process_one_job(stale_timeout_minutes: int) -> bool:
    """Process one available rerun job and report whether any work was done."""
    recovered_jobs = recover_stale_running_jobs(stale_timeout_minutes)
    if recovered_jobs:
        logger.warning(
            "Recovered %s stale rerun queue job(s) back to pending after %s minutes",
            recovered_jobs,
            stale_timeout_minutes,
        )

    claimed = claim_next_job()
    if claimed is None:
        return False

    job_id, listing_id = claimed
    logger.info(
        "scraping_run picked up rerun queue job %s for listing %s",
        job_id,
        listing_id,
    )

    try:
        with SessionLocal() as db:
            results = rerun_listings(db, [listing_id])
        result = results[0] if results else None
        if result is None:
            finish_job(job_id, False, "No rerun result returned")
            return True
        finish_job(job_id, result.success, result.message)
        if result.success:
            logger.info(
                "scraping_run completed rerun queue job %s for listing %s",
                job_id,
                listing_id,
            )
        else:
            logger.error(
                "scraping_run failed rerun queue job %s for listing %s: %s",
                job_id,
                listing_id,
                result.message,
            )
    except Exception as exc:
        logger.exception("Unexpected worker failure for queue job %s", job_id)
        finish_job(job_id, False, str(exc))

    return True


def main() -> int:
    """CLI entrypoint for the rerun queue worker."""
    parser = argparse.ArgumentParser(description="Process queued listing reruns.")
    parser.add_argument("--loop", action="store_true", help="Keep polling for new jobs.")
    parser.add_argument(
        "--stale-timeout-minutes",
        type=int,
        default=DEFAULT_STALE_TIMEOUT_MINUTES,
        help="Requeue running jobs that have been stuck longer than this timeout.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=10.0,
        help="Seconds to sleep between polls when no job is available.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    configure_session_local()
    ensure_dashboard_schema()

    while True:
        processed = process_one_job(args.stale_timeout_minutes)
        if processed:
            continue
        if not args.loop:
            return 0
        time.sleep(args.poll_interval)


if __name__ == "__main__":
    raise SystemExit(main())
