"""Oura sync tasks."""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

import logfire

from glider.logging_setup import configure_logfire, configure_logging

logger = logging.getLogger(__name__)


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
class OuraFullSyncResult:
    """Result of a full sync cycle across all data types."""

    results: dict[str, OuraSyncResult] = field(default_factory=dict)
    sync_start: str = ""
    sync_end: str = ""


async def fetch_oura_heartrate(start_datetime: str, end_datetime: str) -> list[dict]:
    """Fetch heart rate data from Oura API."""
    from glider.config import settings
    from glider.integrations.oura import OuraClient

    logger.info("Fetching Oura heartrate from %s to %s", start_datetime, end_datetime)

    client = OuraClient(
        client_id=settings.oura_client_id,
        client_secret=settings.oura_client_secret,
        tokens_path=settings.oura_tokens_path,
    )

    start_dt = datetime.fromisoformat(start_datetime.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end_datetime.replace("Z", "+00:00"))

    return client.get_heartrate(start_datetime=start_dt, end_datetime=end_dt)


async def fetch_oura_daily_data(data_type: str, start_date: str, end_date: str) -> list[dict]:
    """Fetch daily data from Oura API for a specific data type."""
    from glider.config import settings
    from glider.integrations.oura import OuraClient

    logger.info("Fetching Oura %s from %s to %s", data_type, start_date, end_date)

    client = OuraClient(
        client_id=settings.oura_client_id,
        client_secret=settings.oura_client_secret,
        tokens_path=settings.oura_tokens_path,
    )

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


async def load_oura_sync_state() -> dict | None:
    """Load the last sync state from DB."""
    return await load_oura_sync_state_for_type("heartrate")


async def load_oura_sync_state_for_type(data_type: str) -> dict | None:
    """Load the last sync state from DB for a specific data type."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    logger.info("Loading Oura sync state for %s", data_type)

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


async def save_oura_sync_state(state: dict) -> None:
    """Save sync state to DB."""
    await save_oura_sync_state_for_type("heartrate", state)


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

    logger.info("Storing %s heartrate samples", len(samples))

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
                logger.warning("Invalid timestamp: %s", timestamp)
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

        logger.info("Stored %s heartrate samples", stored_count)
        return stored_count
    finally:
        await db.close()


async def store_oura_daily_data(data_type: str, records: list[dict]) -> int:
    """Store daily Oura data in SurrealDB."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    if not records:
        return 0

    logger.info("Storing %s %s records", len(records), data_type)

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

        logger.info("Stored %s %s records", stored_count, data_type)
        return stored_count
    finally:
        await db.close()


async def sync_oura_heartrate(lookback_days: int = 7) -> OuraSyncResult:
    logger.info("Starting Oura heartrate sync")

    with logfire.span("sync_oura_heartrate", lookback_days=lookback_days):
        # Load previous sync state
        sync_state = await load_oura_sync_state()

        now = datetime.now(UTC)
        end_datetime = now

        # Determine start datetime based on last sync or lookback period
        if sync_state and sync_state.get("last_sync_end"):
            # Continue from last sync, with a small overlap to catch any missed data
            last_sync = sync_state["last_sync_end"]
            try:
                last_sync_clean = last_sync.replace("Z", "+00:00")
                start_datetime = datetime.fromisoformat(last_sync_clean) - timedelta(minutes=5)
            except ValueError:
                start_datetime = now - timedelta(days=lookback_days)
        else:
            # First sync - look back N days
            start_datetime = now - timedelta(days=lookback_days)

        start_str = start_datetime.isoformat()
        end_str = end_datetime.isoformat()

        # Fetch heart rate data
        samples = await fetch_oura_heartrate(start_str, end_str)
        samples = samples if samples is not None else []

        # Store samples
        stored_count = 0
        if samples:
            stored_count = await store_heartrate_samples(samples)

        # Save sync state
        await save_oura_sync_state(
            {
                "last_sync_start": start_str,
                "last_sync_end": end_str,
                "last_sync_at": now.isoformat(),
                "samples_fetched": len(samples),
                "samples_stored": stored_count,
            }
        )

        logfire.info(
            "Oura heartrate sync complete",
            samples_fetched=len(samples),
            samples_stored=stored_count,
        )

        return OuraSyncResult(
            samples_fetched=len(samples),
            samples_stored=stored_count,
            sync_start=start_str,
            sync_end=end_str,
        )


async def sync_oura_full(
    lookback_days: int = 7,
    data_types: list[str] | None = None,
) -> OuraFullSyncResult:
    logger.info("Starting Oura full sync")

    with logfire.span("sync_oura_full", lookback_days=lookback_days):
        now = datetime.now(UTC)
        end_date = now
        start_date = now - timedelta(days=lookback_days)

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # Determine which data types to sync
        types = (
            data_types
            if data_types
            else [
                OuraDataType.DAILY_STRESS.value,
                OuraDataType.DAILY_ACTIVITY.value,
                OuraDataType.DAILY_READINESS.value,
                OuraDataType.DAILY_SLEEP.value,
                OuraDataType.DAILY_SPO2.value,
                OuraDataType.SLEEP.value,
                OuraDataType.SESSION.value,
                OuraDataType.WORKOUT.value,
            ]
        )

        results: dict[str, OuraSyncResult] = {}

        for data_type in types:
            try:
                # Load sync state for this type
                sync_state = await load_oura_sync_state_for_type(data_type)

                # Determine start date based on last sync
                type_start_str = start_str
                if sync_state and sync_state.get("last_sync_end"):
                    last_sync = sync_state["last_sync_end"]
                    try:
                        # Go back 1 day for overlap
                        last_sync_clean = last_sync.replace("Z", "+00:00")
                        last_sync_dt = datetime.fromisoformat(last_sync_clean)
                        overlap_start = last_sync_dt - timedelta(days=1)
                        type_start_str = overlap_start.strftime("%Y-%m-%d")
                    except ValueError:
                        pass

                # Fetch data
                records = await fetch_oura_daily_data(data_type, type_start_str, end_str)
                records = records if records is not None else []

                # Store data
                stored_count = 0
                if records:
                    stored_count = await store_oura_daily_data(data_type, records)

                # Save sync state
                await save_oura_sync_state_for_type(
                    data_type,
                    {
                        "last_sync_start": type_start_str,
                        "last_sync_end": end_str,
                        "last_sync_at": now.isoformat(),
                        "records_fetched": len(records),
                        "records_stored": stored_count,
                    },
                )

                results[data_type] = OuraSyncResult(
                    samples_fetched=len(records),
                    samples_stored=stored_count,
                    sync_start=type_start_str,
                    sync_end=end_str,
                )

            except Exception as exc:
                logger.error("Failed to sync %s: %s", data_type, exc)
                # Continue with other types even if one fails

        logfire.info("Oura full sync complete", types_synced=len(results))

        return OuraFullSyncResult(
            results=results,
            sync_start=start_str,
            sync_end=end_str,
        )


def _parse_data_types(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    configure_logging()
    configure_logfire()
    parser = argparse.ArgumentParser(description="Sync Oura data")
    parser.add_argument("--mode", choices=["heartrate", "full"], default="heartrate")
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--data-types", default="")
    args = parser.parse_args()

    if args.mode == "heartrate":
        asyncio.run(sync_oura_heartrate(lookback_days=args.lookback_days))
    else:
        data_types = _parse_data_types(args.data_types)
        asyncio.run(
            sync_oura_full(
                lookback_days=args.lookback_days,
                data_types=data_types or None,
            )
        )


if __name__ == "__main__":
    main()
