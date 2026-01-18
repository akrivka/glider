"""
Script to create a Temporal schedule for Spotify listening tracking.

Usage:
    python -m glider.scripts.create_spotify_schedule

This creates a schedule that runs the SpotifyListeningWorkflow at configured intervals.
"""

import asyncio
from datetime import timedelta

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleSpec,
)

from glider.config import settings
from glider.workflows.spotify import SpotifyListeningWorkflow, SpotifyPollInput

SCHEDULE_ID = "spotify-listening-schedule"


async def main() -> None:
    """Create the Spotify listening schedule."""
    print(f"Connecting to Temporal at {settings.temporal_address}")
    client = await Client.connect(settings.temporal_address)

    # Check if schedule already exists
    try:
        handle = client.get_schedule_handle(SCHEDULE_ID)
        desc = await handle.describe()
        print(f"Schedule '{SCHEDULE_ID}' already exists.")
        print(f"  State: {desc.schedule.state}")
        last_run = desc.info.recent_actions[-1].start_time if desc.info.recent_actions else "Never"
        print(f"  Last run: {last_run}")
        print("\nTo delete and recreate, use Temporal CLI:")
        print(f"  temporal schedule delete --schedule-id {SCHEDULE_ID}")
        return
    except Exception:
        pass  # Schedule doesn't exist, create it

    interval_seconds = settings.spotify_poll_interval_seconds
    print(f"Creating schedule '{SCHEDULE_ID}'...")

    await client.create_schedule(
        SCHEDULE_ID,
        Schedule(
            action=ScheduleActionStartWorkflow(
                SpotifyListeningWorkflow.run,
                SpotifyPollInput(),
                id="spotify-listening-poll",
                task_queue=settings.temporal_task_queue,
            ),
            spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=timedelta(seconds=interval_seconds))]),
        ),
    )

    print("Schedule created successfully!")
    print(f"  ID: {SCHEDULE_ID}")
    print(f"  Interval: Every {interval_seconds} seconds")
    print(f"  Task queue: {settings.temporal_task_queue}")
    print(f"\nView in Temporal UI: http://localhost:8080/schedules/{SCHEDULE_ID}")


if __name__ == "__main__":
    asyncio.run(main())
