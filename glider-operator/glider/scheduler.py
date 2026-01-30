"""Async scheduler for Glider sync tasks."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import logfire

from glider.config import settings
from glider.logging_setup import configure_logfire
from glider.sync.google_calendar import sync_google_calendar
from glider.sync.oura import DEFAULT_DATA_TYPES, sync_oura
from glider.sync.spotify import sync_spotify

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class TaskSpec:
    name: str
    interval_seconds: int
    handler: Callable[..., Awaitable[Any]]
    kwargs: dict[str, Any]


def _load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _get_required_int(config: dict, key: str, task_name: str) -> int:
    value = config.get(key)
    if value is None:
        raise ValueError(f"Missing required field '{key}' for task '{task_name}'")
    if not isinstance(value, int):
        raise ValueError(f"Field '{key}' for task '{task_name}' must be an int")
    if value <= 0:
        raise ValueError(f"Field '{key}' for task '{task_name}' must be > 0")
    return value


def _build_tasks(config: dict) -> tuple[list[TaskSpec], bool]:
    scheduler_config = config.get("scheduler", {})
    store_run_status = scheduler_config.get("store_run_status", True)

    sync_config = config.get("sync", {})
    tasks: list[TaskSpec] = []

    google_cfg = sync_config.get("google_calendar", {})
    if google_cfg.get("enabled", False):
        interval = _get_required_int(google_cfg, "interval_seconds", "google_calendar")
        calendar_id = google_cfg.get("calendar_id", "primary")
        tasks.append(
            TaskSpec(
                name="google_calendar",
                interval_seconds=interval,
                handler=sync_google_calendar,
                kwargs={"calendar_id": calendar_id},
            )
        )

    spotify_cfg = sync_config.get("spotify", {})
    if spotify_cfg.get("enabled", False):
        interval = _get_required_int(spotify_cfg, "interval_seconds", "spotify")
        tasks.append(
            TaskSpec(
                name="spotify",
                interval_seconds=interval,
                handler=sync_spotify,
                kwargs={},
            )
        )

    oura_cfg = sync_config.get("oura", {})
    if oura_cfg.get("enabled", False):
        interval = _get_required_int(oura_cfg, "interval_seconds", "oura")
        lookback_days = oura_cfg.get("lookback_days", 7)
        data_types = oura_cfg.get("data_types")
        tasks.append(
            TaskSpec(
                name="oura",
                interval_seconds=interval,
                handler=sync_oura,
                kwargs={"lookback_days": lookback_days, "data_types": data_types},
            )
        )
    elif "oura" not in sync_config:
        oura_heartrate_cfg = sync_config.get("oura_heartrate", {})
        oura_full_cfg = sync_config.get("oura_full", {})
        if oura_heartrate_cfg.get("enabled", False) or oura_full_cfg.get("enabled", False):
            interval = None
            lookback_days = 7
            data_types: list[str] = []

            if oura_heartrate_cfg.get("enabled", False):
                interval = _get_required_int(
                    oura_heartrate_cfg, "interval_seconds", "oura_heartrate"
                )
                lookback_days = oura_heartrate_cfg.get("lookback_days", lookback_days)
                data_types.append("heartrate")

            if oura_full_cfg.get("enabled", False):
                interval = _get_required_int(oura_full_cfg, "interval_seconds", "oura_full")
                lookback_days = oura_full_cfg.get("lookback_days", lookback_days)
                data_types.extend(oura_full_cfg.get("data_types") or DEFAULT_DATA_TYPES)

            tasks.append(
                TaskSpec(
                    name="oura",
                    interval_seconds=interval or settings.oura_sync_interval_minutes * 60,
                    handler=sync_oura,
                    kwargs={"lookback_days": lookback_days, "data_types": data_types or None},
                )
            )

    return tasks, bool(store_run_status)


async def _update_run_status(
    task_name: str,
    status: str,
    started_at: str,
    finished_at: str | None,
    error: str | None,
) -> None:
    from surrealdb import AsyncSurreal

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin({"username": settings.surrealdb_user, "password": settings.surrealdb_pass})
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        record_id = f"sync_runs:{task_name}"
        payload = {
            "task": task_name,
            "last_started_at": started_at,
            "last_finished_at": finished_at,
            "last_status": status,
            "last_error": error,
        }
        await db.upsert(record_id, payload)
    finally:
        await db.close()


async def _safe_update_run_status(
    task_name: str,
    status: str,
    started_at: str,
    finished_at: str | None,
    error: str | None,
) -> None:
    try:
        await _update_run_status(task_name, status, started_at, finished_at, error)
    except Exception:
        logfire.exception("Failed to update sync run status", task=task_name)


async def _run_task_loop(task: TaskSpec, store_run_status: bool) -> None:
    while True:
        started_at = datetime.now(UTC).isoformat() + "Z"
        finished_at = None
        error = None
        status = "running"

        if store_run_status:
            await _safe_update_run_status(task.name, status, started_at, finished_at, error)

        with logfire.span("sync_run", task=task.name):
            try:
                await task.handler(**task.kwargs)
                status = "success"
            except Exception as exc:
                status = "error"
                error = str(exc)
                logfire.exception("Sync task failed", task=task.name)
            finally:
                finished_at = datetime.now(UTC).isoformat() + "Z"
                if store_run_status:
                    await _safe_update_run_status(task.name, status, started_at, finished_at, error)

        await asyncio.sleep(task.interval_seconds)


async def main(config_path: Path | None = None) -> None:
    configure_logfire()

    path = config_path or settings.config_toml_path
    config = _load_config(path)
    tasks, store_run_status = _build_tasks(config)

    if not tasks:
        raise RuntimeError("No enabled sync tasks found in config")

    logfire.info("Scheduler starting", config_path=str(path), task_count=len(tasks))

    await asyncio.gather(
        *[asyncio.create_task(_run_task_loop(task, store_run_status)) for task in tasks]
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Glider sync scheduler")
    parser.add_argument("--config", type=Path, default=None)
    return parser.parse_args()


def run() -> None:
    args = _parse_args()
    asyncio.run(main(config_path=args.config))


if __name__ == "__main__":
    run()
