"""Spotify listening tracking sync task."""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import logfire

from glider.logging_setup import configure_logfire, configure_logging

logger = logging.getLogger(__name__)

# Lookback window: fetch tracks played in last 2 hours to handle gaps
LOOKBACK_HOURS = 2

# Duplicate detection: tracks within this window are considered the same play
DUPLICATE_TOLERANCE_SECONDS = 30


@dataclass
class SpotifyPollResult:
    tracks_fetched: int
    tracks_recorded: int
    latest_played_at: str | None


def _extract_track_info(item: dict) -> dict:
    """Extract relevant track info from Spotify recently-played item."""
    track = item.get("track", {})
    played_at = item.get("played_at", "")

    return {
        "spotify_track_id": track.get("id"),
        "track_name": track.get("name"),
        "artist_names": [a.get("name") for a in track.get("artists", [])],
        "artist_ids": [a.get("id") for a in track.get("artists", [])],
        "album_name": track.get("album", {}).get("name"),
        "album_id": track.get("album", {}).get("id"),
        "duration_ms": track.get("duration_ms", 0),
        "explicit": track.get("explicit", False),
        "popularity": track.get("popularity", 0),
        "played_at": played_at,
        "_raw": track,
    }


async def fetch_recently_played(after_timestamp_ms: int | None) -> list[dict]:
    """Fetch recently played tracks from Spotify API."""
    from glider.config import settings
    from glider.integrations.spotify import SpotifyClient

    logger.info("Fetching recently played tracks (after=%s)", after_timestamp_ms)

    client = SpotifyClient(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
        tokens_path=settings.spotify_tokens_path,
    )

    items = client.get_recently_played(after_timestamp_ms=after_timestamp_ms)
    return [_extract_track_info(item) for item in items]


async def get_last_scrobble_timestamp() -> int | None:
    """Get the timestamp of the most recent scrobble from the database."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    logger.info("Getting last scrobble timestamp")

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin(
            {
                "username": settings.surrealdb_user,
                "password": settings.surrealdb_pass,
            }
        )
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        # Get the most recent scrobble
        result = await db.query(
            "SELECT played_at FROM spotify_listening_history ORDER BY played_at DESC LIMIT 1"
        )

        if result and result[0].get("result"):
            records = result[0]["result"]
            if records:
                played_at = records[0].get("played_at")
                if played_at:
                    # Parse ISO timestamp and convert to milliseconds
                    played_at_clean = played_at.replace("Z", "").replace("+00:00", "")
                    dt = datetime.fromisoformat(played_at_clean).replace(tzinfo=UTC)
                    return int(dt.timestamp() * 1000)

        return None
    finally:
        await db.close()


async def check_duplicate(track_id: str, played_at: str) -> bool:
    """Check if a track play already exists within the tolerance window."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin(
            {
                "username": settings.surrealdb_user,
                "password": settings.surrealdb_pass,
            }
        )
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        # Parse the played_at timestamp
        played_at_clean = played_at.replace("Z", "").replace("+00:00", "")
        dt = datetime.fromisoformat(played_at_clean).replace(tzinfo=UTC)

        # Calculate tolerance window
        before = (dt - timedelta(seconds=DUPLICATE_TOLERANCE_SECONDS)).isoformat() + "Z"
        after = (dt + timedelta(seconds=DUPLICATE_TOLERANCE_SECONDS)).isoformat() + "Z"

        # Check for existing record within tolerance window
        result = await db.query(
            "SELECT id FROM spotify_listening_history "
            "WHERE spotify_track_id = $track_id "
            "AND played_at >= $before AND played_at <= $after "
            "LIMIT 1",
            {"track_id": track_id, "before": before, "after": after},
        )

        if result and result[0].get("result"):
            return len(result[0]["result"]) > 0

        return False
    finally:
        await db.close()


async def record_listening_event(event: dict) -> str:
    """Record a listening event in the DB."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    logger.info("Recording: %s", event.get("track_name"))

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin(
            {
                "username": settings.surrealdb_user,
                "password": settings.surrealdb_pass,
            }
        )
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        # Create unique ID from timestamp and track ID
        played_at = event.get("played_at", "")
        if played_at:
            played_at_clean = played_at.replace("Z", "").replace("+00:00", "")
            dt = datetime.fromisoformat(played_at_clean).replace(tzinfo=UTC)
            timestamp_ms = int(dt.timestamp() * 1000)
        else:
            timestamp_ms = int(datetime.now(UTC).timestamp() * 1000)

        track_id = event.get("spotify_track_id", "unknown")[:12]
        record_id = f"spotify_listening_history:{timestamp_ms}_{track_id}"

        event["_synced_at"] = datetime.now(UTC).isoformat() + "Z"

        await db.upsert(record_id, event)
        logger.info("Recorded: %s", record_id)
        return record_id
    finally:
        await db.close()


async def sync_spotify() -> SpotifyPollResult:
    logger.info("Starting Spotify sync")

    with logfire.span("sync_spotify"):
        # Get last scrobble timestamp to determine lookback
        last_timestamp = await get_last_scrobble_timestamp()

        # Calculate lookback: use last timestamp minus 2 hours, or None for first run
        if last_timestamp:
            lookback_ms = last_timestamp - (LOOKBACK_HOURS * 60 * 60 * 1000)
        else:
            lookback_ms = None
            logger.info("First run - fetching all available history")

        # Fetch recently played tracks
        tracks = await fetch_recently_played(lookback_ms)

        logger.info("Fetched %s tracks from Spotify", len(tracks))

        if not tracks:
            logfire.info("Spotify sync complete", tracks_fetched=0, tracks_recorded=0)
            return SpotifyPollResult(
                tracks_fetched=0,
                tracks_recorded=0,
                latest_played_at=None,
            )

        # Process each track - check for duplicates and record new ones
        recorded_count = 0
        latest_played_at = None

        for track in tracks:
            track_id = track.get("spotify_track_id")
            played_at = track.get("played_at")

            if not track_id or not played_at:
                continue

            # Track the latest played_at for reporting
            if latest_played_at is None or played_at > latest_played_at:
                latest_played_at = played_at

            # Check for duplicates
            is_duplicate = await check_duplicate(track_id, played_at)

            if is_duplicate:
                logger.debug("Skipping duplicate: %s", track.get("track_name"))
                continue

            # Record new track
            await record_listening_event(track)
            recorded_count += 1

        logger.info(
            "Recorded %s new tracks out of %s fetched",
            recorded_count,
            len(tracks),
        )
        logfire.info(
            "Spotify sync complete",
            tracks_fetched=len(tracks),
            tracks_recorded=recorded_count,
            latest_played_at=latest_played_at,
        )

        return SpotifyPollResult(
            tracks_fetched=len(tracks),
            tracks_recorded=recorded_count,
            latest_played_at=latest_played_at,
        )


def main() -> None:
    configure_logging()
    configure_logfire()
    parser = argparse.ArgumentParser(description="Sync Spotify listening history")
    parser.parse_args()

    asyncio.run(sync_spotify())


if __name__ == "__main__":
    main()
