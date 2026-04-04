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
from backend.app.security.key_storage import (
    DATA_ENCRYPTION_KEY_NAME,
    DEVICE_TOKEN_SECRET_KEY_NAME,
    JWT_SECRET_KEY_NAME,
    KeyStorageStatus,
    build_bootstrap_secret_map,
    generate_secret_value,
    get_data_encryption_key,
    get_device_token_secret_key,
    get_jwt_secret_key,
    get_key_storage,
    get_key_storage_status,
    resolve_secret_value,
)
from backend.app.security.sanitization import (
    require_non_empty_sanitized_text,
    sanitize_email_input,
    sanitize_nested_strings,
    sanitize_text_input,
    validate_secret_input,
)

__all__ = [
    "build_api_key_lookup",
    "build_bootstrap_secret_map",
    "create_access_token",
    "create_device_access_token",
    "DATA_ENCRYPTION_KEY_NAME",
    "decode_access_token",
    "decode_device_access_token",
    "decrypt_text",
    "DEVICE_TOKEN_SECRET_KEY_NAME",
    "encrypt_text",
    "generate_device_api_key",
    "generate_secret_value",
    "get_data_encryption_key",
    "get_device_token_secret_key",
    "get_jwt_secret_key",
    "get_key_storage",
    "get_key_storage_status",
    "hash_password",
    "is_encrypted",
    "JWT_SECRET_KEY_NAME",
    "KeyStorageStatus",
    "require_non_empty_sanitized_text",
    "resolve_secret_value",
    "sanitize_email_input",
    "sanitize_nested_strings",
    "sanitize_text_input",
    "validate_secret_input",
    "verify_password",
]
