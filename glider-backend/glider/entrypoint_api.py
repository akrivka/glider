from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from glider.api.workflows import router as workflows_router

app = FastAPI(title="Glider Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workflows_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Serve frontend static files (in production Docker build)
static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")
else:

    @app.get("/")
    def root() -> dict[str, str]:
        return {"message": "Hello from Glider Backend!"}
