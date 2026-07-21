# Deterministic Routing Rules

## Authority boundary

The backend domain layer is the source of truth. A conversational model may collect, clarify, and normalize a caller's words, but it cannot decide physician eligibility, patient-doctor status, location validity, slot availability, or booking success.

## Canonical values

Body parts:

- Knee
- Hip
- Shoulder
- Hand/Wrist
- Foot/Ankle
- Spine

Issue types:

- Fracture
- Joint Replacement
- Sports Medicine
- General

The normalizer accepts unambiguous caller phrases such as “broke my ankle,” “ACL injury,” and “knee replacement consultation.” Unsupported or ambiguous values receive a validation response instead of a silent guess.

## Exact capability matching

A doctor qualifies only when a capability row matches both the canonical body part and canonical issue type.

`General` is not a wildcard. It never matches:

- Fracture
- Joint Replacement
- Sports Medicine

Therefore, a doctor with `Spine / General` is invalid for a spine fracture, and a doctor with `Hand/Wrist / General` is invalid for a sports injury.

## New-patient logic

Eligibility is evaluated per doctor:

- `accepts_new_patients = true`: new and returning patients may qualify.
- `accepts_new_patients = false`: only patients with an existing `patient_doctor_history` row for that doctor may qualify.

A patient who has visited the facility but has never seen Dr. Patel is still new to Dr. Patel. Returning facility status alone is insufficient.

When a request says `RETURNING` but omits a patient ID, non-new-patient doctors remain ineligible because treatment history cannot be proven.

## Preferred doctor

A preferred doctor receives priority only after all rules pass:

1. Doctor exists and is active.
2. Exact body-part and issue-type capability exists.
3. Per-doctor new-patient rule passes.
4. Doctor supports the requested location when one is specified.
5. A valid open slot exists in the requested date range.

When invalid, the result includes a plain-language explanation and valid alternatives. Example:

> Dr. Maria Chen was not selected because she does not treat knee fractures. Dr. James Walsh and Dr. Elena Vasquez match that request.

## Preferred location

A preferred location changes ranking, not clinical eligibility:

1. Valid physicians with open slots at the preferred location rank first.
2. If no valid opening exists there, the response states that clearly.
3. Valid slots at other locations are returned as alternatives.
4. A different location is never booked without explicit confirmation.

## Slot handling

Only `OPEN` slots in the requested date window are considered. A slot is valid only when its doctor-location pair exists in `doctor_locations`.

Protocol eligibility and availability are reported separately:

- `eligible_doctors`: clinically/protocol eligible doctors.
- `availability_exceptions`: otherwise-valid doctors with no open slot.
- `ranked_recommendations`: valid doctors that currently have open slots.

This distinction makes fallback behavior explainable.

## Stable ranking

Recommendations are sorted by:

1. Valid preferred doctor.
2. Open slot at preferred location.
3. Earliest open slot.
4. Stable doctor ID tie-breaker.

This makes identical input and database state produce identical output.

## Fallback

When the first protocol-eligible doctor has no openings:

- The request context is preserved.
- The doctor is recorded as having `NO_OPEN_SLOTS`.
- The next valid doctor with availability is selected.
- The caller-safe response explains why an alternative is being offered.
- Booking still requires explicit confirmation.

The seeded knee-fracture scenario demonstrates this: Dr. James Walsh is clinically valid but intentionally has no open slot; Dr. Elena Vasquez is selected as the available fallback.

## Routing audit

When a request includes `call_id`, the service stores a decision for each evaluated doctor. Example reason codes:

- `BODY_PART_NOT_SUPPORTED`
- `ISSUE_TYPE_NOT_SUPPORTED`
- `NOT_ACCEPTING_NEW_PATIENTS`
- `PATIENT_HAS_NO_HISTORY_WITH_DOCTOR`
- `LOCATION_NOT_SUPPORTED`
- `NO_OPEN_SLOTS`
- `VALID_CANDIDATE`
- `PREFERRED_DOCTOR_INVALID`
- `FALLBACK_SELECTED`

The dashboard renders `human_readable_reason`, not just the code.

## Booking-time revalidation

Recommendations are not reservations. During confirmed booking, `BookingService`:

1. Starts a transaction.
2. Loads and locks the slot with `SELECT ... FOR UPDATE` on PostgreSQL.
3. Confirms the slot is still `OPEN`.
4. Confirms the doctor practices at the slot location.
5. Re-runs exact protocol and patient-history eligibility.
6. Inserts one appointment for the unique slot.
7. Marks the slot `BOOKED`.
8. Updates the call and patient-doctor history.
9. Commits.

A conflicting request receives HTTP `409` and does not create another appointment.
