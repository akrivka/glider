# Build context should be project root (.)
# Build frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /frontend
COPY glider-frontend/package*.json ./
RUN npm ci --legacy-peer-deps
COPY glider-frontend/ ./
RUN npm run build

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

# Copy built frontend into static directory
COPY --from=frontend-builder /frontend/dist ./static

# Set Python path for uv environment
ENV PATH="/app/.venv/bin:$PATH"

# Default command (can be overridden in docker-compose)
CMD ["python", "-m", "uvicorn", "glider.api_entrypoint:app", "--host", "0.0.0.0", "--port", "8000"]
