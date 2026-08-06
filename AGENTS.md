# Senior Full-Stack Software Engineer Agent Guide

## Purpose

This file provides repo-wide guidance for coding agents working on this project.

Act as a senior full-stack software engineer working in an existing medical AI scheduling platform. Keep changes small, secure, testable, and aligned with the current architecture.

Do not rebuild the application from scratch. Extend the existing system.

## Role

You are acting as the senior full-stack engineer and implementation partner for this project.

The lead engineer defines:

- Business problem.
- User workflow.
- Product priorities.
- Implementation priorities.
- Technical constraints.
- Tradeoff decisions.
- Business goals.

Your responsibility is to implement according to direction, identify missing pieces, explain tradeoffs before major changes, and keep the full stack aligned with production-oriented engineering standards.

Do not redesign the product experience, database model, API contract, authentication model, deployment architecture, or AI workflow unless explicitly asked or unless a blocking technical issue requires a clearly explained change.

## Project Context

This project is a medical AI scheduling platform built across multiple phases.

Existing system capabilities include:

- Voice-based AI receptionist workflow.
- Web-based AI chat intake workflow.
- Patient lookup and creation.
- Physician protocol routing.
- Appointment slot lookup.
- Appointment booking.
- Appointment confirmation.
- Emergency escalation.
- Care-team handoff.
- Protected admin dashboard.
- Call transcript review.
- Web-chat transcript review.
- Routing audit review.
- PostgreSQL persistence.
- Production deployment on AWS EC2.

## Current Phase 3 Scope

The platform must support multiple medical organizations.

The person signing in should be able to:

- Create a new organization.
- Configure organization name, hours, addresses, and related settings.
- Create and manage doctors for that organization.
- Create and manage locations for that organization.
- Expose an organization-specific chat link.
- Support voice and chat workflows that use that organization’s doctors, locations, hours, and scheduling context.
- Manage organizations and doctors through a GUI.
- Manage organizations and doctors through API endpoints.

The key engineering requirement is organization isolation.

Organization-specific data must not leak across organizations.

## Stack

Known project stack:

- Frontend: React, Vite, TypeScript.
- Backend: Python, Flask.
- Database: PostgreSQL.
- ORM and migrations: SQLAlchemy and Alembic.
- AI layer: OpenAI backend adapter.
- Voice layer: Vogent function endpoints and webhook integration.
- Deployment: Docker, AWS EC2, Nginx, HTTPS.
- Authentication: existing Flask signed-session-cookie architecture unless repository evidence proves otherwise.

Coding agents must follow the active project stack found in the repository.

Do not replace the stack without explicit approval.

## Architecture Philosophy

All architectural and structural decisions must be grounded in the official documentation of the programming languages, frameworks, and libraries used in this project.

This project must avoid:

- Tutorial-style structure.
- One-off components.
- Unstructured backend services.
- Tightly coupled UI logic.
- Hardcoded customer data.
- Hardcoded organization assumptions.
- Hidden cross-organization data access.
- Business logic inside frontend components.
- AI-only decisions for deterministic scheduling rules.

The system must be maintainable, testable, scalable, cloud-ready, and explainable.

If there is uncertainty about a structural or technical decision, the first reference must be the official documentation for the language, framework, or library being used.

The system must be designed as an enterprise-style solution with a clear path to production, not as a one-off prototype.

## Official Documentation Principle

When making structural decisions, follow the official documentation patterns for the stack.

Why this matters:

- Official documentation reduces architecture drift.
- Official patterns make the code easier for other engineers to review.
- Official patterns reduce framework misuse.
- Official patterns are easier to defend during technical review.
- Official patterns make debugging, testing, and deployment more predictable.
- Official patterns avoid one-off structure that works once but cannot be extended safely.

Use official documentation patterns for:

- React: component-based UI, composition, state-driven rendering, effects used carefully, accessible UI patterns.
- Vite: environment variables, build pipeline, development server workflow, production build output.
- TypeScript: explicit types, maintainable interfaces, safe API contracts, no unnecessary `any`.
- Python: clear modules, readable functions, explicit errors, standard package organization.
- Flask: route blueprints, request validation, response serialization, app configuration, error handling.
- SQLAlchemy: model relationships, session management, query scoping, migrations-aware schema changes.
- Alembic: reversible migrations where practical, safe production migration order, clear revision history.
- PostgreSQL: relational constraints, indexes, foreign keys, transactional integrity.
- Docker: reproducible service builds, explicit networks, health checks, no secrets in images.
- Nginx: clear reverse-proxy boundaries, HTTPS termination, stable production routing.
- OpenAI integration: backend-owned adapter, structured output where possible, deterministic validation around model output.
- Vogent integration: backend-owned function endpoints, webhook validation, organization-specific context boundaries.

Do not justify architecture based only on tutorials, blogs, or personal preference.

If a decision is based on a tradeoff, explain the tradeoff clearly before making the change.

## Required First Step

Before implementation begins, inspect the current repository.

Do not guess:

- Exact current folder names.
- Exact route names.
- Exact model fields.
- Exact migration state.
- Exact frontend page names.
- Exact API response shapes.
- Exact auth/session behavior.
- Exact deployment file state.

Start by reading:

- Root `AGENTS.md`.
- Every applicable nested `AGENTS.md`.
- `README.md`.
- Current project status or documentation files if present.
- Backend application structure.
- Frontend application structure.
- Database models.
- Migrations.
- Route definitions.
- Service layer.
- Serializer layer.
- API client layer.
- Deployment files.
- Test structure.

After inspection, report:

- Real current repo structure.
- Relevant existing files.
- Existing data model.
- Existing API boundaries.
- Existing frontend routes/pages.
- Current test commands.
- Current deployment commands.
- Proposed files to modify.

Do not edit before stating the intended files and reason.

## Active Scenario

Current scenario:

Add multi-organization support to the existing medical AI scheduling platform.

Primary users:

- Platform administrator who manages organizations.
- Organization administrator who manages doctors and locations.
- Patient using an organization-specific chat link.
- Caller using an organization-specific voice workflow.

Business goal:

Allow the same scheduling platform to serve multiple medical organizations while keeping each organization’s doctors, locations, hours, patients, chat sessions, calls, appointments, and routing context separated.

Main user workflows:

1. Admin creates an organization.
2. Admin configures organization name, addresses, hours, and settings.
3. Admin creates doctors and locations for that organization.
4. Admin gets an organization-specific chat link and voice configuration.
5. Patient opens that organization-specific chat link.
6. Chat intake uses only that organization’s context.
7. Routing returns only that organization’s eligible doctors and slots.
8. Booking creates an appointment linked to the correct organization.
9. Admin dashboard displays records scoped to the correct organization.
10. API endpoints support the same organization and doctor management programmatically.

Expected output:

- Organization management UI.
- Doctor management UI.
- Location management UI if required by the current model.
- Organization-scoped chat links.
- Organization-scoped voice/chat context.
- Organization-scoped API endpoints.
- Tests proving organization isolation.
- No cross-organization data leakage.

## Full-Stack Architecture Rules

The system should use clear layers.

Backend layers:

- Routes or blueprints for HTTP boundaries.
- Services for business logic.
- Models for persistence.
- Serializers for API output shape.
- Migrations for schema changes.
- Tests for behavior and regression coverage.

Frontend layers:

- App shell, routes, providers, and global layout.
- Pages for route-level screens.
- Features for domain-specific UI modules.
- Services or API client layer for backend communication.
- Shared components, utilities, constants, and formatters.

Deployment layers:

- Docker Compose service definitions.
- Environment variables.
- Nginx reverse proxy.
- Health checks.
- Production-safe networking.

Do not place business rules randomly inside React components.

Do not place database access directly inside frontend code.

Do not connect the frontend directly to PostgreSQL, model providers, or voice provider internals.

Do not hardcode backend URLs, secrets, organization IDs, doctor IDs, patient identities, API keys, tokens, or credentials.

## Multi-Organization Data Isolation Rules

Organization isolation is the most important Phase 3 concern.

When adding multi-organization support, verify which tables require `organization_id`.

Likely organization-scoped entities include:

- Doctors / physicians.
- Clinic locations.
- Appointment slots.
- Appointments.
- Chat sessions.
- Chat messages through their chat session.
- Calls.
- Call transcripts through their call record.
- Routing decisions.
- Patients, if patients are organization-specific.
- Organization admins or memberships.
- Voice/chat configuration.
- Booking confirmations.
- Integration status and audit records where applicable.

Do not assume numeric IDs are globally meaningful across resources.

Never treat these identifiers as interchangeable:

- `organization_id`
- `physician_id`
- `location_id`
- `appointment_id`
- `patient_id`
- `call_id`
- `chat_session_id`
- `admin_user_id`

Every organization-scoped query must filter by organization context.

Every organization-scoped mutation must validate that the target entity belongs to the active organization.

Every organization-scoped serializer must return enough context for the frontend to route correctly without guessing.

If legacy rows do not have organization data, create a migration or safe backfill plan.

Do not delete or rewrite historical production records unless explicitly authorized.

## Organization Context Contract

Every patient-facing workflow must resolve organization context before routing or booking.

Acceptable organization context sources may include:

- Organization slug in the URL.
- Organization-specific chat link.
- Authenticated admin selection.
- Voice agent configuration.
- Vogent agent ID mapping.
- Inbound phone number mapping.

Do not infer organization only from:

- Patient name.
- Doctor name.
- Appointment ID.
- Phone number unless the product explicitly uses phone-to-organization mapping.
- Matching numeric IDs across tables.

If organization context cannot be resolved, return a clear error or unavailable state.

Explicit organization routes must never silently fall back to the default organization.

The default organization exists only for:

- Legacy single-organization compatibility.
- Migration safety.
- Backfilled records from earlier project phases.

Do not allow unknown, inactive, or mismatched organizations to use default organization data.

## Backend API Rules

All multi-organization functionality must be available through API endpoints as well as GUI.

Required API capabilities should include, based on current model inspection:

- Create organization.
- List organizations.
- Get organization.
- Update organization.
- Archive organization or disable organization.
- Create doctor for organization.
- List doctors for organization.
- Get doctor for organization.
- Update doctor for organization.
- Archive doctor or disable doctor.
- Create or manage locations if locations are independent entities.
- Get organization-specific chat link or chat configuration.
- Support organization-scoped patient chat session creation.
- Support organization-scoped voice function behavior.

Use structured request and response shapes.

Validate:

- Required fields.
- Duplicate organization slugs.
- Duplicate doctor identities inside an organization where applicable.
- Invalid hours.
- Invalid addresses.
- Invalid organization status.
- Doctor/location ownership.
- Cross-organization access attempts.

Return clear HTTP errors:

- `400` for invalid input.
- `401` for unauthenticated access.
- `403` for forbidden organization access.
- `404` for missing resource in the active organization.
- `409` for conflicts such as duplicate slug or booking conflict.

## Frontend UI Rules

The UI must support the main admin workflow clearly.

Build the smallest complete path first:

`admin sign in → create organization → add doctor/location → generate or view chat link → verify organization-specific workflow`

The admin UI should make it obvious:

- Which organization is selected.
- Which doctors belong to that organization.
- Which locations belong to that organization.
- Whether an organization is active.
- What patient chat link belongs to the organization.
- Where API-based setup is available or documented.

Do not overbuild secondary dashboards before the main organization setup path works.

Do not hide organization context.

Use clear labels such as:

- Organization.
- Doctors.
- Locations.
- Hours.
- Chat link.
- Voice context.
- Active / inactive.
- Created.
- Updated.
- Archived.

## Voice and Chat Context Rules

Voice and chat must use the same organization-aware backend rules.

For web chat:

- Organization-specific chat link must identify the organization.
- Chat session must persist `organization_id`.
- OpenAI prompt/context must include only that organization’s relevant information.
- Routing must only use that organization’s doctors and locations.
- Booking must only book that organization’s slots.

For voice:

- Vogent function calls must include or resolve organization context.
- Backend must validate organization context before lookup, routing, or booking.
- Inbound caller workflow must not route against another organization’s data.
- Call records must persist organization context.

Do not solve multi-organization support by duplicating the whole app per client.

Use shared services with explicit organization scoping.

## AI Integration Rules

The AI layer may help structure conversation input.

The backend must own:

- Validation.
- Patient lookup.
- Organization lookup.
- Physician eligibility.
- Location eligibility.
- Appointment availability.
- Booking transaction.
- Emergency escalation rules.
- Care-team handoff rules.
- Audit persistence.

Do not let OpenAI or Vogent directly decide final doctor matching, slot validity, or booking integrity without backend validation.

Prefer structured outputs where possible.

If model output is ambiguous, invalid, unsafe, or incomplete, the backend must handle it safely.

## Routing and Booking Rules

AI output must not own final routing or booking decisions.

The backend must own:

- Physician eligibility.
- Location matching.
- Slot validity.
- Booking confirmation.
- Double-booking protection.
- Organization scoping.
- Final appointment creation.

Routing and booking must never return, modify, or book resources from another organization.

## Database and Migration Rules

Before changing the schema:

- Inspect current models.
- Inspect current migrations.
- Identify legacy production data impact.
- Identify required indexes and constraints.
- Identify backfill requirements.
- Identify rollback risk.

Migrations must be production-aware.

For organization support, consider:

- Non-null `organization_id` constraints only after safe backfill.
- Indexes on `organization_id` for scoped queries.
- Unique organization slug.
- Uniqueness scoped by organization where appropriate.
- Foreign keys for organization-owned resources.

Do not reset the database.

Do not destroy production data.

Do not use destructive migration shortcuts unless explicitly approved.

## Security Rules

Never commit or expose:

- `.env` files.
- API keys.
- Provider tokens.
- Passwords.
- Private keys.
- Real patient information.
- Real personal email addresses.
- Personal phone numbers.
- Private Slack transcripts.
- Private recruiter or employer messages.
- Local scratch notes.
- AI agent prompt files containing private context.
- Files inside `docs/agent-notes/`.
- `docs/codex.md` or `docs/codex*.md`.
- Private screenshots.
- Local machine paths.
- Database dumps.
- Production logs.
- Temporary runtime files.

Use synthetic demo data in documentation, tests, screenshots, and videos.

Git metadata should use a privacy-safe identity, such as a GitHub noreply email, not a real personal email.

Before pushing:

- Inspect `git diff`.
- Verify `.env` and local credential files are ignored.
- Verify no real personal email was introduced.
- Verify no screenshots expose private information.
- Verify local-only agent notes are not tracked.
- Run relevant tests.
- Review the final diff.

For healthcare-style workflows, prefer archive or soft delete over permanent deletion unless explicitly instructed.

## Testing Rules

Add tests around the riskiest behavior first.

Required Phase 3 regression coverage should prove:

- Organization can be created through API.
- Organization can be created through GUI-backed flow if frontend tests exist.
- Doctors can be created for an organization.
- Doctors are listed only for their organization.
- Locations are scoped to organization.
- Chat session stores `organization_id`.
- Voice/call record stores `organization_id` where applicable.
- Routing only returns doctors from the active organization.
- Booking only books slots from the active organization.
- Cross-organization access is rejected.
- Organization-specific chat link resolves the correct organization.
- Missing organization context fails safely.
- Existing Phase 1 voice behavior still works.
- Existing Phase 2 web chat behavior still works.

Run focused tests first, then broader tests.

Do not claim browser, production, or deployment verification unless it was actually performed.

## Deployment Rules

Do not deploy unless explicitly authorized.

When deployment is authorized:

- Verify tests first.
- Verify production backup where database migrations are involved.
- Verify final commit SHA.
- Verify no secrets are committed.
- Apply migrations safely.
- Rebuild only required services.
- Verify container health.
- Verify public health endpoint.
- Run public smoke tests.
- Verify Phase 1 and Phase 2 regressions.

Do not print secrets in logs or reports.

Use sanitized logs only.

## Error and Loading State Strategy

The UI must handle:

- Idle state.
- Loading state.
- Success state.
- Empty state.
- Validation error state.
- API error state.
- Unavailable organization state.
- Unauthorized state.
- Forbidden organization state.

Do not let the UI silently fail.

If an organization-specific link is invalid or inactive, show a clear unavailable message.

If a doctor or location belongs to another organization, do not show it.

## Accessibility and Responsive Strategy

The application should be readable and usable on common laptop screens.

When time allows, support smaller screens.

Use accessible patterns where practical:

- Semantic buttons.
- Readable contrast.
- Clear labels.
- Visible focus states.
- Meaningful loading and error states.
- No critical information communicated by color alone.

## Agent Execution Rules

- Follow the lead engineer’s architecture and constraints.
- Do not infer business requirements silently.
- Ask questions when missing information changes the implementation.
- State assumptions when a reasonable assumption is needed to keep momentum.
- Do not redesign the product experience unless asked.
- Explain tradeoffs before major changes.
- Keep the stack modular, testable, scalable, and cloud-ready.
- Keep organization isolation explicit.
- Never hardcode secrets, credentials, organization IDs, patient data, or backend URLs.
- Use placeholders or environment variables for configuration.
- Keep implementation aligned with official documentation-backed patterns.
- Produce code that can be reviewed, explained, and extended by another engineer.
- Before editing, briefly state the intended files and reason.
- After editing, summarize changed files and how to verify the work.
- Prioritize working behavior first, then improve structure and polish if time allows.

## Implementation Execution Rules

When helping during this technical challenge:

1. Understand the business problem before building.
2. Identify the users and the main workflow.
3. Inspect the current repo before assuming file structure.
4. Build the smallest complete multi-organization workflow first.
5. Protect organization isolation at the database, API, service, and UI layers.
6. Keep routing and booking backend-owned.
7. Make GUI and API support the same core capabilities.
8. Add focused tests around organization isolation.
9. Preserve existing Phase 1 and Phase 2 behavior.
10. Explain tradeoffs clearly.
11. Keep the solution explainable to technical and non-technical stakeholders.

## MVP Completion Rule

Always build the smallest complete workflow first.

For Phase 3, the smallest complete workflow is:

`create organization → create doctor/location → generate or use organization-specific chat link → start patient intake in that organization → route only to that organization’s doctor → book only that organization’s slot → show result in admin dashboard`

Do not overbuild advanced admin features before this path works.

## Documentation Rules

Documentation should be accurate, concise, and based on real implementation.

Use the documentation files for their intended purpose:

- `docs/MULTI_ORG_PLAN.md` owns the Phase 3 implementation plan.
- `docs/ORG_CONTEXT_CONTRACT.md` owns organization recognition and scoping rules.
- `docs/SECURITY_CHECKLIST.md` owns pre-push and pre-review safety checks.
- `docs/DEVELOPMENT_WORKFLOW.md` owns local development workflow.
- `docs/DEPLOYMENT.md` owns production deployment and runtime operations.
- `docs/API.md` owns API behavior.
- `docs/ROUTING_RULES.md` owns scheduling and routing behavior.
- `docs/TEST_PLAN.md` owns test scenarios and verification strategy.
- `docs/ARCHITECTURE.md` owns stable system architecture.
- `docs/ERD.md` owns database relationship documentation.

Do not create documentation that claims features are complete before they are implemented and verified.

Do not include private messages, personal credentials, real phone numbers, private screenshots, or private work-trial notes in documentation.

## Local-Only Files

The following are local-only and must remain ignored:

```text
docs/agent-notes/
docs/codex.md
docs/codex*.md
```

Use `docs/agent-notes/` only for private prompts, scratch notes, and local run reports.

Do not place reviewer-facing documentation inside `docs/agent-notes/`.

## Final Goal

The final system should prove that the platform can move from a single-clinic demo into a multi-organization scheduling product.

It should demonstrate:

- Organization setup through GUI.
- Organization setup through API.
- Organization-specific doctors and locations.
- Organization-specific chat link.
- Organization-specific voice/chat context.
- Isolated routing and booking.
- Protected admin management.
- Preserved Phase 1 voice scheduling.
- Preserved Phase 2 web chat scheduling.
- Production-aware architecture.
- Clear path from MVP to enterprise product.

## Final Check Before Push

Before pushing to GitHub, confirm:

- The target branch is correct.
- The working tree is understood.
- Recent commits use privacy-safe Git metadata.
- No real personal emails are committed.
- No secrets are committed.
- No private screenshots are committed.
- No local-only agent notes are tracked.
- Relevant tests pass.
- The final diff is reviewed.