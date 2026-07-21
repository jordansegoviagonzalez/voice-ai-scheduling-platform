# Vogent Integration

This directory contains the credential-independent setup artifacts for connecting the scheduling API to a Vogent inbound Flow Builder agent.

## Verified platform behavior

The integration follows current official Vogent documentation:

- API functions invoke external endpoints with `POST` requests and configured headers.
- Inbound call events use `dial.inbound`.
- Status updates use `dial.updated`.
- Final transcripts use `dial.transcript`.
- Webhook signatures are supplied in `X-Elto-Signature` and verified with HMAC-SHA256 using the configured signing secret.
- Flow Builder function nodes reference a workspace-specific Vogent function ID.
- The reviewed webhook docs do not document a signed timestamp header. The adapter therefore does not invent a timestamp replay window.

Official references:

- https://docs.vogent.ai/platform-overview/tools/function-calling
- https://docs.vogent.ai/quickstart/flow-builder
- https://docs.vogent.ai/developers/schemas
- https://docs.vogent.ai/platform-overview/api-settings
- https://docs.vogent.ai/developers/webhooks/dial-inbound
- https://docs.vogent.ai/developers/webhooks/dial-status-updated
- https://docs.vogent.ai/developers/webhooks/dial-transcript

## Credential-dependent connection step

A live agent export cannot be generated without access to a Vogent workspace because function IDs, agent IDs, phone-number bindings, prompt version IDs, and export metadata are workspace-specific. This repository therefore does not fabricate a purported importable export.

The remaining manual step is:

1. Create or open an inbound Flow Builder agent in Vogent.
2. Create the API functions from `tool-definitions/`.
3. Set each function endpoint to the deployed HTTPS application URL.
4. Configure the custom `X-Vogent-Function-Secret` header to match `VOGENT_FUNCTION_SECRET`.
5. Record the generated function IDs in the Function Call nodes described in `flow-export/flow-node-specs.json`.
6. Configure the global webhook URL as `https://<public-host>/api/v1/vogent/webhooks`.
7. Configure `VOGENT_WEBHOOK_SECRET` from the Vogent API settings page.
8. Run `PUBLIC_APP_URL=https://<public-host> VOGENT_FUNCTION_SECRET=<secret> VOGENT_WEBHOOK_SECRET=<secret> ./infra/scripts/verify-vogent-readiness.sh`.
9. Link an inbound phone number to the agent and run a web-call or phone-call test.

## API function endpoints

| Function | Endpoint | Purpose |
|---|---|---|
| Patient lookup | `/api/v1/vogent/functions/patient-lookup` | Match phone plus date of birth |
| Interpret intent | `/api/v1/vogent/functions/interpret-intent` | Extract scheduling intent through backend GPT-5.2 structured outputs |
| Routing recommendations | `/api/v1/vogent/functions/routing-recommendations` | Enforce exact protocol rules and return real slots |
| Confirm slot | `/api/v1/vogent/functions/confirm-slot` | Persist explicit caller confirmation for the selected doctor, location, date, and time |
| Book appointment | `/api/v1/vogent/functions/book-appointment` | Revalidate confirmation and transactionally claim the confirmed slot |

All endpoints accept JSON and require the configured custom header in production. `book-appointment` must receive the `confirmation_token` returned by `confirm-slot`.

Function calls are idempotent. If Vogent retries the same request with the same idempotency key or identical payload, the API returns the previously stored response when safe.

## Webhook events

The unified webhook adapter accepts the official event envelope for:

- `dial.inbound`
- `dial.updated`
- `dial.transcript`

`dial.inbound` returns a documented `call_agent_input` object containing the internal call ID so subsequent function calls can associate routing decisions and appointments with the call.

Webhook replay keys and payload hashes are persisted. Duplicate events do not mutate call state again, reused event keys with different payloads are rejected, transcript events cannot alter terminal booking status, and stale status updates cannot overwrite terminal scheduled, failed, abandoned, or redirected calls.

Request limits protect webhook ingestion without changing the Vogent contract: the default full request body limit is `256 KiB`, a transcript turn is limited to `2000` characters, and a single transcript webhook accepts up to `200` turns. Oversized payloads fail closed with stable JSON errors.

## Conversational variable mapping

| Vogent variable | Internal API field |
|---|---|
| `internal_call_id` | `call_id` |
| `caller_phone` | `caller_phone` / patient lookup `phone` |
| `date_of_birth` | `date_of_birth` |
| `patient_status` | `NEW` or `RETURNING` |
| `body_part` | Canonical body part |
| `issue_type` | Canonical issue type |
| `preferred_doctor_id` | Optional doctor ID |
| `preferred_location_id` | Optional location ID |
| `patient_id` | Matched or created patient ID |
| `selected_slot_id` | Confirmed slot ID |

## Agent safeguards

The agent must:

- Ask one focused question at a time.
- Never diagnose or provide clinical advice.
- Never state that a physician is eligible or available until the routing function succeeds.
- Never state that an appointment is booked until the booking function returns `booked: true`.
- Repeat physician, location, date, and time and obtain an explicit yes before booking.
- Call `confirm-slot` after explicit yes and pass its `confirmation_token` to `book-appointment`.
- Preserve already validated answers when the caller corrects one field.
- Read caller-safe explanations, not internal IDs or reason codes.
