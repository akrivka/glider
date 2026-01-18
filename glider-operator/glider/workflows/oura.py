"""Oura Ring heart rate sync workflow and activities."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from temporalio import activity, workflow


@dataclass
class OuraSyncInput:
    """Input for the sync workflow."""

    # Number of days to look back for initial sync
    lookback_days: int = 7


@dataclass
class OuraSyncResult:
    """Result of a sync cycle."""

    samples_fetched: int
    samples_stored: int
    sync_start: str
    sync_end: str


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
async def load_oura_sync_state() -> dict | None:
    """Load the last sync state from DB."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    activity.logger.info("Loading Oura sync state")

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin({"username": settings.surrealdb_user, "password": settings.surrealdb_pass})
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        result = await db.select("oura_sync_state:heartrate")

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
    from surrealdb import AsyncSurreal

    from glider.config import settings

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin({"username": settings.surrealdb_user, "password": settings.surrealdb_pass})
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        await db.upsert("oura_sync_state:heartrate", state)
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
            # Sample format from Oura: {"bpm": 72, "source": "awake", "timestamp": "2024-01-15T10:30:00+00:00"}
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
