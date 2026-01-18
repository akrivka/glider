"""Google Calendar sync workflow and activities."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from temporalio import activity, workflow


@dataclass
class CalendarSyncInput:
    calendar_id: str = "primary"


@dataclass
class CalendarSyncResult:
    events_synced: int
    sync_token: str | None


@dataclass
class SyncState:
    calendar_id: str
    sync_token: str | None
    last_sync: str


@dataclass
class CalendarEvent:
    google_id: str
    calendar_id: str
    summary: str
    start: dict
    end: dict
    status: str
    html_link: str | None
    location: str | None
    description: str | None
    created: str | None
    updated: str | None
    raw: dict


# --- Activities ---


@activity.defn
async def fetch_google_calendar_events(calendar_id: str) -> tuple[list[dict], str | None]:
    """Fetch events from Google Calendar."""
    from glider.config import settings
    from glider.integrations.google_calendar import GoogleCalendarClient

    activity.logger.info(f"Fetching events from calendar: {calendar_id}")

    client = GoogleCalendarClient(
        client_secret_path=settings.google_client_secret_path,
        tokens_path=settings.google_tokens_path,
    )

    # Get sync state to do incremental sync if available
    sync_token = await _get_sync_token_from_db(calendar_id)

    # If no sync token, fetch events from the last 30 days
    time_min = None
    if not sync_token:
        time_min = datetime.now(UTC) - timedelta(days=30)

    events, next_sync_token = client.fetch_events(
        calendar_id=calendar_id,
        sync_token=sync_token,
        time_min=time_min,
    )

    activity.logger.info(f"Fetched {len(events)} events")
    return events, next_sync_token


async def _get_sync_token_from_db(calendar_id: str) -> str | None:
    """Helper to get sync token from SurrealDB."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin({"username": settings.surrealdb_user, "password": settings.surrealdb_pass})
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        record_id = f"google_calendar_sync_state:{calendar_id}"
        result = await db.select(record_id)

        if result and isinstance(result, dict):
            return result.get("sync_token")  # type: ignore[return-value]
        return None
    finally:
        await db.close()


@activity.defn
async def store_calendar_events(events: list[dict], calendar_id: str) -> int:
    """Store calendar events in SurrealDB."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    if not events:
        activity.logger.info("No events to store")
        return 0

    activity.logger.info(f"Storing {len(events)} events in SurrealDB")

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin({"username": settings.surrealdb_user, "password": settings.surrealdb_pass})
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        synced_at = datetime.now(UTC).isoformat() + "Z"
        stored_count = 0

        for event in events:
            google_id = event.get("id")
            if not google_id:
                continue

            # Handle cancelled events (deleted)
            if event.get("status") == "cancelled":
                record_id = f"google_calendar_events:{google_id}"
                await db.delete(record_id)
                activity.logger.info(f"Deleted cancelled event: {google_id}")
                continue

            event_data = {
                "google_id": google_id,
                "calendar_id": calendar_id,
                "summary": event.get("summary", ""),
                "start": event.get("start", {}),
                "end": event.get("end", {}),
                "status": event.get("status", ""),
                "html_link": event.get("htmlLink"),
                "location": event.get("location"),
                "description": event.get("description"),
                "created": event.get("created"),
                "updated": event.get("updated"),
                "_raw": event,
                "_synced_at": synced_at,
            }

            # Upsert using the Google event ID as record ID
            record_id = f"google_calendar_events:{google_id}"
            await db.upsert(record_id, event_data)
            stored_count += 1

        activity.logger.info(f"Stored {stored_count} events")
        return stored_count
    finally:
        await db.close()


@activity.defn
async def save_sync_state(calendar_id: str, sync_token: str | None) -> None:
    """Save the sync state for incremental updates."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    activity.logger.info(f"Saving sync state for calendar: {calendar_id}")

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin({"username": settings.surrealdb_user, "password": settings.surrealdb_pass})
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        record_id = f"google_calendar_sync_state:{calendar_id}"
        state_data = {
            "calendar_id": calendar_id,
            "sync_token": sync_token,
            "last_sync": datetime.now(UTC).isoformat() + "Z",
        }

        await db.upsert(record_id, state_data)
        activity.logger.info("Sync state saved")
    finally:
        await db.close()


# --- Workflow ---


@workflow.defn
class GoogleCalendarSyncWorkflow:
    """Workflow that syncs Google Calendar events to SurrealDB."""

    def __init__(self) -> None:
        self._status = "pending"
        self._events_synced = 0

    @workflow.run
    async def run(self, input: CalendarSyncInput) -> CalendarSyncResult:
        self._status = "fetching"

        # Fetch events from Google Calendar
        events, next_sync_token = await workflow.execute_activity(
            fetch_google_calendar_events,
            input.calendar_id,
            start_to_close_timeout=timedelta(minutes=5),
        )

        self._status = "storing"

        # Store events in SurrealDB
        events_synced_result = await workflow.execute_activity(
            store_calendar_events,
            args=[events, input.calendar_id],
            start_to_close_timeout=timedelta(minutes=5),
        )
        events_synced = events_synced_result if events_synced_result is not None else 0
        self._events_synced = events_synced

        self._status = "saving_state"

        # Save sync state for incremental updates
        await workflow.execute_activity(
            save_sync_state,
            args=[input.calendar_id, next_sync_token],
            start_to_close_timeout=timedelta(minutes=1),
        )

        self._status = "completed"

        return CalendarSyncResult(
            events_synced=events_synced,
            sync_token=next_sync_token,
        )

    @workflow.query
    def get_status(self) -> dict:
        return {
            "status": self._status,
            "events_synced": self._events_synced,
        }
