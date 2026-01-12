from fastapi import FastAPI

app = FastAPI(title="Glider Backend")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Hello from Glider Backend!"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
