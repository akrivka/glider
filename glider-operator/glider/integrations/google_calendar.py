"""Google Calendar integration client."""

from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


class GoogleCalendarClient:
    """Client for interacting with Google Calendar API."""

    def __init__(self, client_secret_path: Path, tokens_path: Path) -> None:
        self.client_secret_path = client_secret_path
        self.tokens_path = tokens_path
        self._service = None

    def _load_credentials(self) -> Credentials | None:
        """Load credentials from tokens.json, refresh if expired."""
        if not self.tokens_path.exists():
            return None

        creds = Credentials.from_authorized_user_file(str(self.tokens_path), SCOPES)

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self._save_credentials(creds)

        return creds

    def _save_credentials(self, creds: Credentials) -> None:
        """Save credentials to tokens.json."""
        self.tokens_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.tokens_path, "w") as f:
            f.write(creds.to_json())

    def is_authenticated(self) -> bool:
        """Check if valid credentials exist."""
        creds = self._load_credentials()
        return creds is not None and creds.valid

    def get_service(self):
        """Build and return the Calendar API service."""
        if self._service is not None:
            return self._service

        creds = self._load_credentials()
        if not creds or not creds.valid:
            raise RuntimeError(
                "No valid credentials. Run 'python -m glider.integrations.google_auth_setup' first."
            )

        self._service = build("calendar", "v3", credentials=creds)
        return self._service

    def fetch_events(
        self,
        calendar_id: str = "primary",
        sync_token: str | None = None,
        time_min: datetime | None = None,
        show_deleted: bool = True,
        *,
        _retried: bool = False,
    ) -> tuple[list[dict], str | None]:
        """
        Fetch events from Google Calendar.

        Args:
            calendar_id: Calendar ID to fetch from (default: "primary")
            sync_token: Token for incremental sync (from previous fetch)
            time_min: Minimum time bound for events (only for initial sync)
            show_deleted: Include deleted events (returns status="cancelled")
            _retried: Internal flag to prevent infinite retry loops.

        Returns:
            Tuple of (events list, next sync token)
        """
        service = self.get_service()
        all_events = []
        page_token = None

        while True:
            request_params = {
                "calendarId": calendar_id,
                "singleEvents": True,
                "orderBy": "startTime",
                "showDeleted": show_deleted,
            }

            if sync_token:
                request_params["syncToken"] = sync_token
            else:
                # Only use time_min for initial sync
                if time_min:
                    # Format as RFC3339 for Google Calendar API
                    request_params["timeMin"] = time_min.strftime("%Y-%m-%dT%H:%M:%SZ")

            if page_token:
                request_params["pageToken"] = page_token

            try:
                result = service.events().list(**request_params).execute()
            except Exception as e:
                # If sync token is invalid, clear it and do a full sync (but only once)
                if "Sync token" in str(e) and sync_token and not _retried:
                    return self.fetch_events(
                        calendar_id=calendar_id, time_min=time_min, _retried=True
                    )
                raise

            events = result.get("items", [])
            all_events.extend(events)

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        next_sync_token = result.get("nextSyncToken")
        return all_events, next_sync_token

    def get_calendars(self) -> list[dict]:
        """Get list of calendars the user has access to."""
        service = self.get_service()
        result = service.calendarList().list().execute()
        return result.get("items", [])
