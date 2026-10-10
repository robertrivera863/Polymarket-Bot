import base64
import time

from cryptography.hazmat.primitives.asymmetric import ed25519


class AuthError(Exception):
    pass


def build_auth_headers(method: str, path: str, key_id: str, secret_key: str) -> dict:
    if not key_id or not secret_key:
        raise AuthError("Missing POLYMARKET_KEY_ID or POLYMARKET_SECRET_KEY")

    try:
        seed = base64.b64decode(secret_key)[:32]
    except Exception as exc:  # noqa: BLE001 - surface a clear message to the user
        raise AuthError(f"Could not decode POLYMARKET_SECRET_KEY: {exc}") from exc

    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
    timestamp = str(int(time.time() * 1000))
    message = f"{timestamp}{method}{path}".encode()
    signature = base64.b64encode(private_key.sign(message)).decode()

    return {
        "X-PM-Access-Key": key_id,
        "X-PM-Timestamp": timestamp,
        "X-PM-Signature": signature,
        "Content-Type": "application/json",
    }
