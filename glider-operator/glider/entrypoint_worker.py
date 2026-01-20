import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from glider.config import settings
from glider.workflows.activities import sleep_activity, store_in_surrealdb
from glider.workflows.demo import DemoWorkflow
from glider.workflows.google_calendar import (
    GoogleCalendarSyncWorkflow,
    fetch_google_calendar_events,
    save_sync_state,
    store_calendar_events,
)
from glider.workflows.oura import (
    OuraHeartrateSyncWorkflow,
    fetch_oura_heartrate,
    load_oura_sync_state,
    save_oura_sync_state,
    store_heartrate_samples,
)
from glider.workflows.spotify import (
    SpotifyListeningWorkflow,
    check_duplicate,
    fetch_recently_played,
    get_last_scrobble_timestamp,
    record_listening_event,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info(f"Connecting to Temporal at {settings.temporal_address}")

    client = await Client.connect(settings.temporal_address)

    logger.info(f"Starting worker on task queue: {settings.temporal_task_queue}")

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[
            DemoWorkflow,
            GoogleCalendarSyncWorkflow,
            SpotifyListeningWorkflow,
            OuraHeartrateSyncWorkflow,
        ],
        activities=[
            sleep_activity,
            store_in_surrealdb,
            fetch_google_calendar_events,
            store_calendar_events,
            save_sync_state,
            # Spotify activities (recently-played approach)
            fetch_recently_played,
            get_last_scrobble_timestamp,
            check_duplicate,
            record_listening_event,
            # Oura activities
            fetch_oura_heartrate,
            load_oura_sync_state,
            save_oura_sync_state,
            store_heartrate_samples,
        ],
    )

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
