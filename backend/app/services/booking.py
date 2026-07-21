from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, selectinload

from app.domain.routing import PhysicianRoutingService, RoutingRequest
from app.errors import ApiError
from app.models import Appointment, Call, DoctorLocation, Patient, PatientDoctorHistory, Slot
from app.services.confirmation import BookingConfirmationService


class BookingService:
    def __init__(self, session: Session):
        self.session = session

    def book(
        self,
        *,
        patient_id: int,
        slot_id: int,
        body_part: str,
        issue_type: str,
        call_id: int | None,
        booking_source: str,
        confirmation_token: str | None,
    ) -> Appointment:
        try:
            confirmation_service = BookingConfirmationService(self.session)
            confirmation = confirmation_service.validate_for_booking(
                confirmation_token=confirmation_token,
                patient_id=patient_id,
                slot_id=slot_id,
                body_part=body_part,
                issue_type=issue_type,
                call_id=call_id,
            )
            slot = self.session.scalar(
                select(Slot)
                .where(Slot.id == slot_id)
                .with_for_update()
                .options(selectinload(Slot.doctor), selectinload(Slot.location))
            )
            if slot is None:
                raise ApiError("SLOT_NOT_FOUND", "The selected appointment slot was not found.", 404)
            patient = self.session.get(Patient, patient_id)
            if patient is None:
                raise ApiError("PATIENT_NOT_FOUND", "Patient was not found.", 404)
            if slot.status != "OPEN":
                raise ApiError(
                    "SLOT_ALREADY_BOOKED",
                    "That appointment time is no longer available. Please choose another slot.",
                    409,
                )
            location_link = self.session.scalar(
                select(DoctorLocation).where(
                    DoctorLocation.doctor_id == slot.doctor_id,
                    DoctorLocation.location_id == slot.location_id,
                )
            )
            if location_link is None:
                raise ApiError(
                    "INVALID_SLOT_LOCATION",
                    "The selected physician does not practice at this slot location.",
                    422,
                )

            history_exists = self.session.scalar(
                select(PatientDoctorHistory.id).where(
                    PatientDoctorHistory.patient_id == patient_id,
                    PatientDoctorHistory.doctor_id == slot.doctor_id,
                )
            )
            patient_status = "RETURNING" if history_exists else "NEW"
            routing = PhysicianRoutingService(self.session).recommend(
                RoutingRequest(
                    patient_id=patient_id,
                    patient_status=patient_status,
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
                available["id"] == slot_id
                for item in routing["ranked_recommendations"]
                for available in item["available_slots"]
            )
            if not exact_slot_valid:
                raise ApiError(
                    "PHYSICIAN_NOT_ELIGIBLE",
                    "The selected physician or slot no longer matches the scheduling protocol.",
                    422,
                )

            appointment = Appointment(
                patient_id=patient_id,
                doctor_id=slot.doctor_id,
                location_id=slot.location_id,
                slot_id=slot.id,
                body_part=routing["normalized_request"]["body_part"],
                issue_type=routing["normalized_request"]["issue_type"],
                status="SCHEDULED",
                booking_source=booking_source.upper(),
                call_id=call_id,
            )
            self.session.add(appointment)
            slot.status = "BOOKED"
            self.session.flush()
            confirmation_service.mark_used(confirmation, appointment_id=appointment.id)

            now = datetime.now(UTC)
            history = self.session.scalar(
                select(PatientDoctorHistory).where(
                    PatientDoctorHistory.patient_id == patient_id,
                    PatientDoctorHistory.doctor_id == slot.doctor_id,
                )
            )
            if history is None:
                history = PatientDoctorHistory(
                    patient_id=patient_id,
                    doctor_id=slot.doctor_id,
                    first_seen_at=slot.starts_at,
                    most_recent_seen_at=slot.starts_at,
                    source="appointment_booking",
                    appointment_id=appointment.id,
                )
                self.session.add(history)
            else:
                history.most_recent_seen_at = max(history.most_recent_seen_at, slot.starts_at)
                history.appointment_id = appointment.id
                history.updated_at = now

            if call_id is not None:
                call = self.session.get(Call, call_id)
                if call is None:
                    raise ApiError("CALL_NOT_FOUND", "Call was not found.", 404)
                call.appointment_id = appointment.id
                call.patient_id = patient_id
                call.status = "SCHEDULED"
                call.ended_at = call.ended_at or now

            self.session.commit()
            return appointment
        except ApiError:
            self.session.rollback()
            raise
        except (IntegrityError, OperationalError) as error:
            self.session.rollback()
            raise ApiError(
                "SLOT_ALREADY_BOOKED",
                "That appointment time was just booked by another request. Please choose another slot.",
                409,
            ) from error
