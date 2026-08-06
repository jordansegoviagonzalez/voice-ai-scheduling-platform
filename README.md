# AI Medical Scheduling Agent

A voice-ready and web-ready medical scheduling platform for orthopedic appointment booking. The system combines a Flask API, deterministic physician routing, PostgreSQL scheduling data, a transactional booking workflow, Vogent integration boundaries, OpenAI-backed intake interpretation, and a React review dashboard.

The central design rule is that conversational channels collect and normalize information, while backend domain services remain the authority for physician eligibility, patient-doctor history, location validity, slot availability, and appointment booking.

## What Is Included

- Flask application factory with versioned API routes.
- SQLAlchemy 2.x models and Alembic migrations for patients, physicians, locations, capabilities, slots, appointments, calls, transcripts, web chat sessions, confirmations, and integration logs.
- PostgreSQL-backed scheduling data with idempotent protocol and slot seeding.
- Deterministic physician routing using exact body-part and issue-type capability matches.
- Per-physician new-patient eligibility based on patient-doctor history.
- Real slot lookup, preferred physician validation, preferred location prioritization, and fallback recommendations.
- Transactional appointment booking with a final eligibility check and duplicate-slot protection.
- Call and web-chat transcript persistence for operational review.
- Vogent adapter endpoints and tool blueprints for voice scheduling integration.
- OpenAI GPT-5.2 structured intake adapter behind the Flask backend.
- React/TypeScript dashboard for calls, web chat sessions, patients, appointments, physicians, routing audit, and local simulation.
- Docker Compose configurations for local development and single-host production deployment.
- Backend and frontend tests covering routing, booking, account access, web chat, Vogent boundaries, and security checks.

## Product Boundary

This application schedules medical appointments. It does not diagnose, triage, recommend treatment, generate clinical notes, verify insurance, process payments, or claim HIPAA compliance. All committed patient data is synthetic demonstration data.

## Architecture

```mermaid
flowchart TB
    Caller["Caller"] --> Vogent["Vogent voice flow"]
    BrowserPatient["Patient web chat"] --> API["Flask API"]
    Dashboard["React review dashboard"] --> API
    Simulator["Local simulator"] --> API

    Vogent --> Adapter["Vogent adapter routes"]
    Adapter --> API
    API --> Domain["Scheduling and routing services"]
    API --> Intake["OpenAI structured intake adapter"]
    Intake --> Domain
    Domain --> Database["PostgreSQL"]

    Nginx["Nginx production entrypoint"] --> Dashboard
    Nginx --> BrowserPatient
    Nginx --> API
```

More detail is available in:

- [Architecture](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Entity Relationship Diagram](docs/ERD.md)
- [Routing Rules](docs/ROUTING_RULES.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Test Plan](docs/TEST_PLAN.md)

## Repository Structure

```text
.
├── backend/               Flask app, domain services, migrations, tests
├── frontend/              React dashboard and patient chat interface
├── infra/                 Nginx and deployment helper scripts
├── vogent/                Voice integration docs and tool definitions
├── docs/                  Technical architecture, API, deployment, QA docs
├── docker-compose.yml     Local development stack
├── docker-compose.prod.yml
└── Makefile
```

## Local Setup With Docker

Prerequisites:

- Docker Engine with the Compose plugin
- Git

```bash
cp .env.example .env
docker compose up --build
```

Local endpoints:

- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8000/api/v1/health`

The backend container runs migrations and idempotent seed data on startup.

When changing environment values after containers already exist, recreate the affected service so Docker injects the new values:

```bash
docker compose up -d --force-recreate backend
```

## Local Setup Without Docker

Prerequisites:

- Python 3.12+
- PostgreSQL 15+
- Node.js 22+
- npm

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -e './backend[dev]'
cd frontend
npm ci
cd ..
```

Set `DATABASE_URL` in `.env`, then run:

```bash
source .venv/bin/activate
set -a
source .env
set +a
cd backend
alembic upgrade head
flask --app app:create_app seed
gunicorn --bind 127.0.0.1:8000 --workers 2 --threads 2 app.wsgi:app
```

In a second terminal:

```bash
cd frontend
npm run dev
```

## Environment Variables

Copy `.env.example` to `.env`. Never commit `.env`.

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development`, `test`, or `production` |
| `SECRET_KEY` | Flask signing secret; use a generated production value |
| `POSTGRES_DB` | PostgreSQL database name |
| `POSTGRES_USER` | PostgreSQL user |
| `POSTGRES_PASSWORD` | PostgreSQL credential |
| `DATABASE_URL` | SQLAlchemy database URL for non-Compose execution |
| `FRONTEND_ORIGIN` | Allowed browser origin |
| `PUBLIC_APP_URL` | Public application URL |
| `LOG_LEVEL` | Structured log level |
| `VOGENT_API_KEY` | Optional Vogent API credential |
| `VOGENT_WEBHOOK_SECRET` | Vogent webhook-signature secret |
| `VOGENT_FUNCTION_SECRET` | Shared secret for configured Vogent function calls |
| `VOGENT_AGENT_ID` | Optional Vogent agent identifier |
| `OPENAI_API_KEY` | Server-side OpenAI credential; never expose to browser code |
| `OPENAI_MODEL` | Expected model name, currently `gpt-5.2` |
| `OPENAI_INTEGRATION_MODE` | `live` for OpenAI calls or `test` for deterministic fixtures |
| `OPENAI_TIMEOUT_SECONDS` | OpenAI request timeout |
| `OPENAI_MAX_RETRIES` | Bounded retry count |
| `MAX_CONTENT_LENGTH` | Flask request-body limit |
| `JSON_STRING_FIELD_MAX_LENGTH` | Global JSON string limit |
| `RAW_USER_TEXT_MAX_LENGTH` | Caller utterance limit for intake interpretation |
| `TRANSCRIPT_TURN_MAX_LENGTH` | Single transcript-turn text limit |
| `TRANSCRIPT_TURN_MAX_COUNT` | Transcript turns accepted per webhook payload |
| `RATE_LIMIT_ENABLED` | Enables DB-backed fixed-window rate limiting |
| `RATE_LIMIT_WINDOW_SECONDS` | Rate-limit window |
| `RATE_LIMIT_MAX_REQUESTS` | Protected POST requests per route/identifier/window |
| `SESSION_IDLE_TIMEOUT_MINUTES` | Patient/admin idle timeout |
| `ALLOW_OPENAI_TEST_MODE_IN_PRODUCTION` | Must be explicitly enabled before production can use test mode |

## Database

```bash
make migrate
make seed
```

The seed command is idempotent and creates:

- The configured physician protocol and practice locations.
- Exact physician capability rows.
- Synthetic patients and patient-doctor history.
- Realistic future slots.
- Sample calls, appointments, transcript turns, and routing decisions for dashboard review.

## Tests And Quality Checks

With Docker running:

```bash
make test
make lint
make build
```

For local non-Docker development, use the backend and frontend package commands directly:

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

## Smoke Testing

The smoke script uses environment variables and does not store credentials in source control:

```bash
SMOKE_BASE_URL=http://localhost:8000/api \
SMOKE_PATIENT_EMAIL=<synthetic-patient-email> \
SMOKE_PATIENT_PASSWORD=<synthetic-patient-password> \
SMOKE_ADMIN_EMAIL=<admin-email> \
SMOKE_ADMIN_PASSWORD=<admin-password> \
python scripts/smoke/smoke_test.py
```

Use only synthetic patient accounts for smoke tests.

## Vogent Integration

The repository includes backend endpoints, security checks, idempotency handling, and tool blueprints for Vogent. Workspace-specific function IDs, webhook secrets, phone-number bindings, and final flow setup are configured outside source control.

See [Vogent integration documentation](vogent/README.md).

## OpenAI Intake

Patient-facing web chat calls OpenAI only through the Flask backend. The frontend never receives the OpenAI API key. Structured intake output is validated before deterministic backend routing or booking services are called.

Live OpenAI checks are credential-gated. Use the helper script only after providing credentials through environment variables:

```bash
OPENAI_API_KEY=<key> OPENAI_MODEL=gpt-5.2 OPENAI_INTEGRATION_MODE=live \
  ./infra/scripts/verify-openai-live.sh
```

## Production Deployment Overview

```bash
cp .env.example .env
# Set production environment values outside source control.
docker compose -f docker-compose.prod.yml up -d --build
```

The production Compose topology runs PostgreSQL, Gunicorn, and Nginx on a single host. Nginx is the public entrypoint. PostgreSQL is internal only and uses a named volume.

See [Deployment Guide](docs/DEPLOYMENT.md) for EC2 setup, security groups, restart commands, logs, health checks, backups, and optional HTTPS.

## Known Limitations

- Production authentication is intentionally minimal and should be hardened before real use.
- Password reset, MFA, OAuth, advanced role-based authorization, and account-wide logout are not implemented.
- Cancellation, rescheduling, reminders, billing, insurance verification, and EHR integration are not implemented.
- Vogent live operation requires external workspace credentials and flow configuration.
- Large-scale production concerns such as managed databases, observability, WAF rules, and automated backups are documented as next steps.

## Next Engineering Priorities

1. Complete a credentialed Vogent end-to-end call in the target workspace.
2. Harden authentication and authorization for a real deployment.
3. Move PostgreSQL to managed private infrastructure.
4. Add cancellation, rescheduling, reminders, and slot holds.
5. Add production observability, audit retention, and automated deployment checks.
