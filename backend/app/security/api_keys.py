import hashlib
import secrets

API_KEY_PREFIX_LENGTH = 12
API_KEY_TOKEN_BYTES = 32
API_KEY_PREFIX = "iomt"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def build_api_key_lookup(api_key: str) -> tuple[str, str]:
    return api_key[:API_KEY_PREFIX_LENGTH], hash_api_key(api_key)


def generate_device_api_key() -> tuple[str, str, str]:
    api_key = f"{API_KEY_PREFIX}_{secrets.token_urlsafe(API_KEY_TOKEN_BYTES)}"
    api_key_prefix, api_key_hash = build_api_key_lookup(api_key)
    return api_key, api_key_prefix, api_key_hash
