#!/usr/bin/env bash
set -euo pipefail
mkdir -p backups
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom \
  > "backups/scheduling-${STAMP}.dump"
printf 'Backup written to backups/scheduling-%s.dump\n' "$STAMP"
