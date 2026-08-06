# Organization Context Contract

## Purpose

This document defines how the application identifies, resolves, and enforces organization context across the multi-organization scheduling platform.

Organization context must be resolved before any workflow touches doctors, locations, office hours, slots, appointments, chat sessions, calls, routing decisions, or booking records.

The goal is to make every chat, voice, API, dashboard, routing, and booking action operate inside the correct organization boundary.

## Organization Identity

Each organization should have a stable identity that can be used internally and externally.

Required organization identity fields should include:

- `id`: internal database identifier.
- `slug`: public-safe unique identifier used in URLs and integrations.
- `name`: display name for the organization.
- `status`: whether the organization is active or inactive.
- `timezone`: scheduling timezone for the organization.

The `slug` is the main public recognition value. It should be unique, stable, URL-safe, and safe to expose in patient-facing links.

Example pattern:

`/o/{organizationSlug}/schedule`

## Slug-Based Recognition

Public organization routes should resolve organization context from the slug before any workflow begins.

Example:

`/o/demo-orthopedics/schedule`

Expected behavior:

1. Read `organizationSlug` from the route.
2. Look up the organization by slug.
3. Reject the request if the organization does not exist.
4. Reject the request if the organization is inactive.
5. Attach organization context to the request/workflow.
6. Use that organization context for every downstream query.

A valid slug should never resolve to another organization’s doctors, locations, slots, appointments, calls, chat sessions, or routing records.

## Admin API Context

Admin API routes may resolve organization context by internal organization ID or slug, depending on the endpoint.

Examples:

`GET /api/v1/organizations`
`POST /api/v1/organizations`
`GET /api/v1/organizations/{organizationId}`
`PATCH /api/v1/organizations/{organizationId}`
`GET /api/v1/organizations/{organizationId}/doctors`
`POST /api/v1/organizations/{organizationId}/doctors`

Admin routes that manage organization-owned resources must explicitly identify the organization being managed.

Platform-admin views may list multiple organizations, but organization-owned records should still be clearly tied to their organization.

## Public Chat Context

Public chat routes must resolve organization context before creating or resuming a chat session.

Expected behavior:

- A chat session created from `/o/{organizationSlug}/schedule` belongs to that organization.
- Resuming a chat session must verify that the session belongs to the same organization.
- Doctor, location, slot, and routing options shown in chat must be scoped to the resolved organization.
- Chat should not expose another organization’s names, doctors, locations, hours, slots, or appointments.

If the organization slug is missing, unknown, or inactive, the public chat route should return a clear error instead of falling back to the default organization.

## Voice Context

Voice workflows must also resolve organization context before patient lookup, routing, confirmation, booking, transcript storage, or review.

The preferred approach is to use an explicit organization-specific route or configured organization identifier.

Example route pattern:

`/api/v1/organizations/{organizationSlug}/vogent/functions/{functionName}`

Alternative future options may include:

- Mapping an inbound phone number to an organization.
- Passing a trusted organization identifier from the voice integration.
- Configuring a dedicated voice agent per organization.

Regardless of the mechanism, the backend must resolve organization context before using any scheduling or routing data.

## Default Organization Compatibility

The default organization exists only for legacy compatibility and migration safety.

It may be used for:

- Existing single-organization routes during the transition.
- Backfilled records from earlier project phases.
- Internal compatibility while explicit organization routes are being added.

It must not be used as a silent fallback for new explicit multi-organization routes.

If a new route includes an organization slug or organization ID, failure to resolve that organization should produce a clear error.

## No Silent Fallback Rule

Explicit organization routes must never silently fall back to the default organization.

Invalid examples:

- Unknown organization slug loads default doctors.
- Inactive organization slug opens default chat.
- Missing organization ID books into default slots.
- Voice route without valid organization context uses default scheduling data.

Correct behavior:

- Unknown organization returns a not-found error.
- Inactive organization returns an inactive/unavailable error.
- Missing organization context returns a validation error.
- Cross-organization records are rejected.

## Organization-Scoped Entities

The following records must be organization-scoped:

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

Every query that reads or writes these records should include organization scope unless it is intentionally operating from a platform-admin view.

## Cross-Organization Isolation Rules

The system must prevent cross-organization leakage.

Required rules:

- Routing must only consider doctors, locations, capabilities, history, and slots from the active organization.
- Booking must reject slots that do not belong to the active organization.
- Chat sessions must not be resumed across organizations.
- Voice calls must not route or book against another organization’s data.
- Dashboard views must clearly scope or label organization-owned records.
- Audit records must store the organization context used for the decision.
- Serializers and response objects must not expose another organization’s data.

## Error Handling

Organization resolution errors should be explicit and safe.

Recommended responses:

- Unknown organization: return a not-found response.
- Inactive organization: return an unavailable or inactive organization response.
- Missing organization context: return a validation error.
- Cross-organization record mismatch: return a conflict or validation error.

Error responses should not leak private organization data.

## Test Expectations

Tests should prove that organization context is enforced.

Minimum expected tests:

- A newly created organization can be resolved by slug.
- Duplicate organization slugs are rejected or safely de-duplicated.
- Inactive organizations are rejected from public chat routes.
- Two organizations can have separate doctors.
- Two organizations can have separate locations.
- Two organizations can have separate slots.
- Routing for one organization never returns doctors or slots from another organization.
- Booking rejects a slot from another organization.
- Chat session resume rejects cross-organization access.
- Voice context resolution rejects unknown or inactive organizations.
- Legacy routes can use the default organization only where explicitly allowed.

## Contract Summary

Organization context is a required boundary for Phase 3.

Every workflow must answer this question before doing work:

`Which organization owns this request?`

If the organization cannot be resolved safely, the workflow should stop instead of falling back silently.
