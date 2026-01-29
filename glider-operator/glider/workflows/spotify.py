"""Spotify listening tracking workflow using recently-played endpoint.

This approach is based on Your Spotify's scrobbling architecture:
- Polls every 2 minutes instead of real-time
- Uses /me/player/recently-played with 2-hour lookback
- Deduplicates using ±30 second tolerance
- Much simpler and more reliable than real-time polling
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from temporalio import activity, workflow

# Lookback window: fetch tracks played in last 2 hours to handle gaps
LOOKBACK_HOURS = 2

# Duplicate detection: tracks within this window are considered the same play
DUPLICATE_TOLERANCE_SECONDS = 30


@dataclass
class SpotifyPollInput:
    """Input for the polling workflow."""

    pass


@dataclass
class SpotifyPollResult:
    """Result of a poll cycle."""

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


# --- Activities ---


@activity.defn
async def fetch_recently_played(after_timestamp_ms: int | None) -> list[dict]:
    """Fetch recently played tracks from Spotify API."""
    from glider.config import settings
    from glider.integrations.spotify import SpotifyClient

    activity.logger.info(f"Fetching recently played tracks (after={after_timestamp_ms})")

    client = SpotifyClient(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
        tokens_path=settings.spotify_tokens_path,
    )

    items = client.get_recently_played(after_timestamp_ms=after_timestamp_ms)
    return [_extract_track_info(item) for item in items]


@activity.defn
async def get_last_scrobble_timestamp() -> int | None:
    """Get the timestamp of the most recent scrobble from the database."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    activity.logger.info("Getting last scrobble timestamp")

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


@activity.defn
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


@activity.defn
async def record_listening_event(event: dict) -> str:
    """Record a listening event in the DB."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    activity.logger.info(f"Recording: {event.get('track_name')}")

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
        activity.logger.info(f"Recorded: {record_id}")
        return record_id
    finally:
        await db.close()


# --- Workflow ---


@workflow.defn
class SpotifyListeningWorkflow:
    """Workflow that fetches recently played tracks and records new scrobbles.

    This uses Spotify's /me/player/recently-played endpoint instead of
    real-time polling. Benefits:
    - Works even if the service was offline (catches up on history)
    - Provides exact played_at timestamps from Spotify
    - Much simpler logic - no state machine needed
    - Lower API usage (every 2 minutes vs every 7 seconds)
    """

    def __init__(self) -> None:
        self._status = "pending"
        self._tracks_recorded = 0

    @workflow.run
    async def run(self, input: SpotifyPollInput) -> SpotifyPollResult:
        self._status = "fetching_timestamp"

        # Get last scrobble timestamp to determine lookback
        last_timestamp = await workflow.execute_activity(
            get_last_scrobble_timestamp,
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Calculate lookback: use last timestamp minus 2 hours, or None for first run
        if last_timestamp:
            lookback_ms = last_timestamp - (LOOKBACK_HOURS * 60 * 60 * 1000)
        else:
            lookback_ms = None
            workflow.logger.info("First run - fetching all available history")

        # Fetch recently played tracks
        self._status = "fetching_tracks"
        tracks = await workflow.execute_activity(
            fetch_recently_played,
            lookback_ms,
            start_to_close_timeout=timedelta(seconds=60),
        )

        workflow.logger.info(f"Fetched {len(tracks)} tracks from Spotify")

        if not tracks:
            return SpotifyPollResult(
                tracks_fetched=0,
                tracks_recorded=0,
                latest_played_at=None,
            )

        # Process each track - check for duplicates and record new ones
        self._status = "recording"
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
            is_duplicate = await workflow.execute_activity(
                check_duplicate,
                args=[track_id, played_at],
                start_to_close_timeout=timedelta(seconds=30),
            )

            if is_duplicate:
                workflow.logger.debug(f"Skipping duplicate: {track.get('track_name')}")
                continue

            # Record new track
            await workflow.execute_activity(
                record_listening_event,
                track,
                start_to_close_timeout=timedelta(seconds=30),
            )
            recorded_count += 1
            self._tracks_recorded = recorded_count

        self._status = "completed"
        workflow.logger.info(f"Recorded {recorded_count} new tracks out of {len(tracks)} fetched")

        return SpotifyPollResult(
            tracks_fetched=len(tracks),
            tracks_recorded=recorded_count,
            latest_played_at=latest_played_at,
        )

    @workflow.query
    def get_status(self) -> dict:
        return {
            "status": self._status,
            "tracks_recorded": self._tracks_recorded,
        }
