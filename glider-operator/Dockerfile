# Backend with uv
FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy Python dependencies and install
COPY glider-operator/pyproject.toml glider-operator/uv.lock ./
RUN uv sync --frozen --no-dev

# Copy backend code
COPY glider-operator/glider/ ./glider/

# Set Python path for uv environment
ENV PATH="/app/.venv/bin:$PATH"

# Default command (can be overridden in docker-compose)
CMD ["python", "-m", "glider.entrypoint_worker"]
