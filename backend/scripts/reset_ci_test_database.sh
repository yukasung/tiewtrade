#!/usr/bin/env bash
# Destructive: use only with the disposable PostgreSQL container for backend tests.
set -euo pipefail

test_postgres_container="${1:?Pass the disposable test PostgreSQL container ID}"
cd "$(dirname "$0")/.."

docker exec "$test_postgres_container" psql -U postgres -d postgres \
  -v ON_ERROR_STOP=1 \
  -c 'DROP DATABASE tiewtrade WITH (FORCE)' \
  -c 'CREATE DATABASE tiewtrade'
for script in db/bootstrap/*.sql; do
  docker exec -i "$test_postgres_container" psql -U postgres -d tiewtrade \
    -v ON_ERROR_STOP=1 < "$script"
done
uv run alembic upgrade head
