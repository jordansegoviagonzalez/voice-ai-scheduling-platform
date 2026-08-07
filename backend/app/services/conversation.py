from __future__ import annotations

from typing import Any

from flask import Flask
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.routing import PhysicianRoutingService, RoutingRequest
from app.errors import ApiError
from app.integrations.openai import OpenAIIntentAdapter, StructuredIntent
from app.models import Call, Doctor, Location
from app.services.integration_status import OPENAI_INTEGRATION, record_integration_result
from app.services.organization_context import default_organization_id


class ConversationOrchestrator:
    def __init__(self, session: Session, app: Flask, adapter: OpenAIIntentAdapter | None = None):
        self.session = session
        self.app = app
        self.adapter = adapter or OpenAIIntentAdapter(
            api_key=app.config.get("OPENAI_API_KEY"),
            model=str(app.config.get("OPENAI_MODEL", "gpt-5.2")),
            integration_mode=str(app.config.get("OPENAI_INTEGRATION_MODE", "live")),
            timeout_seconds=float(app.config.get("OPENAI_TIMEOUT_SECONDS", 8)),
            max_retries=int(app.config.get("OPENAI_MAX_RETRIES", 2)),
        )

    def interpret(
        self,
        *,
        raw_user_text: str,
        previous_state: dict[str, Any] | None = None,
        patient_id: int | None = None,
        call_id: int | None = None,
        organization_id: int | None = None,
    ) -> dict[str, Any]:
        organization_id = self._organization_id(call_id, explicit_organization_id=organization_id)
        doctors = list(
            self.session.scalars(
                select(Doctor)
                .where(Doctor.organization_id == organization_id, Doctor.active.is_(True))
                .order_by(Doctor.last_name)
            )
        )
        locations = list(
            self.session.scalars(
                select(Location).where(Location.organization_id == organization_id).order_by(Location.id)
            )
        )
        intent = self.adapter.extract(
            raw_user_text=raw_user_text,
            known_doctor_names=[doctor.full_name for doctor in doctors],
            known_location_codes={location.code for location in locations},
        )
        if str(self.app.config.get("OPENAI_INTEGRATION_MODE", "live")).lower() == "live":
            record_integration_result(
                self.session,
                integration_name=OPENAI_INTEGRATION,
                status="connected",
                detail="Latest live GPT-5.2 structured intent extraction succeeded.",
                metadata={"model": self.app.config.get("OPENAI_MODEL")},
                success=True,
            )
        state = self._merged_state(previous_state or {}, intent)
        if call_id is not None:
            self._persist_call_state(call_id, state, doctors, locations)
        missing = self._missing_required_fields(state)
        if missing:
            return {
                "status": "clarification_required",
                "intent": _intent_json(intent),
                "state": state,
                "missing_fields": missing,
                "clarification_question": intent.clarification_question or self._clarification_for(missing),
                "routing": None,
            }

        doctor_id = (
            self._doctor_id_for_name(str(state["preferred_doctor_name"]), doctors)
            if state.get("preferred_doctor_name")
            else None
        )
        location_id = (
            self._location_id_for_code(str(state["preferred_location_code"]), locations)
            if state.get("preferred_location_code")
            else None
        )
        routing = PhysicianRoutingService(self.session).recommend(
            RoutingRequest(
                organization_id=organization_id,
                patient_id=patient_id,
                patient_status=str(state["patient_status"]),
                body_part=str(state["body_part"]),
                issue_type=str(state["issue_type"]),
                preferred_doctor_id=doctor_id,
                preferred_location_id=location_id,
                call_id=call_id,
            ),
            persist=bool(call_id),
        )
        return {
            "status": "routing_ready",
            "intent": _intent_json(intent),
            "state": state,
            "missing_fields": [],
            "clarification_question": None,
            "routing": routing,
        }

    @staticmethod
    def _merged_state(previous_state: dict[str, Any], intent: StructuredIntent) -> dict[str, Any]:
        state = {
            "patient_status": previous_state.get("patient_status"),
            "body_part": previous_state.get("body_part"),
            "issue_type": previous_state.get("issue_type"),
            "preferred_doctor_name": previous_state.get("preferred_doctor_name"),
            "preferred_location_code": previous_state.get("preferred_location_code"),
        }
        extracted = {
            "patient_status": None if intent.patient_status == "UNKNOWN" else intent.patient_status,
            "body_part": intent.body_part,
            "issue_type": intent.issue_type,
            "preferred_doctor_name": intent.preferred_doctor_name,
            "preferred_location_code": intent.preferred_location_code,
        }
        for key, value in extracted.items():
            if value is not None and not state.get(key):
                state[key] = value
        for key, value in intent.caller_correction.items():
            state[key] = value
        return state

    @staticmethod
    def _missing_required_fields(state: dict[str, Any]) -> list[str]:
        return [field for field in ("patient_status", "body_part", "issue_type") if not state.get(field)]

    @staticmethod
    def _clarification_for(missing: list[str]) -> str:
        prompts = {
            "patient_status": "Are you a new patient or have you seen this physician before?",
            "body_part": "Which body part is the appointment for?",
            "issue_type": "Is this for a fracture, joint replacement, sports injury, or general pain/consultation?",
        }
        return prompts[missing[0]]

    @staticmethod
    def _doctor_id_for_name(name: str, doctors: list[Doctor]) -> int | None:
        return next((doctor.id for doctor in doctors if doctor.full_name == name), None)

    @staticmethod
    def _location_id_for_code(code: str, locations: list[Location]) -> int | None:
        return next((location.id for location in locations if location.code == code), None)

    def _persist_call_state(
        self,
        call_id: int,
        state: dict[str, Any],
        doctors: list[Doctor],
        locations: list[Location],
    ) -> None:
        call = self.session.get(Call, call_id)
        if call is None or call.status in {"SCHEDULED", "REDIRECTED", "ABANDONED", "FAILED"}:
            return
        if state.get("patient_status"):
            call.patient_status = str(state["patient_status"])
        if state.get("body_part"):
            call.requested_body_part = str(state["body_part"])
        if state.get("issue_type"):
            call.requested_issue_type = str(state["issue_type"])
        if state.get("preferred_doctor_name"):
            call.preferred_doctor_id = self._doctor_id_for_name(str(state["preferred_doctor_name"]), doctors)
        if state.get("preferred_location_code"):
            call.preferred_location_id = self._location_id_for_code(str(state["preferred_location_code"]), locations)

    def _organization_id(self, call_id: int | None, *, explicit_organization_id: int | None = None) -> int:
        if call_id is not None:
            call = self.session.get(Call, call_id)
            if call is not None:
                if explicit_organization_id is not None and call.organization_id != explicit_organization_id:
                    raise ApiError(
                        "ORGANIZATION_CONTEXT_MISMATCH",
                        "The requested call does not belong to this organization.",
                        409,
                    )
                return call.organization_id
        if explicit_organization_id is not None:
            return explicit_organization_id
        return default_organization_id(self.session)


def _intent_json(intent: StructuredIntent) -> dict[str, Any]:
    return {
        "raw_user_text": intent.raw_user_text,
        "patient_status": intent.patient_status,
        "body_part": intent.body_part,
        "issue_type": intent.issue_type,
        "preferred_doctor_name": intent.preferred_doctor_name,
        "preferred_location_code": intent.preferred_location_code,
        "clarification_required": intent.clarification_required,
        "clarification_question": intent.clarification_question,
        "caller_correction": intent.caller_correction,
    }
