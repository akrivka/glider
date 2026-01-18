"""Spotify listening tracking workflow and activities."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from temporalio import activity, workflow

# Debounce configuration
DEBOUNCE_MIN_LISTEN_SECONDS = 30
DEBOUNCE_MIN_PERCENTAGE = 20
CONSECUTIVE_POLLS_THRESHOLD = 2


@dataclass
class SpotifyPollInput:
    """Input for the polling workflow."""

    pass


@dataclass
class SpotifyPollResult:
    """Result of a poll cycle."""

    track_id: str | None
    track_name: str | None
    is_playing: bool
    recorded: bool


@dataclass
class TrackingState:
    """Current tracking state."""

    current_track_id: str | None = None
    track_started_at: str | None = None
    first_seen_progress_ms: int = 0
    last_seen_progress_ms: int = 0
    last_poll_at: str = ""
    is_playing: bool = False
    consecutive_playing_polls: int = 0
    recorded: bool = False
    track_info: dict = field(default_factory=dict)


# --- Helper Functions ---


def meets_debounce_criteria(state: TrackingState, duration_ms: int) -> bool:
    """Check if current tracking state meets recording criteria."""
    if state.consecutive_playing_polls < CONSECUTIVE_POLLS_THRESHOLD:
        return False

    listen_duration_ms = state.last_seen_progress_ms - state.first_seen_progress_ms
    listen_duration_seconds = listen_duration_ms / 1000
    percentage = (listen_duration_ms / duration_ms) * 100 if duration_ms > 0 else 0

    return listen_duration_seconds >= DEBOUNCE_MIN_LISTEN_SECONDS or percentage >= DEBOUNCE_MIN_PERCENTAGE


def _extract_track_info(item: dict) -> dict:
    """Extract relevant track info from Spotify item."""
    return {
        "spotify_track_id": item.get("id"),
        "track_name": item.get("name"),
        "artist_names": [a.get("name") for a in item.get("artists", [])],
        "artist_ids": [a.get("id") for a in item.get("artists", [])],
        "album_name": item.get("album", {}).get("name"),
        "album_id": item.get("album", {}).get("id"),
        "duration_ms": item.get("duration_ms", 0),
        "explicit": item.get("explicit", False),
        "popularity": item.get("popularity", 0),
        "_raw": item,
    }


def _build_listening_event(state: TrackingState) -> dict:
    """Build a listening event dict from tracking state."""
    info = state.track_info
    duration_ms = info.get("duration_ms", 0)
    progress_reached = state.last_seen_progress_ms - state.first_seen_progress_ms

    return {
        "spotify_track_id": info.get("spotify_track_id"),
        "track_name": info.get("track_name"),
        "artist_names": info.get("artist_names", []),
        "artist_ids": info.get("artist_ids", []),
        "album_name": info.get("album_name"),
        "album_id": info.get("album_id"),
        "duration_ms": duration_ms,
        "listened_at": state.track_started_at,
        "progress_reached_ms": progress_reached,
        "percentage_listened": (progress_reached / duration_ms * 100) if duration_ms else 0,
        "explicit": info.get("explicit", False),
        "popularity": info.get("popularity", 0),
        "_raw": info.get("_raw", {}),
    }


def _state_to_dict(state: TrackingState) -> dict:
    """Convert TrackingState to dict for DB storage."""
    return {
        "current_track_id": state.current_track_id,
        "track_started_at": state.track_started_at,
        "first_seen_progress_ms": state.first_seen_progress_ms,
        "last_seen_progress_ms": state.last_seen_progress_ms,
        "last_poll_at": state.last_poll_at,
        "is_playing": state.is_playing,
        "consecutive_playing_polls": state.consecutive_playing_polls,
        "recorded": state.recorded,
        "track_info": state.track_info,
    }


def _dict_to_state(data: dict | None) -> TrackingState:
    """Convert dict from DB to TrackingState."""
    if not data:
        return TrackingState()
    return TrackingState(
        current_track_id=data.get("current_track_id"),
        track_started_at=data.get("track_started_at"),
        first_seen_progress_ms=data.get("first_seen_progress_ms", 0),
        last_seen_progress_ms=data.get("last_seen_progress_ms", 0),
        last_poll_at=data.get("last_poll_at", ""),
        is_playing=data.get("is_playing", False),
        consecutive_playing_polls=data.get("consecutive_playing_polls", 0),
        recorded=data.get("recorded", False),
        track_info=data.get("track_info", {}),
    )


# --- Activities ---


@activity.defn
async def poll_spotify_playback() -> dict | None:
    """Poll current Spotify playback state."""
    from glider.config import settings
    from glider.integrations.spotify import SpotifyClient

    activity.logger.info("Polling Spotify playback")

    client = SpotifyClient(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
        tokens_path=settings.spotify_tokens_path,
    )

    return client.get_currently_playing()


@activity.defn
async def load_tracking_state() -> dict | None:
    """Load current tracking state from DB."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    activity.logger.info("Loading tracking state")

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin({"username": settings.surrealdb_user, "password": settings.surrealdb_pass})
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        result = await db.select("spotify_tracking_state:current")

        # SurrealDB select returns a list, extract first element
        if isinstance(result, list) and len(result) > 0:
            result = result[0]

        if isinstance(result, dict):
            # Remove the 'id' field which contains a non-serializable RecordID
            # Rebuild dict without the 'id' field to avoid type issues
            return {k: v for k, v in result.items() if k != "id"}
        return None
    finally:
        await db.close()


@activity.defn
async def save_tracking_state(state: dict) -> None:
    """Save tracking state to DB."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin({"username": settings.surrealdb_user, "password": settings.surrealdb_pass})
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        await db.upsert("spotify_tracking_state:current", state)
    finally:
        await db.close()


@activity.defn
async def record_listening_event(event: dict) -> str:
    """Record a listening event in the DB."""
    from surrealdb import AsyncSurreal

    from glider.config import settings

    activity.logger.info(f"Recording listening event for: {event.get('track_name')}")

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin({"username": settings.surrealdb_user, "password": settings.surrealdb_pass})
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        # Create unique ID from timestamp and track ID
        listened_at = event.get("listened_at", "")
        if listened_at:
            # Handle various timezone formats (Z suffix or +00:00)
            listened_at_clean = listened_at.replace("Z", "").replace("+00:00", "")
            dt = datetime.fromisoformat(listened_at_clean).replace(tzinfo=UTC)
            timestamp_ms = int(dt.timestamp() * 1000)
        else:
            timestamp_ms = int(datetime.now(UTC).timestamp() * 1000)

        track_id = event.get("spotify_track_id", "unknown")[:12]
        record_id = f"spotify_listening_history:{timestamp_ms}_{track_id}"

        event["_synced_at"] = datetime.now(UTC).isoformat() + "Z"

        await db.upsert(record_id, event)
        activity.logger.info(f"Recorded event: {record_id}")
        return record_id
    finally:
        await db.close()


# --- Workflow ---


@workflow.defn
class SpotifyListeningWorkflow:
    """Workflow that polls Spotify and records listening events."""

    def __init__(self) -> None:
        self._status = "pending"
        self._last_track = None

    @workflow.run
    async def run(self, input: SpotifyPollInput) -> SpotifyPollResult:
        self._status = "polling"

        # Poll Spotify
        playback = await workflow.execute_activity(
            poll_spotify_playback,
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Load tracking state
        state_dict = await workflow.execute_activity(
            load_tracking_state,
            start_to_close_timeout=timedelta(seconds=30),
        )
        state = _dict_to_state(state_dict)

        now = workflow.now().isoformat()
        recorded = False
        current_track_id = None
        current_track_name = None
        is_playing = False

        if playback and playback.get("item"):
            item = playback["item"]
            current_track_id = item.get("id")
            current_track_name = item.get("name")
            is_playing = playback.get("is_playing", False)
            progress_ms = playback.get("progress_ms", 0)
            duration_ms = item.get("duration_ms", 0)

            self._last_track = current_track_name

            # Check if track changed or restarted
            track_restarted = state.current_track_id == current_track_id and progress_ms < state.last_seen_progress_ms - 5000
            track_changed = state.current_track_id != current_track_id

            if track_changed or track_restarted:
                # Record previous track if it meets criteria
                if (
                    state.current_track_id
                    and state.track_info
                    and not state.recorded
                    and meets_debounce_criteria(state, state.track_info.get("duration_ms", 0))
                ):
                    self._status = "recording"
                    event = _build_listening_event(state)
                    await workflow.execute_activity(
                        record_listening_event,
                        event,
                        start_to_close_timeout=timedelta(seconds=30),
                    )

                # Initialize new tracking
                state = TrackingState(
                    current_track_id=current_track_id,
                    track_started_at=now,
                    first_seen_progress_ms=progress_ms,
                    last_seen_progress_ms=progress_ms,
                    last_poll_at=now,
                    is_playing=is_playing,
                    consecutive_playing_polls=1 if is_playing else 0,
                    recorded=False,
                    track_info=_extract_track_info(item),
                )
            else:
                # Same track - update state
                state.last_poll_at = now
                state.last_seen_progress_ms = max(state.last_seen_progress_ms, progress_ms)
                state.is_playing = is_playing

                if is_playing:
                    state.consecutive_playing_polls += 1

                # Check if we should record
                if not state.recorded and meets_debounce_criteria(state, duration_ms):
                    self._status = "recording"
                    event = _build_listening_event(state)
                    await workflow.execute_activity(
                        record_listening_event,
                        event,
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                    state.recorded = True
                    recorded = True
        else:
            # Nothing playing - record previous if meets criteria
            if (
                state.current_track_id
                and state.track_info
                and not state.recorded
                and meets_debounce_criteria(state, state.track_info.get("duration_ms", 0))
            ):
                self._status = "recording"
                event = _build_listening_event(state)
                await workflow.execute_activity(
                    record_listening_event,
                    event,
                    start_to_close_timeout=timedelta(seconds=30),
                )

            # Clear state
            state = TrackingState(last_poll_at=now)

        # Save state
        self._status = "saving_state"
        await workflow.execute_activity(
            save_tracking_state,
            _state_to_dict(state),
            start_to_close_timeout=timedelta(seconds=30),
        )

        self._status = "completed"
        return SpotifyPollResult(
            track_id=current_track_id,
            track_name=current_track_name,
            is_playing=is_playing,
            recorded=recorded,
        )

    @workflow.query
    def get_status(self) -> dict:
        return {
            "status": self._status,
            "last_track": self._last_track,
        }
