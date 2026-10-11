"""Research worker: runs jobs queued from the website admin and stores the results.

    python -m gse_research worker [--once] [--poll 60]
    python -m gse_research publish      # one-off: store the committed results/ as runs

Connects with RESEARCH_DATABASE_URL (in .env): a login limited to research_jobs,
research_runs and research_state. Every poll writes a heartbeat to
research_state('worker') and claims the oldest queued job with FOR UPDATE
SKIP LOCKED. A job runs, its result is stored in research_runs, and the job is
marked done or failed. Jobs write their files to out/jobs/<id>/ (git-ignored).

No database connection is held while idle: each action opens a short
connection and retries if the server dropped it, so the worker survives
Neon closing idle connections. Neon can only suspend its compute when nothing
touches the database for its suspend window (5 minutes by default), so a poll
shorter than that keeps the database awake while the worker runs.
"""

from __future__ import annotations

import os
import socket
import threading
import time
import traceback
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb

from . import data, experiments, jobs

JOB_HEARTBEAT_S = 60   # heartbeat while a long job runs (the poll loop is paused)
RETRIES = 4


def _url() -> str:
    url = os.environ.get("RESEARCH_DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("RESEARCH_DATABASE_URL is not set in .env")
    return url


def _connect() -> psycopg.Connection:
    return psycopg.connect(_url(), autocommit=True, connect_timeout=20)


def db(action, retries: int = RETRIES):
    """Run action(conn) on a fresh connection; retry if the connection fails."""
    for attempt in range(retries):
        try:
            with _connect() as conn:
                return action(conn)
        except psycopg.OperationalError:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_state(conn: psycopg.Connection, key: str, value: dict) -> None:
    conn.execute(
        "insert into research_state(key, value, updated_at) values (%s, %s, now()) "
        "on conflict (key) do update set value = excluded.value, updated_at = now()",
        (key, Jsonb(value)))


def store_run(conn: psycopg.Connection, run: dict, job_id=None) -> str:
    row = conn.execute(
        "insert into research_runs(job_id, kind, title, params, summary, equity, tables, report_md, provenance) "
        "values (%s, %s, %s, %s, %s, %s, %s, %s, %s) returning id",
        (job_id, run["kind"], run["title"], Jsonb(run["params"]), Jsonb(run["summary"]),
         Jsonb(run["equity"]) if run.get("equity") is not None else None,
         Jsonb(run["tables"]) if run.get("tables") is not None else None, run.get("report_md"), Jsonb(run["provenance"]))).fetchone()
    return str(row[0])


class Worker:
    def __init__(self, poll: float):
        self.name = f"{socket.gethostname()}:{os.getpid()}"
        self.poll = poll
        self.started = _now()
        self.git = experiments._git()["commit"][:10]
        self.current: dict | None = None

    def heartbeat(self, conn: psycopg.Connection) -> None:
        # poll_s lets the admin judge "online" (no heartbeat for 3 polls = offline).
        set_state(conn, "worker", {"name": self.name, "host": socket.gethostname(), "pid": os.getpid(),
                                   "started_at": self.started, "git": self.git, "poll_s": max(self.poll, JOB_HEARTBEAT_S if self.current else 0),
                                   "current_job": self.current, "seen_at": _now()})

    def claim(self):
        def action(conn):
            self.heartbeat(conn)
            with conn.transaction():
                row = conn.execute(
                    "select id, kind, params from research_jobs where status = 'queued' "
                    "order by created_at limit 1 for update skip locked").fetchone()
                if row is not None:
                    conn.execute("update research_jobs set status = 'running', started_at = now(), worker = %s, "
                                 "message = 'starting', progress = 0 where id = %s", (self.name, row[0]))
            return row
        return db(action)

    def run_job(self, job_id, kind: str, params: dict) -> None:
        def progress(fraction: float, message: str) -> None:
            try:
                db(lambda c: c.execute("update research_jobs set progress = %s, message = %s where id = %s",
                                       (max(0.0, min(1.0, float(fraction))), message[:200], job_id)))
            except psycopg.OperationalError:
                pass  # progress is informative; the job carries on

        stop = threading.Event()

        def beat():
            while not stop.wait(JOB_HEARTBEAT_S):
                try:
                    db(self.heartbeat, retries=1)
                except psycopg.OperationalError:
                    pass
        self.current = {"id": str(job_id), "kind": kind}
        threading.Thread(target=beat, daemon=True).start()
        try:
            clean_params = jobs.validate(kind, params)
            work = data.ROOT / "out" / "jobs" / str(job_id)
            work.mkdir(parents=True, exist_ok=True)
            run, state = jobs.RUNNERS[kind](clean_params, work, progress)

            def finish(conn):
                run_id = store_run(conn, run, job_id) if run else None
                if state is not None:
                    set_state(conn, "dataset", state)
                conn.execute("update research_jobs set status = 'done', progress = 1, message = 'done', run_id = %s, "
                             "finished_at = now() where id = %s", (run_id, job_id))
            db(finish)
        except Exception as exc:  # the job fails, the worker carries on
            detail = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
            db(lambda c: c.execute("update research_jobs set status = 'failed', error = %s, message = 'failed', "
                                   "finished_at = now() where id = %s", (detail[:2000], job_id)))
        finally:
            stop.set()
            self.current = None

    def run(self, once: bool = False) -> None:
        # A job left running by a previous worker on this machine cannot finish any more.
        db(lambda c: c.execute("update research_jobs set status = 'failed', error = 'worker restarted', message = 'failed', "
                               "finished_at = now() where status = 'running' and worker like %s", (f"{socket.gethostname()}:%",)))
        if db(lambda c: c.execute("select 1 from research_state where key = 'dataset'").fetchone()) is None:
            state = jobs.dataset_state()
            db(lambda c: set_state(c, "dataset", state))
        print(f"worker {self.name} ready; polling every {self.poll:.0f}s", flush=True)
        while True:
            try:
                job = self.claim()
            except psycopg.OperationalError as exc:
                print(f"{_now()} database unreachable ({str(exc).splitlines()[0]}); retrying", flush=True)
                time.sleep(self.poll)
                continue
            if job is None:
                if once:
                    return
                time.sleep(self.poll)
                continue
            job_id, kind, params = job
            print(f"{_now()} {kind} {job_id} started", flush=True)
            self.run_job(job_id, kind, params or {})
            print(f"{_now()} {kind} {job_id} finished", flush=True)


def run_worker(once: bool = False, poll: float = 60.0) -> None:
    try:
        Worker(poll).run(once)
    except KeyboardInterrupt:
        print("stopping", flush=True)


def publish_committed() -> list[str]:
    """Store results/ (R001 train, O1, O2) as runs once; skips any already stored."""
    runs = jobs.committed_results()
    state = jobs.dataset_state()

    def action(conn):
        have = {r[0] for r in conn.execute("select provenance->>'source' from research_runs where provenance ? 'source'").fetchall()}
        stored = [store_run(conn, run) for run in runs if run["provenance"].get("source") not in have]
        set_state(conn, "dataset", state)
        return stored
    return db(action)
