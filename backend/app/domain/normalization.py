from __future__ import annotations

import re
from datetime import date

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

MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

DAY_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
    "sixteenth": 16,
    "seventeenth": 17,
    "eighteenth": 18,
    "nineteenth": 19,
    "twentieth": 20,
    "thirtieth": 30,
}

DAY_TENS = {"twenty": 20, "thirty": 30}
DAY_UNITS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
}
YEAR_TENS = {
    "zero": 0,
    "oh": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


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


def normalize_date_of_birth(value: str, field: str = "date_of_birth") -> date:
    cleaned = value.strip()
    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        pass

    numeric = re.fullmatch(r"\s*(\d{1,2})[/-](\d{1,2})[/-](\d{4})\s*", cleaned)
    if numeric:
        month, day, year = (int(part) for part in numeric.groups())
        return _build_date(year, month, day, field)

    tokens = _date_tokens(cleaned)
    parsed = _parse_numeric_spoken_date(tokens, field) or _parse_month_spoken_date(tokens, field)
    if parsed is not None:
        return parsed
    raise ApiError(
        "VALIDATION_ERROR",
        f"{field} could not be parsed.",
        422,
        {field: ["Could not parse date"]},
    )


def _date_tokens(value: str) -> list[str]:
    cleaned = value.lower().replace(",", " ")
    cleaned = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", cleaned)
    return re.findall(r"[a-z]+|\d+", cleaned)


def _parse_numeric_spoken_date(tokens: list[str], field: str) -> date | None:
    if len(tokens) == 3 and all(token.isdigit() for token in tokens):
        month, day, year = (int(token) for token in tokens)
        if len(tokens[2]) == 4:
            return _build_date(year, month, day, field)
    if len(tokens) == 4 and all(token.isdigit() for token in tokens):
        month = int(tokens[0])
        day = int(tokens[1])
        if len(tokens[2]) == 2 and len(tokens[3]) == 2:
            return _build_date(int(f"{tokens[2]}{tokens[3]}"), month, day, field)
    return None


def _parse_month_spoken_date(tokens: list[str], field: str) -> date | None:
    if len(tokens) < 3:
        return None
    month = MONTHS.get(tokens[0])
    if month is None:
        return None
    day_result = _parse_day(tokens, 1)
    if day_result is None:
        return None
    day, year_index = day_result
    year = _parse_year(tokens[year_index:])
    if year is None:
        return None
    return _build_date(year, month, day, field)


def _parse_day(tokens: list[str], index: int) -> tuple[int, int] | None:
    token = tokens[index]
    if token.isdigit():
        return int(token), index + 1
    if token in DAY_WORDS:
        return DAY_WORDS[token], index + 1
    if token in DAY_TENS and index + 1 < len(tokens):
        next_token = tokens[index + 1]
        if next_token in DAY_WORDS:
            return DAY_TENS[token] + DAY_WORDS[next_token], index + 2
        if next_token in DAY_UNITS:
            return DAY_TENS[token] + DAY_UNITS[next_token], index + 2
    return None


def _parse_year(tokens: list[str]) -> int | None:
    if len(tokens) == 1 and tokens[0].isdigit() and len(tokens[0]) == 4:
        return int(tokens[0])
    if len(tokens) == 2 and all(token.isdigit() and len(token) == 2 for token in tokens):
        return int(f"{tokens[0]}{tokens[1]}")
    if len(tokens) == 2 and tokens[0] in {"nineteen", "twenty"} and tokens[1] in YEAR_TENS:
        century = 1900 if tokens[0] == "nineteen" else 2000
        return century + YEAR_TENS[tokens[1]]
    if len(tokens) == 3 and tokens[0] in {"nineteen", "twenty"} and tokens[1] in YEAR_TENS and tokens[2] in DAY_UNITS:
        century = 1900 if tokens[0] == "nineteen" else 2000
        return century + YEAR_TENS[tokens[1]] + DAY_UNITS[tokens[2]]
    return None


def _build_date(year: int, month: int, day: int, field: str) -> date:
    try:
        return date(year, month, day)
    except ValueError as error:
        raise ApiError(
            "VALIDATION_ERROR",
            f"{field} could not be parsed.",
            422,
            {field: ["Could not parse date"]},
        ) from error


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
