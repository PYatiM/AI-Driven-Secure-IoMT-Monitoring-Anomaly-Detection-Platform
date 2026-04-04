from __future__ import annotations

import argparse
from typing import Iterable

from backend.app.security.key_storage import (
    DATA_ENCRYPTION_KEY_NAME,
    DEVICE_TOKEN_SECRET_KEY_NAME,
    JWT_SECRET_KEY_NAME,
    build_bootstrap_secret_map,
    get_key_storage,
    get_key_storage_status,
)

ALLOWED_SECRET_NAMES = {
    JWT_SECRET_KEY_NAME,
    DEVICE_TOKEN_SECRET_KEY_NAME,
    DATA_ENCRYPTION_KEY_NAME,
}


def _require_storage():
    status = get_key_storage_status()
    storage = get_key_storage()
    if not status.enabled:
        raise SystemExit("Secure key storage is disabled. Set SECURE_KEY_STORAGE_ENABLED=true first.")
    if storage is None:
        raise SystemExit(
            "Secure key storage is not configured. Set KEY_STORAGE_MASTER_KEY before using this tool."
        )
    return storage, status


def _print_secret_names(names: Iterable[str]) -> None:
    for name in sorted(names):
        print(name)


def command_init(_: argparse.Namespace) -> int:
    storage, status = _require_storage()
    secret_map = build_bootstrap_secret_map()
    for name, value in secret_map.items():
        storage.set_secret(name, value)

    print(f"Initialized secure key store at {status.path}")
    print("Stored secrets:")
    _print_secret_names(secret_map.keys())
    return 0


def command_set(args: argparse.Namespace) -> int:
    storage, status = _require_storage()
    if args.name not in ALLOWED_SECRET_NAMES:
        raise SystemExit(
            f"Unsupported secret name '{args.name}'. Use one of: {', '.join(sorted(ALLOWED_SECRET_NAMES))}."
        )

    storage.set_secret(args.name, args.value)
    print(f"Stored {args.name} in secure key store {status.path}")
    return 0


def command_list(_: argparse.Namespace) -> int:
    storage, status = _require_storage()
    names = storage.list_secret_names()
    print(f"Secure key store path: {status.path}")
    print("Stored secrets:")
    if not names:
        print("<empty>")
        return 0

    _print_secret_names(names)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage the encrypted application key store."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="Initialize the secure key store using configured or generated secrets.",
    )
    init_parser.set_defaults(func=command_init)

    set_parser = subparsers.add_parser(
        "set",
        help="Store a single secret in the secure key store.",
    )
    set_parser.add_argument("name", help="Secret name to store.")
    set_parser.add_argument("value", help="Secret value to store.")
    set_parser.set_defaults(func=command_set)

    list_parser = subparsers.add_parser(
        "list",
        help="List the secret names currently stored in the secure key store.",
    )
    list_parser.set_defaults(func=command_list)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
