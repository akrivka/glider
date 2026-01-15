import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from temporalio.client import Client

from glider.config import settings
from glider.workflows.demo import DemoInput, DemoWorkflow

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

_client: Client | None = None


async def get_client() -> Client:
    global _client
    if _client is None:
        _client = await Client.connect(settings.temporal_address)
    return _client


class StartWorkflowRequest(BaseModel):
    sleep_seconds: int = 5
    message: str = ""


class StartWorkflowResponse(BaseModel):
    workflow_id: str
    message: str


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    status: str
    result: str | None


@router.post("/demo/start", response_model=StartWorkflowResponse)
async def start_demo_workflow(request: StartWorkflowRequest):
    """Start a new demo workflow."""
    client = await get_client()
    workflow_id = f"demo-{uuid.uuid4()}"

    workflow_input = DemoInput(
        sleep_seconds=request.sleep_seconds,
        message=request.message,
    )

    await client.start_workflow(
        DemoWorkflow.run,
        workflow_input,
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )

    msg = f"Workflow started with {request.sleep_seconds} second sleep"
    if request.message:
        msg += " and message to store"

    return StartWorkflowResponse(
        workflow_id=workflow_id,
        message=msg,
    )


@router.get("/demo/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_demo_workflow_status(workflow_id: str):
    """Get the status of a demo workflow."""
    client = await get_client()

    try:
        handle = client.get_workflow_handle(workflow_id)
        status_data = await handle.query(DemoWorkflow.get_status)

        return WorkflowStatusResponse(
            workflow_id=workflow_id,
            status=status_data["status"],
            result=status_data["result"],
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {e!s}") from None
