"""Spotify integration client."""

import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import logfire

SCOPES = ["user-read-recently-played"]
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"

# Proactive refresh buffer - refresh tokens 120 seconds before expiry
# This matches YourSpotify's approach for seamless background token renewal
TOKEN_REFRESH_BUFFER_SECONDS = 120


@dataclass
class SpotifyTokens:
    access_token: str
    refresh_token: str
    expires_at: float  # Unix timestamp


class SpotifyClient:
    """Client for interacting with Spotify API."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tokens_path: Path,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.tokens_path = tokens_path
        self._tokens: SpotifyTokens | None = None

    def _load_tokens(self) -> SpotifyTokens | None:
        """Load tokens from file."""
        if not self.tokens_path.exists():
            return None

        with open(self.tokens_path) as f:
            data = json.load(f)

        return SpotifyTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"],
        )

    def _save_tokens(self, tokens: SpotifyTokens) -> None:
        """Save tokens to file."""
        self.tokens_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.tokens_path, "w") as f:
            json.dump(
                {
                    "access_token": tokens.access_token,
                    "refresh_token": tokens.refresh_token,
                    "expires_at": tokens.expires_at,
                },
                f,
            )

    def _refresh_access_token(self) -> None:
        """Refresh the access token using refresh token.

        This implements automatic token refresh similar to YourSpotify's approach.
        Tokens are refreshed proactively before expiration to ensure seamless operation.
        """
        if not self._tokens:
            raise RuntimeError("No tokens available to refresh")

        logfire.info("Refreshing Spotify access token")

        try:
            with httpx.Client() as client:
                response = client.post(
                    TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self._tokens.refresh_token,
                    },
                    auth=(self.client_id, self.client_secret),
                )

                if response.status_code == 400:
                    try:
                        error_data = response.json()
                        error = error_data.get("error", "unknown")
                        error_desc = error_data.get("error_description", "")
                        logfire.error(
                            "Spotify token refresh failed: {error} - {error_desc}",
                            error=error,
                            error_desc=error_desc,
                        )
                        logfire.error("Full error response: {error_data}", error_data=error_data)

                        if "refresh token" in error_desc.lower() or error == "invalid_grant":
                            raise RuntimeError(
                                f"Spotify refresh token expired or revoked "
                                f"({error}: {error_desc}). "
                                "Run 'python -m glider.integrations.spotify_auth_setup' "
                                "to reauthenticate."
                            )
                        else:
                            raise RuntimeError(
                                f"Spotify token refresh failed: {error} - {error_desc}"
                            )
                    except json.JSONDecodeError as e:
                        logfire.error(
                            "Could not parse error response: {response_text}",
                            response_text=response.text,
                        )
                        raise RuntimeError(
                            f"Spotify token refresh failed with status 400: {response.text}"
                        ) from e

                response.raise_for_status()
                data = response.json()

            # Spotify may return a new refresh token - always save it if provided
            new_refresh_token = data.get("refresh_token", self._tokens.refresh_token)

            self._tokens = SpotifyTokens(
                access_token=data["access_token"],
                refresh_token=new_refresh_token,
                expires_at=time.time() + data["expires_in"] - TOKEN_REFRESH_BUFFER_SECONDS,
            )
            self._save_tokens(self._tokens)
            logfire.info("Spotify access token refreshed successfully")

        except httpx.HTTPStatusError as e:
            logfire.error("Failed to refresh Spotify token: {error}", error=e)
            raise RuntimeError(f"Failed to refresh Spotify token: {e}") from e

    def _get_access_token(self) -> str:
        """Get a valid access token, refreshing if needed.

        Proactively refreshes tokens before expiration to ensure API calls
        never fail due to expired tokens during normal operation.
        """
        if not self._tokens:
            self._tokens = self._load_tokens()

        if not self._tokens:
            raise RuntimeError(
                "No tokens available. Run 'python -m glider.integrations.spotify_auth_setup' first."
            )

        # Proactive refresh: refresh if token will expire within the buffer window
        # This ensures we never make API calls with tokens that are about to expire
        if time.time() >= self._tokens.expires_at:
            logfire.debug("Token expired or about to expire, refreshing proactively")
            self._refresh_access_token()

        return self._tokens.access_token

    def is_authenticated(self) -> bool:
        """Check if valid tokens exist."""
        tokens = self._load_tokens()
        return tokens is not None

    def get_currently_playing(self, *, _retried: bool = False) -> dict | None:
        """
        Get the currently playing track.

        Args:
            _retried: Internal flag to prevent infinite retry loops.

        Returns:
            Dict with track info if playing, None if nothing playing.

        Note:
            This method handles automatic token refresh on 401 errors.
            Combined with proactive refresh in _get_access_token(), this ensures
            minimal reauthentication is required (only after ~60 days of inactivity
            or if the user revokes access on Spotify).
        """
        access_token = self._get_access_token()

        with httpx.Client() as client:
            response = client.get(
                f"{API_BASE}/me/player/currently-playing",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"additional_types": "track"},
            )

            # 204 No Content = nothing playing
            if response.status_code == 204:
                logfire.debug("No track currently playing")
                return None

            # 401 = token expired, try refresh once (but only once to prevent infinite loop)
            if response.status_code == 401 and not _retried:
                logfire.warning("Got 401 from Spotify API, attempting token refresh")
                self._refresh_access_token()
                return self.get_currently_playing(_retried=True)

            if response.status_code == 401 and _retried:
                logfire.error(
                    "Got 401 after token refresh. Refresh token may be expired. "
                    "Run 'python -m glider.integrations.spotify_auth_setup' to reauthenticate."
                )

            response.raise_for_status()
            return response.json()

    def get_recently_played(
        self,
        after_timestamp_ms: int | None = None,
        limit: int = 50,
        *,
        _retried: bool = False,
    ) -> list[dict]:
        """
        Get recently played tracks using Spotify's recently-played endpoint.

        This approach is more reliable than polling currently-playing because:
        - Works even if the app was offline (catches up on history)
        - Provides played_at timestamps
        - Handles all pagination automatically

        Args:
            after_timestamp_ms: Unix timestamp in milliseconds. Only return tracks
                played after this timestamp. If None, returns most recent tracks.
            limit: Max tracks per request (1-50, default 50).
            _retried: Internal flag to prevent infinite retry loops.

        Returns:
            List of recently played items, each containing:
            - track: Full track object
            - played_at: ISO timestamp when track was played
        """
        access_token = self._get_access_token()

        all_items: list[dict] = []
        params: dict = {"limit": min(limit, 50)}

        if after_timestamp_ms is not None:
            params["after"] = after_timestamp_ms

        with httpx.Client() as client:
            # Build initial URL
            url = f"{API_BASE}/me/player/recently-played"

            while url:
                response = client.get(
                    url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    params=params if url == f"{API_BASE}/me/player/recently-played" else None,
                )

                # 401 = token expired, try refresh once
                if response.status_code == 401 and not _retried:
                    logfire.warning("Got 401 from Spotify API, attempting token refresh")
                    self._refresh_access_token()
                    return self.get_recently_played(
                        after_timestamp_ms=after_timestamp_ms,
                        limit=limit,
                        _retried=True,
                    )

                if response.status_code == 401 and _retried:
                    logfire.error(
                        "Got 401 after token refresh. Refresh token may be expired. "
                        "Run 'python -m glider.integrations.spotify_auth_setup' to reauthenticate."
                    )

                response.raise_for_status()
                data = response.json()

                items = data.get("items", [])
                all_items.extend(items)

                # Handle pagination - Spotify provides full URL for next page
                url = data.get("next")

                logfire.debug(
                    "Fetched {batch_count} tracks, total: {total_count}, next: {has_next}",
                    batch_count=len(items),
                    total_count=len(all_items),
                    has_next=bool(url),
                )

        logfire.info(
            "Fetched {total_count} recently played tracks",
            total_count=len(all_items),
        )
        return all_items
