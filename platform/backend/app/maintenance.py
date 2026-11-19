"""Housekeeping: old records are deleted, and files follow the records they belonged to."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Job, LoginSession, PasswordSetupToken, WebhookInbox
from app.queue import ClaimedJob, daily_job, job_handler
from app.storage import get_storage

log = logging.getLogger(__name__)

DELETE_FILES = "delete_stored_files"
PRUNE = "prune_old_records"


@job_handler(DELETE_FILES)
async def delete_stored_files(_: AsyncSession, job: ClaimedJob) -> None:
    storage = get_storage()
    for key in job.payload["keys"]:
        await storage.delete(key)


@daily_job(PRUNE)
async def prune_old_records(db: AsyncSession, _: ClaimedJob) -> None:
    """Webhook payloads and job records hold message text and phone numbers, so they aren't kept for long."""
    cutoff = datetime.now(UTC) - timedelta(days=get_settings().retention_days)
    now = datetime.now(UTC)
    inbox = await db.execute(delete(WebhookInbox).where(WebhookInbox.received_at < cutoff))
    jobs = await db.execute(delete(Job).where(Job.status.in_(("done", "dead")), Job.finished_at < cutoff))
    await db.execute(delete(LoginSession).where(LoginSession.expires_at < now))
    await db.execute(delete(PasswordSetupToken).where(PasswordSetupToken.expires_at < now))
    log.info("Pruned %s webhook records and %s jobs", inbox.rowcount, jobs.rowcount)
