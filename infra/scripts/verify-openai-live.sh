#!/usr/bin/env sh
set -eu

API_BASE_URL="${API_BASE_URL:-http://localhost:8000/api/v1}"
MODEL="${OPENAI_MODEL:-}"
MODE="${OPENAI_INTEGRATION_MODE:-live}"

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "FAIL: OPENAI_API_KEY is not set." >&2
  exit 2
fi

if [ "$MODEL" != "gpt-5.2" ]; then
  echo "FAIL: OPENAI_MODEL must be gpt-5.2." >&2
  exit 2
fi

if [ "$MODE" != "live" ]; then
  echo "FAIL: OPENAI_INTEGRATION_MODE must be live." >&2
  exit 2
fi

python3 - "$API_BASE_URL" <<'PY'
import json
import sys
import time
import urllib.error
import urllib.request

api_base = sys.argv[1].rstrip("/")
payload = {
    "raw_user_text": "I am a new patient with a shoulder fracture and no doctor preference.",
    "previous_state": {},
}
request = urllib.request.Request(
    f"{api_base}/conversation/interpret",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
start = time.monotonic()
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        status = response.status
except urllib.error.HTTPError as error:
    body = error.read().decode("utf-8")
    print(f"FAIL: backend returned HTTP {error.code}: {body[:500]}", file=sys.stderr)
    sys.exit(1)
except urllib.error.URLError as error:
    print(f"FAIL: could not reach backend: {error}", file=sys.stderr)
    sys.exit(1)

latency_ms = int((time.monotonic() - start) * 1000)
data = json.loads(body)
if status != 200:
    print(f"FAIL: unexpected HTTP {status}", file=sys.stderr)
    sys.exit(1)
if data.get("status") not in {"routing_ready", "clarification_required"}:
    print(f"FAIL: unexpected interpretation status {data.get('status')}", file=sys.stderr)
    sys.exit(1)
intent = data.get("intent") or {}
required = {
    "raw_user_text",
    "patient_status",
    "body_part",
    "issue_type",
    "preferred_doctor_name",
    "preferred_location_code",
    "clarification_required",
    "clarification_question",
    "caller_correction",
}
missing = required - set(intent)
if missing:
    print(f"FAIL: missing structured intent fields: {sorted(missing)}", file=sys.stderr)
    sys.exit(1)
print(json.dumps({"status": "PASS", "latency_ms": latency_ms, "interpretation_status": data["status"]}))
PY
