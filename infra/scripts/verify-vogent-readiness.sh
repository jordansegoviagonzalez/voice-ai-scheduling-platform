#!/usr/bin/env sh
set -eu

PUBLIC_URL="${PUBLIC_APP_URL:-}"

if [ -z "$PUBLIC_URL" ]; then
  echo "FAIL: PUBLIC_APP_URL is not set." >&2
  exit 2
fi

case "$PUBLIC_URL" in
  https://localhost*|https://127.0.0.1*|http://localhost*|http://127.0.0.1*)
    echo "FAIL: PUBLIC_APP_URL must be a non-local HTTPS URL for Vogent callbacks." >&2
    exit 2
    ;;
  https://*)
    ;;
  *)
    echo "FAIL: PUBLIC_APP_URL must start with https:// for Vogent callbacks." >&2
    exit 2
    ;;
esac

if [ -z "${VOGENT_FUNCTION_SECRET:-}" ]; then
  echo "FAIL: VOGENT_FUNCTION_SECRET is not set." >&2
  exit 2
fi

if [ -z "${VOGENT_WEBHOOK_SECRET:-}" ]; then
  echo "FAIL: VOGENT_WEBHOOK_SECRET is not set." >&2
  exit 2
fi

BASE_URL="${PUBLIC_URL%/}"
HEALTH_URL="$BASE_URL/api/v1/health"

curl -fsS -o /dev/null "$HEALTH_URL"

check_route() {
  route="$1"
  status="$(curl -sS -o /dev/null -w "%{http_code}" -X OPTIONS "$BASE_URL$route" || true)"
  case "$status" in
    200|204|405)
      ;;
    404|000)
      echo "FAIL: route is not reachable: $route" >&2
      exit 1
      ;;
    *)
      echo "FAIL: unexpected HTTP $status for route $route" >&2
      exit 1
      ;;
  esac
}

check_route "/api/v1/vogent/functions/patient-lookup"
check_route "/api/v1/vogent/functions/interpret-intent"
check_route "/api/v1/vogent/functions/routing-recommendations"
check_route "/api/v1/vogent/functions/confirm-slot"
check_route "/api/v1/vogent/functions/book-appointment"
check_route "/api/v1/vogent/webhooks"

if [ -n "${VOGENT_AGENT_ID:-}" ]; then
  AGENT_ID_CONFIGURED=true
else
  AGENT_ID_CONFIGURED=false
fi

printf '{"status":"PASS","ready_for_workspace_configuration":true,"workspace_connectivity_verified":false,"agent_id_configured":%s}\n' "$AGENT_ID_CONFIGURED"
