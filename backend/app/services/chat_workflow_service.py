from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.domain.chat.chat_state import ChatState
from app.domain.chat.chat_steps import ChatStep
from app.domain.routing import PhysicianRoutingService, RoutingRequest
from app.errors import ApiError
from app.models import Appointment, Doctor, Location, Slot
from app.models.chat import ChatMessage, ChatSession, ChatSessionEvent
from app.services.ai_intake_service import AIIntakeService
from app.services.booking import BookingService
from app.services.chat_session_service import ChatSessionService
from app.services.confirmation import BookingConfirmationService
from app.services.escalation_service import EscalationService
from app.services.patient_access_service import PatientAccessService
from app.services.serializers import appointment_json

RETURNING_REQUIRED_FIELDS = [
    "chief_complaint",
    "body_part",
    "side",
    "symptom_duration",
    "severity",
    "appointment_type",
    "issue_type",
    "preferred_location",
    "preferred_time_of_day",
    "preferred_date_or_time",
]
NEW_PATIENT_FIELDS = ["full_name", "date_of_birth", "phone", "email", "insurance_provider"]
TERMINAL_STATES = {ChatState.CONFIRMED, ChatState.ESCALATED, ChatState.CARE_TEAM_HANDOFF, ChatState.ABANDONED}
CLINIC_TIMEZONE = ZoneInfo("America/Los_Angeles")


class ChatWorkflowService:
    def __init__(
        self,
        *,
        organization_id: int,
        db_session: Session,
        chat_service: ChatSessionService,
        patient_access: PatientAccessService,
        ai_intake: AIIntakeService,
        escalation: EscalationService,
        routing: PhysicianRoutingService,
        booking: BookingService,
    ):
        self.organization_id = organization_id
        self.session = db_session
        self.chat_service = chat_service
        self.patient_access = patient_access
        self.ai_intake = ai_intake
        self.escalation = escalation
        self.routing = routing
        self.booking = booking

    def authenticate_returning_patient(self, session_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        patient = self.patient_access.verify_returning_patient(
            organization_id=self.organization_id,
            email=payload.get("email"),
            password=payload.get("password"),
            full_name=payload.get("fullName"),
            dob=payload.get("dateOfBirth"),
            phone=payload.get("phone"),
        )
        chat_session = self.chat_service.update_session_state(
            session_id,
            patient_id=patient.id,
            status=ChatState.COLLECTING_INTAKE,
            current_step=ChatStep.COLLECT_INTAKE,
            collected_data={
                **(self._session_or_404(session_id).collected_data_json or {}),
                "patient_type": "returning",
                "full_name": patient.full_name,
                "date_of_birth": patient.date_of_birth.isoformat(),
                "phone": patient.phone,
                "email": patient.email,
            },
        )
        msg = self.chat_service.ensure_welcome_message(chat_session, patient, "returning")
        return self._session_payload(chat_session, assistant_message=msg)

    from app.observability.langsmith_tracing import safe_traceable

    @safe_traceable(name="Chat Scheduling Flow")
    def handle_message(self, session_id: int, message: str) -> dict[str, Any]:
        if not isinstance(message, str) or not message.strip():
            raise ApiError("VALIDATION_ERROR", "Message is required.", 422, {"message": ["Required"]})
        chat_session = self._session_or_404(session_id)
        if chat_session.status in TERMINAL_STATES:
            raise ApiError("SESSION_CLOSED", "This chat session is closed for new messages.", 409)

        patient_msg = self.chat_service.add_message(session_id, "patient", message)
        chat_session = self._session_or_404(session_id)
        recent = self.chat_service.get_recent_messages(session_id, 10)
        result = self.ai_intake.process_message(
            session=chat_session,
            recent_messages=recent[:-1],
            latest_message=message,
        )

        if result.escalation_type:
            assistant = self.chat_service.add_message(session_id, "assistant", result.assistant_reply)
            self.escalation.escalate_session(
                session_id,
                result.escalation_type,
                result.escalation_type,
                patient_msg.id,
            )
            return self._session_payload(self._session_or_404(session_id), assistant_message=assistant)

        if result.provider_error:
            self.chat_service.log_event(session_id, "provider_failure", result.provider_error)

        if result.invalid_fields:
            self.chat_service.log_event(session_id, "invalid_input", {"fields": result.invalid_fields})
            self.chat_service.update_session_state(session_id, collected_data=result.updated_data)
            assistant = self.chat_service.add_message(session_id, "assistant", result.assistant_reply)
            return self._session_payload(self._session_or_404(session_id), assistant_message=assistant)

        for correction in result.corrections or []:
            self.chat_service.log_event(session_id, "field_corrected", correction)

        if result.confidence is not None and result.confidence < 0.35:
            self.chat_service.log_event(session_id, "low_confidence", {"confidence": result.confidence})
            if self._event_count(session_id, "low_confidence") >= 2:
                assistant = self.chat_service.add_message(
                    session_id,
                    "assistant",
                    "I am having trouble interpreting this safely. This should be handled by the care team.",
                )
                self.escalation.escalate_session(
                    session_id,
                    "care_team_handoff",
                    "Repeated low-confidence intake interpretation",
                    patient_msg.id,
                )
                return self._session_payload(self._session_or_404(session_id), assistant_message=assistant)

        if result.off_topic:
            self.chat_service.log_event(session_id, "off_topic", {"confidence": result.confidence})

        chat_session = self.chat_service.update_session_state(session_id, collected_data=result.updated_data)
        if self._intake_complete(chat_session):
            if chat_session.collected_data_json.get("patient_type") == "new" and not chat_session.patient_id:
                patient, created = self.patient_access.create_or_get_new_patient(
                    organization_id=self.organization_id,
                    full_name=str(chat_session.collected_data_json["full_name"]),
                    date_of_birth=str(chat_session.collected_data_json["date_of_birth"]),
                    phone=str(chat_session.collected_data_json["phone"]),
                    email=chat_session.collected_data_json.get("email"),
                    insurance_provider=chat_session.collected_data_json.get("insurance_provider"),
                )
                self.chat_service.log_event(
                    session_id,
                    "patient_created" if created else "patient_reused",
                    {"patient_id": patient.id},
                )
                chat_session = self.chat_service.update_session_state(session_id, patient_id=patient.id)
            return self._route_completed_intake(chat_session)

        assistant = self.chat_service.add_message(session_id, "assistant", result.assistant_reply)
        return self._session_payload(self._session_or_404(session_id), assistant_message=assistant)

    def select_appointment(self, session_id: int, slot_id: int) -> dict[str, Any]:
        chat_session = self._session_or_404(session_id)
        if chat_session.status not in {ChatState.SELECTING_APPOINTMENT, ChatState.CONFIRMED}:
            raise ApiError("SESSION_NOT_READY", "Not ready to select an appointment.", 409)

        self._assert_slot_in_session_organization(chat_session, slot_id)
        if not self._slot_was_offered(chat_session, slot_id):
            raise ApiError("SLOT_NOT_OFFERED", "The selected slot was not offered for this intake.", 422)

        routing_result = dict(chat_session.routing_result_json or {})
        routing_result["selected_slot_id"] = slot_id

        selected = self._selected_recommendation(chat_session, slot_id)
        if selected:
            routing_result["selected_recommendation"] = selected

        self.chat_service.update_session_state(session_id, routing_result=routing_result)
        return self._session_payload(self._session_or_404(session_id))

    def confirm_appointment(self, session_id: int) -> tuple[dict[str, Any], int]:
        chat_session = self._session_or_404(session_id)
        if not chat_session.patient_id:
            raise ApiError("PATIENT_REQUIRED", "Patient identity is required before booking.", 422)

        routing_result = chat_session.routing_result_json or {}
        slot_id = routing_result.get("selected_slot_id")

        if not slot_id:
            raise ApiError("VALIDATION_ERROR", "No slot selected.", 422)

        if chat_session.status == ChatState.CONFIRMED and routing_result.get("appointment_id"):
            return self._session_payload(chat_session), 200

        if chat_session.status != ChatState.SELECTING_APPOINTMENT:
            raise ApiError("SESSION_NOT_READY", "Choose an appointment slot before confirming.", 409)
        self._assert_slot_in_session_organization(chat_session, slot_id)
        if not self._slot_was_offered(chat_session, slot_id):
            raise ApiError("SLOT_NOT_OFFERED", "The selected slot was not offered for this intake.", 422)

        data = chat_session.collected_data_json
        try:
            confirmation = BookingConfirmationService(self.session).confirm(
                call_id=None,
                patient_id=chat_session.patient_id,
                slot_id=slot_id,
                body_part=str(data["body_part"]),
                issue_type=str(data["issue_type"]),
                source="WEB_CHAT",
            )
            appointment = self.booking.book(
                patient_id=chat_session.patient_id,
                slot_id=slot_id,
                body_part=str(data["body_part"]),
                issue_type=str(data["issue_type"]),
                call_id=None,
                booking_source="WEB_CHAT",
                confirmation_token=confirmation.confirmation_token,
            )
        except ApiError as error:
            if error.code in {"SLOT_ALREADY_BOOKED", "BOOKING_CONFIRMATION_STALE"}:
                refreshed = self._route_for_data(chat_session)
                self.chat_service.update_session_state(session_id, routing_result=refreshed)
                assistant = self.chat_service.add_message(
                    session_id,
                    "assistant",
                    "That appointment time is no longer available. I refreshed the available options.",
                )
                return self._session_payload(self._session_or_404(session_id), assistant_message=assistant), 409
            raise

        refreshed_appointment = self.session.scalar(
            select(Appointment)
            .where(Appointment.id == appointment.id)
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.doctor).selectinload(Doctor.locations),
                selectinload(Appointment.doctor).selectinload(Doctor.capabilities),
                selectinload(Appointment.location),
                selectinload(Appointment.slot),
            )
        )
        routing_result = dict(chat_session.routing_result_json or {})
        routing_result["appointment_id"] = appointment.id
        selected = self._selected_recommendation(chat_session, slot_id)
        if selected:
            routing_result["selected_recommendation"] = selected
            fallback = selected.get("location_fallback")
            if fallback:
                routing_result["selected_alternative_location"] = fallback.get("selected_location")
                routing_result["redirect_reason"] = fallback.get("reason_code")
        self.chat_service.update_session_state(
            session_id,
            status=ChatState.CONFIRMED,
            current_step=ChatStep.BOOKING_CONFIRMATION,
            routing_result=routing_result,
            appointment_id=appointment.id,
        )
        self.chat_service.log_event(session_id, "appointment_booked", {"appointment_id": appointment.id})
        app_date = appointment.slot.starts_at.astimezone(CLINIC_TIMEZONE)
        date_str = app_date.strftime("%A, %B ") + str(app_date.day)
        time_str = app_date.strftime("%I:%M %p").lstrip("0")

        assistant = self.chat_service.add_message(
            session_id,
            "assistant",
            f"Your appointment is confirmed with {appointment.doctor.full_name}"
            f" at {appointment.location.name} on {date_str} at {time_str}.",
        )
        payload = self._session_payload(self._session_or_404(session_id), assistant_message=assistant)
        payload["booking"] = appointment_json(refreshed_appointment or appointment)

        return payload, 200

    def _route_completed_intake(self, chat_session: ChatSession) -> dict[str, Any]:
        self.chat_service.update_session_state(
            chat_session.id,
            status=ChatState.ROUTING,
            current_step=ChatStep.ROUTING_RECOMMENDATION,
        )
        routing_result = self._route_for_data(chat_session)
        recommendations = routing_result.get("web_recommendations", [])
        if not recommendations:
            self.chat_service.update_session_state(chat_session.id, routing_result=routing_result)
            assistant_text = routing_result.get("caller_safe_summary") or (
                "I could not find an eligible opening for those details. This should be handled by the care team."
            )
            assistant = self.chat_service.add_message(chat_session.id, "assistant", assistant_text)
            self.escalation.escalate_session(chat_session.id, "care_team_handoff", assistant_text, assistant.id)
            return self._session_payload(self._session_or_404(chat_session.id), assistant_message=assistant)

        self.chat_service.update_session_state(
            chat_session.id,
            status=ChatState.SELECTING_APPOINTMENT,
            current_step=ChatStep.SLOT_SELECTION,
            routing_result=routing_result,
        )
        first = recommendations[0]
        summary = routing_result.get("caller_safe_summary")
        assistant = self.chat_service.add_message(
            chat_session.id,
            "assistant",
            summary
            or (
                f"I found {len(recommendations)} matching option"
                f"{'' if len(recommendations) == 1 else 's'}. The earliest is with "
                f"{first['physician_name']} at {first['clinic_location']}."
            ),
        )
        return self._session_payload(self._session_or_404(chat_session.id), assistant_message=assistant)

    def _route_for_data(self, chat_session: ChatSession) -> dict[str, Any]:
        data = chat_session.collected_data_json
        location_id = self._location_id_for_preference(data.get("preferred_location"))
        doctor_id = self._doctor_id_for_preference(data.get("preferred_physician"))
        routing_result = self.routing.recommend(
            RoutingRequest(
                organization_id=chat_session.organization_id,
                patient_id=chat_session.patient_id,
                patient_status=str(data.get("patient_type", "new")).upper(),
                body_part=str(data["body_part"]),
                issue_type=str(data["issue_type"]),
                preferred_doctor_id=doctor_id,
                preferred_location_id=location_id,
            ),
            persist=False,
        )
        enriched = dict(routing_result)
        enriched["web_recommendations"] = self._web_recommendations(routing_result, data)
        return enriched

    def _web_recommendations(self, routing_result: dict[str, Any], data: dict[str, Any]) -> list[dict[str, Any]]:
        preferred_time = data.get("preferred_time_of_day")
        preferred_location = _preferred_location_payload(routing_result)
        recommendations: list[dict[str, Any]] = []
        for item in routing_result.get("ranked_recommendations", [])[:3]:
            slots = self._rank_slots(item.get("available_slots", []), preferred_time)
            if not slots:
                continue
            doctor = item["doctor"]

            slots_by_loc: dict[int, list[dict[str, Any]]] = {}
            for slot in slots:
                loc_id = slot["location"]["id"]
                if loc_id not in slots_by_loc:
                    slots_by_loc[loc_id] = []
                slots_by_loc[loc_id].append(slot)

            locations: list[dict[str, Any]] = []
            for _loc_id, loc_slots in slots_by_loc.items():
                first_slot = loc_slots[0]
                loc_labels = []
                alternative_location = (
                    preferred_location is not None and first_slot["location"]["code"] != preferred_location["code"]
                )
                if alternative_location:
                    loc_labels.append("Alternative location")
                elif preferred_location is not None and first_slot["location"]["code"] == preferred_location["code"]:
                    loc_labels.append("Preferred location")

                locations.append(
                    {
                        "clinic_location": first_slot["location"]["name"],
                        "clinic_location_code": first_slot["location"]["code"],
                        "is_preferred": not alternative_location if preferred_location else True,
                        "labels": loc_labels,
                        "available_slots": loc_slots[:6],
                    }
                )

            # Sort locations: preferred first, then by earliest slot
            locations.sort(
                key=lambda loc_item: (
                    0 if loc_item["is_preferred"] else 1,
                    loc_item["available_slots"][0]["starts_at"],
                )
            )

            labels = ["Recommended"]
            if item.get("has_patient_history"):
                labels.append("Previous physician")
            if (
                preferred_time
                and preferred_time != "any"
                and any(_slot_matches_time(loc["available_slots"][0], preferred_time) for loc in locations)
            ):
                labels.append("Matches preferred time")
            if len(labels) == 1:
                labels.append("Earliest available")

            match_explanation = (
                f"{doctor['full_name']} matches your orthopedic scheduling request and has real open slots."
            )
            if item.get("is_general_orthopedics") or doctor.get("is_general_orthopedics"):
                labels.append("General Orthopedics")
                match_explanation = (
                    "This physician provides general orthopedic evaluation and can help determine the appropriate "
                    "next step for your condition."
                )
            elif preferred_location is not None and not any(loc["is_preferred"] for loc in locations):
                match_explanation = (
                    f"No matching opening was available at {preferred_location['name']}. "
                    f"{doctor['full_name']} matches your orthopedic request and has real open slots at "
                    f"alternative locations."
                )

            rec = {
                "physician_id": doctor["id"],
                "physician_name": doctor["full_name"],
                "initials": f"{doctor['first_name'][:1]}{doctor['last_name'][:1]}",
                "specialty": _recommendation_specialty(item, doctor, data),
                "is_general_orthopedics": bool(item.get("is_general_orthopedics")),
                "primary_specialty": item.get("primary_specialty") or doctor.get("primary_specialty"),
                "match_explanation": match_explanation,
                "labels": labels,
                "locations": locations,
            }
            if "location_fallback" in item:
                rec["location_fallback"] = item["location_fallback"]

            recommendations.append(rec)
        return recommendations

    def _rank_slots(self, slots: list[dict[str, Any]], preferred_time: object) -> list[dict[str, Any]]:
        if preferred_time and preferred_time != "any":
            ranked = sorted(slots, key=lambda slot: 0 if _slot_matches_time(slot, preferred_time) else 1)
        else:
            ranked = slots

        deduped: list[dict[str, Any]] = []
        seen: set[tuple[object, object, object]] = set()
        for slot in ranked:
            key = (slot.get("doctor_id"), slot.get("location", {}).get("id"), slot.get("starts_at"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(slot)
        return deduped

    def _intake_complete(self, chat_session: ChatSession) -> bool:
        data = chat_session.collected_data_json or {}
        required = list(RETURNING_REQUIRED_FIELDS)
        if data.get("patient_type") == "new":
            required.extend(NEW_PATIENT_FIELDS)
        return all(data.get(field) not in (None, "") for field in required)

    def _slot_was_offered(self, chat_session: ChatSession, slot_id: int) -> bool:
        routing_result = chat_session.routing_result_json or {}
        for recommendation in routing_result.get("web_recommendations", []):
            if any(slot["id"] == slot_id for slot in recommendation.get("available_slots", [])):
                return True
            if any(
                slot["id"] == slot_id
                for loc in recommendation.get("locations", [])
                for slot in loc.get("available_slots", [])
            ):
                return True
        return False

    def _selected_recommendation(self, chat_session: ChatSession, slot_id: int) -> dict[str, Any] | None:
        routing_result = chat_session.routing_result_json or {}
        for recommendation in routing_result.get("web_recommendations", []):
            if any(slot["id"] == slot_id for slot in recommendation.get("available_slots", [])):
                return recommendation
            if any(
                slot["id"] == slot_id
                for loc in recommendation.get("locations", [])
                for slot in loc.get("available_slots", [])
            ):
                return recommendation
        return None

    def _event_count(self, session_id: int, event_type: str) -> int:
        return int(
            self.session.scalar(
                select(func.count(ChatSessionEvent.id)).where(
                    ChatSessionEvent.session_id == session_id,
                    ChatSessionEvent.event_type == event_type,
                )
            )
            or 0
        )

    def _location_id_for_preference(self, value: object) -> int | None:
        if not value:
            return None
        code = str(value).strip().upper()
        if code in {"ANY", "NEAREST", "NEAREST_AVAILABLE", "EARLIEST_ANY_LOCATION"}:
            return None
        return self.session.scalar(
            select(Location.id).where(Location.organization_id == self.organization_id, Location.code == code)
        )

    def _doctor_id_for_preference(self, value: object) -> int | None:
        if not value:
            return None
        cleaned = _doctor_key(str(value))
        doctors = self.session.scalars(
            select(Doctor).where(Doctor.organization_id == self.organization_id, Doctor.active.is_(True))
        ).all()
        for doctor in doctors:
            if cleaned in {_doctor_key(doctor.full_name), _doctor_key(doctor.last_name)}:
                return doctor.id
        return None

    def _session_or_404(self, session_id: int) -> ChatSession:
        chat_session = self.chat_service.get_session(session_id)
        if chat_session is None:
            raise ApiError("CHAT_SESSION_NOT_FOUND", "Chat session was not found.", 404)
        if chat_session.organization_id != self.organization_id:
            raise ApiError("CHAT_SESSION_NOT_FOUND", "Chat session was not found.", 404)
        return chat_session

    def _assert_slot_in_session_organization(self, chat_session: ChatSession, slot_id: int) -> None:
        slot_organization_id = self.session.scalar(select(Slot.organization_id).where(Slot.id == slot_id))
        if slot_organization_id != chat_session.organization_id:
            raise ApiError("SLOT_NOT_OFFERED", "The selected slot was not offered for this intake.", 422)

    def _session_payload(self, chat_session: ChatSession, *, assistant_message: object | None = None) -> dict[str, Any]:
        from app.domain.routing_action import compute_routing_action
        routing_result = chat_session.routing_result_json or {}
        action = compute_routing_action(
            chat_status=chat_session.status,
            escalation_type=chat_session.escalation_type,
            routing_result=routing_result,
            is_clarifying=chat_session.status == ChatState.COLLECTING_INTAKE
        )
        payload: dict[str, Any] = {
            "sessionId": chat_session.id,
            "status": chat_session.status,
            "currentStep": chat_session.current_step,
            "routingAction": action.value,
            "patient": {
                "id": chat_session.patient.id,
                "fullName": chat_session.patient.full_name,
            }
            if chat_session.patient
            else None,
            "collectedData": chat_session.collected_data_json,
            "routingResult": routing_result,
            "recommendations": routing_result.get("web_recommendations", []),
            "availableSlots": [
                slot
                for recommendation in routing_result.get("web_recommendations", [])
                for loc in recommendation.get("locations", [])
                for slot in loc.get("available_slots", [])
            ],
            "appointmentId": chat_session.appointment_id,
            "booking": appointment_json(chat_session.appointment) if chat_session.appointment else None,
            "escalation": {
                "type": chat_session.escalation_type,
                "reason": chat_session.escalation_reason,
                "triggerMessageId": chat_session.escalation_trigger_message_id,
            }
            if chat_session.escalation_type
            else None,
            "messages": [
                {"role": message.role, "content": message.content, "sequenceNumber": message.sequence_number}
                for message in self.session.scalars(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == chat_session.id)
                    .order_by(ChatMessage.sequence_number)
                )
            ],
        }
        if assistant_message is not None:
            payload["assistantMessage"] = {
                "role": getattr(assistant_message, "role", "assistant"),
                "content": getattr(assistant_message, "content", ""),
            }
        return payload


def _slot_matches_time(slot: dict[str, Any], preferred_time: object) -> bool:
    starts_at = datetime.fromisoformat(str(slot["starts_at"]))
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=UTC)
    local_hour = starts_at.astimezone(CLINIC_TIMEZONE).hour
    if preferred_time == "morning":
        return local_hour < 12
    if preferred_time == "afternoon":
        return local_hour >= 12
    return True


def _preferred_location_payload(routing_result: dict[str, Any]) -> dict[str, Any] | None:
    normalized = routing_result.get("normalized_request")
    if not isinstance(normalized, dict):
        return None
    preferred_location = normalized.get("preferred_location")
    if isinstance(preferred_location, dict) and preferred_location.get("code") and preferred_location.get("name"):
        return preferred_location
    return None


def _doctor_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().replace("dr.", "").strip())


def _recommendation_specialty(item: dict[str, Any], doctor: dict[str, Any], data: dict[str, Any]) -> str:
    if item.get("is_general_orthopedics") or doctor.get("is_general_orthopedics"):
        return "General Orthopedics"
    body_part = str(data["body_part"])
    issue_type = str(data["issue_type"])
    if body_part == "Foot/Ankle":
        return "Foot and Ankle Orthopedics"
    if issue_type == "Sports Medicine":
        return f"{body_part} Sports Medicine"
    if issue_type == "Joint Replacement":
        return f"{body_part} Joint Replacement"
    if issue_type == "Fracture":
        return f"{body_part} Fracture Care"
    return f"{body_part} Orthopedics"
