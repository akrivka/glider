import asyncio
from dataclasses import dataclass

from temporalio import activity


@dataclass
class StoreResult:
    record_id: str
    message: str


@activity.defn
async def sleep_activity(seconds: int) -> str:
    """Demo activity that sleeps for a specified number of seconds."""
    activity.logger.info(f"Starting sleep for {seconds} seconds")
    await asyncio.sleep(seconds)
    activity.logger.info(f"Completed sleep for {seconds} seconds")
    return f"Slept for {seconds} seconds"


@activity.defn
async def store_in_surrealdb(message: str) -> StoreResult:
    """Store a message in SurrealDB."""
    # Import inside activity to avoid Temporal sandbox restrictions
    from surrealdb import AsyncSurreal

    from glider.config import settings

    activity.logger.info(f"Storing message in SurrealDB: {message}")

    db = AsyncSurreal(settings.surrealdb_url)
    try:
        await db.connect(settings.surrealdb_url)
        await db.signin({"username": settings.surrealdb_user, "password": settings.surrealdb_pass})
        await db.use(settings.surrealdb_ns, settings.surrealdb_db)

        result = await db.create("demo_messages", {"message": message})

        record_id = result["id"] if isinstance(result, dict) else str(result)
        activity.logger.info(f"Stored message with ID: {record_id}")

        return StoreResult(record_id=str(record_id), message=message)
    finally:
        await db.close()
