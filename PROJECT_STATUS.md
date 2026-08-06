# Project Status

Updated: 2026-08-05

## Current Phase

PARTIAL - Phase 3 multi-organization foundation is implemented at the backend data-model and service-boundary level. Organization API endpoints and admin UI are not implemented yet.

## Product Status

The application is a Flask, PostgreSQL, and React scheduling platform for orthopedic appointment intake. The voice, simulator, and web-chat channels use shared backend scheduling, routing, booking, and persistence services.

Overall status remains PARTIAL. The core scheduling workflow has been implemented and locally verified through targeted backend, frontend, migration, and smoke checks. Live Vogent operation, credentialed OpenAI verification, production authentication hardening, and final EC2 verification remain outside the current implemented scope.

## Phase 3 Foundation Status

- PASS: Added an `Organization` model and default organization helper.
- PASS: Added organization ownership to doctors, locations, slots, appointments, calls, routing decisions, and chat sessions.
- PASS: Added default-organization scoping to legacy routing, booking, calls, protocol, slots, dashboard, simulator, chat, and Vogent adapter paths.
- PASS: Added a migration that creates the default organization, backfills existing rows, requires organization ownership, and adds organization-scoped uniqueness and indexes for the first core scheduling tables.
- PASS: Added focused regression tests for default organization creation/backfill, protocol visibility, legacy chat-session scoping, and routing-audit scoping.
- PARTIAL: Patient records, patient-doctor history, transcript turns, booking confirmations, and integration logs are not fully organization-scoped yet.
- NOT IMPLEMENTED: Organization administration API.
- NOT IMPLEMENTED: Organization administration GUI.
- NOT IMPLEMENTED: Organization-specific patient chat links.
- NOT IMPLEMENTED: Organization-specific Vogent phone-number or tenant mapping.

## Verified Capabilities

- PASS: Flask backend starts through Docker Compose.
- PASS: PostgreSQL-backed migrations run through the current Alembic head.
- PASS: Idempotent seed data creates the physician protocol, locations, capabilities, synthetic patients, slots, calls, appointments, and routing audit data.
- PASS: Patient lookup and duplicate-safe patient creation are implemented.
- PASS: Exact physician routing evaluates body part, issue type, new-patient eligibility, physician locations, patient-doctor history, and real slot availability.
- PASS: General issue type does not act as a wildcard for fracture, joint replacement, or sports medicine.
- PASS: Preferred physician validation rejects unsupported requests with patient-safe explanations.
- PASS: Preferred location handling prioritizes valid slots at that location and provides alternatives when needed.
- PASS: Fallback recommendations preserve the scheduling context when the first eligible physician has no open slot.
- PASS: Appointment booking revalidates eligibility, verifies slot location, claims the slot transactionally, and prevents duplicate appointments for one slot.
- PASS: Calls, transcript turns, web-chat messages, booking status, appointment details, and routing decisions are persisted for dashboard review.
- PASS: React dashboard retrieves real backend data for calls, web chat sessions, patients, appointments, physicians, routing audit, and simulator views.
- PASS: Patient-facing web chat uses backend scheduling and routing services rather than a separate frontend routing engine.
- PASS: OpenAI intake is called only from the Flask backend and uses structured-output validation before deterministic routing or booking services are called.
- PASS: Vogent function endpoints and webhook adapter boundaries are present with shared-secret and idempotency protections.
- PASS: Local Docker runtime is configured for `db`, `backend`, and `frontend`.

## Recent Verification

- PASS: `python3 -m compileall -q backend/app backend/tests`
- PASS: `docker compose run --rm --no-deps backend ruff check .`
- PASS: `docker compose run --rm --no-deps backend ruff format --check .`
- PASS: `docker compose run --rm --no-deps backend mypy app`
- PASS: Targeted backend tests for organization foundation, routing scenarios, API workflows, chat entry, chat intake, and booking confirmation: 115 passed, 4 existing datetime deprecation warnings.
- PASS: Vogent adapter tests: 10 passed.
- PASS: Alembic upgrade and seed completed against a fresh temporary PostgreSQL Compose project.

## Known Limitations

- PARTIAL: Full local stack and browser verification should be rerun after local Docker database configuration is reconciled.
- PARTIAL: Live Vogent operation requires workspace credentials, tool IDs, webhook secrets, phone-number bindings, and final flow setup.
- PARTIAL: Live OpenAI operation requires a server-side API key and account access to the configured model.
- PARTIAL: Production authentication is intentionally minimal and should be hardened before real patient usage.
- PARTIAL: Browser verification has been handled through focused tests and smoke checks, not a full end-to-end browser suite.
- NOT IMPLEMENTED: Cancellation, rescheduling, reminders, billing, insurance verification, and EHR integration.
- NOT IMPLEMENTED: Managed database, WAF, centralized logs, alerting, and production backup automation.

## Next Engineering Priorities

1. Stabilize the local Docker runtime and rerun full-stack smoke checks.
2. Add organization API endpoints for listing, creating, and updating organizations.
3. Add organization-aware admin UI controls after the API exists.
4. Extend organization scoping to patient memberships, patient-doctor history, confirmations, and integration logs.
5. Run a credentialed Vogent end-to-end scheduling call in the target workspace.
6. Harden authentication and authorization before any real deployment.
7. Expand browser-based end-to-end coverage for patient chat and review-dashboard workflows.
