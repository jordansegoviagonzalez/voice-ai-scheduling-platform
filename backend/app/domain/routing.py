from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, and_, select
from sqlalchemy.orm import Session, selectinload

from app.domain.normalization import normalize_body_part, normalize_issue_type
from app.errors import ApiError
from app.models import (
    Doctor,
    Location,
    Patient,
    PatientDoctorHistory,
    RoutingDecision,
    Slot,
)


@dataclass(frozen=True)
class RoutingRequest:
    patient_id: int | None
    patient_status: str
    body_part: str
    issue_type: str
    preferred_doctor_id: int | None = None
    preferred_location_id: int | None = None
    call_id: int | None = None
    starts_after: datetime | None = None
    ends_before: datetime | None = None


class PhysicianRoutingService:
    def __init__(self, session: Session):
        self.session = session

    def recommend(self, request: RoutingRequest, *, persist: bool = True) -> dict[str, Any]:
        patient_status = request.patient_status.strip().upper()
        if patient_status not in {"NEW", "RETURNING"}:
            raise ApiError(
                "INVALID_PATIENT_STATUS",
                "Patient status must be NEW or RETURNING.",
                422,
                {"patient_status": ["Expected NEW or RETURNING"]},
            )

        body_part = normalize_body_part(request.body_part)
        issue_type = normalize_issue_type(request.issue_type)
        starts_after = request.starts_after or datetime.now(UTC)
        ends_before = request.ends_before or starts_after + timedelta(days=14)
        if ends_before <= starts_after:
            raise ApiError("INVALID_DATE_RANGE", "The end date must be after the start date.", 422)

        patient = self._get_patient(request.patient_id)
        preferred_doctor = self._get_doctor(request.preferred_doctor_id)
        preferred_location = self._get_location(request.preferred_location_id)

        doctors = list(
            self.session.scalars(
                select(Doctor)
                .where(Doctor.active.is_(True))
                .options(selectinload(Doctor.capabilities), selectinload(Doctor.locations))
                .order_by(Doctor.last_name, Doctor.first_name)
            )
        )
        history_doctor_ids = self._history_doctor_ids(patient.id if patient else None)
        open_slots = self._open_slots(starts_after, ends_before)
        slots_by_doctor: dict[int, list[Slot]] = {}
        for slot in open_slots:
            slots_by_doctor.setdefault(slot.doctor_id, []).append(slot)

        eligible: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        availability_exceptions: list[dict[str, Any]] = []
        decisions: list[RoutingDecision] = []
        context = {
            "patient_id": request.patient_id,
            "patient_status": patient_status,
            "body_part": body_part,
            "issue_type": issue_type,
            "preferred_doctor_id": request.preferred_doctor_id,
            "preferred_location_id": request.preferred_location_id,
            "starts_after": starts_after.isoformat(),
            "ends_before": ends_before.isoformat(),
        }

        for doctor in doctors:
            reason = self._eligibility_reason(
                doctor=doctor,
                body_part=body_part,
                issue_type=issue_type,
                history_doctor_ids=history_doctor_ids,
            )
            if reason is not None:
                reason_code, message = reason
                item = {
                    "doctor": self._doctor_payload(doctor),
                    "reason_code": reason_code,
                    "reason": message,
                    "is_preferred_doctor": doctor.id == request.preferred_doctor_id,
                }
                rejected.append(item)
                decisions.append(
                    self._decision(
                        request.call_id,
                        request.patient_id,
                        doctor.id,
                        "REJECTED",
                        reason_code,
                        message,
                        context,
                    )
                )
                continue

            doctor_slots = slots_by_doctor.get(doctor.id, [])
            location_match_slots = [slot for slot in doctor_slots if slot.location_id == request.preferred_location_id]
            ordered_slots = sorted(
                doctor_slots,
                key=lambda slot: (
                    0 if slot.location_id == request.preferred_location_id else 1,
                    slot.starts_at,
                    slot.id,
                ),
            )
            item = {
                "doctor": self._doctor_payload(doctor),
                "has_patient_history": doctor.id in history_doctor_ids,
                "is_preferred_doctor": doctor.id == request.preferred_doctor_id,
                "preferred_location_match": bool(location_match_slots) if request.preferred_location_id else None,
                "available_slots": [self._slot_payload(slot) for slot in ordered_slots],
            }
            eligible.append(item)
            decisions.append(
                self._decision(
                    request.call_id,
                    request.patient_id,
                    doctor.id,
                    "ACCEPTED",
                    "VALID_CANDIDATE",
                    f"{doctor.full_name} matches the requested body part, issue type, and patient eligibility rules.",
                    context,
                )
            )
            if not ordered_slots:
                message = f"{doctor.full_name} is clinically eligible but has no open slots in the selected date range."
                availability_exceptions.append(
                    {
                        "doctor": self._doctor_payload(doctor),
                        "reason_code": "NO_OPEN_SLOTS",
                        "reason": message,
                    }
                )
                decisions.append(
                    self._decision(
                        request.call_id,
                        request.patient_id,
                        doctor.id,
                        "REJECTED",
                        "NO_OPEN_SLOTS",
                        message,
                        context,
                    )
                )

        ranked = [item for item in eligible if item["available_slots"]]
        ranked.sort(
            key=lambda item: (
                0 if item["is_preferred_doctor"] else 1,
                0 if item["preferred_location_match"] else 1,
                item["available_slots"][0]["starts_at"],
                item["doctor"]["id"],
            )
        )

        recommendation = ranked[0] if ranked else None
        fallback_info = self._fallback_info(
            eligible=eligible,
            ranked=ranked,
            preferred_doctor=preferred_doctor,
            preferred_location=preferred_location,
        )
        if fallback_info and recommendation:
            decisions.append(
                self._decision(
                    request.call_id,
                    request.patient_id,
                    recommendation["doctor"]["id"],
                    "ACCEPTED",
                    "FALLBACK_SELECTED",
                    fallback_info,
                    context,
                )
            )

        if persist and decisions:
            self.session.add_all(decisions)
            self.session.flush()

        return {
            "normalized_request": context,
            "eligible_doctors": eligible,
            "rejected_doctors": rejected,
            "availability_exceptions": availability_exceptions,
            "ranked_recommendations": ranked,
            "recommended": recommendation,
            "fallback_explanation": fallback_info,
            "caller_safe_summary": self._caller_summary(
                recommendation, rejected, availability_exceptions, preferred_doctor, preferred_location
            ),
        }

    def _get_patient(self, patient_id: int | None) -> Patient | None:
        if patient_id is None:
            return None
        patient = self.session.get(Patient, patient_id)
        if patient is None:
            raise ApiError("PATIENT_NOT_FOUND", "Patient was not found.", 404)
        return patient

    def _get_doctor(self, doctor_id: int | None) -> Doctor | None:
        if doctor_id is None:
            return None
        doctor = self.session.get(Doctor, doctor_id)
        if doctor is None:
            raise ApiError("DOCTOR_NOT_FOUND", "Preferred physician was not found.", 404)
        return doctor

    def _get_location(self, location_id: int | None) -> Location | None:
        if location_id is None:
            return None
        location = self.session.get(Location, location_id)
        if location is None:
            raise ApiError("LOCATION_NOT_FOUND", "Preferred location was not found.", 404)
        return location

    def _history_doctor_ids(self, patient_id: int | None) -> set[int]:
        if patient_id is None:
            return set()
        return set(
            self.session.scalars(
                select(PatientDoctorHistory.doctor_id).where(PatientDoctorHistory.patient_id == patient_id)
            )
        )

    def _open_slots(self, starts_after: datetime, ends_before: datetime) -> list[Slot]:
        statement: Select[tuple[Slot]] = (
            select(Slot)
            .where(
                and_(
                    Slot.status == "OPEN",
                    Slot.starts_at >= starts_after,
                    Slot.starts_at < ends_before,
                )
            )
            .options(selectinload(Slot.location), selectinload(Slot.doctor))
            .order_by(Slot.starts_at, Slot.id)
        )
        return list(self.session.scalars(statement))

    def _eligibility_reason(
        self,
        *,
        doctor: Doctor,
        body_part: str,
        issue_type: str,
        history_doctor_ids: set[int],
    ) -> tuple[str, str] | None:
        capabilities_for_body = [cap for cap in doctor.capabilities if cap.body_part == body_part]
        if not capabilities_for_body:
            return (
                "BODY_PART_NOT_SUPPORTED",
                f"{doctor.full_name} does not treat {body_part.lower()} conditions under this protocol.",
            )
        exact_match = any(cap.issue_type == issue_type for cap in capabilities_for_body)
        if not exact_match:
            accepted = ", ".join(sorted({cap.issue_type for cap in capabilities_for_body}))
            return (
                "ISSUE_TYPE_NOT_SUPPORTED",
                f"{doctor.full_name} treats {body_part.lower()} cases for {accepted}, but not {issue_type.lower()}.",
            )
        if not doctor.accepts_new_patients and doctor.id not in history_doctor_ids:
            return (
                "PATIENT_HAS_NO_HISTORY_WITH_DOCTOR",
                f"{doctor.full_name} is not accepting patients who have not previously been treated by this physician.",
            )
        return None

    def _fallback_info(
        self,
        *,
        eligible: list[dict[str, Any]],
        ranked: list[dict[str, Any]],
        preferred_doctor: Doctor | None,
        preferred_location: Location | None,
    ) -> str | None:
        if not ranked:
            return None
        selected = ranked[0]
        selected_name = selected["doctor"]["full_name"]
        if preferred_doctor and selected["doctor"]["id"] != preferred_doctor.id:
            preferred = next((item for item in eligible if item["doctor"]["id"] == preferred_doctor.id), None)
            if preferred and not preferred["available_slots"]:
                return (
                    f"{preferred_doctor.full_name} meets the clinical rules but has no open slots, "
                    f"so {selected_name} is the next valid option."
                )
        if preferred_location and not selected["preferred_location_match"]:
            return (
                f"No matching opening was found at {preferred_location.name}; the next valid opening "
                f"is with {selected_name} at another approved location and requires caller confirmation."
            )
        no_slot_doctors = [item for item in eligible if not item["available_slots"]]
        if no_slot_doctors:
            return (
                f"The first clinically eligible physician has no open slots, so {selected_name} is the "
                "next physician with a valid opening."
            )
        return None

    def _caller_summary(
        self,
        recommendation: dict[str, Any] | None,
        rejected: list[dict[str, Any]],
        availability_exceptions: list[dict[str, Any]],
        preferred_doctor: Doctor | None,
        preferred_location: Location | None,
    ) -> str:
        if recommendation:
            slot = recommendation["available_slots"][0]
            intro = (
                f"The earliest matching opening is with {recommendation['doctor']['full_name']} at "
                f"{slot['location']['name']} on {slot['starts_at']}."
            )
            if preferred_doctor:
                rejection = next(
                    (item for item in rejected if item["doctor"]["id"] == preferred_doctor.id),
                    None,
                )
                if rejection:
                    intro = f"{rejection['reason']} {intro}"
            if preferred_location and not recommendation["preferred_location_match"]:
                intro = (
                    f"There are no matching openings at {preferred_location.name}. "
                    f"{intro} Please confirm the different location before booking."
                )
            return intro
        if availability_exceptions:
            return "Matching physicians were found, but none has an open slot in the selected date range."
        return "No physician matches the requested body part, issue type, and patient eligibility rules."

    @staticmethod
    def _doctor_payload(doctor: Doctor) -> dict[str, Any]:
        return {
            "id": doctor.id,
            "first_name": doctor.first_name,
            "last_name": doctor.last_name,
            "full_name": doctor.full_name,
            "accepts_new_patients": doctor.accepts_new_patients,
            "locations": [
                {"id": location.id, "code": location.code, "name": location.name}
                for location in sorted(doctor.locations, key=lambda item: item.id)
            ],
            "capabilities": [
                {"body_part": cap.body_part, "issue_type": cap.issue_type}
                for cap in sorted(doctor.capabilities, key=lambda item: (item.body_part, item.issue_type))
            ],
        }

    @staticmethod
    def _slot_payload(slot: Slot) -> dict[str, Any]:
        return {
            "id": slot.id,
            "starts_at": slot.starts_at.isoformat(),
            "ends_at": slot.ends_at.isoformat(),
            "status": slot.status,
            "doctor_id": slot.doctor_id,
            "location": {
                "id": slot.location.id,
                "code": slot.location.code,
                "name": slot.location.name,
            },
        }

    @staticmethod
    def _decision(
        call_id: int | None,
        patient_id: int | None,
        doctor_id: int | None,
        decision: str,
        reason_code: str,
        message: str,
        context: dict[str, Any],
    ) -> RoutingDecision:
        return RoutingDecision(
            call_id=call_id,
            patient_id=patient_id,
            doctor_id=doctor_id,
            decision=decision,
            reason_code=reason_code,
            human_readable_reason=message,
            request_context=context,
            created_at=datetime.now(UTC),
        )
