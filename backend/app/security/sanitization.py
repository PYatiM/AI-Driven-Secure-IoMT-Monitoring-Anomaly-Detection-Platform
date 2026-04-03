from __future__ import annotations

import re
import unicodedata
from typing import Any

CONTROL_CHARACTERS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
WHITESPACE_RE = re.compile(r"\s+")


def sanitize_text_input(
    value: Any,
    *,
    lowercase: bool = False,
    collapse_whitespace: bool = True,
    strip: bool = True,
    empty_to_none: bool = False,
):
    if value is None or not isinstance(value, str):
        return value

    sanitized = unicodedata.normalize("NFKC", value)
    sanitized = CONTROL_CHARACTERS_RE.sub(" ", sanitized)
    if collapse_whitespace:
        sanitized = WHITESPACE_RE.sub(" ", sanitized)
    if strip:
        sanitized = sanitized.strip()
    if lowercase:
        sanitized = sanitized.lower()
    if empty_to_none and sanitized == "":
        return None
    return sanitized


def require_non_empty_sanitized_text(
    value: Any,
    *,
    field_name: str,
    lowercase: bool = False,
) -> str:
    sanitized = sanitize_text_input(value, lowercase=lowercase)
    if not isinstance(sanitized, str) or sanitized == "":
        raise ValueError(f"{field_name} must not be blank.")
    return sanitized


def sanitize_email_input(value: Any) -> str:
    sanitized = require_non_empty_sanitized_text(
        value,
        field_name="email",
        lowercase=True,
    )
    if any(character.isspace() for character in sanitized):
        raise ValueError("email must not contain whitespace.")
    return sanitized


def validate_secret_input(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    if CONTROL_CHARACTERS_RE.search(value):
        raise ValueError(f"{field_name} contains unsupported control characters.")
    return value


def sanitize_nested_strings(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text_input(value)
    if isinstance(value, list):
        return [sanitize_nested_strings(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_nested_strings(item) for key, item in value.items()}
    return value
