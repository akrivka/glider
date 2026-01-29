"""Oura Ring integration client."""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

SCOPES = ["heartrate", "daily", "workout", "session", "spo2"]
AUTH_URL = "https://cloud.ouraring.com/oauth/authorize"
TOKEN_URL = "https://api.ouraring.com/oauth/token"
API_BASE = "https://api.ouraring.com/v2"


@dataclass
class OuraTokens:
    access_token: str
    refresh_token: str
    expires_at: float  # Unix timestamp


class OuraClient:
    """Client for interacting with Oura API."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tokens_path: Path,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.tokens_path = tokens_path
        self._tokens: OuraTokens | None = None

    def _load_tokens(self) -> OuraTokens | None:
        """Load tokens from file."""
        if not self.tokens_path.exists():
            return None

        with open(self.tokens_path) as f:
            data = json.load(f)

        return OuraTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"],
        )

    def _save_tokens(self, tokens: OuraTokens) -> None:
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
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            response.raise_for_status()
            data = response.json()

        self._tokens = OuraTokens(
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
                "No tokens available. Run 'python -m glider.integrations.oura_auth_setup' first."
            )

        # Refresh if expired or about to expire
        if time.time() >= self._tokens.expires_at:
            self._refresh_access_token()

        return self._tokens.access_token

    def is_authenticated(self) -> bool:
        """Check if valid tokens exist."""
        tokens = self._load_tokens()
        return tokens is not None

    def get_heartrate(
        self,
        start_datetime: datetime | None = None,
        end_datetime: datetime | None = None,
        *,
        _retried: bool = False,
    ) -> list[dict]:
        """
        Get heart rate data from Oura.

        Args:
            start_datetime: Start of the time range (ISO format).
            end_datetime: End of the time range (ISO format).
            _retried: Internal flag to prevent infinite retry loops.

        Returns:
            List of heart rate samples with bpm, source, and timestamp.
        """
        access_token = self._get_access_token()

        params = {}
        if start_datetime:
            params["start_datetime"] = start_datetime.isoformat()
        if end_datetime:
            params["end_datetime"] = end_datetime.isoformat()

        with httpx.Client() as client:
            all_data = []
            next_token = None

            while True:
                if next_token:
                    params["next_token"] = next_token

                response = client.get(
                    f"{API_BASE}/usercollection/heartrate",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params=params,
                )

                # 401 = token expired, try refresh once
                if response.status_code == 401 and not _retried:
                    self._refresh_access_token()
                    return self.get_heartrate(start_datetime, end_datetime, _retried=True)

                response.raise_for_status()
                data = response.json()

                all_data.extend(data.get("data", []))

                # Check for pagination
                next_token = data.get("next_token")
                if not next_token:
                    break

            return all_data

    def _get_daily_data(
        self,
        endpoint: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        *,
        _retried: bool = False,
    ) -> list[dict]:
        """
        Generic method to fetch daily data from Oura.

        Args:
            endpoint: The API endpoint (e.g., 'daily_stress', 'daily_activity').
            start_date: Start of the date range.
            end_date: End of the date range.
            _retried: Internal flag to prevent infinite retry loops.

        Returns:
            List of daily data records.
        """
        access_token = self._get_access_token()

        params = {}
        if start_date:
            params["start_date"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["end_date"] = end_date.strftime("%Y-%m-%d")

        with httpx.Client() as client:
            all_data = []
            next_token = None

            while True:
                if next_token:
                    params["next_token"] = next_token

                response = client.get(
                    f"{API_BASE}/usercollection/{endpoint}",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params=params,
                )

                if response.status_code == 401 and not _retried:
                    self._refresh_access_token()
                    return self._get_daily_data(endpoint, start_date, end_date, _retried=True)

                response.raise_for_status()
                data = response.json()

                all_data.extend(data.get("data", []))

                next_token = data.get("next_token")
                if not next_token:
                    break

            return all_data

    def get_daily_stress(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """
        Get daily stress data from Oura.

        Returns:
            List of daily stress records with day, stress_high, recovery_high, day_summary.
        """
        return self._get_daily_data("daily_stress", start_date, end_date)

    def get_daily_activity(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """
        Get daily activity data from Oura.

        Returns:
            List of daily activity records with score, steps, calories, etc.
        """
        return self._get_daily_data("daily_activity", start_date, end_date)

    def get_daily_readiness(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """
        Get daily readiness data from Oura.

        Returns:
            List of daily readiness records with score and contributors.
        """
        return self._get_daily_data("daily_readiness", start_date, end_date)

    def get_daily_sleep(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """
        Get daily sleep data from Oura.

        Returns:
            List of daily sleep records with score and contributors.
        """
        return self._get_daily_data("daily_sleep", start_date, end_date)

    def get_daily_spo2(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """
        Get daily SpO2 data from Oura.

        Returns:
            List of daily SpO2 records with spo2_percentage.
        """
        return self._get_daily_data("daily_spo2", start_date, end_date)

    def get_sleep(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """
        Get detailed sleep period data from Oura.

        Returns:
            List of sleep period records with HRV, heart rate, sleep phases, etc.
        """
        return self._get_daily_data("sleep", start_date, end_date)

    def get_sessions(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """
        Get session data (meditation, breathing) from Oura.

        Returns:
            List of session records.
        """
        return self._get_daily_data("session", start_date, end_date)

    def get_workouts(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """
        Get workout data from Oura.

        Returns:
            List of workout records with activity, calories, distance, etc.
        """
        return self._get_daily_data("workout", start_date, end_date)
