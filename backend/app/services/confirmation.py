from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.normalization import normalize_body_part, normalize_issue_type
from app.domain.routing import PhysicianRoutingService, RoutingRequest
from app.errors import ApiError
from app.models import BookingConfirmation, Call, Patient, PatientDoctorHistory, Slot

CONFIRMATION_TTL_MINUTES = 20


class BookingConfirmationService:
    def __init__(self, session: Session):
        self.session = session

    def confirm(
        self,
        *,
        call_id: int,
        patient_id: int,
        slot_id: int,
        body_part: str,
        issue_type: str,
        source: str,
    ) -> BookingConfirmation:
        try:
            call = self.session.get(Call, call_id)
            if call is None:
                raise ApiError("CALL_NOT_FOUND", "Call was not found.", 404)
            if call.status in {"SCHEDULED", "FAILED", "ABANDONED"}:
                raise ApiError("CALL_NOT_ACTIVE", "This call is no longer active for booking confirmation.", 409)

            patient = self.session.get(Patient, patient_id)
            if patient is None:
                raise ApiError("PATIENT_NOT_FOUND", "Patient was not found.", 404)
            if call.patient_id not in (None, patient_id):
                raise ApiError("CALL_PATIENT_MISMATCH", "The selected patient does not match the active call.", 409)

            slot = self._open_slot(slot_id)
            normalized_body_part = normalize_body_part(body_part)
            normalized_issue_type = normalize_issue_type(issue_type)
            self._assert_slot_still_eligible(
                patient_id=patient_id,
                call_id=call_id,
                slot=slot,
                body_part=normalized_body_part,
                issue_type=normalized_issue_type,
            )

            now = datetime.now(UTC)
            confirmation = BookingConfirmation(
                confirmation_token=secrets.token_urlsafe(32),
                call_id=call_id,
                patient_id=patient_id,
                slot_id=slot.id,
                doctor_id=slot.doctor_id,
                location_id=slot.location_id,
                body_part=normalized_body_part,
                issue_type=normalized_issue_type,
                starts_at=slot.starts_at,
                ends_at=slot.ends_at,
                status="CONFIRMED",
                source=source.upper(),
                confirmed_at=now,
                expires_at=now + timedelta(minutes=CONFIRMATION_TTL_MINUTES),
            )
            self.session.add(confirmation)
            call.patient_id = patient_id
            call.patient_status = self._patient_status(patient_id, slot.doctor_id)
            call.requested_body_part = normalized_body_part
            call.requested_issue_type = normalized_issue_type
            call.preferred_doctor_id = slot.doctor_id
            call.preferred_location_id = slot.location_id
            self.session.commit()
            return confirmation
        except ApiError:
            self.session.rollback()
            raise

    def validate_for_booking(
        self,
        *,
        confirmation_token: str | None,
        patient_id: int,
        slot_id: int,
        body_part: str,
        issue_type: str,
        call_id: int | None,
    ) -> BookingConfirmation:
        if not confirmation_token:
            raise ApiError(
                "BOOKING_CONFIRMATION_REQUIRED",
                "Caller confirmation is required before booking an appointment.",
                422,
                {"confirmation_token": ["This field is required"]},
            )

        confirmation = self.session.scalar(
            select(BookingConfirmation)
            .where(BookingConfirmation.confirmation_token == confirmation_token)
            .with_for_update()
            .options(
                selectinload(BookingConfirmation.slot),
                selectinload(BookingConfirmation.doctor),
                selectinload(BookingConfirmation.location),
            )
        )
        if confirmation is None:
            raise ApiError("BOOKING_CONFIRMATION_NOT_FOUND", "The booking confirmation was not found.", 404)

        now = datetime.now(UTC)
        expires_at = _as_utc(confirmation.expires_at)
        if confirmation.status == "USED":
            raise ApiError("BOOKING_CONFIRMATION_USED", "This booking confirmation has already been used.", 409)
        if confirmation.status != "CONFIRMED" or expires_at <= now:
            confirmation.status = "EXPIRED"
            raise ApiError(
                "BOOKING_CONFIRMATION_STALE",
                "The booking confirmation expired. Confirm the slot again.",
                409,
            )

        normalized_body_part = normalize_body_part(body_part)
        normalized_issue_type = normalize_issue_type(issue_type)
        mismatches: dict[str, list[str]] = {}
        if confirmation.patient_id != patient_id:
            mismatches["patient_id"] = ["Does not match the confirmed patient"]
        if confirmation.slot_id != slot_id:
            mismatches["slot_id"] = ["Does not match the confirmed slot"]
        if confirmation.body_part != normalized_body_part:
            mismatches["body_part"] = ["Does not match the confirmed body part"]
        if confirmation.issue_type != normalized_issue_type:
            mismatches["issue_type"] = ["Does not match the confirmed issue type"]
        if call_id is not None and confirmation.call_id != call_id:
            mismatches["call_id"] = ["Does not match the confirmed call"]
        if mismatches:
            raise ApiError(
                "BOOKING_CONFIRMATION_MISMATCH",
                "The booking request does not match the confirmed caller selection.",
                409,
                mismatches,
            )

        slot = self._open_slot(slot_id)
        if (
            confirmation.doctor_id != slot.doctor_id
            or confirmation.location_id != slot.location_id
            or _as_utc(confirmation.starts_at) != _as_utc(slot.starts_at)
            or _as_utc(confirmation.ends_at) != _as_utc(slot.ends_at)
        ):
            raise ApiError(
                "BOOKING_CONFIRMATION_STALE",
                "The selected appointment details changed. Confirm the slot again.",
                409,
            )
        self._assert_slot_still_eligible(
            patient_id=patient_id,
            call_id=confirmation.call_id,
            slot=slot,
            body_part=normalized_body_part,
            issue_type=normalized_issue_type,
        )
        return confirmation

    def mark_used(self, confirmation: BookingConfirmation, *, appointment_id: int) -> None:
        confirmation.status = "USED"
        confirmation.used_at = datetime.now(UTC)
        confirmation.appointment_id = appointment_id

    def _open_slot(self, slot_id: int) -> Slot:
        slot = self.session.scalar(
            select(Slot)
            .where(Slot.id == slot_id)
            .with_for_update()
            .options(selectinload(Slot.doctor), selectinload(Slot.location))
        )
        if slot is None:
            raise ApiError("SLOT_NOT_FOUND", "The selected appointment slot was not found.", 404)
        if slot.status != "OPEN":
            raise ApiError(
                "SLOT_ALREADY_BOOKED",
                "That appointment time is no longer available. Please choose another slot.",
                409,
            )
        return slot

    def _patient_status(self, patient_id: int, doctor_id: int) -> str:
        history_exists = self.session.scalar(
            select(PatientDoctorHistory.id).where(
                PatientDoctorHistory.patient_id == patient_id,
                PatientDoctorHistory.doctor_id == doctor_id,
            )
        )
        return "RETURNING" if history_exists else "NEW"

    def _assert_slot_still_eligible(
        self,
        *,
        patient_id: int,
        call_id: int | None,
        slot: Slot,
        body_part: str,
        issue_type: str,
    ) -> None:
        routing = PhysicianRoutingService(self.session).recommend(
            RoutingRequest(
                patient_id=patient_id,
                patient_status=self._patient_status(patient_id, slot.doctor_id),
                body_part=body_part,
                issue_type=issue_type,
                preferred_doctor_id=slot.doctor_id,
                preferred_location_id=slot.location_id,
                call_id=call_id,
                starts_after=slot.starts_at,
                ends_before=slot.ends_at,
            ),
            persist=True,
        )
        exact_slot_valid = any(
            available["id"] == slot.id
            for item in routing["ranked_recommendations"]
            for available in item["available_slots"]
        )
        if not exact_slot_valid:
            self.session.refresh(slot)
            if slot.status != "OPEN":
                raise ApiError(
                    "SLOT_ALREADY_BOOKED",
                    "That appointment time is no longer available. Please choose another slot.",
                    409,
                )
            raise ApiError(
                "PHYSICIAN_NOT_ELIGIBLE",
                "The selected physician or slot no longer matches the scheduling protocol.",
                422,
            )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
