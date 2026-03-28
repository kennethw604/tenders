FROM python:3.13-slim

WORKDIR /app

# System deps for Playwright browsers and Scrapy
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock* ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev 2>/dev/null || \
    uv sync --no-install-project --no-dev

COPY src/ ./src/
COPY scrapy.cfg ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev 2>/dev/null || \
    uv sync --no-dev

# Install Playwright browsers for JS-heavy spiders (ON, BC, AB, MB)
RUN uv run playwright install chromium --with-deps 2>/dev/null || true

ENV PATH="/app/.venv/bin:$PATH"
ENV SCRAPY_SETTINGS_MODULE="purchasingcad.scrapy_settings"
