# Multi-Organization Plan

## Purpose

Phase 3 extends the existing AI medical scheduling platform from a single-organization scheduling system into a multi-organization platform.

This is an extension of the current Flask, PostgreSQL, React, chat, voice, routing, and booking application. It should build on the existing architecture instead of creating a second backend, second frontend, second routing engine, or parallel scheduling workflow.

## Assignment Scope

The system must support:

- Creating medical organizations.
- Configuring each organization's name, hours, and addresses.
- Configuring each organization's doctors.
- Generating organization-specific chat context.
- Preparing organization-specific voice context.
- Managing organizations and doctors through the GUI.
- Managing organizations and doctors through API endpoints.
- Preventing cross-organization data leakage.

The GUI and API should use the same backend service layer so organization setup works the same way whether it is done manually in the admin interface or programmatically through the API.

## Existing Foundation

The project already includes:

- Backend scheduling, routing, and booking logic.
- Chat intake workflow.
- Voice function endpoint integration.
- Admin and patient dashboard areas.
- Database migrations.
- Deterministic backend-owned routing.
- Initial `organization_id` foundation.
- Default organization compatibility for legacy single-organization behavior.

The next Phase 3 work should continue from this foundation and make organization context explicit across the product.

## Target Architecture

An organization can be created by API or GUI and receives a unique slug.

Doctors, locations, hours, slots, appointments, calls, chat sessions, and routing decisions are scoped to that organization.

Public chat links resolve organization context from the slug before intake begins. For example, a patient-facing route can use a pattern such as:

`/o/{organizationSlug}/schedule`

Voice workflows should resolve organization context from an explicit organization-specific route or configured organization identifier before patient lookup, routing, confirmation, booking, transcript storage, or review.

The GUI should call the same backend APIs used by programmatic clients so organization management has one service layer, one validation path, and one source of truth.

## Organization-Owned Data

The key organization-scoped records are:

- Doctors.
- Locations.
- Office hours.
- Slots.
- Appointments.
- Patients or patient/organization relationships, depending on implementation.
- Chat sessions.
- Calls.
- Routing decisions.
- Booking confirmations.
- Integration status and audit records where applicable.

Any query that touches organization-owned data should include organization scope unless it is intentionally operating from a platform-admin view.

## Implementation Slices

1. Organization API and slug resolver.
2. Organization doctors, locations, and hours APIs.
3. Public organization config endpoint.
4. Client-specific chat link.
5. Admin GUI using the same APIs.
6. Voice endpoint organization context.
7. Cross-organization isolation tests.
8. Documentation and final verification.

## Definition of Done

- At least two organizations can exist.
- A newly created organization can be recognized by slug.
- Admin users can create and update organizations through API endpoints.
- Admin users can manage doctors, locations, and hours through API endpoints.
- The GUI uses the same backend APIs as programmatic clients.
- Public chat links are organization-specific.
- Voice workflows can resolve organization context.
- Routing and booking never return or modify resources from another organization.
- Tests prove cross-organization isolation.
- No secrets, personal emails, private screenshots, or local-only notes are committed.

## Risks and Guardrails

- Explicit organization routes must not silently fall back to the default organization.
- The default organization should be used only for legacy compatibility and migration safety.
- Business logic must not be duplicated in the frontend.
- AI output must not own routing, slot-validity, or booking decisions.
- Queries, serializers, dashboard views, chat workflows, voice workflows, and audit records must not leak data across organizations.
- Documentation and commits must not include private data, private screenshots, credentials, local-only notes, or personal contact information.

## Recommended Next Step

The next recommended implementation step is organization recognition through API:

- Create, list, and update organization endpoints.
- Generate unique organization slugs.
- Enforce slug uniqueness.
- Resolve organizations by slug.
- Reject inactive or missing organizations clearly.
- Add tests proving newly created organizations are recognized.

This should be completed before building the full admin GUI or final voice integration, because the GUI, chat link, and voice workflow all depend on reliable organization recognition.