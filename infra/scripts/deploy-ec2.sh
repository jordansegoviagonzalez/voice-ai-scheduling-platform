#!/usr/bin/env bash
set -euo pipefail
docker compose -f docker-compose.prod.yml pull db
docker compose -f docker-compose.prod.yml build --pull
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
