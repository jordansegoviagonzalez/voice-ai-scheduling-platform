import re
from dataclasses import dataclass
from typing import Any

from app.domain.chat.chat_types import ChatModelResponse
from app.domain.normalization import BODY_PARTS, ORTHOPEDIC_BODY_PARTS
from app.domain.rules.care_team_handoff_rules import HANDOFF_MESSAGE, requires_handoff
from app.domain.rules.emergency_rules import EMERGENCY_MESSAGE, is_possible_emergency
from app.domain.rules.intake_validation import validate_intake_fields
from app.infrastructure.ai.structured_intake import OpenAIIntakeClient
from app.integrations.openai.errors import OpenAIIntegrationError
from app.models.chat import ChatSession

APPROVED_FIELD_QUESTIONS = {
    "symptom_duration": "How long has this been going on?",
    "severity": "On a scale of 1-10, how severe is your pain today?",
    "appointment_type": "Is this a new-patient visit, follow-up, post-op visit, or urgent appointment?",
    "preferred_location": "Which location do you prefer: Main, East, North, West, or South?",
    "preferred_time_of_day": "Do you prefer morning, afternoon, or does any time work?",
    "preferred_date_or_time": "Do you want the earliest available appointment, or do you have a specific date in mind?",
}


@dataclass(frozen=True)
class IntakeProcessingResult:
    updated_data: dict[str, Any]
    assistant_reply: str
    escalation_type: str | None = None
    invalid_fields: dict[str, str] | None = None
    corrections: list[dict[str, Any]] | None = None
    off_topic: bool = False
    confidence: float | None = None
    provider_error: dict[str, object | None] | None = None


class AIIntakeService:
    def __init__(self, ai_client: OpenAIIntakeClient):
        self.ai_client = ai_client

    from app.observability.langsmith_tracing import safe_traceable
    @safe_traceable(name="GPT-5.2 Structured Intake")
    def process_message(
        self, session: ChatSession, recent_messages: list[dict[str, str]], latest_message: str
    ) -> IntakeProcessingResult:
        # 1. Hardcoded safety checks first
        if is_possible_emergency(latest_message):
            return IntakeProcessingResult(session.collected_data_json, EMERGENCY_MESSAGE, "emergency")

        if requires_handoff(latest_message):
            return IntakeProcessingResult(session.collected_data_json, HANDOFF_MESSAGE, "care_team_handoff")

        # 2. Call AI
        required_fields = [
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
        if session.collected_data_json.get("patient_type") == "new":
            required_fields.extend(["full_name", "date_of_birth", "phone", "email", "insurance_provider"])

        missing_fields = [f for f in required_fields if f not in session.collected_data_json]

        try:
            response: ChatModelResponse = self.ai_client.analyze_message(
                current_state=session.current_step,
                recent_messages=recent_messages,
                latest_message=latest_message,
                required_fields=missing_fields,
            )
        except OpenAIIntegrationError as error:
            return IntakeProcessingResult(
                session.collected_data_json,
                "I’m having trouble interpreting that safely right now. Please try again in a moment.",
                provider_error=error.provider_error,
            )

        # 3. Handle model safety overrides
        if response.get("possible_emergency"):
            return IntakeProcessingResult(session.collected_data_json, EMERGENCY_MESSAGE, "emergency")

        if response.get("handoff_requested"):
            return IntakeProcessingResult(session.collected_data_json, HANDOFF_MESSAGE, "care_team_handoff")

        # 4. Apply corrections and new fields. Already collected fields are stable
        # unless the model explicitly reports a patient correction.
        updated_data = dict(session.collected_data_json)
        corrections = response.get("corrections", [])
        correction_fields: dict[str, Any] = {}
        for correction in response.get("corrections", []):
            field = correction.get("field")
            new_value = correction.get("new_value")
            if isinstance(field, str) and new_value not in (None, ""):
                correction_fields[field] = new_value

        # 5. Add new extracted fields
        extracted_fields = {
            key: value for key, value in response.get("extracted_fields", {}).items() if value not in (None, "")
        }
        for key, value in _deterministic_fields_from_text(latest_message).items():
            if key == "preferred_time_of_day":
                extracted_fields[key] = value
            else:
                extracted_fields.setdefault(key, value)

        new_fields = {
            key: value
            for key, value in extracted_fields.items()
            if key in correction_fields or _field_missing(updated_data, key)
        }
        new_fields.update(correction_fields)

        # Validate newly extracted fields
        clean_fields, errors = validate_intake_fields(new_fields)
        severity_error = _invalid_severity_from_text(latest_message)
        severity_was_addressed = (
            "severity" in missing_fields or "severity" in extracted_fields or "severity" in new_fields
        )
        if severity_error and severity_was_addressed:
            clean_fields.pop("severity", None)
            errors["severity"] = severity_error
        if errors:
            updated_data.update(clean_fields)
            return IntakeProcessingResult(
                updated_data,
                f"I couldn’t record that because: {' '.join(errors.values())} Could you clarify?",
                invalid_fields=errors,
                corrections=corrections,
                confidence=response.get("confidence"),
            )

        _default_availability_preference(updated_data, clean_fields)
        updated_data.update(clean_fields)
        assistant_reply = _next_question(
            required_fields,
            updated_data,
            response.get("assistant_message", "Okay. What is the next detail?"),
        )

        return IntakeProcessingResult(
            updated_data,
            assistant_reply,
            corrections=corrections,
            off_topic=bool(response.get("off_topic")),
            confidence=response.get("confidence"),
        )


def _invalid_severity_from_text(message: str) -> str | None:
    if re.search(r"(?<!\d)-\s*\d{1,2}\b", message):
        return "Severity must be between 1 and 10."
    matches = re.findall(
        r"\b(?:severity|pain|rate)\D{0,30}(-?\d{1,2})\b|(?<!\d)(-?\d{1,2})\s*(?:/|out of)\s*10\b",
        message,
        flags=re.IGNORECASE,
    )
    for left, right in matches:
        raw_value = left or right
        if not raw_value:
            continue
        value = int(raw_value)
        if value < 1 or value > 10:
            return "Severity must be between 1 and 10."
    return None


def _field_missing(data: dict[str, Any], field: str) -> bool:
    return data.get(field) in (None, "")


def _next_question(required_fields: list[str], updated_data: dict[str, Any], model_reply: str) -> str:
    for field in required_fields:
        if _field_missing(updated_data, field):
            return APPROVED_FIELD_QUESTIONS.get(field, model_reply)
    return model_reply


def _deterministic_fields_from_text(message: str) -> dict[str, Any]:
    raw_lower = message.lower()
    cleaned = re.sub(r"[^a-z0-9\s/]", " ", raw_lower)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    tokens = set(cleaned.split())
    fields: dict[str, Any] = {}

    if re.search(r"\bright\b", cleaned):
        fields["side"] = "right"
    elif re.search(r"\bleft\b", cleaned):
        fields["side"] = "left"
    elif {"both", "bilateral"} & tokens:
        fields["side"] = "bilateral"

    body_aliases = {body_part: set(aliases) for body_part, aliases in BODY_PARTS.items()}
    body_aliases["Knee"].add("nee")
    for body_part, aliases in body_aliases.items():
        if aliases & tokens or any(
            " " in alias and re.search(rf"\b{re.escape(alias)}\b", cleaned) for alias in aliases
        ):
            fields["body_part"] = body_part
            break

    non_orthopedic_area = fields.get("body_part") not in (None, *ORTHOPEDIC_BODY_PARTS)
    if {"sports", "athletic", "acl", "soccer", "basketball", "baseball"} & tokens:
        fields["issue_type"] = "Sports Medicine"
    elif {"fracture", "fractured", "broke", "broken"} & tokens:
        fields["issue_type"] = "Fracture"
    elif {"replacement", "arthroplasty"} & tokens:
        fields["issue_type"] = "Joint Replacement"
    elif {"rash", "itching", "itchy"} & tokens:
        fields["issue_type"] = "Rash/Itching"
    elif {"infection", "infected"} & tokens:
        fields["issue_type"] = "Infection"
    elif {"numbness", "numb", "tingling"} & tokens:
        fields["issue_type"] = "Numbness/Tingling"
    elif {"breathing", "breath", "cough"} & tokens:
        fields["issue_type"] = "Breathing Concern"
    elif re.search(r"\bfollow[-\s]*up\b|\bfollowup\b", cleaned) and non_orthopedic_area:
        fields["issue_type"] = "Follow-up"
    elif "routine" in tokens and non_orthopedic_area:
        fields["issue_type"] = "Routine Consult"
    elif {"pain", "hurts", "hurt", "ache", "aches", "sore", "headache", "earache"} & tokens:
        fields["issue_type"] = "Pain" if non_orthopedic_area else "General"
    elif {"pain", "consultation", "general"} & tokens:
        fields["issue_type"] = "General"

    if re.search(r"\bfollow[-\s]*up\b|\bfollowup\b", cleaned):
        fields["appointment_type"] = "follow_up"
    elif re.search(r"\bpost\s*op\b|\bpostop\b", cleaned):
        fields["appointment_type"] = "post_op"
    elif "urgent" in tokens:
        fields["appointment_type"] = "urgent"
    elif re.search(r"\bnew\s+patient\b|\bfirst\s+visit\b", cleaned):
        fields["appointment_type"] = "new_patient"

    if "east" in tokens:
        fields["preferred_location"] = "EAST"
    elif "north" in tokens:
        fields["preferred_location"] = "NORTH"
    elif "main" in tokens:
        fields["preferred_location"] = "MAIN"
    elif "west" in tokens or "westside" in tokens:
        fields["preferred_location"] = "WEST"
    elif "south" in tokens:
        fields["preferred_location"] = "SOUTH"
    elif re.search(
        r"\bnearest\s+available\b|\bany\s+location\b|\bearliest\s+available\s+at\s+any\s+location\b", cleaned
    ):
        fields["preferred_location"] = "ANY"

    time_of_day = _time_of_day_from_text(cleaned, tokens)
    if time_of_day:
        fields["preferred_time_of_day"] = time_of_day

    if _availability_order_preference(cleaned, tokens):
        fields["preferred_date_or_time"] = "earliest possible"
        fields.setdefault("preferred_time_of_day", "any")

    duration = _duration_from_text(cleaned)
    if duration:
        fields["symptom_duration"] = duration

    severity = _severity_from_text(raw_lower)
    if severity is not None:
        fields["severity"] = severity

    if ("body_part" in fields or "issue_type" in fields) and len(cleaned) > 8:
        fields["chief_complaint"] = message.strip()

    return fields


def _time_of_day_from_text(cleaned: str, tokens: set[str]) -> str | None:
    if "morning" in tokens or "mornings" in tokens:
        return "morning"
    if "afternoon" in tokens or "afternoons" in tokens:
        return "afternoon"
    if (
        "anytime" in tokens
        or re.search(r"\bany\s*(time|appointment)?\b", cleaned)
        or re.search(r"\b(do\s+not|don t|dont)\s+care\s+what\s+time\b", cleaned)
        or re.search(r"\bno\s+(time\s+)?preference\b", cleaned)
        or re.search(r"\bwhatever\s+time\b", cleaned)
    ):
        return "any"
    return None


def _availability_order_preference(cleaned: str, tokens: set[str]) -> bool:
    return (
        "earliest" in tokens
        or "soonest" in tokens
        or re.search(r"\bas\s+soon\s+as\s+possible\b|\basap\b", cleaned) is not None
        or re.search(r"\bfirst\s+(?:available|appointment\s+available|opening|openings)\b", cleaned) is not None
    )


def _default_availability_preference(updated_data: dict[str, Any], clean_fields: dict[str, Any]) -> None:
    preferred_time = clean_fields.get("preferred_time_of_day") or updated_data.get("preferred_time_of_day")
    if (
        preferred_time in {"morning", "afternoon", "any"}
        and _field_missing(updated_data, "preferred_date_or_time")
        and _field_missing(clean_fields, "preferred_date_or_time")
    ):
        clean_fields["preferred_date_or_time"] = "earliest possible"


def _duration_from_text(cleaned: str) -> str | None:
    amount = r"\d+|one|two|three|four|five|six|seven|eight|nine|ten|couple|few"
    match = re.search(
        rf"\b(?:for\s+)?(?P<qualifier>about\s+|around\s+|almost\s+|over\s+|under\s+)?"
        rf"(?P<amount>{amount})\s+(?P<unit>days?|weeks?|months?|years?)\b",
        cleaned,
    )
    if not match:
        return None
    qualifier = (match.group("qualifier") or "").strip()
    duration = f"{match.group('amount')} {match.group('unit')}"
    return f"{qualifier} {duration}".strip()


def _severity_from_text(cleaned: str) -> int | None:
    if re.search(r"(?<!\d)-\s*\d{1,2}\b", cleaned):
        return None
    numeric = re.findall(r"\b\d{1,2}\b", cleaned)
    if len(numeric) != 1:
        return None
    value = int(numeric[0])
    if 1 <= value <= 10:
        return value
    return None
