# Integration Readiness

Date/time: 2026-07-20 22:02 PDT

## Executive Summary

The credential-free pre-live integration work is implemented and verified locally. A credentialed OpenAI GPT-5.2 structured-output request has also been verified through the application adapter after adding a real key to the ignored root `.env` and recreating the backend container. The backend owns deterministic physician routing, patient status evaluation, slot availability, explicit caller confirmation, and final booking. Vogent and OpenAI can collect or normalize caller information, but neither integration is treated as the final authority for eligibility, availability, or booking.

Live readiness remains credential-dependent:

- Vogent requires a public HTTPS deployment, workspace function IDs, webhook signing secret, phone or web-call binding, and a signed callback test.
- OpenAI requires `OPENAI_API_KEY`, account-level access to `gpt-5.2`, and a successful live Responses API structured-output call. The local Docker environment passed that check on 2026-07-20.

## Current Status

| Area | Status |
|---|---|
| Core Flask API, PostgreSQL, routing, transcripts | Operational in local Docker |
| Dashboard readiness panel | Backend-derived; no secrets exposed |
| Vogent adapter | Adapter ready when credentials/public HTTPS are configured; not shown as operational until a live success is recorded |
| OpenAI GPT-5.2 | Connected in local Docker after one live structured-output request; still fails closed when `OPENAI_API_KEY` is missing |
| Booking | Requires persisted caller confirmation token before appointment creation |
| Simulator | Uses the same confirmation and booking services as Vogent/API flows |

## Final Pre-Credential Hardening

- Normal runtime now requires `DATABASE_URL` and rejects silent SQLite fallback; production also rejects non-PostgreSQL URLs and development placeholder `SECRET_KEY` values.
- Production rejects `OPENAI_INTEGRATION_MODE=test` unless `ALLOW_OPENAI_TEST_MODE_IN_PRODUCTION=true` is explicitly set.
- OpenAI live mode fails closed without `OPENAI_API_KEY`, preserves `OPENAI_MODEL=gpt-5.2`, and does not fall back to deterministic fixtures.
- Public write and integration endpoints enforce request-size and field-size limits.
- A DB-backed fixed-window limiter protects conversation interpretation, patient creation, confirmations, booking, Vogent function calls, and Vogent webhooks.
- Vogent replay defense uses persisted event keys and payload hashes. Official Vogent docs reviewed do not document a signed timestamp header, so no timestamp replay window was invented.
- Terminal call statuses cannot be overwritten by stale status webhooks, and transcript events cannot alter terminal booking status.
- First-live helper scripts are ready under `infra/scripts/`; the OpenAI app adapter was verified with one synthetic live request, while Vogent remains credential/workspace dependent.

## Implemented Boundaries

- `backend/app/integrations/openai/`: official SDK Responses API adapter, structured-output schema, prompt boundary, error mapping.
- `backend/app/services/conversation.py`: orchestration from GPT-extracted intent to deterministic routing.
- `backend/app/services/confirmation.py`: durable explicit caller confirmation and stale/mismatch rejection.
- `backend/app/services/idempotency.py`: Vogent function retry and webhook replay protection.
- `backend/app/services/rate_limit.py`: DB-backed fixed-window limiter for protected public/integration POST routes.
- `backend/app/services/integration_status.py`: backend-derived readiness statuses.
- `backend/app/routes/vogent.py`: patient lookup, intent extraction, routing, confirmation, booking, and webhooks.

## OpenAI Contract

Configured model: `OPENAI_MODEL=gpt-5.2`.

Mode behavior:

- `OPENAI_INTEGRATION_MODE=live`: requires `OPENAI_API_KEY`; no fake fallback is used.
- `OPENAI_INTEGRATION_MODE=test`: deterministic fixture path for tests/dev only.

Structured intent fields:

- `raw_user_text`
- `patient_status`
- `body_part`
- `issue_type`
- `preferred_doctor_name`
- `preferred_location_code`
- `clarification_required`
- `clarification_question`
- `caller_correction`

Validation rejects unsupported enums, unknown doctor names, unknown location codes, unsafe medical/booking claims, and malformed output before deterministic routing is called.

## Vogent Contract

Function endpoints:

- `/api/v1/vogent/functions/patient-lookup`
- `/api/v1/vogent/functions/interpret-intent`
- `/api/v1/vogent/functions/routing-recommendations`
- `/api/v1/vogent/functions/confirm-slot`
- `/api/v1/vogent/functions/book-appointment`

Webhook endpoint:

- `/api/v1/vogent/webhooks`

The booking function requires `confirmation_token` from `confirm-slot`. Duplicate function calls with the same idempotency key or identical payload return the previously stored result when safe. Duplicate webhook events short-circuit before mutating call state, and stale status events cannot overwrite scheduled, failed, abandoned, or redirected calls.

Request protection defaults:

- Body limit: `MAX_CONTENT_LENGTH=262144`.
- Caller text: `RAW_USER_TEXT_MAX_LENGTH=4000`.
- Transcript turn text: `TRANSCRIPT_TURN_MAX_LENGTH=2000`.
- Transcript turns per webhook: `TRANSCRIPT_TURN_MAX_COUNT=200`.
- Protected POST rate limit: `60` requests per `60` seconds per route/identifier.

## Official Documentation Reviewed

OpenAI:

- https://developers.openai.com/api/docs/models
- https://developers.openai.com/api/docs/models/gpt-5.2
- https://platform.openai.com/docs/api-reference/responses
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/reference/overview#authentication
- https://developers.openai.com/api/reference/resources/models/methods/list

Vogent:

- https://docs.vogent.ai/platform-overview/tools/function-calling
- https://docs.vogent.ai/platform-overview/api-settings
- https://docs.vogent.ai/developers/webhooks/dial-inbound
- https://docs.vogent.ai/developers/webhooks/dial-status-updated
- https://docs.vogent.ai/developers/webhooks/dial-transcript
- https://docs.vogent.ai/developers/webhooks/function-call

## Verification Snapshot

- Backend tests: `75 passed in 6.56s`
- Backend lint: `ruff check .` passed
- Backend format: `ruff format --check .` passed
- Backend type check: `mypy app` passed
- Frontend tests: `9 passed`
- Frontend lint/build: passed; production build retained the existing non-fatal chunk-size warning
- Docker/config: dev and production Compose config checked with redacted OpenAI output; only frontend/dev and Nginx/prod publish host ports, and PostgreSQL publishes no host port
- Alembic migration: upgraded through `20260720_0003`
- Seed: two consecutive runs produced stable protocol and workflow counts

## Live OpenAI Verification - 2026-07-20 21:45 PDT

- PASS - Root `.env` exists, is ignored by Git, and contains `OPENAI_API_KEY`, `OPENAI_MODEL=gpt-5.2`, and `OPENAI_INTEGRATION_MODE=live`; checks printed only presence/length, never the key value.
- PASS - `docker compose config` resolves the backend OpenAI environment from root `.env`.
- PASS - The running backend initially had no OpenAI key because the container was created before `.env` was updated.
- PASS - Recreated only `backend` with `docker compose up -d --force-recreate backend`.
- PASS - Backend container and Flask app config then reported `OPENAI_API_KEY` present, `OPENAI_MODEL=gpt-5.2`, and `OPENAI_INTEGRATION_MODE=live`.
- PASS - One synthetic request through `POST /api/v1/conversation/interpret` succeeded via `ConversationOrchestrator -> OpenAIIntentAdapter -> SDKResponsesProvider`.
- PASS - Dashboard API now reports `OpenAI GPT-5.2` as `Connected` with detail `Latest live GPT-5.2 structured intent extraction succeeded.`
- PASS - Headless Chrome rendered the Overview page with `OpenAI GPT-5.2` shown as `Connected`.
- PASS - Default backend pytest fixture now deletes `OPENAI_API_KEY` so routine tests cannot accidentally make paid live OpenAI calls from a credentialed container.
- PARTIAL - Vogent still reports `Awaiting credentials` because workspace secrets and a verified signed callback are not configured.
