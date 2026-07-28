from __future__ import annotations

from typing import Protocol

from app.domain.normalization import BODY_PARTS

GENERAL_ORTHOPEDICS_DOCTOR = ("David", "Nguyen")
GENERAL_ORTHOPEDICS_SUPPORTED_ISSUES = {"General", "Sports Medicine"}
GENERAL_ORTHOPEDICS_SUPPORTED_BODY_PARTS = set(BODY_PARTS)

PRIMARY_SPECIALTIES = {
    ("Maria", "Chen"): "Hip and Knee Joint Replacement",
    ("James", "Walsh"): "Foot and Ankle Orthopedics",
    ("Aisha", "Patel"): "Hip and Spine Orthopedics",
    ("Robert", "Kim"): "Hand, Wrist, and Shoulder Orthopedics",
    ("Linda", "Torres"): "Shoulder, Hip, and Knee Orthopedics",
    GENERAL_ORTHOPEDICS_DOCTOR: "General Orthopedics",
    ("Sarah", "O'Brien"): "Spine Orthopedics",
    ("Michael", "Brooks"): "Shoulder and Knee Orthopedics",
    ("Priya", "Sharma"): "Foot, Ankle, and Hip Orthopedics",
    ("Thomas", "Reed"): "Hand, Wrist, and Spine Orthopedics",
    ("Elena", "Vasquez"): "Lower-Extremity and Shoulder Orthopedics",
    ("Carlos", "Mendez"): "Foot, Ankle, and Spine Orthopedics",
}


class PhysicianLike(Protocol):
    first_name: str
    last_name: str


def is_general_orthopedics(doctor: PhysicianLike) -> bool:
    return (doctor.first_name, doctor.last_name) == GENERAL_ORTHOPEDICS_DOCTOR


def primary_specialty(doctor: PhysicianLike) -> str:
    return PRIMARY_SPECIALTIES.get((doctor.first_name, doctor.last_name), "Orthopedic Specialist")


def general_orthopedics_can_evaluate(body_part: str, issue_type: str) -> bool:
    return body_part in GENERAL_ORTHOPEDICS_SUPPORTED_BODY_PARTS and issue_type in GENERAL_ORTHOPEDICS_SUPPORTED_ISSUES
