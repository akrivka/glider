import asyncio
import logging

import logfire
from temporalio.client import Client
from temporalio.worker import Worker

from glider.config import settings

# Configure Logfire for OpenTelemetry tracing and logging
logfire.configure(
    service_name=settings.logfire_service_name,
    environment=settings.logfire_environment,
    token=settings.logfire_token,
    console=logfire.ConsoleOptions(
        colors="auto",
        verbose=True,
    ) if settings.logfire_console_enabled else False,
    send_to_logfire="if-token-present",
)

# Instrument httpx for automatic tracing of HTTP requests
logfire.instrument_httpx()

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
    logfire.info("Connecting to Temporal", temporal_address=settings.temporal_address)

    client = await Client.connect(settings.temporal_address)

    logfire.info("Starting worker", task_queue=settings.temporal_task_queue)

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

    with logfire.span("temporal_worker_running", task_queue=settings.temporal_task_queue):
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
