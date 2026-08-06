# QA Report

Date: 2026-08-05

## Summary

The repository contains a working local implementation of the medical scheduling workflow with deterministic backend routing, transactional booking, persisted transcripts, and a React review dashboard. The validation scope is local Docker and automated tests unless explicitly noted.

## Runtime Checks

- PASS: Docker Compose defines `db`, `backend`, and `frontend` services.
- PASS: PostgreSQL runs behind the backend and is not intended to be public.
- PASS: Backend health endpoint reports application and database health.
- PASS: Frontend serves the React application.
- PASS: Production Compose config uses Gunicorn behind Nginx.

## Database And Seed Checks

- PASS: Alembic migrations are versioned and run to the current head.
- PASS: Seed behavior is idempotent for protocol data.
- PASS: Physician, location, capability, slot, patient, appointment, call, transcript, and routing-audit records are represented in normalized tables.
- PASS: Synthetic patient records are used for testing and demonstration.
- PASS: Seeded data supports fallback and duplicate-booking scenarios.

## Routing Checks

- PASS: Final eligibility uses exact body-part and issue-type capability rows.
- PASS: General issue type does not match fracture, joint replacement, or sports medicine.
- PASS: New-patient restrictions are evaluated per physician.
- PASS: A returning facility patient is still ineligible for a no-new-patients physician unless that patient has prior history with that physician.
- PASS: Preferred physicians are validated and rejected with patient-safe explanations when unsupported.
- PASS: Preferred location is prioritized without silently booking an alternate location.
- PASS: Real open slots are returned from the database.
- PASS: Fallback recommendations are provided when an otherwise valid physician has no open slots.

## Booking Checks

- PASS: Booking validates patient, slot, physician eligibility, physician location, and request context before committing.
- PASS: Booking uses transactional database writes.
- PASS: A unique appointment-per-slot constraint protects against duplicate bookings.
- PASS: Conflict handling returns an error instead of creating duplicate appointments.
- PASS: Confirmation is required before booking through public scheduling flows.

## Dashboard Checks

- PASS: Calls and web-chat sessions are displayed from backend API data.
- PASS: Call detail displays transcript, patient context, booking status, appointment details, and routing decisions.
- PASS: Appointment records link back to the correct source channel.
- PASS: Physicians and protocol pages display seeded protocol data.
- PASS: Loading, empty, and error states are represented in the frontend.

## Integration Checks

- PASS: Vogent function endpoints exist for patient lookup, intent interpretation, routing recommendations, slot confirmation, and booking.
- PASS: Vogent webhooks are handled through an adapter boundary with replay/idempotency controls.
- PASS: OpenAI intake is server-side only and never called from browser code.
- PASS: Structured intake output is validated before backend routing and booking.
- PARTIAL: Live Vogent operation requires external workspace configuration and secrets.
- PARTIAL: Live OpenAI operation requires a server-side credential and model access.

## Quality Gates

Expected local verification commands:

```bash
make test
make lint
make build
```

Equivalent direct commands:

```bash
cd backend
pytest -q
ruff check .
ruff format --check .
mypy app

cd ../frontend
npm test -- --run
npm run lint
npm run build
```

## Remaining Risks

- PARTIAL: Browser automation coverage can be expanded for the patient chat booking path and dashboard review path.
- PARTIAL: Production security hardening remains incomplete for real patient use.
- PARTIAL: Live third-party integrations require credentialed validation outside the committed source.
- NOT IMPLEMENTED: Cancellation, rescheduling, reminders, billing, insurance verification, and EHR integration.
