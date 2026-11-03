#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Mandatory Pre-Migration Snapshot Wrapper
# Captures a verified custom-format PostgreSQL dump BEFORE running Alembic DDL.
# ==============================================================================

SNAPSHOT_DIR="${BACKUP_ROOT:-./backups}/pre_migration"
mkdir -p "$SNAPSHOT_DIR"

POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-football}"
POSTGRES_HOST="${POSTGRES_HOST:-db}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
TARGET_REV="${1:-head}"

CURRENT_REV="$(alembic current 2>/dev/null | awk '{print $1}' | head -n 1 || echo 'none')"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SNAPSHOT_FILE="${SNAPSHOT_DIR}/pre_migrate_${CURRENT_REV:-base}_${TIMESTAMP}.dump"

echo "[pre-migrate] Taking safety snapshot before upgrading '${CURRENT_REV:-base}' -> '${TARGET_REV}'..."

if [ -n "${DB_CONTAINER:-}" ]; then
    docker exec -i "$DB_CONTAINER" pg_dump -Fc --no-owner --no-acl \
        -U "$POSTGRES_USER" -d "$POSTGRES_DB" > "$SNAPSHOT_FILE"
else
    PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_dump -Fc --no-owner --no-acl \
        -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" > "$SNAPSHOT_FILE"
fi

if [ ! -s "$SNAPSHOT_FILE" ]; then
    echo "[pre-migrate] ABORTING: Pre-migration snapshot failed or produced an empty file!" >&2
    rm -f "$SNAPSHOT_FILE"
    exit 1
fi

sha256sum "$SNAPSHOT_FILE" > "${SNAPSHOT_FILE}.sha256"
echo "[pre-migrate] Verified snapshot saved: ${SNAPSHOT_FILE}"

echo "[pre-migrate] Running: alembic upgrade ${TARGET_REV}"
if ! alembic upgrade "$TARGET_REV"; then
    echo "[pre-migrate] ERROR: Migration failed!" >&2
    echo "[pre-migrate] Rollback command:" >&2
    echo "  pg_restore --clean --if-exists --no-owner -d ${POSTGRES_DB} ${SNAPSHOT_FILE}" >&2
    exit 1
fi

echo "[pre-migrate] Migration to '${TARGET_REV}' succeeded cleanly."
