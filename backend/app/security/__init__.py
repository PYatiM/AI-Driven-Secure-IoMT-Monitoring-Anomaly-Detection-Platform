"""Security helpers for authentication and authorization."""

from backend.app.security.api_keys import build_api_key_lookup, generate_device_api_key
from backend.app.security.auth import (
    create_access_token,
    create_device_access_token,
    decode_access_token,
    decode_device_access_token,
    hash_password,
    verify_password,
)
from backend.app.security.encryption import decrypt_text, encrypt_text, is_encrypted
from backend.app.security.sanitization import (
    require_non_empty_sanitized_text,
    sanitize_email_input,
    sanitize_nested_strings,
    sanitize_text_input,
    validate_secret_input,
)

__all__ = [
    "build_api_key_lookup",
    "create_access_token",
    "create_device_access_token",
    "decode_access_token",
    "decode_device_access_token",
    "decrypt_text",
    "encrypt_text",
    "generate_device_api_key",
    "hash_password",
    "is_encrypted",
    "require_non_empty_sanitized_text",
    "sanitize_email_input",
    "sanitize_nested_strings",
    "sanitize_text_input",
    "validate_secret_input",
    "verify_password",
]
