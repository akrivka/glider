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
from glider.workflows.spotify import (
    SpotifyListeningWorkflow,
    load_tracking_state,
    poll_spotify_playback,
    record_listening_event,
    save_tracking_state,
)
from glider.workflows.oura import (
    OuraHeartrateSyncWorkflow,
    fetch_oura_heartrate,
    load_oura_sync_state,
    save_oura_sync_state,
    store_heartrate_samples,
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
        workflows=[DemoWorkflow, GoogleCalendarSyncWorkflow, SpotifyListeningWorkflow, OuraHeartrateSyncWorkflow],
        activities=[
            sleep_activity,
            store_in_surrealdb,
            fetch_google_calendar_events,
            store_calendar_events,
            save_sync_state,
            # Spotify activities
            poll_spotify_playback,
            load_tracking_state,
            save_tracking_state,
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
