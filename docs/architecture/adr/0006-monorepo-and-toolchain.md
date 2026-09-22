# ADR-0006: Monorepo และ Toolchain

- Status: **Accepted** (2026-09-22)
- Date: 2026-09-22
- Related: NFR-03, NFR-19, FR-CHT-06

## Decision
- Monorepo: `backend/` (uv workspace: packages + services), `frontend/`, `deploy/`, `docs/`
- Backend: Python 3.12+, uv, ruff, mypy (strict สำหรับ core), pytest + hypothesis, import-linter, FastAPI + Pydantic v2, SQLAlchemy 2 (async) + asyncpg, Alembic (ตอนสร้าง migration), redis-py
- Frontend: Vite, React, TypeScript, TanStack Query, Zustand, i18next, Lightweight Charts, generate type จาก OpenAPI
- Dependency rule: core ← strategies; core ← binance, infra; services ประกอบทุกอย่างและห้าม import กันเอง

## Consequences
- แชร์ test vectors และ API types ระหว่าง backend และ frontend ได้ง่าย
- CI เดียวตรวจทั้ง repo; แต่ละ service build เป็น Docker image แยก
