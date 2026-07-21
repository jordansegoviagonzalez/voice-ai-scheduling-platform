# Demo Video Script and Checklist

Target duration: 5–7 minutes.

The candidate must record the video. This repository prepares the script and verification checklist; it does not claim that a video has been recorded.

## 0:00–0:30 — Introduction

Show the dashboard Overview page.

Suggested narration:

> This is an AI Medical Scheduling Agent built around a deterministic Flask scheduling backend, a PostgreSQL protocol and availability model, a voice-integration boundary for Vogent, and a React call-review dashboard. Because the assignment is intentionally larger than two days, I prioritized a reliable end-to-end scheduling workflow over raw feature count. The conversational layer gathers information, while the backend remains the final authority for eligibility and booking.

Point out:

- Database-derived metrics.
- Core pages in the sidebar.
- The Call Simulator as a demo/developer tool, not a replacement for Vogent.

## 0:30–2:30 — Successful scheduling call

Open Call Simulator.

Use a synthetic new patient and select:

- Body part: Shoulder
- Issue type: Fracture

Demonstrate:

1. Patient identification fields.
2. New/returning status.
3. Body part and issue type.
4. Routing preview.
5. Only Dr. Elena Vasquez is protocol eligible.
6. Real open slots returned from the database.
7. Select a slot.
8. Read back doctor, location, date, and time.
9. Confirm and book.
10. Open the completed call from Calls.

Narration emphasis:

> The UI does not hardcode this result. It calls the same backend services used by the Vogent adapter. The booking endpoint revalidates the physician and slot inside the transaction before it confirms anything.

## 2:30–3:45 — Invalid requested physician

Create a new call:

- New patient
- Knee
- Fracture
- Preferred physician: Dr. Maria Chen

Show:

- Dr. Chen is rejected because she treats knee joint-replacement and sports-medicine cases, not knee fractures.
- Dr. James Walsh and Dr. Elena Vasquez are the protocol-valid alternatives.
- The response uses a plain-language explanation rather than only an internal reason code.

Suggested narration:

> The system does not return every knee doctor. It requires an exact body-part and issue-type capability. A geographically convenient or generally relevant doctor is not accepted unless the exact protocol row exists.

## 3:45–4:30 — Fallback

Continue with the knee-fracture scenario.

The seed intentionally gives Dr. Walsh no open slots while Dr. Vasquez has availability.

Show:

- Walsh remains protocol eligible.
- `NO_OPEN_SLOTS` is recorded as an availability exception.
- Vasquez becomes the available fallback.
- When the alternate slot is at another location, the UI explains the location difference.
- A user must explicitly choose and confirm the alternative before booking.

Suggested narration:

> The request context is preserved. The system does not terminate when the first valid physician is full; it continues deterministically to the next physician with a real opening.

## 4:30–5:30 — Dashboard review

Open Calls and then the newly created call.

Show:

- Caller/patient identification.
- New/returning status.
- Requested body part and issue type.
- Full transcript with speaker labels.
- Booking status.
- Doctor, location, date, and time.
- Routing timeline.
- Rejected doctors with human-readable reasons.
- Fallback event.

Then briefly show:

- Appointments page.
- Physicians protocol page.
- Routing Audit page.

## 5:30–6:30 — Code structure

Show these files in the editor:

1. `backend/app/__init__.py` — Flask application factory and versioned API registration.
2. `backend/app/domain/routing.py` — deterministic routing service.
3. `backend/app/services/booking.py` — transaction, final eligibility check, row lock, conflict handling.
4. `backend/app/models/entities.py` — normalized schema and uniqueness constraints.
5. `backend/app/integrations/vogent/` and `backend/app/routes/vogent.py` — integration boundary and webhook security.
6. `frontend/src/api/` and `frontend/src/pages/` — typed API boundary and feature pages.
7. `backend/tests/` — scenarios and concurrency test.
8. `docker-compose.prod.yml` and `infra/nginx/` — EC2 production topology.

Suggested narration:

> The route handlers stay thin. Protocol logic lives in the domain layer, and Vogent-specific fields are translated at the adapter boundary. This keeps the same routing and booking behavior available to voice calls, the simulator, automated tests, and any future scheduling integration.

## 6:30–7:00 — Tradeoffs

Explain:

- Production authentication and multi-tenancy were deliberately skipped.
- Cancellation, rescheduling, insurance, payments, and EHR integration were deferred.
- PostgreSQL remains in a Docker volume for the work-trial EC2 deployment; the next production step is private RDS.
- A live Vogent call requires workspace credentials and the final configured flow connection.
- The implemented core remains fully demonstrable through the local simulator and dashboard.

Close with:

> The main result is a complete, explainable scheduling path: identify, route, offer real availability, confirm, book transactionally, and review the transcript and routing evidence.

## Final recording checklist

### Privacy and security

- [ ] Use only synthetic patient data.
- [ ] Hide `.env`, terminal history containing secrets, and password-manager windows.
- [ ] Hide AWS account ID and billing details.
- [ ] Hide Vogent API keys, webhook secrets, and shared function secret.
- [ ] Hide SSH private-key paths and contents.
- [ ] Confirm no database password appears on screen.

### Functional readiness

- [ ] Public URL works in a private/incognito browser.
- [ ] `/api/v1/health` reports backend and database healthy.
- [ ] Seeded demo data is present.
- [ ] Successful scheduling scenario completes.
- [ ] Invalid Dr. Chen scenario explains the rejection.
- [ ] Fallback scenario shows Walsh unavailable and Vasquez available.
- [ ] Preferred-location difference requires confirmation.
- [ ] Newly booked appointment appears in Calls and Appointments.
- [ ] Full transcript and routing audit render.
- [ ] No browser console errors.
- [ ] No failed network requests.

### Recording quality

- [ ] Microphone input is clear and at a consistent level.
- [ ] System audio is disabled unless needed.
- [ ] Screen resolution keeps dashboard and code readable.
- [ ] Browser zoom is appropriate.
- [ ] Notifications and personal tabs are closed.
- [ ] Cursor movement is deliberate.
- [ ] Final recording is reviewed from start to finish.
- [ ] Submission links are verified after upload.
