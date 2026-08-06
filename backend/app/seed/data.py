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


class OrganizationSeed(TypedDict):
    slug: str
    name: str
    status: str
    timezone: str


DEMO_ORGANIZATIONS: list[OrganizationSeed] = [
    {
        "slug": "northside-dental-care",
        "name": "Northside Dental Care",
        "status": "ACTIVE",
        "timezone": "America/Los_Angeles",
    },
    {
        "slug": "summit-family-medicine",
        "name": "Summit Family Medicine",
        "status": "ACTIVE",
        "timezone": "America/Denver",
    },
    {
        "slug": "westview-dermatology-clinic",
        "name": "Westview Dermatology Clinic",
        "status": "ACTIVE",
        "timezone": "America/Chicago",
    },
    {
        "slug": "harbor-pediatrics",
        "name": "Harbor Pediatrics",
        "status": "ACTIVE",
        "timezone": "America/New_York",
    },
]


LOCATIONS: list[LocationSeed] = [
    {"code": "MAIN", "name": "Main Campus"},
    {"code": "EAST", "name": "East Clinic"},
    {"code": "NORTH", "name": "North Clinic"},
    {"code": "WEST", "name": "Westside Office"},
    {"code": "SOUTH", "name": "South Clinic"},
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
        "capabilities": [
            ("Knee", "Fracture"),
            ("Knee", "Sports Medicine"),
            ("Foot/Ankle", "Fracture"),
            ("Foot/Ankle", "General"),
        ],
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
        "locations": ["MAIN", "EAST", "NORTH", "WEST", "SOUTH"],
        "capabilities": [("Foot/Ankle", "Fracture"), ("Foot/Ankle", "General"), ("Hand/Wrist", "General")],
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
        "capabilities": [("Foot/Ankle", "Joint Replacement"), ("Foot/Ankle", "General"), ("Spine", "General")],
    },
]
