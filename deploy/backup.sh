#!/usr/bin/env bash
# Nightly backup of the main platform database (users, progress, content edits). Keeps 14 days.
# Sandbox databases (PostgreSQL / MySQL / SQLite) are learner scratch space and are rebuilt by the seed.
set -euo pipefail
DIR="${DIR:-/opt/sqlab}"; OUT="$DIR/backups"; mkdir -p "$OUT"; chmod 700 "$OUT"
cd "$DIR"
set -a; . ./.env; set +a
f="$OUT/main-$(date -u +%Y%m%d-%H%M).sql.gz"
docker compose -f docker-compose.yml -f deploy/docker-compose.vps.yml exec -T main-db \
  pg_dump -U "${MAIN_DB_USER:-sqlab}" -d "${MAIN_DB_NAME:-sqlab}" --no-owner | gzip > "$f"
chmod 600 "$f"
find "$OUT" -name 'main-*.sql.gz' -mtime +14 -delete
echo "backup written: $f"
