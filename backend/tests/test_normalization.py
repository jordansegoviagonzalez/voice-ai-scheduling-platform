from __future__ import annotations

from datetime import date

import pytest

from app.domain.normalization import normalize_body_part, normalize_date_of_birth, normalize_issue_type
from app.errors import ApiError


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("I broke my ankle", "Fracture"),
        ("possible broken wrist", "Fracture"),
        ("knee replacement consultation", "Joint Replacement"),
        ("ACL injury from soccer", "Sports Medicine"),
        ("general hip pain", "General"),
    ],
)
def test_issue_type_normalization(phrase: str, expected: str) -> None:
    assert normalize_issue_type(phrase) == expected


def test_uncertain_issue_requires_clarification() -> None:
    with pytest.raises(ApiError) as exc:
        normalize_issue_type("something feels strange")
    assert exc.value.code == "ISSUE_TYPE_CLARIFICATION_REQUIRED"


def test_body_part_aliases() -> None:
    assert normalize_body_part("back") == "Spine"
    assert normalize_body_part("wrist") == "Hand/Wrist"


@pytest.mark.parametrize(
    "phrase",
    [
        "1990-04-12",
        "April 12 1990",
        "April 12, 1990",
        "Apr 12 1990",
        "04/12/1990",
        "4/12/1990",
        "04-12-1990",
        "4-12-1990",
        "April 12 19 90",
        "4 12 1990",
        "4 12 19 90",
        "April twelfth nineteen ninety",
    ],
)
def test_date_of_birth_normalization_accepts_voice_formats(phrase: str) -> None:
    assert normalize_date_of_birth(phrase) == date(1990, 4, 12)


def test_date_of_birth_normalization_accepts_ordinal_voice_day() -> None:
    assert normalize_date_of_birth("April twentieth nineteen ninety") == date(1990, 4, 20)


def test_date_of_birth_normalization_rejects_invalid_dates() -> None:
    with pytest.raises(ApiError) as exc:
        normalize_date_of_birth("April 40 1990")
    assert exc.value.status_code == 422
    assert exc.value.message == "date_of_birth could not be parsed."
