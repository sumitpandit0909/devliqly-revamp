import asyncio
import subprocess
import sys
import textwrap

from sqlalchemy import text

from app import queue
from app.db import set_scope, standalone_session
from app.models import ExpoEvent, WebhookInbox
from app.queue import claim_job, enqueue, job_handler, run_due_jobs, run_job, run_worker, wake_worker
from tests.conftest import BACKEND_DIR, bearer, owner_engine

ran: list[str] = []


@job_handler("test_record")
async def _record(_, job) -> None:
    ran.append(job.payload["name"])


@job_handler("test_explode")
async def _explode(db, job) -> None:
    # This write must disappear when the handler fails
    db.add(WebhookInbox(event_key=f"should-not-exist:{job.seq}", kind="test", payload={}))
    await db.flush()
    raise RuntimeError("boom")


def setup_function() -> None:
    ran.clear()


async def add_job(kind="test_record", name="x", **options) -> None:
    async with standalone_session() as db:
        await set_scope(db, system=True)
        await enqueue(db, kind, {"name": name}, **options)
        await db.commit()


async def sql(statement: str, **params) -> list:
    engine = owner_engine()
    async with engine.begin() as connection:
        result = await connection.execute(text(statement), params)
        rows = result.all() if result.returns_rows else []
    await engine.dispose()
    return rows


async def job_row() -> tuple:
    rows = await sql("SELECT status, attempts, last_error FROM job_queue ORDER BY seq LIMIT 1")
    return tuple(rows[0])


async def test_job_runs_once():
    await add_job()
    assert await run_due_jobs() == 1
    assert await run_due_jobs() == 0
    assert ran == ["x"]
    assert (await job_row())[0] == "done"


async def test_dedupe_key_blocks_a_second_job():
    await add_job(dedupe_key="same")
    await add_job(dedupe_key="same")
    await run_due_jobs()
    assert ran == ["x"]


async def test_failed_job_undoes_its_writes_and_waits_to_retry():
    await add_job("test_explode")
    assert await run_due_jobs() == 1
    status, attempts, error = await job_row()
    assert (status, attempts) == ("pending", 1)
    assert "boom" in error
    assert await sql("SELECT 1 FROM webhook_inbox") == []
    assert await run_due_jobs() == 0  # Not due yet: it's backing off


async def test_job_goes_dead_after_max_attempts_and_staff_can_retry_it(client, operator_token):
    await add_job("test_explode", max_attempts=2)
    for _ in range(2):
        await run_due_jobs()
        await sql("UPDATE job_queue SET run_after = now() WHERE status = 'pending'")
    assert (await job_row())[0] == "dead"

    staff = bearer(operator_token)
    assert (await client.get("/api/operator/jobs/summary", headers=staff)).json()["dead"] == 1
    dead = (await client.get("/api/operator/jobs/dead", headers=staff)).json()
    assert dead[0]["kind"] == "test_explode"
    assert "boom" in dead[0]["last_error"]

    assert (await client.post(f"/api/operator/jobs/{dead[0]['seq']}/retry", headers=staff)).status_code == 204
    assert (await job_row())[:2] == ("pending", 0)
    assert (await client.post(f"/api/operator/jobs/{dead[0]['seq']}/retry", headers=staff)).status_code == 404


async def test_job_routes_are_staff_only(client, two_orgs):
    owner = bearer(two_orgs["a"]["token"])
    assert (await client.get("/api/operator/jobs/summary", headers=owner)).status_code == 403
    assert (await client.post("/api/operator/jobs/1/retry", headers=owner)).status_code == 403


async def test_unknown_job_kind_fails_visibly():
    await add_job("test_no_such_kind")
    await run_due_jobs()
    assert "No handler" in (await job_row())[2]


async def test_same_lock_key_never_runs_at_once_and_keeps_order():
    for name in ("a", "b", "c"):
        await add_job(name=name, lock_key="rep-1")
    first = await claim_job()
    assert first.payload["name"] == "a"
    assert await claim_job() is None  # b must wait for a

    await run_job(first)
    second = await claim_job()
    assert second.payload["name"] == "b"


async def test_a_failing_job_holds_back_later_jobs_with_its_key_only():
    await add_job("test_explode", name="bad", lock_key="rep-1")
    await add_job(name="blocked", lock_key="rep-1")
    await add_job(name="other", lock_key="rep-2")
    await run_due_jobs()
    assert ran == ["other"]


async def test_dead_job_stops_blocking_its_key():
    await add_job("test_explode", name="bad", lock_key="rep-1", max_attempts=1)
    await add_job(name="next", lock_key="rep-1")
    await run_due_jobs()
    assert ran == ["next"]


async def test_many_workers_never_claim_the_same_job():
    for number in range(20):
        await add_job(name=str(number))

    async def worker() -> list[int]:
        claimed = []
        while (job := await claim_job()) is not None:
            claimed.append(job.seq)
        return claimed

    results = await asyncio.gather(*(worker() for _ in range(4)))
    everything = [seq for result in results for seq in result]
    assert len(everything) == 20
    assert len(set(everything)) == 20


async def test_killed_process_loses_nothing():
    """A real worker process dies the moment after claiming a job. The job must run again afterwards."""
    await add_job(name="survivor")
    script = textwrap.dedent(
        """
        import asyncio, os
        from app.queue import claim_job

        async def main():
            job = await claim_job(lease_seconds=1)
            assert job is not None
            os._exit(9)  # No cleanup at all, like a crash or power loss

        asyncio.run(main())
        """
    )
    process = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-c", script],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 9, process.stderr
    assert (await job_row())[:2] == ("running", 1)
    assert await run_due_jobs() == 0  # Still inside its lease

    await asyncio.sleep(1.2)
    assert await run_due_jobs() == 1
    assert ran == ["survivor"]
    status, attempts, error = await job_row()
    assert (status, attempts) == ("done", 2)
    assert "Worker stopped" in error


async def test_job_at_its_attempt_limit_goes_dead_when_its_worker_vanishes():
    await add_job(name="x", max_attempts=1)
    assert await claim_job(lease_seconds=0) is not None
    await asyncio.sleep(0.05)
    assert await run_due_jobs() == 0
    assert (await job_row())[0] == "dead"


async def test_worker_that_lost_its_lease_cannot_overwrite_the_newer_attempt():
    await add_job(name="x")
    stale = await claim_job(lease_seconds=0)
    await asyncio.sleep(0.05)
    newer = await claim_job()
    assert newer.attempts == 2

    await run_job(stale)  # Finishes late
    assert (await job_row())[:2] == ("running", 2)
    await run_job(newer)
    assert (await job_row())[:2] == ("done", 2)


async def test_scope_is_enforced_on_a_job_session():
    """The worker's system scope doesn't let customer data be written into a table it has only read access to."""
    org_id = (await sql("INSERT INTO organizations (id, name) VALUES (gen_random_uuid(), 'A') RETURNING id"))[0][0]
    async with standalone_session() as db:
        await set_scope(db, system=True)
        db.add(ExpoEvent(organization_id=org_id, name="Not via system scope"))
        try:
            await db.flush()
            raise AssertionError("The write should have been refused")
        except Exception as exc:  # noqa: BLE001
            assert "row-level security" in str(exc)


async def test_running_worker_picks_up_new_work_immediately():
    worker = asyncio.create_task(run_worker())
    try:
        await asyncio.sleep(0.2)
        await add_job(name="live")
        wake_worker()
        async with asyncio.timeout(5):
            while "live" not in ran:  # noqa: ASYNC110
                await asyncio.sleep(0.02)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


async def test_idle_worker_checks_rarely(monkeypatch):
    assert await queue._seconds_until_next_job() == queue.IDLE_CHECK_SECONDS
    await add_job(name="due")
    assert await queue._seconds_until_next_job() <= 0.2
