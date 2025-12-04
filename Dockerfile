# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install system dependencies (kept minimal to reduce image size)
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv (faster dependency manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

# Install Python dependencies with uv
COPY pyproject.toml uv.lock ./
RUN uv pip sync --system uv.lock

# Default FastAPI host/port
ENV API_HOST=0.0.0.0 \
    API_PORT=8000

# Copy project files
COPY . .

EXPOSE 8000

CMD ["python", "-m", "server.run_server"]
