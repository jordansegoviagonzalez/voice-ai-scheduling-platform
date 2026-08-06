# API Reference

Base path: `/api/v1`

All write endpoints accept and return JSON. Datetimes are ISO 8601 with timezone offsets. Errors use:

```json
{
  "error": {
    "code": "SLOT_ALREADY_BOOKED",
    "message": "The selected appointment time is no longer available.",
    "field_errors": {},
    "request_id": "f4bd91d0-..."
  }
}
```

## Request and abuse limits

The Flask app sets `MAX_CONTENT_LENGTH=262144` by default. Public write and integration-facing endpoints also apply field-level limits:

- Global JSON string field: `8192` characters.
- Conversation `raw_user_text`: `4000` characters.
- Transcript turn text: `2000` characters.
- Transcript turns per Vogent webhook payload: `200`.
- Confirmation tokens: `128` characters.

Oversized request bodies return `413` with `REQUEST_ENTITY_TOO_LARGE`. Oversized accepted JSON fields return `413` with `FIELD_TOO_LONG`.

Protected POST routes use a database-backed fixed-window limiter by route and caller identifier. Defaults are `RATE_LIMIT_MAX_REQUESTS=60` per `RATE_LIMIT_WINDOW_SECONDS=60`. Exceeded windows return `429 RATE_LIMIT_EXCEEDED` with `retry_after_seconds` details. This is a work-trial abuse boundary, not a replacement for production edge/WAF controls.

## Health

### `GET /health`

Response `200`:

```json
{
  "status": "ok",
  "backend": "healthy",
  "database": "healthy"
}
```

## Organizations

Organization management endpoints require a valid admin session, except slug resolution. Slug resolution is public-safe and returns only active organizations.

### `POST /organizations`

Creates an organization. `name` is required. `slug`, `status`, and `timezone` are optional. When `slug` is omitted, the API generates one from `name`.

```json
{
  "name": "Summit Orthopedics",
  "slug": "summit-orthopedics",
  "timezone": "America/Los_Angeles"
}
```

Responses: `201` created, `409 ORGANIZATION_SLUG_CONFLICT` when the normalized slug already exists, `422` invalid input.

### `GET /organizations`

Lists organizations for the authenticated admin.

### `GET /organizations/{organization_id}`

Returns one organization by internal ID. Missing IDs return `404 ORGANIZATION_NOT_FOUND`.

### `PATCH /organizations/{organization_id}`

Updates `name`, `slug`, `status`, or `timezone`. Supported statuses are `ACTIVE` and `INACTIVE`. Updating the name does not automatically change the slug.

### `GET /organizations/slug/{organization_slug}`

Resolves an active organization by public slug. Unknown slugs return `404 ORGANIZATION_NOT_FOUND`; inactive organizations return `409 ORGANIZATION_INACTIVE`. Explicit slug resolution never falls back to the default organization.

## Organization Doctors

Organization doctor endpoints require a valid admin session and scope every lookup by `organization_id`.

### `POST /organizations/{organization_id}/doctors`

Creates a doctor under the selected organization.

```json
{
  "first_name": "Iris",
  "last_name": "Stone",
  "accepts_new_patients": true,
  "active": true,
  "location_ids": [12],
  "capabilities": [
    {"body_part": "Knee", "issue_type": "General"}
  ]
}
```

`location_ids` must belong to the selected organization. Capabilities are optional and use the existing normalized body part and issue type rules.

### `GET /organizations/{organization_id}/doctors`

Lists only doctors owned by the selected organization.

### `GET /organizations/{organization_id}/doctors/{doctor_id}`

Returns one doctor only when the doctor belongs to the selected organization. A doctor from another organization returns `404 DOCTOR_NOT_FOUND`.

### `PATCH /organizations/{organization_id}/doctors/{doctor_id}`

Updates doctor name, new-patient eligibility, active state, locations, or capabilities within the selected organization. Cross-organization doctor access returns `404 DOCTOR_NOT_FOUND`.

## Patients

### `POST /patients/lookup`

Input:

```json
{
  "phone": "+18055550105",
  "date_of_birth": "1982-11-06"
}
```

Response `200`:

```json
{
  "found": true,
  "patient": {
    "id": 1,
    "first_name": "Maya",
    "last_name": "Patel",
    "phone": "+18055550105",
    "date_of_birth": "1982-11-06"
  }
}
```

### `POST /patients`

Creates a patient or returns the existing phone/date-of-birth match.

```json
{
  "first_name": "Avery",
  "last_name": "Stone",
  "date_of_birth": "1991-04-12",
  "phone": "+18055550999",
  "email": "avery@example.test"
}
```

Responses: `201` created, `200` existing duplicate match, `400/422` invalid input.

### `GET /patients/{patient_id}`

Returns patient details. `404` when missing.

### `GET /patients/{patient_id}/appointments`

Returns the patient's appointments with doctor, location, and slot information.

## Doctors and protocol

### `GET /doctors`

Returns active doctors with locations, capabilities, and new-patient status.

### `GET /doctors/{doctor_id}`

Returns one doctor. `404` when missing.

### `GET /locations`

Returns `MAIN`, `NORTH`, and `WEST` locations.

### `GET /protocol`

Returns the full read-only normalized physician protocol.

## Routing

### `POST /routing/recommendations`

Input:

```json
{
  "patient_id": 1,
  "patient_status": "RETURNING",
  "body_part": "spine",
  "issue_type": "general pain",
  "preferred_doctor_id": 3,
  "preferred_location_id": 1,
  "call_id": 12,
  "starts_after": "2026-07-20T00:00:00Z",
  "ends_before": "2026-08-03T00:00:00Z"
}
```

`patient_id`, preferences, call, and date range are optional. Patient status, body part, and issue type are required.

Response `200` includes:

```json
{
  "normalized_request": {
    "patient_status": "RETURNING",
    "body_part": "Spine",
    "issue_type": "General"
  },
  "eligible_doctors": [],
  "rejected_doctors": [],
  "availability_exceptions": [],
  "ranked_recommendations": [],
  "recommended": null,
  "fallback_explanation": null,
  "caller_safe_summary": "..."
}
```

Each rejection includes a `reason_code` and a caller-safe `reason`. Every recommendation includes the doctor, available slots, preference matches, and ranking data.

Errors: `400` malformed request; `404` referenced patient/doctor/location missing; `422` unsupported or ambiguous domain input.

## Slots

### `GET /slots`

Optional query parameters:

- `doctor_id`
- `location_id`
- `body_part`
- `issue_type`
- `starts_after`
- `ends_before`

Only open slots are returned. When body part or issue type is supplied, both are required as a valid exact capability combination.

## Appointments

### `POST /booking-confirmations`

Input:

```json
{
  "call_id": 12,
  "patient_id": 1,
  "slot_id": 25,
  "body_part": "Spine",
  "issue_type": "General",
  "source": "VOGENT"
}
```

Response `201` returns a durable `confirmation_token` plus the exact confirmed physician, location, slot, date/time, patient, call, body part, and issue type.

The token expires and can be used only for a matching booking request. Missing, mismatched, used, stale, or expired confirmations fail before an appointment is created.

### `POST /appointments`

Input:

```json
{
  "patient_id": 1,
  "slot_id": 25,
  "body_part": "Spine",
  "issue_type": "General",
  "call_id": 12,
  "confirmation_token": "6f3d...",
  "booking_source": "VOGENT"
}
```

Response `201` contains the confirmed appointment.

The endpoint validates the caller confirmation, locks the slot on PostgreSQL, re-runs eligibility, validates location, inserts the appointment, updates the slot, marks the confirmation used, and associates call/history records in one transaction.

Errors:

- `404`: patient, slot, or call missing.
- `409`: slot already booked or conflicting unique appointment.
- `422`: doctor is no longer eligible or slot/location is invalid.

### `GET /appointments`

Returns all appointments for the operational dashboard.

### `GET /appointments/{appointment_id}`

Returns one appointment. `404` when missing.

## Calls

### `POST /calls`

Input:

```json
{
  "external_call_id": "vogent-call-123",
  "caller_phone": "+18055550105",
  "patient_id": 1,
  "status": "IN_PROGRESS",
  "patient_status": "RETURNING",
  "requested_body_part": "Spine",
  "requested_issue_type": "General",
  "preferred_doctor_id": 3,
  "preferred_location_id": 1
}
```

Response `201` returns the call.

### `PATCH /calls/{call_id}`

Supports status, patient, request context, appointment, end time, failure reason, and redirect summary updates.

### `POST /calls/{call_id}/transcript-turns`

Input:

```json
{
  "sequence_number": 4,
  "speaker": "CALLER",
  "text": "Tuesday morning works for me.",
  "occurred_at": "2026-07-20T16:02:30Z"
}
```

Response `201`. Duplicate sequence numbers receive a conflict/validation response.

### `GET /calls`

Filters:

- `search`
- `status`
- `doctor_id`
- `location_id`
- `started_after`
- `started_before`

Returns call summaries for the table.

### `GET /calls/{call_id}`

Returns full call detail: transcript, patient, preferences, appointment, routing timeline, failure, and redirect information.

## Dashboard

### `GET /dashboard/overview`

Returns database-derived 30-day metrics, outcome series, recent calls, upcoming appointments, recent routing exceptions, and backend-derived integration statuses for core services, OpenAI GPT-5.2, and Vogent.

### `GET /routing-audit`

Returns explainable routing decisions. Optional query filters include call and result context.

## Conversation interpretation

### `POST /conversation/interpret`

Input:

```json
{
  "raw_user_text": "I am a new patient with a shoulder fracture.",
  "patient_id": 9,
  "call_id": 15,
  "previous_state": {
    "patient_status": "NEW",
    "body_part": "Shoulder"
  }
}
```

The endpoint uses the backend GPT-5.2 adapter to extract structured scheduling intent, validates the output against the deterministic doctor/location roster and scheduling enums, merges caller corrections, and calls deterministic routing only when required fields are complete. It does not book appointments.

## Local simulator

### `POST /simulator/preview`

Looks up or creates a patient, creates an in-progress call, adds transcript turns, executes the real routing service, and returns valid/rejected doctors and slots.

Input:

```json
{
  "caller_phone": "+18055550999",
  "first_name": "Avery",
  "last_name": "Stone",
  "date_of_birth": "1991-04-12",
  "patient_status": "NEW",
  "body_part": "Knee",
  "issue_type": "Fracture",
  "preferred_doctor_id": null,
  "preferred_location_id": null
}
```

### `POST /simulator/book`

Input:

```json
{
  "call_id": 15,
  "patient_id": 9,
  "slot_id": 44,
  "body_part": "Knee",
  "issue_type": "Fracture",
  "confirmation_token": "6f3d..."
}
```

Books through `BookingService`, appends confirmation transcript turns, and returns the completed call and appointment. The simulator frontend obtains this token from `/booking-confirmations` before calling `/simulator/book`.

## Vogent adapter

### `POST /vogent/functions/patient-lookup`
### `POST /vogent/functions/interpret-intent`
### `POST /vogent/functions/routing-recommendations`
### `POST /vogent/functions/confirm-slot`
### `POST /vogent/functions/book-appointment`

These routes accept the header configured in Vogent:

```text
X-Vogent-Function-Secret: <shared secret>
```

The route-specific inputs are documented in `vogent/tool-definitions/`. `book-appointment` requires the `confirmation_token` returned by `confirm-slot`.

### `POST /vogent/webhooks`

Receives configured transcript/status events. When `VOGENT_WEBHOOK_SECRET` is set, the raw request body must pass the signature validation documented in `vogent/README.md`.
