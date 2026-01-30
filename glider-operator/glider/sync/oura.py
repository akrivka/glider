"""Oura sync tasks."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

import logfire

from glider.config import settings
from glider.integrations.oura import OuraClient
from glider.logging_setup import configure_logfire


class OuraDataType(str, Enum):
    """Oura data types that can be synced."""

    HEARTRATE = "heartrate"
    DAILY_STRESS = "daily_stress"
    DAILY_ACTIVITY = "daily_activity"
    DAILY_READINESS = "daily_readiness"
    DAILY_SLEEP = "daily_sleep"
    DAILY_SPO2 = "daily_spo2"
    SLEEP = "sleep"
    SESSION = "session"
    WORKOUT = "workout"


DEFAULT_DATA_TYPES = [
    OuraDataType.HEARTRATE.value,
    OuraDataType.DAILY_STRESS.value,
    OuraDataType.DAILY_ACTIVITY.value,
    OuraDataType.DAILY_READINESS.value,
    OuraDataType.DAILY_SLEEP.value,
    OuraDataType.DAILY_SPO2.value,
    OuraDataType.SLEEP.value,
    OuraDataType.SESSION.value,
    OuraDataType.WORKOUT.value,
]

HEARTRATE_MIN_WINDOW_HOURS = 24


@dataclass
class OuraSyncInput:
    """Input for the sync workflow."""

    # Number of days to look back for initial sync
    lookback_days: int = 7
    # Data types to sync (empty = all)
    data_types: list[str] = field(default_factory=list)


@dataclass
class OuraSyncResult:
    """Result of a sync cycle."""

    samples_fetched: int
    samples_stored: int
    sync_start: str
    sync_end: str


@dataclass
class OuraSyncSummary:
    """Result of a sync cycle across all data types."""

    results: dict[str, OuraSyncResult] = field(default_factory=dict)
    sync_start: str = ""
    sync_end: str = ""


def _get_oura_client() -> OuraClient:
    return OuraClient(
        client_id=settings.oura_client_id,
        client_secret=settings.oura_client_secret,
        tokens_path=settings.oura_tokens_path,
    )


async def fetch_oura_heartrate(start_datetime: str, end_datetime: str) -> list[dict]:
    """Fetch heart rate data from Oura API."""
    logfire.info(
        "Fetching Oura heartrate from {start_datetime} to {end_datetime}",
        start_datetime=start_datetime,
        end_datetime=end_datetime,
    )

    client = _get_oura_client()

    start_dt = datetime.fromisoformat(start_datetime.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end_datetime.replace("Z", "+00:00"))

    return client.get_heartrate(start_datetime=start_dt, end_datetime=end_dt)


async def fetch_oura_daily_data(data_type: str, start_date: str, end_date: str) -> list[dict]:
    """Fetch daily data from Oura API for a specific data type."""
    logfire.info(
        "Fetching Oura {data_type} from {start_date} to {end_date}",
        data_type=data_type,
        start_date=start_date,
        end_date=end_date,
    )

    client = _get_oura_client()

    start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

    method_map = {
        OuraDataType.DAILY_STRESS.value: client.get_daily_stress,
        OuraDataType.DAILY_ACTIVITY.value: client.get_daily_activity,
        OuraDataType.DAILY_READINESS.value: client.get_daily_readiness,
        OuraDataType.DAILY_SLEEP.value: client.get_daily_sleep,
        OuraDataType.DAILY_SPO2.value: client.get_daily_spo2,
        OuraDataType.SLEEP.value: client.get_sleep,
        OuraDataType.SESSION.value: client.get_sessions,
        OuraDataType.WORKOUT.value: client.get_workouts,
    }

    fetch_method = method_map.get(data_type)
    if not fetch_method:
        raise ValueError(f"Unknown data type: {data_type}")

    return fetch_method(start_date=start_dt, end_date=end_dt)


async def load_oura_sync_state_for_type(data_type: str) -> dict | None:
    """Load the last sync state from DB for a specific data type."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    logfire.info("Loading Oura sync state for {data_type}", data_type=data_type)

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin({"username": settings.surrealdb_user, "password": settings.surrealdb_pass})
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        result = await db.select(f"oura_sync_state:{data_type}")

        if isinstance(result, list) and len(result) > 0:
            result = result[0]

        if isinstance(result, dict):
            # Rebuild dict without the 'id' field to avoid type issues
            return {k: v for k, v in result.items() if k != "id"}
        return None
    finally:
        await db.close()


async def save_oura_sync_state_for_type(data_type: str, state: dict) -> None:
    """Save sync state to DB for a specific data type."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin({"username": settings.surrealdb_user, "password": settings.surrealdb_pass})
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        await db.upsert(f"oura_sync_state:{data_type}", state)
    finally:
        await db.close()


async def store_heartrate_samples(samples: list[dict]) -> int:
    """Store heart rate samples in SurrealDB."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    if not samples:
        return 0

    logfire.info("Storing {sample_count} heartrate samples", sample_count=len(samples))

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin({"username": settings.surrealdb_user, "password": settings.surrealdb_pass})
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        stored_count = 0
        now = datetime.now(UTC).isoformat() + "Z"

        for sample in samples:
            # Sample: {"bpm": 72, "source": "awake", "timestamp": "2024-01-15T10:30:00+00:00"}
            timestamp = sample.get("timestamp", "")
            bpm = sample.get("bpm")
            source = sample.get("source", "unknown")

            if not timestamp or bpm is None:
                continue

            # Create unique ID from timestamp
            # Parse timestamp and convert to milliseconds
            try:
                # Handle various timestamp formats
                ts_clean = timestamp.replace("Z", "+00:00")
                dt = datetime.fromisoformat(ts_clean)
                timestamp_ms = int(dt.timestamp() * 1000)
            except ValueError:
                logfire.warning("Invalid timestamp: {timestamp}", timestamp=timestamp)
                continue

            record_id = f"oura_heartrate:{timestamp_ms}"

            record = {
                "timestamp": timestamp,
                "bpm": bpm,
                "source": source,
                "_synced_at": now,
            }

            await db.upsert(record_id, record)
            stored_count += 1

        logfire.info("Stored {stored_count} heartrate samples", stored_count=stored_count)
        return stored_count
    finally:
        await db.close()


async def store_oura_daily_data(data_type: str, records: list[dict]) -> int:
    """Store daily Oura data in SurrealDB."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    if not records:
        return 0

    logfire.info(
        "Storing {record_count} {data_type} records",
        record_count=len(records),
        data_type=data_type,
    )

    # Map data type to table name
    table_map = {
        OuraDataType.DAILY_STRESS.value: "oura_daily_stress",
        OuraDataType.DAILY_ACTIVITY.value: "oura_daily_activity",
        OuraDataType.DAILY_READINESS.value: "oura_daily_readiness",
        OuraDataType.DAILY_SLEEP.value: "oura_daily_sleep",
        OuraDataType.DAILY_SPO2.value: "oura_daily_spo2",
        OuraDataType.SLEEP.value: "oura_sleep",
        OuraDataType.SESSION.value: "oura_session",
        OuraDataType.WORKOUT.value: "oura_workout",
    }

    table_name = table_map.get(data_type)
    if not table_name:
        raise ValueError(f"Unknown data type: {data_type}")

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin({"username": settings.surrealdb_user, "password": settings.surrealdb_pass})
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        stored_count = 0
        now = datetime.now(UTC).isoformat() + "Z"

        for record in records:
            # Use day or id as unique identifier
            day = record.get("day", "")
            record_id_suffix = record.get("id", day)

            if not record_id_suffix:
                continue

            # Clean the ID (Oura IDs have format like "abc123-def456")
            clean_id = record_id_suffix.replace("-", "_")
            record_id = f"{table_name}:{clean_id}"

            # Add sync timestamp and store the full record
            record_data = {**record, "_synced_at": now}
            # Remove the original 'id' field to avoid conflicts
            record_data.pop("id", None)

            await db.upsert(record_id, record_data)
            stored_count += 1

        logfire.info(
            "Stored {stored_count} {data_type} records",
            stored_count=stored_count,
            data_type=data_type,
        )
        return stored_count
    finally:
        await db.close()


def _normalize_data_types(data_types: list[str] | None) -> list[str]:
    types = data_types or []
    if not types:
        return DEFAULT_DATA_TYPES
    return [item.strip() for item in types if item.strip()]


def _resolve_heartrate_window(
    sync_state: dict | None,
    now: datetime,
    lookback_days: int,
    force_lookback: bool,
) -> tuple[str, str]:
    # Always pull a generous rolling window, and go further back if we're behind.
    start_datetime = now - timedelta(hours=HEARTRATE_MIN_WINDOW_HOURS)
    if lookback_days > 1:
        start_datetime = min(start_datetime, now - timedelta(days=lookback_days))

    if not force_lookback and sync_state and sync_state.get("last_sync_end"):
        last_sync = sync_state["last_sync_end"]
        try:
            last_sync_clean = last_sync.replace("Z", "+00:00")
            last_sync_dt = datetime.fromisoformat(last_sync_clean)
            start_datetime = min(start_datetime, last_sync_dt - timedelta(minutes=5))
        except ValueError:
            pass

    return start_datetime.isoformat(), now.isoformat()


def _resolve_daily_window(
    sync_state: dict | None,
    now: datetime,
    lookback_days: int,
    force_lookback: bool,
) -> tuple[str, str]:
    end_str = now.strftime("%Y-%m-%d")
    start_str = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    if not force_lookback and sync_state and sync_state.get("last_sync_end"):
        last_sync = sync_state["last_sync_end"]
        try:
            last_sync_clean = last_sync.replace("Z", "+00:00")
            last_sync_dt = datetime.fromisoformat(last_sync_clean)
            overlap_start = last_sync_dt - timedelta(days=1)
            start_str = overlap_start.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return start_str, end_str


async def sync_oura(
    lookback_days: int = 7,
    data_types: list[str] | None = None,
    force_lookback: bool = False,
) -> OuraSyncSummary:
    logfire.info("Starting Oura sync")

    types = _normalize_data_types(data_types)
    now = datetime.now(UTC)
    results: dict[str, OuraSyncResult] = {}

    with logfire.span(
        "sync_oura",
        lookback_days=lookback_days,
        types=types,
        force_lookback=force_lookback,
    ):
        for data_type in types:
            try:
                with logfire.span("sync_oura_type", data_type=data_type):
                    sync_state = await load_oura_sync_state_for_type(data_type)

                    if data_type == OuraDataType.HEARTRATE.value:
                        start_str, end_str = _resolve_heartrate_window(
                            sync_state, now, lookback_days, force_lookback
                        )
                        samples = await fetch_oura_heartrate(start_str, end_str)
                        samples = samples if samples is not None else []
                        stored_count = await store_heartrate_samples(samples) if samples else 0
                        await save_oura_sync_state_for_type(
                            data_type,
                            {
                                "last_sync_start": start_str,
                                "last_sync_end": end_str,
                                "last_sync_at": now.isoformat(),
                                "samples_fetched": len(samples),
                                "samples_stored": stored_count,
                            },
                        )
                        results[data_type] = OuraSyncResult(
                            samples_fetched=len(samples),
                            samples_stored=stored_count,
                            sync_start=start_str,
                            sync_end=end_str,
                        )
                    else:
                        start_str, end_str = _resolve_daily_window(
                            sync_state, now, lookback_days, force_lookback
                        )
                        records = await fetch_oura_daily_data(data_type, start_str, end_str)
                        records = records if records is not None else []
                        stored_count = (
                            await store_oura_daily_data(data_type, records) if records else 0
                        )
                        await save_oura_sync_state_for_type(
                            data_type,
                            {
                                "last_sync_start": start_str,
                                "last_sync_end": end_str,
                                "last_sync_at": now.isoformat(),
                                "records_fetched": len(records),
                                "records_stored": stored_count,
                            },
                        )
                        results[data_type] = OuraSyncResult(
                            samples_fetched=len(records),
                            samples_stored=stored_count,
                            sync_start=start_str,
                            sync_end=end_str,
                        )
            except Exception as exc:
                logfire.error("Failed to sync {data_type}: {error}", data_type=data_type, error=exc)
                logfire.exception("Oura sync failed", data_type=data_type)

    logfire.info("Oura sync complete", types_synced=len(results))

    return OuraSyncSummary(
        results=results,
        sync_start=now.isoformat(),
        sync_end=now.isoformat(),
    )


def _parse_data_types(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    configure_logfire()
    parser = argparse.ArgumentParser(description="Sync Oura data")
    parser.add_argument("--mode", choices=["heartrate", "full"], default="full")
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--data-types", default="")
    parser.add_argument("--force-lookback", action="store_true")
    args = parser.parse_args()

    data_types = _parse_data_types(args.data_types)
    if args.mode == "heartrate" and not data_types:
        data_types = [OuraDataType.HEARTRATE.value]

    asyncio.run(
        sync_oura(
            lookback_days=args.lookback_days,
            data_types=data_types or None,
            force_lookback=args.force_lookback,
        )
    )


if __name__ == "__main__":
    main()
