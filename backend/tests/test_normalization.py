from __future__ import annotations

import pytest

from app.domain.normalization import normalize_body_part, normalize_issue_type
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
