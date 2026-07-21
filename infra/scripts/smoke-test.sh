#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${1:-http://localhost}"
curl --fail --silent --show-error "${BASE_URL}/api/v1/health"
curl --fail --silent --show-error "${BASE_URL}/api/v1/protocol" >/dev/null
curl --fail --silent --show-error "${BASE_URL}/api/v1/dashboard/overview" >/dev/null
printf '\nSmoke test passed for %s\n' "$BASE_URL"
