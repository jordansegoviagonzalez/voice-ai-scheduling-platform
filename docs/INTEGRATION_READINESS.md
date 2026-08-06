# Integration Readiness

Date: 2026-08-05

## Summary

The repository includes integration boundaries for Vogent voice scheduling and OpenAI-backed intake interpretation. Both integrations preserve the core product rule: external conversational systems may collect or normalize information, but backend domain services remain authoritative for physician eligibility, patient history, slot availability, confirmation, and booking.

## Current Status

| Area | Status |
|---|---|
| Flask API and scheduling domain services | PASS |
| PostgreSQL-backed routing and booking | PASS |
| React review dashboard | PASS |
| Vogent adapter routes and tool blueprints | PASS |
| Vogent live workspace connection | PARTIAL |
| OpenAI server-side intake adapter | PASS |
| OpenAI live credentialed operation | PARTIAL |
| Production authentication hardening | PARTIAL |

## Vogent Boundary

Implemented endpoints:

- `/api/v1/vogent/functions/patient-lookup`
- `/api/v1/vogent/functions/interpret-intent`
- `/api/v1/vogent/functions/routing-recommendations`
- `/api/v1/vogent/functions/confirm-slot`
- `/api/v1/vogent/functions/book-appointment`
- `/api/v1/vogent/webhooks`

Implemented protections:

- Shared-secret validation for configured function calls.
- Webhook signature validation when a webhook secret is configured.
- Idempotency handling for function retries and duplicate webhook events.
- Terminal-state protection for scheduled, failed, abandoned, and redirected calls.
- Required caller confirmation token before appointment booking.

External setup still required:

- Public HTTPS application endpoint.
- Vogent workspace function IDs.
- Webhook signing secret.
- Function shared secret.
- Agent or phone/web-call binding.
- Credentialed call test in the Vogent workspace.

## OpenAI Boundary

Implemented behavior:

- Server-side OpenAI adapter for structured intake.
- Configurable model through `OPENAI_MODEL`.
- Live mode fails closed when credentials are unavailable.
- Test mode uses deterministic fixtures only when explicitly configured.
- Structured response validation rejects missing fields, unsupported enums, malformed output, and unsafe medical or booking claims.
- Deterministic backend routing is called only after validated intake data is available.

External setup still required:

- Server-side OpenAI API credential supplied through environment configuration.
- Account access to the configured model.
- Credentialed synthetic request using the verification helper before relying on live mode.

Verification helper:

```bash
OPENAI_API_KEY=<key> OPENAI_MODEL=gpt-5.2 OPENAI_INTEGRATION_MODE=live \
  ./infra/scripts/verify-openai-live.sh
```

## Request Protection

- Request body limits are configured through `MAX_CONTENT_LENGTH`.
- Caller text and transcript length limits are enforced at the API boundary.
- Public write and integration endpoints use DB-backed fixed-window rate limiting.
- Booking confirmation tokens are generated server-side and are single-use.

## Reviewer-Facing Verification

Recommended checks:

```bash
make test
make lint
make build
docker compose up --build
curl --fail http://localhost:8000/api/v1/health
```

Credentialed integration checks should be run only after environment variables are set outside source control.

## Limitations

- The repository does not include workspace-specific Vogent IDs, phone bindings, or secrets.
- The repository does not include OpenAI credentials.
- Live third-party integration success should be verified in the target environment before public claims are made.
