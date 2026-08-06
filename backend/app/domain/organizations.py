from __future__ import annotations

ORGANIZATION_TYPES_BY_SLUG = {
    "default-orthopedics": "Orthopedics",
    "northside-dental-care": "Dental",
    "summit-family-medicine": "Primary Care",
    "westview-dermatology-clinic": "Dermatology",
    "harbor-pediatrics": "Pediatrics",
}


def organization_type_for_slug(slug: str) -> str:
    return ORGANIZATION_TYPES_BY_SLUG.get(slug, "Medical organization")
