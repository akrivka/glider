"""Spotify integration client."""

import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

SCOPES = ["user-read-currently-playing", "user-read-playback-state"]
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"


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
        """Refresh the access token using refresh token."""
        if not self._tokens:
            raise RuntimeError("No tokens available to refresh")

        with httpx.Client() as client:
            response = client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._tokens.refresh_token,
                },
                auth=(self.client_id, self.client_secret),
            )
            response.raise_for_status()
            data = response.json()

        self._tokens = SpotifyTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", self._tokens.refresh_token),
            expires_at=time.time() + data["expires_in"] - 60,  # 60s buffer
        )
        self._save_tokens(self._tokens)

    def _get_access_token(self) -> str:
        """Get a valid access token, refreshing if needed."""
        if not self._tokens:
            self._tokens = self._load_tokens()

        if not self._tokens:
            raise RuntimeError(
                "No tokens available. Run 'python -m glider.integrations.spotify_auth_setup' first."
            )

        # Refresh if expired or about to expire
        if time.time() >= self._tokens.expires_at:
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
                return None

            # 401 = token expired, try refresh once (but only once to prevent infinite loop)
            if response.status_code == 401 and not _retried:
                self._refresh_access_token()
                return self.get_currently_playing(_retried=True)

            response.raise_for_status()
            return response.json()
