#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PROJECT_DIR}/config/.env"
BACKUP_DIR="${PROJECT_DIR}/volumes/backup"
MEDIA_DIR="${PROJECT_DIR}/media"
TMP_DIR=""
ASSUME_YES=0

usage() {
    cat <<'EOF'
Usage:
  ./scripts/restore_local.sh [--yes] [--env-file PATH] <backup-file-name-or-path>

Examples:
  ./scripts/restore_local.sh 20260605-021500.tar.gz
  ./scripts/restore_local.sh ./volumes/backup/20260605-021500.tar.gz
  ./scripts/restore_local.sh --yes --env-file ./config/.env 20260605-021500.tar.gz

Behavior:
  - Reads DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT from the env file
  - Restores postgres.sql into the local PostgreSQL database
  - Replaces the local media/ directory with the archived media/
EOF
}

cleanup() {
    if [[ -n "${TMP_DIR}" && -d "${TMP_DIR}" ]]; then
        rm -rf "${TMP_DIR}"
    fi
}

require_command() {
    local command_name="$1"
    if ! command -v "${command_name}" >/dev/null 2>&1; then
        echo "Missing required command: ${command_name}" >&2
        exit 1
    fi
}

resolve_backup_archive() {
    local input_path="$1"

    if [[ -f "${input_path}" ]]; then
        printf '%s\n' "${input_path}"
        return 0
    fi

    if [[ -f "${BACKUP_DIR}/${input_path}" ]]; then
        printf '%s\n' "${BACKUP_DIR}/${input_path}"
        return 0
    fi

    echo "Backup archive not found: ${input_path}" >&2
    echo "Expected either an existing path or a file under ${BACKUP_DIR}" >&2
    exit 1
}

query_postgres_value() {
    local sql="$1"
    psql \
        -h "${DB_HOST}" \
        -p "${DB_PORT}" \
        -U "${DB_USER}" \
        -d postgres \
        -tA \
        -v ON_ERROR_STOP=1 \
        -c "${sql}"
}

preflight_check_permissions() {
    local current_user
    local is_superuser
    local can_create_db
    local can_signal_backend
    local db_exists
    local db_owner=""

    echo "Checking database permissions..."

    current_user="$(query_postgres_value "SELECT current_user;")"
    is_superuser="$(query_postgres_value "SELECT rolsuper::int FROM pg_roles WHERE rolname = current_user;")"
    can_create_db="$(query_postgres_value "SELECT rolcreatedb::int FROM pg_roles WHERE rolname = current_user;")"
    can_signal_backend="$(query_postgres_value "SELECT pg_has_role(current_user, 'pg_signal_backend', 'MEMBER')::int;")"
    db_exists="$(query_postgres_value "SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}')::int;")"

    if [[ "${db_exists}" == "1" ]]; then
        db_owner="$(query_postgres_value "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = '${DB_NAME}';")"
    fi

    if [[ "${can_signal_backend}" != "1" && "${is_superuser}" != "1" ]]; then
        echo "Permission check failed: ${current_user} cannot terminate active connections for ${DB_NAME}." >&2
        echo "Grant membership in pg_signal_backend or use a superuser account such as postgres." >&2
        exit 1
    fi

    if [[ "${can_create_db}" != "1" && "${is_superuser}" != "1" ]]; then
        echo "Permission check failed: ${current_user} cannot create database ${DB_NAME}." >&2
        echo "Use a role with CREATEDB or a superuser account such as postgres." >&2
        exit 1
    fi

    if [[ "${db_exists}" == "1" && "${db_owner}" != "${current_user}" && "${is_superuser}" != "1" ]]; then
        echo "Permission check failed: ${current_user} is not the owner of existing database ${DB_NAME}." >&2
        echo "Current owner: ${db_owner}. Use the owner role or a superuser account such as postgres." >&2
        exit 1
    fi

    echo "Permission check passed."
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --yes)
            ASSUME_YES=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
        *)
            if [[ -n "${BACKUP_ARCHIVE_INPUT:-}" ]]; then
                echo "Only one backup archive may be provided." >&2
                usage
                exit 1
            fi
            BACKUP_ARCHIVE_INPUT="$1"
            shift
            ;;
    esac
done

if [[ -z "${BACKUP_ARCHIVE_INPUT:-}" ]]; then
    usage
    exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Env file not found: ${ENV_FILE}" >&2
    exit 1
fi

require_command tar
require_command psql
require_command dropdb
require_command createdb

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

: "${DB_NAME:?DB_NAME is required in ${ENV_FILE}}"
: "${DB_USER:?DB_USER is required in ${ENV_FILE}}"
: "${DB_PASSWORD:?DB_PASSWORD is required in ${ENV_FILE}}"
: "${DB_HOST:?DB_HOST is required in ${ENV_FILE}}"
: "${DB_PORT:?DB_PORT is required in ${ENV_FILE}}"

export PGPASSWORD="${DB_PASSWORD}"

BACKUP_ARCHIVE="$(resolve_backup_archive "${BACKUP_ARCHIVE_INPUT}")"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/navu-house-restore.XXXXXX")"
trap cleanup EXIT

echo "Project directory : ${PROJECT_DIR}"
echo "Env file          : ${ENV_FILE}"
echo "Backup archive    : ${BACKUP_ARCHIVE}"
echo "Target database   : ${DB_NAME} (${DB_USER}@${DB_HOST}:${DB_PORT})"
echo "Target media dir  : ${MEDIA_DIR}"
echo

preflight_check_permissions

if [[ "${ASSUME_YES}" -ne 1 ]]; then
    read -r -p "This will overwrite the local database and media directory. Continue? [y/N] " reply
    if [[ ! "${reply}" =~ ^[Yy]$ ]]; then
        echo "Restore cancelled."
        exit 0
    fi
fi

echo "Extracting backup archive..."
tar -xzf "${BACKUP_ARCHIVE}" -C "${TMP_DIR}"

if [[ ! -f "${TMP_DIR}/postgres.sql" ]]; then
    echo "Invalid backup archive: postgres.sql is missing." >&2
    exit 1
fi

if [[ ! -d "${TMP_DIR}/media" ]]; then
    echo "Invalid backup archive: media/ is missing." >&2
    exit 1
fi

echo "Terminating existing connections..."
psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d postgres \
    -v ON_ERROR_STOP=1 \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${DB_NAME}' AND pid <> pg_backend_pid();" \
    >/dev/null

echo "Dropping and recreating database..."
dropdb \
    --if-exists \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    "${DB_NAME}"

createdb \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    "${DB_NAME}"

echo "Restoring postgres.sql..."
psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    -v ON_ERROR_STOP=1 \
    -f "${TMP_DIR}/postgres.sql" \
    >/dev/null

echo "Replacing media directory..."
rm -rf "${MEDIA_DIR}"
mkdir -p "${MEDIA_DIR}"
cp -R "${TMP_DIR}/media/." "${MEDIA_DIR}/"

echo
echo "Local restore completed successfully."
echo "If your Django dev server is running, restart it to pick up the restored state."
