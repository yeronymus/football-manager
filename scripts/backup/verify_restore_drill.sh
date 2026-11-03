#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Automated Disaster Recovery Restore Drill
# Spins up an isolated ephemeral PostgreSQL 15 container, verifies SHA-256,
# restores the dump, validates core schema & Alembic state, and cleans up.
# ==============================================================================

DUMP_INPUT="${1:-}"
if [ -z "$DUMP_INPUT" ]; then
    DUMP_INPUT="$(ls -1t ./backups/daily/pg_* ./backups/pre_migration/pre_migrate_* 2>/dev/null | grep -v '\.sha256$' | head -n 1 || true)"
fi

if [ -z "$DUMP_INPUT" ] || [ ! -f "$DUMP_INPUT" ]; then
    echo "[restore-drill] ERROR: No backup dump file found. Pass path as first argument." >&2
    exit 1
fi

if [ -f "${DUMP_INPUT}.sha256" ]; then
    echo "[restore-drill] Verifying SHA-256 checksum for ${DUMP_INPUT}..."
    sha256sum -c "${DUMP_INPUT}.sha256"
fi

DRILL_CONTAINER="fm-restore-drill-$$"
TEMP_DUMP=""

cleanup() {
    echo "[restore-drill] Cleaning up ephemeral container ${DRILL_CONTAINER}..."
    docker rm -f "$DRILL_CONTAINER" >/dev/null 2>&1 || true
    [ -n "$TEMP_DUMP" ] && rm -f "$TEMP_DUMP" || true
}
trap cleanup EXIT

WORK_DUMP="$DUMP_INPUT"
if [[ "$DUMP_INPUT" == *.age ]]; then
    : "${BACKUP_AGE_KEY_FILE:?Set BACKUP_AGE_KEY_FILE to decrypt .age archive}"
    TEMP_DUMP="$(mktemp /tmp/fm_drill_XXXXXX.dump)"
    age -d -i "$BACKUP_AGE_KEY_FILE" -o "$TEMP_DUMP" "$DUMP_INPUT"
    WORK_DUMP="$TEMP_DUMP"
elif [[ "$DUMP_INPUT" == *.gpg ]]; then
    : "${BACKUP_GPG_PASSPHRASE:?Set BACKUP_GPG_PASSPHRASE to decrypt .gpg archive}"
    TEMP_DUMP="$(mktemp /tmp/fm_drill_XXXXXX.dump)"
    gpg --batch --yes --decrypt --passphrase "$BACKUP_GPG_PASSPHRASE" -o "$TEMP_DUMP" "$DUMP_INPUT"
    WORK_DUMP="$TEMP_DUMP"
fi

echo "[restore-drill] Starting isolated PostgreSQL 15 container..."
docker run -d --name "$DRILL_CONTAINER" \
    -e POSTGRES_USER=drill_user \
    -e POSTGRES_PASSWORD=drill_pass \
    -e POSTGRES_DB=drill_db \
    postgres:15-alpine >/dev/null

for _ in $(seq 1 30); do
    if docker exec "$DRILL_CONTAINER" pg_isready -U drill_user -d drill_db >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

echo "[restore-drill] Restoring dump into ephemeral database..."
docker exec -i "$DRILL_CONTAINER" pg_restore --no-owner --no-acl -U drill_user -d drill_db < "$WORK_DUMP"

echo "[restore-drill] Auditing restored schema & row counts..."
docker exec "$DRILL_CONTAINER" psql -U drill_user -d drill_db -v ON_ERROR_STOP=1 -c "
SELECT
    (SELECT version_num FROM alembic_version LIMIT 1) AS alembic_revision,
    (SELECT COUNT(*) FROM users) AS users_count,
    (SELECT COUNT(*) FROM chats) AS chats_count,
    (SELECT COUNT(*) FROM games) AS games_count,
    (SELECT COUNT(*) FROM signups) AS signups_count;
"

echo "[restore-drill] SUCCESS: Backup archive is healthy and 100% restorable."
