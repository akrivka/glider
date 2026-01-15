from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    temporal_address: str = "localhost:7233"
    temporal_task_queue: str = "glider-tasks"

    surrealdb_url: str = "ws://localhost:8000"
    surrealdb_user: str = "root"
    surrealdb_pass: str = "root"
    surrealdb_ns: str = "glider"
    surrealdb_db: str = "glider"

    google_client_secret_path: Path = Path("secrets/client_secret.json")
    google_tokens_path: Path = Path("secrets/tokens.json")


settings = Settings()
