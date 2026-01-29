"""
Script to create a Temporal schedule for Google Calendar sync.

Usage:
    python -m glider.scripts.create_calendar_schedule

This creates a schedule that runs the GoogleCalendarSyncWorkflow every 30 minutes.
Run this script once after setting up the Google Calendar integration.
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
from glider.workflows.google_calendar import CalendarSyncInput, GoogleCalendarSyncWorkflow

SCHEDULE_ID = "google-calendar-sync-schedule"


async def main() -> None:
    """Create the Google Calendar sync schedule."""
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
        print("\nTo delete and recreate, run:")
        print("  python -m glider.scripts.delete_calendar_schedule")
        return
    except Exception:
        pass  # Schedule doesn't exist, create it

    print(f"Creating schedule '{SCHEDULE_ID}'...")

    await client.create_schedule(
        SCHEDULE_ID,
        Schedule(
            action=ScheduleActionStartWorkflow(
                GoogleCalendarSyncWorkflow.run,
                CalendarSyncInput(calendar_id="primary"),
                id="google-calendar-sync",
                task_queue=settings.temporal_task_queue,
            ),
            spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=timedelta(minutes=30))]),
        ),
    )

    print("Schedule created successfully!")
    print(f"  ID: {SCHEDULE_ID}")
    print("  Interval: Every 30 minutes")
    print(f"  Task queue: {settings.temporal_task_queue}")
    print(f"\nView in Temporal UI: http://localhost:8080/schedules/{SCHEDULE_ID}")


if __name__ == "__main__":
    asyncio.run(main())
