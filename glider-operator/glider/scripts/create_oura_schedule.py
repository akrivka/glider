"""
Script to create Temporal schedules for Oura data sync.

Usage:
    python -m glider.scripts.create_oura_schedule

This creates schedules that run OuraHeartrateSyncWorkflow and OuraFullSyncWorkflow at configured intervals.
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
from glider.workflows.oura import OuraHeartrateSyncWorkflow, OuraFullSyncWorkflow, OuraSyncInput

HEARTRATE_SCHEDULE_ID = "oura-heartrate-sync-schedule"
FULL_SYNC_SCHEDULE_ID = "oura-full-sync-schedule"


async def create_schedule_if_not_exists(
    client: Client,
    schedule_id: str,
    workflow_class: type,
    workflow_id: str,
    interval_minutes: int,
) -> bool:
    """Create a schedule if it doesn't exist. Returns True if created."""
    try:
        handle = client.get_schedule_handle(schedule_id)
        desc = await handle.describe()
        print(f"Schedule '{schedule_id}' already exists.")
        print(f"  State: {desc.schedule.state}")
        last_run = desc.info.recent_actions[-1].start_time if desc.info.recent_actions else "Never"
        print(f"  Last run: {last_run}")
        return False
    except Exception:
        pass  # Schedule doesn't exist, create it

    print(f"Creating schedule '{schedule_id}'...")

    await client.create_schedule(
        schedule_id,
        Schedule(
            action=ScheduleActionStartWorkflow(
                workflow_class.run,
                OuraSyncInput(),
                id=workflow_id,
                task_queue=settings.temporal_task_queue,
            ),
            spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=timedelta(minutes=interval_minutes))]),
        ),
    )

    print(f"  Created! Interval: Every {interval_minutes} minutes")
    return True


async def main() -> None:
    """Create the Oura sync schedules."""
    print(f"Connecting to Temporal at {settings.temporal_address}")
    client = await Client.connect(settings.temporal_address)

    interval_minutes = settings.oura_sync_interval_minutes

    # Create heartrate sync schedule (runs frequently)
    await create_schedule_if_not_exists(
        client,
        HEARTRATE_SCHEDULE_ID,
        OuraHeartrateSyncWorkflow,
        "oura-heartrate-sync",
        interval_minutes,
    )

    # Create full sync schedule (runs less frequently - daily data doesn't change often)
    # Run every 2 hours for daily data
    full_sync_interval = max(interval_minutes * 4, 120)
    await create_schedule_if_not_exists(
        client,
        FULL_SYNC_SCHEDULE_ID,
        OuraFullSyncWorkflow,
        "oura-full-sync",
        full_sync_interval,
    )

    print(f"\nTask queue: {settings.temporal_task_queue}")
    print(f"\nView schedules in Temporal UI:")
    print(f"  http://localhost:8080/schedules/{HEARTRATE_SCHEDULE_ID}")
    print(f"  http://localhost:8080/schedules/{FULL_SYNC_SCHEDULE_ID}")
    print("\nTo delete and recreate, use Temporal CLI:")
    print(f"  temporal schedule delete --schedule-id {HEARTRATE_SCHEDULE_ID}")
    print(f"  temporal schedule delete --schedule-id {FULL_SYNC_SCHEDULE_ID}")


if __name__ == "__main__":
    asyncio.run(main())
