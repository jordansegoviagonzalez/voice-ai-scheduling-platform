# Test Plan

## Test strategy

The test suite separates deterministic domain behavior, HTTP workflows, concurrency, and frontend presentation. Backend tests use isolated databases for speed and reproducibility. Production uses PostgreSQL; the booking implementation adds PostgreSQL row locking and retains a database uniqueness constraint as the final invariant.

## Automated commands

```bash
source .venv/bin/activate
cd backend
pytest -q
ruff check .
ruff format --check .
mypy app
```

```bash
cd frontend
npm run lint
npm test -- --run
npm run build
```

```bash
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
./infra/scripts/smoke-test.sh http://localhost
```

The Docker commands require a host with Docker Engine and the Compose plugin.

## Required scenarios A-I

| Scenario | Expected behavior | Automated coverage |
|---|---|---|
| A — New knee fracture | Walsh and Vasquez protocol-valid; Chen, Torres, Brooks invalid | `test_routing_scenarios.py` |
| B — New general spine pain | Mendez valid; Patel/Reed reject new patient; O'Brien wrong issue type | `test_routing_scenarios.py` |
| C — Returning patient seen by Patel | Patel valid for Spine / General | `test_routing_scenarios.py` |
| D — New hand/wrist sports injury | Kim valid; Reed rejects new patient; Nguyen wrong issue type | `test_routing_scenarios.py` |
| E — Shoulder fracture | Only Vasquez valid | `test_routing_scenarios.py` |
| F — Invalid preferred Chen | Plain-language rejection; Walsh/Vasquez alternatives | `test_routing_scenarios.py`, API workflow test |
| G — First valid doctor unavailable | Walsh no slots; Vasquez selected as fallback | `test_routing_scenarios.py` |
| H — Preferred location unavailable | No valid preferred-location opening; alternatives returned with explanation | `test_routing_scenarios.py` |
| I — Concurrent same-slot booking | Exactly one success, one conflict, one appointment | `test_concurrency.py` |

## Backend unit/domain coverage

| Requirement | Coverage |
|---|---|
| Exact body-part and issue-type match | Routing scenario tests |
| General does not match Fracture | Routing/normalization tests |
| General does not match Joint Replacement | Routing tests |
| General does not match Sports Medicine | Routing tests |
| New-patient rejection | Scenarios B/D |
| Returning-to-same-doctor exception | Scenario C |
| Returning to facility but new to doctor | Dedicated routing test |
| Location preference | Scenarios H and ranking tests |
| Multi-location physician | Vasquez/Torres slot tests |
| Preferred-doctor rejection | Scenario F |
| Fallback selection | Scenario G |
| No-slot handling | Availability-exception tests |
| Stable deterministic ranking | Repeated recommendation assertion |
| Slot-location validation | Booking/domain test |
| Caller phrase normalization | `test_normalization.py` |
| Ambiguous/unsupported values | Validation tests |

## Backend integration coverage

| API behavior | Coverage |
|---|---|
| Health and database check | API workflow test |
| Patient lookup | API workflow test |
| Patient creation | API workflow test |
| Duplicate patient handling | API workflow test |
| Doctors, locations, protocol | API workflow test |
| Routing endpoint | API workflow and scenario tests |
| Open-slot endpoint | API workflow test |
| Appointment booking | API workflow test |
| Durable caller confirmation before booking | `test_confirmation.py`, API workflow test |
| Double-booking conflict | API workflow and concurrency tests |
| Appointment lookup | API workflow test |
| Call creation/update | API workflow test |
| Transcript persistence | API workflow test |
| Full call review | API workflow test |
| Routing-audit persistence | API workflow test |
| Simulator preview and book | API workflow test |
| PostgreSQL-only runtime guardrails | `test_config.py` |
| Request body and field-size limits | `test_security_boundaries.py` |
| DB-backed rate-limit boundary | `test_security_boundaries.py` |
| OpenAI GPT-5.2 structured-intent adapter | `test_openai_adapter.py` |
| OpenAI provider auth/model/rate/network/server failures | `test_openai_adapter.py` |
| OpenAI malformed, missing, extra, unsafe output rejection | `test_openai_adapter.py` |
| Conversation orchestration to deterministic routing | `test_conversation_orchestration.py` |
| Conversation state reconstruction across DB sessions | `test_conversation_orchestration.py` |
| Vogent idempotency/replay/terminal state handling | `test_vogent_adapter.py` |
| Concurrent booking and idempotency-log protection | `test_concurrency.py` |

## Frontend coverage

| UI requirement | Coverage |
|---|---|
| Calls table renders API data | `calls-page.test.tsx` |
| Status badges | `components.test.tsx` |
| Full transcript timeline | `components.test.tsx` |
| Appointment summary | `components.test.tsx` |
| Human-readable routing rejection | `components.test.tsx` |
| Empty state | `components.test.tsx` |
| Error state | `components.test.tsx` |
| Status/search filter behavior | `calls-page.test.tsx` |
| Product branding | `branding-status.test.tsx` |
| Backend-derived OpenAI/Vogent status panel | `branding-status.test.tsx` |

## Manual QA matrix

### Responsive and accessibility

- Desktop at 1440 px and 1280 px.
- Tablet-width navigation behavior.
- Visible keyboard focus on links, buttons, forms, and table actions.
- Logical heading hierarchy.
- Form labels associated with inputs.
- Status never represented only by color.
- Loading, error, and empty states remain understandable.

### End-to-end simulator

1. Run the seed twice and verify counts do not increase unexpectedly.
2. Preview Shoulder / Fracture and confirm only Vasquez is valid.
3. Preview new Knee / Fracture with Dr. Chen preferred.
4. Confirm Chen rejection, Walsh no slots, and Vasquez fallback.
5. Book the Vasquez slot.
6. Confirm a missing or mismatched `confirmation_token` is rejected.
7. Confirm the appointment appears in Calls and Appointments.
8. Confirm transcript and routing decisions appear in call detail.
9. Attempt to book the same slot again and confirm deterministic rejection.

### Vogent credentialed test

1. Configure the shared function-call secret.
2. Configure a signed webhook secret.
3. Run `./infra/scripts/verify-vogent-readiness.sh` with a non-local HTTPS `PUBLIC_APP_URL`.
4. Run patient lookup from the Vogent test flow.
5. Run GPT-5.2 intent extraction only after backend OpenAI credentials are configured.
6. Run routing with invalid Dr. Chen preference.
7. Confirm function output contains caller-safe summary and live slot IDs.
8. Run `confirm-slot` and verify the agent repeats physician, location, date, and time.
9. Run booking with the returned `confirmation_token` and confirm response only after success.
10. Retry the same function payload and confirm the stored response is returned.
11. Confirm transcript/status webhook data appears in dashboard.
12. Export the verified workspace flow and add it under `vogent/flow-export/`.

### OpenAI credentialed test

Run only after intentionally setting a real key:

```bash
OPENAI_API_KEY=<key> OPENAI_MODEL=gpt-5.2 OPENAI_INTEGRATION_MODE=live \
  ./infra/scripts/verify-openai-live.sh
```

The helper executes one paid synthetic interpretation request and fails nonzero if the backend response is not a valid structured scheduling intent.

## Exit criteria

- All automated tests pass.
- Lint, type-check, and production frontend build pass.
- Migration and seed run successfully from a clean database.
- Seed is idempotent.
- Health check passes under Gunicorn.
- Docker Compose builds and starts on a Docker-capable host.
- No core dashboard page uses hardcoded records.
- No secret or synthetic-data violation appears in the repository or video.

Latest full-suite result after OpenAI live local verification: backend `pytest -q` passed with `75` tests, Ruff format/lint and mypy passed, frontend Vitest passed with `9` tests, frontend lint passed, and frontend build passed with the existing chunk-size warning. Re-run before submission after any code change.
