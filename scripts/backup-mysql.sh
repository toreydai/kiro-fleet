#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="$root_dir/deploy/docker-compose.yml"
backup_dir="${BACKUP_DIR:-$root_dir/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$backup_dir"
docker compose -f "$compose_file" exec -T mysql sh -c \
  'exec mysqldump --single-transaction --routines --events -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  | gzip > "$backup_dir/kiro-fleet-$timestamp.sql.gz"

echo "backup written to $backup_dir/kiro-fleet-$timestamp.sql.gz"
