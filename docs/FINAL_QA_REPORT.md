# Final QA Report

Fresh verification performed on 2026-07-20 12:52 PDT.

## Root Causes Fixed

- The local `frontend` service ran `npm ci` at container startup. That made the runtime depend on package downloads every time and the container exited before Vite started.
- `frontend/package-lock.json` contained 360 tarball URLs for an internal OpenAI package mirror. Docker and host installs failed against that private mirror; the lockfile now resolves to `https://registry.npmjs.org/`.
- Vite's `/api` proxy defaulted to `localhost:8000`, which is incorrect inside the frontend container. Docker now sets `API_PROXY_TARGET=http://backend:8000`.
- The seed data used `O’Brien` while the official protocol specifies `O'Brien`. Seed lookup now updates the old curly-apostrophe row instead of duplicating the doctor.

## Files Changed

- `docker-compose.yml`
- `frontend/Dockerfile`
- `frontend/.dockerignore`
- `frontend/vite.config.ts`
- `frontend/package-lock.json`
- `backend/app/seed/data.py`
- `backend/app/seed/command.py`
- `backend/tests/test_api_workflows.py`
- `backend/tests/test_routing_scenarios.py`
- `docs/TEST_PLAN.md`
- `docs/FINAL_QA_REPORT.md`
- `PROJECT_STATUS.md`

## Local Docker Runtime

Command:

```bash
docker compose up -d --build
```

Result: passed.

Service status:

```text
db        Up, healthy
backend   Up, healthy, 0.0.0.0:8000->8000/tcp
frontend  Up, 0.0.0.0:5173->5173/tcp
```

Frontend logs show successful Vite startup:

```text
VITE v6.4.3 ready in 102 ms
Local:   http://localhost:5173/
Network: http://172.22.0.3:5173/
```

HTTP smoke checks from the host passed:

- `GET http://localhost:5173` returned `HTTP/1.1 200 OK` and frontend HTML.
- `GET http://localhost:8000/api/v1/health` returned `HTTP/1.1 200 OK` with `{"backend":"healthy","database":"healthy","status":"ok"}`.
- `GET http://localhost:5173/api/v1/health` returned the same backend JSON through the Vite proxy.

Headless Chrome rendered the Overview page with live dashboard data. Chrome emitted updater/process noise after termination, but no React crash page or fatal frontend render failure was observed. Frontend container logs remained clean.

SPA refresh checks returned frontend HTML with `200 OK` for:

- `/calls`
- `/calls/1`
- `/appointments`
- `/physicians`
- `/routing-audit`
- `/simulator`

## Database, Migration, and Seed

Commands:

```bash
docker compose exec backend alembic current
docker compose exec backend alembic upgrade head
docker compose exec backend flask --app app:create_app seed
```

Results:

- Alembic current: `20260720_0001 (head)`.
- `alembic upgrade head`: passed.
- Seed rerun: `Seed data is ready.`
- Seed idempotency before smoke mutations preserved stable protocol counts:
  - locations: 3
  - doctors: 12
  - doctor_locations: 14
  - doctor_capabilities: 32
  - patients: 5
  - patient_doctor_history: 1
  - slots: 560
  - appointments: 1
  - calls: 4
  - transcript_turns: 5
  - routing_decisions: 2

After the live simulator and booking-conflict smoke workflow, stable protocol counts remained correct and the database contained exactly one `Sarah O'Brien` row.

## API and Routing Verification

Live Compose API verification passed for:

- Health, doctors, locations, protocol.
- Patient create, lookup, and duplicate handling.
- Appointment list/detail and patient appointment lookup.
- Calls list/detail and transcript persistence through simulator booking.
- Routing audit persistence.
- Slots query and booked-slot exclusion.

Required routing scenarios verified live:

- Scenario A/G: new knee fracture - Walsh eligible but no open slots; Vasquez selected as fallback.
- Scenario B: new general spine pain - Mendez valid; Patel/Reed/O'Brien rejected.
- Scenario C: returning patient with Patel history - Patel eligible and recommended.
- Scenario D: new hand/wrist sports injury - Kim valid; Reed/Nguyen rejected.
- Scenario E: shoulder fracture - only Vasquez valid.
- Scenario F: preferred Chen for knee fracture - Chen rejected with plain-language reason; Walsh/Vasquez alternatives available.
- Scenario H: preferred North location unavailable - response explains the location mismatch and offers Vasquez at another location.
- Scenario I: concurrent same-slot booking - one request returned `201`, one returned `409`, and exactly one appointment existed for the slot.

Simulator workflow result:

- Preview created patient/call, transcript turns, and routing decisions.
- Booking created appointment `2` for call `5`.
- Call detail returned `SCHEDULED` with transcript length >= 6.
- Appointment appeared in appointment and patient-appointment APIs.
- Booked slot `445` was no longer returned as open.

## Automated Quality Gates

Backend, run inside the backend container after installing dev extras:

```text
pytest -q                       27 passed in 2.83s
ruff check .                    All checks passed!
ruff format --check .           39 files already formatted
mypy app                        Success: no issues found in 31 source files
```

## Pre-Live Integration Verification - 2026-07-20 17:15 PDT

Implemented and verified in this pass:

- Product branding changed to `Voice AI Scheduling Platform`.
- Dashboard readiness rows are backend-derived and no longer mark OpenAI or Vogent as operational without verification.
- Durable caller confirmation is required before API, simulator, or Vogent booking.
- Vogent function calls and webhooks persist idempotency/replay records.
- Vogent stale status events cannot overwrite terminal call state.
- GPT-5.2 adapter path uses the official OpenAI SDK/Responses API shape with strict structured-output validation.
- Conversation orchestration connects extracted intent to deterministic backend routing without model-side booking authority.

Verification commands:

```text
backend pytest                     42 passed in 3.86s
backend ruff check .               All checks passed!
backend mypy app                   Success: no issues found in 42 source files
frontend npm test -- --run         9 passed
frontend npm run lint              passed
frontend npm run build             passed
alembic upgrade head               upgraded to 20260720_0002
```

At that checkpoint, remaining live checks were credential-dependent: a real Vogent workspace/phone callback and a real OpenAI `gpt-5.2` request with `OPENAI_API_KEY`.

## Final Pre-Credential Hardening - 2026-07-20 20:21 PDT

Implemented in this pass:

- Removed unsafe normal-runtime SQLite fallback. `DATABASE_URL` is required, production must use PostgreSQL, and production rejects development `SECRET_KEY` placeholders.
- Added production guard against accidental OpenAI deterministic test mode unless explicitly approved.
- Added request-body, JSON string, caller-text, transcript-turn, and transcript-count limits.
- Added DB-backed fixed-window rate limiting for public write and Vogent integration endpoints.
- Hardened OpenAI provider error handling for authentication, model access, model availability, rate limit, timeout, network, malformed output, missing fields, extra fields, and unsafe medical/booking claims.
- Preserved validated conversation state on the `calls` row so a new backend process/session can reconstruct state.
- Strengthened Vogent idempotency conflict handling and terminal-state protection.
- Switched booking confirmation tokens to cryptographically strong `secrets.token_urlsafe(32)` values and verified single-use replay rejection.
- Added safe first-live helper scripts: `infra/scripts/verify-openai-live.sh` and `infra/scripts/verify-vogent-readiness.sh`.

Verification commands and results:

```text
backend pytest -q                  75 passed
backend ruff format --check .      58 files already formatted
backend ruff check .               All checks passed!
backend mypy app                   Success: no issues found in 43 source files
frontend npm run lint              passed
frontend npm test -- --run         3 files passed, 9 tests passed
frontend npm run build             passed, existing chunk-size warning
alembic upgrade head               upgraded through 20260720_0003
alembic downgrade/upgrade          20260720_0002 -> 20260720_0003 passed
seed twice                         stable counts after second run
docker compose config/build/up      passed
production compose config/build     passed
nginx -t                           passed
gunicorn --check-config            passed with strong SECRET_KEY override
production config negative check    failed fast on placeholder SECRET_KEY as expected
```

Seed counts after two runs:

```text
locations 3, doctors 12, doctor_locations 14, doctor_capabilities 32,
patients 12, patient_doctor_history 6, slots 616, appointments 6,
calls 8, transcript_turns 29, routing_decisions 182,
booking_confirmations 3, integration_request_logs 0,
integration_event_logs 0, api_rate_limit_buckets 0
```

Visual verification:

- Desktop screenshot: `/private/tmp/voice-ai-scheduling-platform-desktop.png`.
- Mobile screenshot: `/private/tmp/voice-ai-scheduling-platform-mobile.png`.
- Both showed `Voice AI Scheduling Platform`, backend-derived data, and no `MedRoute AI` or `Clinical Scheduling` branding.

Remaining blockers are external only: Vogent workspace/phone setup, public HTTPS endpoint, real phone call, and AWS EC2 launch. OpenAI GPT-5.2 is now locally live-verified in the later section below.

## OpenAI Environment Propagation and Live Verification - 2026-07-20 21:45 PDT

Root cause investigated:

- The real `OPENAI_API_KEY` was added to the ignored root `.env`, not `.env.example`.
- Root `.env` was valid and Docker Compose resolved the backend OpenAI variables correctly.
- The running backend container was created before `.env` was updated, so its process environment still had no OpenAI key.
- `.env.example` was not used by runtime configuration and no key material was printed or committed.

Fix:

```bash
docker compose up -d --force-recreate backend
```

Test isolation fix:

- After the backend container received the real key, two ordinary backend tests failed because the shared pytest fixture inherited `OPENAI_API_KEY`; one test made a live request unintentionally.
- `backend/tests/conftest.py` now deletes `OPENAI_API_KEY` and pins `OPENAI_MODEL=gpt-5.2` and `OPENAI_INTEGRATION_MODE=live` for default tests, preserving explicit fake-provider adapter tests.

Verified result:

- Backend container and Flask app config saw `OPENAI_API_KEY` present, `OPENAI_MODEL=gpt-5.2`, and `OPENAI_INTEGRATION_MODE=live`.
- `POST /api/v1/conversation/interpret` completed one synthetic live GPT-5.2 structured-output request through the application adapter.
- Dashboard API reported `OpenAI GPT-5.2` as `Connected`.
- Headless Chrome rendered the Overview page with `OpenAI GPT-5.2` as `Connected`.
- Vogent remained `Awaiting credentials`, which is expected until workspace secrets and a signed callback are configured.
- Backend verification after the test-fixture fix: `75 passed in 6.56s`, Ruff format/lint passed, and `mypy app` passed.
- Frontend verification after the runtime fix: ESLint passed, Vitest `9 passed`, and production build passed with the existing chunk-size warning.
- Redacted dev and production Compose config checks confirmed the backend OpenAI key is present without printing it; PostgreSQL has no published host port.

Frontend, run inside the frontend container:

```text
npm run lint                    passed
npm test -- --run               2 test files passed, 7 tests passed
npm run build                   passed
```

Frontend build output included the existing non-fatal Vite chunk-size warning for a `735.76 kB` JavaScript bundle.

## Production Validation

Commands:

```bash
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm --no-deps nginx nginx -t
```

Results:

- Production Compose config passed.
- Production backend and Nginx/frontend images built successfully.
- Nginx syntax check passed: `configuration file /etc/nginx/nginx.conf test is successful`.

The production Nginx run printed an orphan-container warning because the local development `frontend` service is not part of `docker-compose.prod.yml`; it did not affect the syntax check.

## Remaining Blockers

- Live Vogent phone call remains credential/workspace dependent.
- Live OpenAI GPT-5.2 has been verified locally; repeat it only when intentionally spending a credentialed synthetic request.
- AWS EC2 public deployment was not launched or verified from this local environment.

## Current Startup Commands

Attached mode:

```bash
cd /Users/djjordan/projects/ai-medical-scheduling-agent
docker compose up --build
```

Detached mode:

```bash
cd /Users/djjordan/projects/ai-medical-scheduling-agent
docker compose up -d --build
```

Shutdown:

```bash
docker compose down
```

Logs:

```bash
docker compose logs -f frontend backend db
```
