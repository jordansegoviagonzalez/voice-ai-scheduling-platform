HANDOFF_KEYWORDS = [
    "speak to a person",
    "staff",
    "agent",
    "human",
    "real person",
    "insurance coverage",
    "insurance question",
    "billing",
    "payment",
]


def requires_handoff(message: str) -> bool:
    text = message.lower()
    return any(keyword in text for keyword in HANDOFF_KEYWORDS)


HANDOFF_MESSAGE = (
    "I understand. This would be better handled by the care team. "
    "Please call the practice directly, or a staff member can follow up with you."
)
