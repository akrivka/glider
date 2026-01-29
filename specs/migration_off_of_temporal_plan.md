# Migration off Temporal plan

This plan specifies the minimal, concrete changes to replace Temporal with a single-process asyncio scheduler, while keeping per-sync executables and preserving current data semantics.

## Goals
- Remove Temporal from runtime and deployment (docker-compose + Nix module).
- Replace Temporal schedules with a simple asyncio scheduler and a `config.toml`.
- Keep each sync runnable directly for debugging/development.
- Preserve existing sync state logic in SurrealDB (Google token, Oura sync state, Spotify last scrobble lookup).
- Use Logfire for observability; optionally store minimal run status in DB for UI.

## Non-goals (for this iteration)
- Robust backfill for Spotify beyond current lookback.
- Advanced orchestration features (durable queues, distributed workers).
- High availability or multi-worker scaling.

## Proposed architecture
- A new module `glider/sync/` contains plain async sync functions (no Temporal decorators).
- A new entrypoint `glider/scheduler.py` runs tasks defined in `config.toml` using asyncio.
- Each sync function also has a direct CLI runnable module (e.g. `python -m glider.sync.spotify`).
- Logfire spans wrap each scheduled run; failures are logged.
- Optional: store a small “last run” record in SurrealDB for web UI monitoring.

## Config format (config.toml)
Location: `glider-operator/config.toml`.

Example:
```toml
[scheduler]
store_run_status = true

[sync.google_calendar]
enabled = true
interval_seconds = 1800
calendar_id = "primary"

[sync.spotify]
enabled = true
interval_seconds = 120

[sync.oura_heartrate]
enabled = true
interval_seconds = 1800
lookback_days = 7

[sync.oura_full]
enabled = false
interval_seconds = 86400
lookback_days = 7
```

Notes:
- `interval_seconds` is the only required scheduling field.
- Optional task-specific fields map to the existing input dataclasses.

## Scheduler behavior
- On startup, each enabled task runs once immediately.
- Each task then loops: `run -> sleep(interval) -> run`.
- Overlap is allowed (no hard lock); if desired later, a per-task lock can be added.
- Each run is wrapped in a Logfire span with tags: task name, status, duration, exception.
- Failures do not stop the scheduler; they are logged and the loop continues.

## Minimal DB status (optional)
Store a record per task to support a simple “last run” UI:
- Table: `sync_runs` (record id `sync_runs:{task_name}`)
- Fields: `task`, `last_started_at`, `last_finished_at`, `last_status`, `last_error`
- This is updated best-effort after each run.
- This does not replace existing task-specific sync state tables (`google_calendar_sync_state`, `oura_sync_state`); it is purely a UI/monitoring summary.

## File-by-file changes
### New / updated Python code
- New: `glider-operator/glider/sync/__init__.py`
- New: `glider-operator/glider/sync/google_calendar.py`
- New: `glider-operator/glider/sync/spotify.py`
- New: `glider-operator/glider/sync/oura.py`
- New: `glider-operator/glider/scheduler.py`
- Update: `glider-operator/glider/config.py`
  - Add config path or settings to load `config.toml`.

### Removal of Temporal-specific code
- Remove the old Temporal worker entrypoint (`glider-operator/glider/entrypoint_worker.py`).
- Deprecate Temporal schedule scripts:
  - `glider-operator/glider/scripts/create_calendar_schedule.py`
  - `glider-operator/glider/scripts/create_spotify_schedule.py`
  - `glider-operator/glider/scripts/create_oura_schedule.py`
- Update `glider-operator/pyproject.toml` to drop `temporalio`.
- Update `glider-operator/uv.lock` accordingly.

### Deployment / infra
- `docker-compose.yaml`:
  - Remove `temporal`, `postgresql`, and `temporal-ui` services.
  - Remove `TEMPORAL_*` env vars.
  - Worker service runs `python -m glider.scheduler`.
- `nix/module.nix`:
  - Remove Temporal options + Temporal systemd service.
  - Update `glider-worker` ExecStart to scheduler.
  - Remove `TEMPORAL_*` environment bindings.
- `glider-web/package.json`:
  - Remove `temporalio` dependency if unused in app code.

## Sync logic mapping (Temporal -> plain async)
- Google Calendar:
  - `fetch_google_calendar_events`, `store_calendar_events`, `save_sync_state` remain as async functions.
  - A new `async def sync_google_calendar(calendar_id: str)` wraps the sequence.
- Spotify:
  - Keep existing logic for `get_last_scrobble_timestamp`, `fetch_recently_played`, `check_duplicate`, `record_listening_event`.
  - A new `async def sync_spotify()` wraps the sequence.
- Oura:
  - `sync_oura_heartrate(lookback_days: int)` and `sync_oura_full(lookback_days: int, data_types: list[str])` wrap existing activity logic.

## CLI entrypoints
Each module exposes a `main()` for `python -m` usage:
- `python -m glider.sync.google_calendar --calendar-id primary`
- `python -m glider.sync.spotify`
- `python -m glider.sync.oura --mode heartrate --lookback-days 7`

## Migration steps (checkable)
- [ ] Introduce `glider/sync/` modules and refactor workflow logic to plain async functions.
- [ ] Add `scheduler.py` and `config.toml` parsing.
- [ ] Swap the worker entrypoint in Docker/Nix to the scheduler.
- [ ] Remove Temporal services and config from docker-compose and Nix.
- [ ] Remove Temporal deps from Python + web packages.
- [ ] Smoke test locally: run scheduler; verify DB updates and Logfire traces.

## Testing / verification checklist
- Manual: run each sync module directly and verify SurrealDB writes.
- Manual: run scheduler for 1–2 cycles and check Logfire spans.
- Manual: confirm docker-compose boots without Temporal services.
- Optional: add unit tests for config parsing and run status persistence.

## Open questions / decisions
- Confirm the minimal `sync_runs` status table for UI, or rely solely on Logfire.
