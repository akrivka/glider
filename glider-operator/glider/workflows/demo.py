from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

# Import activity references for execute_activity
# (these are safe - no surrealdb import at module level)
with workflow.unsafe.imports_passed_through():
    from glider.workflows.activities import sleep_activity, store_in_surrealdb


@dataclass
class DemoInput:
    sleep_seconds: int = 5
    message: str = ""


@workflow.defn
class DemoWorkflow:
    """Demo workflow that demonstrates async execution with sleep and SurrealDB storage."""

    def __init__(self) -> None:
        self._status = "pending"
        self._result: str | None = None

    @workflow.run
    async def run(self, input: DemoInput) -> str:
        self._status = "running"

        # First, sleep for the specified duration
        sleep_result = await workflow.execute_activity(
            sleep_activity,
            input.sleep_seconds,
            start_to_close_timeout=timedelta(minutes=2),
        )

        # Then, store the message in SurrealDB if provided
        if input.message:
            self._status = "storing"
            store_result = await workflow.execute_activity(
                store_in_surrealdb,
                input.message,
                start_to_close_timeout=timedelta(minutes=1),
            )
            result = f"{sleep_result}. Stored message with ID: {store_result.record_id}"
        else:
            result = sleep_result

        self._status = "completed"
        self._result = result
        return result

    @workflow.query
    def get_status(self) -> dict[str, str | None]:
        return {
            "status": self._status,
            "result": self._result,
        }
