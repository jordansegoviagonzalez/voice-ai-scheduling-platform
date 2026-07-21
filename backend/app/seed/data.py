from __future__ import annotations

from typing import TypedDict


class LocationSeed(TypedDict):
    code: str
    name: str


class DoctorSeed(TypedDict):
    first_name: str
    last_name: str
    accepts_new_patients: bool
    locations: list[str]
    capabilities: list[tuple[str, str]]


LOCATIONS: list[LocationSeed] = [
    {"code": "MAIN", "name": "Main Campus"},
    {"code": "NORTH", "name": "North Clinic"},
    {"code": "WEST", "name": "Westside Office"},
]

DOCTORS: list[DoctorSeed] = [
    {
        "first_name": "Maria",
        "last_name": "Chen",
        "accepts_new_patients": True,
        "locations": ["MAIN"],
        "capabilities": [("Knee", "Joint Replacement"), ("Knee", "Sports Medicine"), ("Hip", "Joint Replacement")],
    },
    {
        "first_name": "James",
        "last_name": "Walsh",
        "accepts_new_patients": True,
        "locations": ["NORTH"],
        "capabilities": [("Knee", "Fracture"), ("Knee", "Sports Medicine"), ("Foot/Ankle", "Fracture")],
    },
    {
        "first_name": "Aisha",
        "last_name": "Patel",
        "accepts_new_patients": False,
        "locations": ["MAIN"],
        "capabilities": [("Hip", "Joint Replacement"), ("Spine", "General")],
    },
    {
        "first_name": "Robert",
        "last_name": "Kim",
        "accepts_new_patients": True,
        "locations": ["WEST"],
        "capabilities": [
            ("Hand/Wrist", "Fracture"),
            ("Hand/Wrist", "Sports Medicine"),
            ("Shoulder", "Sports Medicine"),
        ],
    },
    {
        "first_name": "Linda",
        "last_name": "Torres",
        "accepts_new_patients": True,
        "locations": ["MAIN", "NORTH"],
        "capabilities": [("Shoulder", "Sports Medicine"), ("Knee", "Joint Replacement"), ("Hip", "General")],
    },
    {
        "first_name": "David",
        "last_name": "Nguyen",
        "accepts_new_patients": True,
        "locations": ["NORTH"],
        "capabilities": [("Foot/Ankle", "Fracture"), ("Hand/Wrist", "General")],
    },
    {
        "first_name": "Sarah",
        "last_name": "O'Brien",
        "accepts_new_patients": False,
        "locations": ["WEST"],
        "capabilities": [("Spine", "Fracture")],
    },
    {
        "first_name": "Michael",
        "last_name": "Brooks",
        "accepts_new_patients": True,
        "locations": ["MAIN"],
        "capabilities": [
            ("Knee", "Joint Replacement"),
            ("Shoulder", "Joint Replacement"),
            ("Shoulder", "Sports Medicine"),
        ],
    },
    {
        "first_name": "Priya",
        "last_name": "Sharma",
        "accepts_new_patients": True,
        "locations": ["NORTH"],
        "capabilities": [("Hip", "Fracture"), ("Foot/Ankle", "Joint Replacement")],
    },
    {
        "first_name": "Thomas",
        "last_name": "Reed",
        "accepts_new_patients": False,
        "locations": ["WEST"],
        "capabilities": [("Hand/Wrist", "Sports Medicine"), ("Spine", "General")],
    },
    {
        "first_name": "Elena",
        "last_name": "Vasquez",
        "accepts_new_patients": True,
        "locations": ["MAIN", "WEST"],
        "capabilities": [
            ("Knee", "Fracture"),
            ("Knee", "Sports Medicine"),
            ("Knee", "Joint Replacement"),
            ("Hip", "Sports Medicine"),
            ("Hip", "Joint Replacement"),
            ("Shoulder", "Fracture"),
        ],
    },
    {
        "first_name": "Carlos",
        "last_name": "Mendez",
        "accepts_new_patients": True,
        "locations": ["NORTH"],
        "capabilities": [("Foot/Ankle", "Joint Replacement"), ("Spine", "General")],
    },
]
