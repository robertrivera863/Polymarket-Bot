"""Encrypted storage for API credentials (Fernet + PBKDF2 passphrase).

Keeps POLYMARKET_KEY_ID / POLYMARKET_SECRET_KEY out of plaintext .env files.
"""
from __future__ import annotations

import base64
import json
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

DEFAULT_FILE = "secrets.enc"
_ITERATIONS = 480_000


class SecretsError(Exception):
    pass


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=_ITERATIONS
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))


def store_keys(
    key_id: str, secret_key: str, passphrase: str, path: str = DEFAULT_FILE
) -> None:
    if not key_id or not secret_key or not passphrase:
        raise SecretsError("key_id, secret_key, and passphrase are all required")
    salt = os.urandom(16)
    fernet = Fernet(_derive_key(passphrase, salt))
    payload = json.dumps({"key_id": key_id, "secret_key": secret_key}).encode()
    blob = json.dumps(
        {
            "salt": base64.b64encode(salt).decode(),
            "data": fernet.encrypt(payload).decode(),
        }
    )
    with open(path, "w") as fh:
        fh.write(blob)


def load_keys(passphrase: str, path: str = DEFAULT_FILE) -> tuple[str, str]:
    try:
        with open(path) as fh:
            blob = json.loads(fh.read())
        salt = base64.b64decode(blob["salt"])
        fernet = Fernet(_derive_key(passphrase, salt))
        payload = json.loads(fernet.decrypt(blob["data"].encode()).decode())
    except (FileNotFoundError, KeyError, json.JSONDecodeError, InvalidToken, ValueError) as exc:
        raise SecretsError(f"could not load secrets: {exc}") from exc
    return payload.get("key_id", ""), payload.get("secret_key", "")


def store_password(password: str, path: str = ".dashboard_password") -> None:
    if not password:
        raise SecretsError("password cannot be empty")
    with open(path, "w") as f:
        f.write(password + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
