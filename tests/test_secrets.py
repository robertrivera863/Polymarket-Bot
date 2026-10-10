import os
import tempfile

from polymarket_bot.secrets import SecretsError, load_keys, store_keys


def test_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "s.enc")
        store_keys("kid", "sk-secret", "hunter2", path)
        key_id, secret = load_keys("hunter2", path)
        assert key_id == "kid"
        assert secret == "sk-secret"


def test_wrong_passphrase_raises():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "s.enc")
        store_keys("kid", "sk-secret", "right", path)
        try:
            load_keys("wrong", path)
        except SecretsError:
            return
        raise AssertionError("expected SecretsError for wrong passphrase")


def test_store_rejects_empty_fields():
    try:
        store_keys("", "sk", "pw", "x")
    except SecretsError:
        return
    raise AssertionError("expected SecretsError for empty key_id")
