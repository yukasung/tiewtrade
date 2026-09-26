# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

# ติดตั้ง uv จาก image ทางการ เพื่อให้เวอร์ชันตรงกับที่ใช้ในเครื่อง
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

# ติดตั้ง dependency ก่อนคัดลอกโค้ด เพื่อให้ชั้น cache ไม่ถูกสร้างใหม่ทุกครั้ง
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
