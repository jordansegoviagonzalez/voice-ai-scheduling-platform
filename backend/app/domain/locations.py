from __future__ import annotations

from typing import Protocol

CANONICAL_LOCATION_CODES = ("MAIN", "EAST", "NORTH", "WEST", "SOUTH")
LOCATION_SORT_ORDER = {code: index for index, code in enumerate(CANONICAL_LOCATION_CODES)}


class LocationLike(Protocol):
    id: int
    code: str


def location_sort_key(location: LocationLike) -> tuple[int, int]:
    return LOCATION_SORT_ORDER.get(location.code, len(LOCATION_SORT_ORDER)), location.id
