from __future__ import annotations

import re

from app.errors import ApiError

BODY_PARTS = {
    "Knee": {"knee", "kneecap"},
    "Hip": {"hip"},
    "Shoulder": {"shoulder"},
    "Hand/Wrist": {"hand", "wrist", "hand/wrist", "hand and wrist"},
    "Foot/Ankle": {"foot", "ankle", "foot/ankle", "foot and ankle"},
    "Spine": {"spine", "back", "neck"},
}

ISSUE_TYPES = {"Fracture", "Joint Replacement", "Sports Medicine", "General"}


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if value.startswith("+") and 10 <= len(digits) <= 15:
        return f"+{digits}"
    raise ApiError(
        "INVALID_PHONE",
        "Enter a valid phone number, including country code when outside the United States.",
        422,
        {"phone": ["Invalid phone number"]},
    )


def normalize_body_part(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value.strip().lower())
    for canonical, aliases in BODY_PARTS.items():
        if cleaned in aliases:
            return canonical
    raise ApiError(
        "UNSUPPORTED_BODY_PART",
        "The body part must be knee, hip, shoulder, hand/wrist, foot/ankle, or spine.",
        422,
        {"body_part": ["Unsupported body part"]},
    )


def normalize_issue_type(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s/]", " ", value.lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    exact = {
        "fracture": "Fracture",
        "joint replacement": "Joint Replacement",
        "sports medicine": "Sports Medicine",
        "general": "General",
    }
    if cleaned in exact:
        return exact[cleaned]

    tokens = set(cleaned.split())
    # Specific clinical categories outrank generic words such as "consultation" or "pain".
    if {"broke", "broken", "fracture", "fractured"} & tokens:
        return "Fracture"
    if {"replacement", "arthroplasty"} & tokens:
        return "Joint Replacement"
    if {"acl", "sports", "soccer", "baseball", "basketball", "athletic"} & tokens:
        return "Sports Medicine"
    if {"general", "pain", "consultation", "ongoing"} & tokens:
        return "General"
    raise ApiError(
        "ISSUE_TYPE_CLARIFICATION_REQUIRED",
        "Please clarify whether this is a fracture, joint replacement, sports injury, or general pain/consultation.",
        422,
        {"issue_type": ["Issue type is uncertain"]},
    )
