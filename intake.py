"""Customer intake validation shared by the UI and persistence layer."""

import hashlib
import json
import re

from config import SERVICES
from followups import URGENCY_HOURS


def validate_inquiry(
    name: str, email: str, phone: str, service: str, description: str, urgency: str
) -> tuple[str, str, str, str, str, str]:
    values = [name, email, phone, service, description, urgency]
    if not all(isinstance(value, str) for value in values):
        raise ValueError("Inquiry fields must be text.")
    name, email, phone, service, description, urgency = [value.strip() for value in values]
    if not name or len(name) > 120 or any((ord(char) < 32 or ord(char) == 127) for char in name):
        raise ValueError("Enter a customer name of 1 to 120 characters.")
    if (
        any(ord(char) < 32 or ord(char) == 127 for char in email)
        or len(email) > 254
        or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
    ):
        raise ValueError("Enter a valid email address, such as name@example.com.")
    if len(phone) > 40 or (phone and not re.fullmatch(r"[0-9+(). xX-]+", phone)):
        raise ValueError("Enter a phone number using digits, spaces or common phone punctuation.")
    if service not in SERVICES:
        raise ValueError("Select a supported service.")
    if urgency not in URGENCY_HOURS:
        raise ValueError("Select a supported urgency.")
    if len(description) > 10000 or "\x00" in description:
        raise ValueError(
            "Project descriptions must be at most 10,000 characters without null characters."
        )
    return name, email, phone, service, description, urgency


def inquiry_fingerprint(values: tuple[str, ...]) -> str:
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode("utf-8")).hexdigest()
