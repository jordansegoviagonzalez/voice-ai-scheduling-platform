from typing import Any, Literal, TypedDict


class ExtractedFields(TypedDict, total=False):
    patient_type: Literal["new", "returning"]
    full_name: str
    date_of_birth: str
    phone: str
    email: str
    insurance_provider: str
    chief_complaint: str
    body_part: str
    side: Literal["left", "right", "bilateral", "not_applicable"]
    symptom_duration: str
    severity: int
    appointment_type: str
    issue_type: str
    preferred_location: str
    preferred_date_or_time: str
    preferred_time_of_day: Literal["morning", "afternoon", "any"]
    preferred_physician: str


class ChatModelResponse(TypedDict):
    intent: str
    assistant_message: str
    extracted_fields: ExtractedFields
    corrections: list[dict[str, Any]]
    off_topic: bool
    possible_emergency: bool
    handoff_requested: bool
    confidence: float
