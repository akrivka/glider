from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    temporal_address: str = "localhost:7233"
    temporal_task_queue: str = "glider-tasks"

    surrealdb_url: str = "ws://localhost:8001"
    surrealdb_user: str = "root"
    surrealdb_pass: str = "root"
    surrealdb_ns: str = "glider"
    surrealdb_db: str = "glider"

    google_client_secret_path: Path = Path("secrets/client_secret.json")
    google_tokens_path: Path = Path("secrets/tokens.json")

    # Spotify OAuth settings
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8091/callback"
    spotify_tokens_path: Path = Path("secrets/spotify_tokens.json")
    spotify_poll_interval_seconds: int = 120  # 2 minutes, matches Your Spotify approach

    # Oura OAuth settings
    oura_client_id: str = ""
    oura_client_secret: str = ""
    oura_redirect_uri: str = "http://localhost:8092/callback"
    oura_tokens_path: Path = Path("secrets/oura_tokens.json")
    oura_sync_interval_minutes: int = 30

    # Logfire/OpenTelemetry settings
    logfire_token: str | None = None
    logfire_service_name: str = "glider-operator"
    logfire_environment: str = "development"
    logfire_console_enabled: bool = True


settings = Settings()
