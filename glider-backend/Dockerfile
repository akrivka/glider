# Backend with uv
FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy Python dependencies and install
COPY glider-backend/pyproject.toml glider-backend/uv.lock ./
RUN uv sync --frozen --no-dev

# Copy backend code
COPY glider-backend/glider/ ./glider/

# Set Python path for uv environment
ENV PATH="/app/.venv/bin:$PATH"

# Default command (can be overridden in docker-compose)
CMD ["python", "-m", "uvicorn", "glider.entrypoint_api:app", "--host", "0.0.0.0", "--port", "8000"]
