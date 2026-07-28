EMERGENCY_KEYWORDS = [
    "chest pain",
    "trouble breathing",
    "numbness down one arm",
    "sudden severe headache",
    "major trauma",
    "severe bleeding",
    "loss of consciousness",
]


def is_possible_emergency(message: str) -> bool:
    text = message.lower()
    return any(keyword in text for keyword in EMERGENCY_KEYWORDS)


EMERGENCY_MESSAGE = (
    "Based on what you described, this may require emergency care. "
    "Please call 911 or go to the nearest emergency room now. "
    "I can't continue scheduling through this chat."
)
