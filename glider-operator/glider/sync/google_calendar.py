"""Google Calendar sync task."""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import logfire

from glider.logging_setup import configure_logfire, configure_logging

logger = logging.getLogger(__name__)


@dataclass
class CalendarSyncResult:
    events_synced: int
    sync_token: str | None


async def fetch_google_calendar_events(calendar_id: str) -> tuple[list[dict], str | None]:
    """Fetch events from Google Calendar."""
    from glider.config import settings
    from glider.integrations.google_calendar import GoogleCalendarClient

    logger.info("Fetching events from calendar: %s", calendar_id)

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

    logger.info("Fetched %s events", len(events))
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


async def store_calendar_events(events: list[dict], calendar_id: str) -> int:
    """Store calendar events in SurrealDB."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    if not events:
        logger.info("No events to store")
        return 0

    logger.info("Storing %s events in SurrealDB", len(events))

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
                logger.info("Deleted cancelled event: %s", google_id)
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

        logger.info("Stored %s events", stored_count)
        return stored_count
    finally:
        await db.close()


async def save_sync_state(calendar_id: str, sync_token: str | None) -> None:
    """Save the sync state for incremental updates."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    logger.info("Saving sync state for calendar: %s", calendar_id)

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
        logger.info("Sync state saved")
    finally:
        await db.close()


async def sync_google_calendar(calendar_id: str = "primary") -> CalendarSyncResult:
    with logfire.span("sync_google_calendar", calendar_id=calendar_id):
        events, next_sync_token = await fetch_google_calendar_events(calendar_id)
        events_synced = await store_calendar_events(events, calendar_id)
        await save_sync_state(calendar_id, next_sync_token)
        logfire.info("Google Calendar sync complete", events_synced=events_synced)
        return CalendarSyncResult(events_synced=events_synced, sync_token=next_sync_token)


def main() -> None:
    configure_logging()
    configure_logfire()
    parser = argparse.ArgumentParser(description="Sync Google Calendar to SurrealDB")
    parser.add_argument("--calendar-id", default="primary")
    args = parser.parse_args()

    asyncio.run(sync_google_calendar(calendar_id=args.calendar_id))


if __name__ == "__main__":
    main()
