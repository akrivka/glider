"""Oura Ring sync workflow and activities for all data types."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

from temporalio import activity, workflow


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


# --- Activities ---


@activity.defn
async def fetch_oura_heartrate(start_datetime: str, end_datetime: str) -> list[dict]:
    """Fetch heart rate data from Oura API."""
    from glider.config import settings
    from glider.integrations.oura import OuraClient

    activity.logger.info(f"Fetching Oura heartrate from {start_datetime} to {end_datetime}")

    client = OuraClient(
        client_id=settings.oura_client_id,
        client_secret=settings.oura_client_secret,
        tokens_path=settings.oura_tokens_path,
    )

    start_dt = datetime.fromisoformat(start_datetime.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end_datetime.replace("Z", "+00:00"))

    return client.get_heartrate(start_datetime=start_dt, end_datetime=end_dt)


@activity.defn
async def fetch_oura_daily_data(data_type: str, start_date: str, end_date: str) -> list[dict]:
    """Fetch daily data from Oura API for a specific data type."""
    from glider.config import settings
    from glider.integrations.oura import OuraClient

    activity.logger.info(f"Fetching Oura {data_type} from {start_date} to {end_date}")

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


@activity.defn
async def load_oura_sync_state() -> dict | None:
    """Load the last sync state from DB."""
    return await load_oura_sync_state_for_type("heartrate")


@activity.defn
async def load_oura_sync_state_for_type(data_type: str) -> dict | None:
    """Load the last sync state from DB for a specific data type."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    activity.logger.info(f"Loading Oura sync state for {data_type}")

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


@activity.defn
async def save_oura_sync_state(state: dict) -> None:
    """Save sync state to DB."""
    await save_oura_sync_state_for_type("heartrate", state)


@activity.defn
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


@activity.defn
async def store_heartrate_samples(samples: list[dict]) -> int:
    """Store heart rate samples in SurrealDB."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    if not samples:
        return 0

    activity.logger.info(f"Storing {len(samples)} heartrate samples")

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
                activity.logger.warning(f"Invalid timestamp: {timestamp}")
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

        activity.logger.info(f"Stored {stored_count} heartrate samples")
        return stored_count
    finally:
        await db.close()


@activity.defn
async def store_oura_daily_data(data_type: str, records: list[dict]) -> int:
    """Store daily Oura data in SurrealDB."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    if not records:
        return 0

    activity.logger.info(f"Storing {len(records)} {data_type} records")

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

        activity.logger.info(f"Stored {stored_count} {data_type} records")
        return stored_count
    finally:
        await db.close()


# --- Workflow ---


@workflow.defn
class OuraHeartrateSyncWorkflow:
    """Workflow that syncs heart rate data from Oura."""

    def __init__(self) -> None:
        self._status = "pending"
        self._samples_count = 0

    @workflow.run
    async def run(self, input: OuraSyncInput) -> OuraSyncResult:
        self._status = "loading_state"

        # Load previous sync state
        sync_state = await workflow.execute_activity(
            load_oura_sync_state,
            start_to_close_timeout=timedelta(seconds=30),
        )

        now = workflow.now()
        end_datetime = now

        # Determine start datetime based on last sync or lookback period
        if sync_state and sync_state.get("last_sync_end"):
            # Continue from last sync, with a small overlap to catch any missed data
            last_sync = sync_state["last_sync_end"]
            try:
                last_sync_clean = last_sync.replace("Z", "+00:00")
                start_datetime = datetime.fromisoformat(last_sync_clean) - timedelta(minutes=5)
            except ValueError:
                start_datetime = now - timedelta(days=input.lookback_days)
        else:
            # First sync - look back N days
            start_datetime = now - timedelta(days=input.lookback_days)

        start_str = start_datetime.isoformat()
        end_str = end_datetime.isoformat()

        # Fetch heart rate data
        self._status = "fetching"
        samples_result = await workflow.execute_activity(
            fetch_oura_heartrate,
            args=[start_str, end_str],
            start_to_close_timeout=timedelta(seconds=120),
        )
        samples = samples_result if samples_result is not None else []

        self._samples_count = len(samples)

        # Store samples
        self._status = "storing"
        stored_count = 0
        if samples:
            stored_count_result = await workflow.execute_activity(
                store_heartrate_samples,
                samples,
                start_to_close_timeout=timedelta(seconds=120),
            )
            stored_count = stored_count_result if stored_count_result is not None else 0

        # Save sync state
        self._status = "saving_state"
        await workflow.execute_activity(
            save_oura_sync_state,
            {
                "last_sync_start": start_str,
                "last_sync_end": end_str,
                "last_sync_at": now.isoformat(),
                "samples_fetched": len(samples),
                "samples_stored": stored_count,
            },
            start_to_close_timeout=timedelta(seconds=30),
        )

        self._status = "completed"
        return OuraSyncResult(
            samples_fetched=len(samples),
            samples_stored=stored_count,
            sync_start=start_str,
            sync_end=end_str,
        )

    @workflow.query
    def get_status(self) -> dict:
        return {
            "status": self._status,
            "samples_count": self._samples_count,
        }


@workflow.defn
class OuraFullSyncWorkflow:
    """Workflow that syncs all data types from Oura."""

    def __init__(self) -> None:
        self._status = "pending"
        self._current_type = ""
        self._results: dict[str, OuraSyncResult] = {}

    @workflow.run
    async def run(self, input: OuraSyncInput) -> OuraFullSyncResult:
        self._status = "starting"

        now = workflow.now()
        end_date = now
        start_date = now - timedelta(days=input.lookback_days)

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # Determine which data types to sync
        data_types = input.data_types if input.data_types else [
            OuraDataType.DAILY_STRESS.value,
            OuraDataType.DAILY_ACTIVITY.value,
            OuraDataType.DAILY_READINESS.value,
            OuraDataType.DAILY_SLEEP.value,
            OuraDataType.DAILY_SPO2.value,
            OuraDataType.SLEEP.value,
            OuraDataType.SESSION.value,
            OuraDataType.WORKOUT.value,
        ]

        for data_type in data_types:
            self._current_type = data_type
            self._status = f"syncing_{data_type}"

            try:
                # Load sync state for this type
                sync_state = await workflow.execute_activity(
                    load_oura_sync_state_for_type,
                    data_type,
                    start_to_close_timeout=timedelta(seconds=30),
                )

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
                records = await workflow.execute_activity(
                    fetch_oura_daily_data,
                    args=[data_type, type_start_str, end_str],
                    start_to_close_timeout=timedelta(seconds=120),
                )
                records = records if records is not None else []

                # Store data
                stored_count = 0
                if records:
                    stored_result = await workflow.execute_activity(
                        store_oura_daily_data,
                        args=[data_type, records],
                        start_to_close_timeout=timedelta(seconds=120),
                    )
                    stored_count = stored_result if stored_result is not None else 0

                # Save sync state
                await workflow.execute_activity(
                    save_oura_sync_state_for_type,
                    args=[
                        data_type,
                        {
                            "last_sync_start": type_start_str,
                            "last_sync_end": end_str,
                            "last_sync_at": now.isoformat(),
                            "records_fetched": len(records),
                            "records_stored": stored_count,
                        },
                    ],
                    start_to_close_timeout=timedelta(seconds=30),
                )

                self._results[data_type] = OuraSyncResult(
                    samples_fetched=len(records),
                    samples_stored=stored_count,
                    sync_start=type_start_str,
                    sync_end=end_str,
                )

            except Exception as e:
                workflow.logger.error(f"Failed to sync {data_type}: {e}")
                # Continue with other types even if one fails

        self._status = "completed"
        return OuraFullSyncResult(
            results=self._results,
            sync_start=start_str,
            sync_end=end_str,
        )

    @workflow.query
    def get_status(self) -> dict:
        return {
            "status": self._status,
            "current_type": self._current_type,
            "results": {k: {"fetched": v.samples_fetched, "stored": v.samples_stored} for k, v in self._results.items()},
        }
