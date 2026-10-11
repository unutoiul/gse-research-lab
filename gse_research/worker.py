"""Research worker: runs jobs queued from the website admin and stores the results.

    python -m gse_research worker [--once] [--poll 10]
    python -m gse_research publish      # one-off: store the committed results/ as runs

Connects with RESEARCH_DATABASE_URL (in .env): a login limited to research_jobs,
research_runs and research_state. It claims the oldest queued job with
FOR UPDATE SKIP LOCKED, runs it, writes a research_runs row and marks the job
done or failed. A heartbeat in research_state('worker') tells the admin
whether a worker is online. Jobs write their files to out/jobs/<id>/ (git-ignored).
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

HEARTBEAT_S = 20


def _url() -> str:
    url = os.environ.get("RESEARCH_DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("RESEARCH_DATABASE_URL is not set in .env")
    return url


def _connect() -> psycopg.Connection:
    return psycopg.connect(_url(), autocommit=True, connect_timeout=20)


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


class Heartbeat(threading.Thread):
    """Keeps research_state('worker') fresh, also while a long job runs."""

    def __init__(self, name: str):
        super().__init__(daemon=True)
        self.name_, self.stop_event, self.current = name, threading.Event(), None
        self.started = _now()

    def run(self) -> None:
        conn = None
        while not self.stop_event.is_set():
            try:
                conn = conn or _connect()
                set_state(conn, "worker", {"name": self.name_, "host": socket.gethostname(), "pid": os.getpid(),
                                           "started_at": self.started, "git": experiments._git()["commit"][:10],
                                           "current_job": self.current, "seen_at": _now()})
            except Exception:  # a dropped connection must not kill the worker; retry next beat
                conn = None
            self.stop_event.wait(HEARTBEAT_S)


def claim(conn: psycopg.Connection, name: str):
    with conn.transaction():
        row = conn.execute(
            "select id, kind, params from research_jobs where status = 'queued' "
            "order by created_at limit 1 for update skip locked").fetchone()
        if row is None:
            return None
        conn.execute("update research_jobs set status = 'running', started_at = now(), worker = %s, "
                     "message = 'starting', progress = 0 where id = %s", (name, row[0]))
    return row


def run_job(conn: psycopg.Connection, job_id, kind: str, params: dict) -> None:
    def progress(fraction: float, message: str) -> None:
        conn.execute("update research_jobs set progress = %s, message = %s where id = %s",
                     (max(0.0, min(1.0, float(fraction))), message[:200], job_id))

    try:
        clean_params = jobs.validate(kind, params)
        work = data.ROOT / "out" / "jobs" / str(job_id)
        work.mkdir(parents=True, exist_ok=True)
        run, state = jobs.RUNNERS[kind](clean_params, work, progress)
        run_id = store_run(conn, run, job_id) if run else None
        if state is not None:
            set_state(conn, "dataset", state)
        conn.execute("update research_jobs set status = 'done', progress = 1, message = 'done', run_id = %s, "
                     "finished_at = now() where id = %s", (run_id, job_id))
    except Exception as exc:  # the job fails, the worker carries on
        detail = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
        conn.execute("update research_jobs set status = 'failed', error = %s, message = 'failed', finished_at = now() "
                     "where id = %s", (detail[:2000], job_id))


def run_worker(once: bool = False, poll: float = 10.0) -> None:
    name = f"{socket.gethostname()}:{os.getpid()}"
    beat = Heartbeat(name)
    beat.start()
    with _connect() as conn:
        # A job left running by a previous worker on this machine cannot finish any more.
        conn.execute("update research_jobs set status = 'failed', error = 'worker restarted', message = 'failed', "
                     "finished_at = now() where status = 'running' and worker like %s", (f"{socket.gethostname()}:%",))
        if conn.execute("select 1 from research_state where key = 'dataset'").fetchone() is None:
            set_state(conn, "dataset", jobs.dataset_state())
        print(f"worker {name} ready; polling every {poll:.0f}s", flush=True)
        try:
            while True:
                job = claim(conn, name)
                if job is None:
                    if once:
                        break
                    time.sleep(poll)
                    continue
                job_id, kind, params = job
                beat.current = {"id": str(job_id), "kind": kind}
                print(f"{_now()} {kind} {job_id} started", flush=True)
                run_job(conn, job_id, kind, params or {})
                beat.current = None
                print(f"{_now()} {kind} {job_id} finished", flush=True)
        except KeyboardInterrupt:
            print("stopping", flush=True)
        finally:
            beat.stop_event.set()


def publish_committed() -> list[str]:
    """Store results/ (R001 train, O1, O2) as runs once; skips any already stored."""
    stored = []
    with _connect() as conn:
        have = {r[0] for r in conn.execute("select provenance->>'source' from research_runs where provenance ? 'source'").fetchall()}
        for run in jobs.committed_results():
            if run["provenance"].get("source") in have:
                continue
            stored.append(store_run(conn, run))
        set_state(conn, "dataset", jobs.dataset_state())
    return stored
