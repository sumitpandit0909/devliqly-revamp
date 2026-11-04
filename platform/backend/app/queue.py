"""A durable job queue in Postgres.

Jobs are written in the same transaction as the data that caused them, so neither exists without the other. A handler's
database changes commit together with its job being marked done, so a crash can't apply them twice. A crashed worker's
job is picked up again when its lease expires, so handlers calling outside services must tolerate running again.
"""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import set_scope, standalone_session
from app.models import Job

log = logging.getLogger(__name__)

LEASE_SECONDS = 300
HANDLER_TIMEOUT_SECONDS = 240
BACKOFF_BASE_SECONDS = 5
BACKOFF_MAX_SECONDS = 900
# With nothing due, check at this interval. Long enough to let Neon suspend when idle.
IDLE_CHECK_SECONDS = 300


@dataclass(frozen=True)
class ClaimedJob:
    seq: int
    kind: str
    payload: dict
    attempts: int
    max_attempts: int


Handler = Callable[[AsyncSession, ClaimedJob], Awaitable[None]]
_handlers: dict[str, Handler] = {}
_wake = asyncio.Event()


def job_handler(kind: str) -> Callable[[Handler], Handler]:
    def register(handler: Handler) -> Handler:
        _handlers[kind] = handler
        return handler

    return register


def wake_worker() -> None:
    """Start on new work right away. Call after committing; if the signal is missed, the idle check still finds it."""
    _wake.set()


async def enqueue(
    db: AsyncSession,
    kind: str,
    payload: dict,
    *,
    lock_key: str | None = None,
    dedupe_key: str | None = None,
    max_attempts: int = 6,
) -> None:
    """Add a job to the caller's transaction. The session must have system scope."""
    await db.execute(
        insert(Job)
        .values(kind=kind, payload=payload, lock_key=lock_key, dedupe_key=dedupe_key, max_attempts=max_attempts)
        .on_conflict_do_nothing(index_elements=[Job.dedupe_key])
    )


_RECOVER = text(
    """
    UPDATE job_queue
    SET status = CASE WHEN attempts >= max_attempts THEN 'dead' ELSE 'pending' END,
        finished_at = CASE WHEN attempts >= max_attempts THEN now() END,
        last_error = COALESCE(last_error, 'Worker stopped before finishing'),
        locked_until = NULL,
        run_after = now()
    WHERE status = 'running' AND locked_until < now()
    """
)

# An earlier unfinished job with the same lock_key blocks this one, even if it's waiting to retry.
# SKIP LOCKED lets several workers claim at once without taking the same job.
_CLAIM = text(
    """
    UPDATE job_queue
    SET status = 'running', attempts = attempts + 1, locked_until = now() + make_interval(secs => :lease)
    WHERE seq = (
        SELECT j.seq FROM job_queue j
        WHERE j.status = 'pending' AND j.run_after <= now()
          AND (j.lock_key IS NULL OR NOT EXISTS (
              SELECT 1 FROM job_queue earlier
              WHERE earlier.lock_key = j.lock_key AND earlier.seq < j.seq
                AND earlier.status IN ('pending', 'running')
          ))
        ORDER BY j.seq
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING seq, kind, payload, attempts, max_attempts
    """
)


async def claim_job(*, lease_seconds: int = LEASE_SECONDS) -> ClaimedJob | None:
    async with standalone_session() as db:
        await set_scope(db, system=True)
        await db.execute(_RECOVER)
        row = (await db.execute(_CLAIM, {"lease": lease_seconds})).one_or_none()
        await db.commit()
    return ClaimedJob(row.seq, row.kind, row.payload, row.attempts, row.max_attempts) if row else None


async def _record_failure(job: ClaimedJob, error: str) -> None:
    delay = min(BACKOFF_BASE_SECONDS * 2 ** (job.attempts - 1), BACKOFF_MAX_SECONDS)
    run_after = datetime.now(UTC) + timedelta(seconds=delay + random.uniform(0, delay / 4))  # noqa: S311
    dead = job.attempts >= job.max_attempts
    async with standalone_session() as db:
        await set_scope(db, system=True)
        await db.execute(
            text(
                """
                UPDATE job_queue
                SET status = :status, last_error = :error, run_after = :run_after, locked_until = NULL,
                    finished_at = CASE WHEN :dead THEN now() END
                WHERE seq = :seq AND attempts = :attempts AND status = 'running'
                """
            ),
            {
                "status": "dead" if dead else "pending",
                "error": error[:2000],
                "run_after": run_after,
                "dead": dead,
                "seq": job.seq,
                "attempts": job.attempts,
            },
        )
        await db.commit()
    if dead:
        log.error("Job %s (%s) failed permanently: %s", job.seq, job.kind, error)
    else:
        log.warning("Job %s (%s) failed on attempt %s: %s", job.seq, job.kind, job.attempts, error)


async def run_job(job: ClaimedJob) -> None:
    handler = _handlers.get(job.kind)
    try:
        if handler is None:
            raise LookupError(f"No handler for job kind {job.kind}")
        async with asyncio.timeout(HANDLER_TIMEOUT_SECONDS):
            async with standalone_session() as db:
                await set_scope(db, system=True)
                await handler(db, job)
                # The attempts check stops a worker that lost its lease from overwriting the newer attempt
                result = await db.execute(
                    text(
                        """
                        UPDATE job_queue SET status = 'done', finished_at = now(), locked_until = NULL
                        WHERE seq = :seq AND attempts = :attempts AND status = 'running'
                        """
                    ),
                    {"seq": job.seq, "attempts": job.attempts},
                )
                if result.rowcount != 1:
                    await db.rollback()
                    log.warning("Job %s lost its lease; discarding this attempt", job.seq)
                    return
                await db.commit()
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - any failure must reach the retry path
        await _record_failure(job, f"{type(exc).__name__}: {exc}")


async def run_due_jobs() -> int:
    """Run jobs one by one until none are due. Returns how many ran."""
    count = 0
    while (job := await claim_job()) is not None:
        await run_job(job)
        count += 1
    return count


async def _seconds_until_next_job() -> float:
    async with standalone_session() as db:
        await set_scope(db, system=True)
        due = await db.scalar(select(Job.run_after).where(Job.status == "pending").order_by(Job.run_after).limit(1))
        lease = await db.scalar(
            select(Job.locked_until).where(Job.status == "running").order_by(Job.locked_until).limit(1)
        )
    moments = [m for m in (due, lease) if m is not None]
    if not moments:
        return IDLE_CHECK_SECONDS
    return max(0.2, min((min(moments) - datetime.now(UTC)).total_seconds(), IDLE_CHECK_SECONDS))


async def run_worker() -> None:
    """Runs for the life of the app. Waits on signals and timers rather than polling constantly."""
    slots = asyncio.Semaphore(get_settings().worker_concurrency)
    running: set[asyncio.Task] = set()

    async def run_then_release(job: ClaimedJob) -> None:
        try:
            await run_job(job)
        finally:
            slots.release()
            _wake.set()

    try:
        while True:
            _wake.clear()
            try:
                while True:
                    await slots.acquire()
                    job = await claim_job()
                    if job is None:
                        slots.release()
                        break
                    task = asyncio.create_task(run_then_release(job))
                    running.add(task)
                    task.add_done_callback(running.discard)
                delay = await _seconds_until_next_job()
            except Exception:
                log.exception("Worker could not reach the database; retrying shortly")
                delay = 5
            try:
                async with asyncio.timeout(delay):
                    await _wake.wait()
            except TimeoutError:
                pass
    finally:
        for task in running:
            task.cancel()
        await asyncio.gather(*running, return_exceptions=True)
