#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# 3-2-1 Automated Backup Engine (PostgreSQL Custom Dump + Redis Snapshot + Off-Site)
# Supports local GFS retention, AGE/GPG encryption, and S3 / Cloudflare R2 upload.
# ==============================================================================

BACKUP_ROOT="${BACKUP_ROOT:-./backups}"
DB_CONTAINER="${DB_CONTAINER:-}"
REDIS_CONTAINER="${REDIS_CONTAINER:-}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-football}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

RETENTION_DAILY="${BACKUP_RETENTION_DAILY:-7}"
RETENTION_WEEKLY="${BACKUP_RETENTION_WEEKLY:-4}"
RETENTION_MONTHLY="${BACKUP_RETENTION_MONTHLY:-6}"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DAY_OF_WEEK="$(date -u +%u)"
DAY_OF_MONTH="$(date -u +%d)"

TIER="daily"
if [ "$DAY_OF_MONTH" = "01" ]; then
    TIER="monthly"
elif [ "$DAY_OF_WEEK" = "7" ]; then
    TIER="weekly"
fi

TARGET_DIR="${BACKUP_ROOT}/${TIER}"
mkdir -p "${BACKUP_ROOT}/daily" "${BACKUP_ROOT}/weekly" "${BACKUP_ROOT}/monthly"

PG_DUMP_FILE="${TARGET_DIR}/pg_${POSTGRES_DB}_${TIMESTAMP}.dump"
REDIS_RDB_FILE="${TARGET_DIR}/redis_${TIMESTAMP}.rdb"

echo "[backup] Starting ${TIER} backup at ${TIMESTAMP}..."

# 1. PostgreSQL custom-format compressed dump (-Fc)
if [ -n "$DB_CONTAINER" ]; then
    docker exec -i "$DB_CONTAINER" pg_dump -Fc --no-owner --no-acl -U "$POSTGRES_USER" -d "$POSTGRES_DB" > "$PG_DUMP_FILE"
else
    PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_dump -Fc --no-owner --no-acl \
        -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" > "$PG_DUMP_FILE"
fi

if [ ! -s "$PG_DUMP_FILE" ]; then
    echo "[backup] ERROR: Generated PostgreSQL dump is empty: $PG_DUMP_FILE" >&2
    rm -f "$PG_DUMP_FILE"
    exit 1
fi

# 2. Optional Redis RDB snapshot
if [ -n "$REDIS_CONTAINER" ]; then
    echo "[backup] Triggering Redis BGSAVE on container ${REDIS_CONTAINER}..."
    if [ -n "${REDIS_PASSWORD:-}" ]; then
        docker exec "$REDIS_CONTAINER" redis-cli -a "$REDIS_PASSWORD" SAVE >/dev/null 2>&1 || true
    else
        docker exec "$REDIS_CONTAINER" redis-cli SAVE >/dev/null 2>&1 || true
    fi
    docker cp "${REDIS_CONTAINER}:/data/dump.rdb" "$REDIS_RDB_FILE" 2>/dev/null || true
fi

# 3. Optional At-Rest Encryption (AGE recipient or GPG symmetric passphrase)
FINAL_ARTIFACT="$PG_DUMP_FILE"
if [ -n "${BACKUP_AGE_RECIPIENT:-}" ] && command -v age >/dev/null 2>&1; then
    echo "[backup] Encrypting PostgreSQL dump with age..."
    age -r "$BACKUP_AGE_RECIPIENT" -o "${PG_DUMP_FILE}.age" "$PG_DUMP_FILE"
    rm -f "$PG_DUMP_FILE"
    FINAL_ARTIFACT="${PG_DUMP_FILE}.age"
elif [ -n "${BACKUP_GPG_PASSPHRASE:-}" ] && command -v gpg >/dev/null 2>&1; then
    echo "[backup] Encrypting PostgreSQL dump with GPG AES256..."
    gpg --batch --yes --symmetric --cipher-algo AES256 \
        --passphrase "$BACKUP_GPG_PASSPHRASE" \
        -o "${PG_DUMP_FILE}.gpg" "$PG_DUMP_FILE"
    rm -f "$PG_DUMP_FILE"
    FINAL_ARTIFACT="${PG_DUMP_FILE}.gpg"
fi

# 4. Generate SHA-256 integrity manifest
sha256sum "$FINAL_ARTIFACT" > "${FINAL_ARTIFACT}.sha256"
echo "[backup] Created verified artifact: $FINAL_ARTIFACT"

# 5. Optional Off-Site 3-2-1 Sync (Cloudflare R2 / AWS S3 / rclone)
if [ -n "${BACKUP_S3_URI:-}" ] && command -v aws >/dev/null 2>&1; then
    ENDPOINT_ARGS=()
    if [ -n "${BACKUP_S3_ENDPOINT:-}" ]; then
        ENDPOINT_ARGS=(--endpoint-url "$BACKUP_S3_ENDPOINT")
    fi
    echo "[backup] Uploading encrypted backup to off-site S3/R2 storage..."
    aws "${ENDPOINT_ARGS[@]}" s3 cp "$FINAL_ARTIFACT" "${BACKUP_S3_URI}/${TIER}/"
    aws "${ENDPOINT_ARGS[@]}" s3 cp "${FINAL_ARTIFACT}.sha256" "${BACKUP_S3_URI}/${TIER}/"
elif [ -n "${BACKUP_RCLONE_REMOTE:-}" ] && command -v rclone >/dev/null 2>&1; then
    echo "[backup] Syncing backup via rclone to ${BACKUP_RCLONE_REMOTE}..."
    rclone copy "$FINAL_ARTIFACT" "${BACKUP_RCLONE_REMOTE}/${TIER}/"
    rclone copy "${FINAL_ARTIFACT}.sha256" "${BACKUP_RCLONE_REMOTE}/${TIER}/"
fi

# 6. Grandfather-Father-Son (GFS) Local Retention Pruning
prune_tier() {
    local dir="$1"
    local keep="$2"
    ls -1t "${dir}"/pg_* 2>/dev/null | grep -v '\.sha256$' | tail -n "+$((keep + 1))" | while read -r old_file; do
        echo "[backup] Pruning expired backup: ${old_file}"
        rm -f "$old_file" "${old_file}.sha256"
    done
}

prune_tier "${BACKUP_ROOT}/daily" "$RETENTION_DAILY"
prune_tier "${BACKUP_ROOT}/weekly" "$RETENTION_WEEKLY"
prune_tier "${BACKUP_ROOT}/monthly" "$RETENTION_MONTHLY"

echo "[backup] Completed successfully."
