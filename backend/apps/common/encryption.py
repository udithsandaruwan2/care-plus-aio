"""App-level AES (Fernet) field encryption for PHI at rest (Steps 34 / 68).

pgcrypto is enabled on Postgres for future DB-native crypto; Fernet keeps
ciphertext opaque to the application DB role today without ORM friction.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class FieldEncryptionError(Exception):
    """Raised when ciphertext cannot be decrypted."""


def _fernet_key_bytes() -> bytes:
    raw = (getattr(settings, "FIELD_ENCRYPTION_KEY", "") or "").strip()
    if raw:
        return raw.encode("utf-8")
    secret = getattr(settings, "SECRET_KEY", "insecure-dev-key-change-me")
    derived = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(derived)


def encrypt_field(plaintext: str) -> str:
    if plaintext is None or plaintext == "":
        return ""
    token = Fernet(_fernet_key_bytes()).encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def decrypt_field(ciphertext: str) -> str:
    if ciphertext is None or ciphertext == "":
        return ""
    try:
        plain = Fernet(_fernet_key_bytes()).decrypt(ciphertext.encode("ascii"))
    except InvalidToken as exc:
        raise FieldEncryptionError("Invalid or corrupted ciphertext.") from exc
    return plain.decode("utf-8")


def encrypt_json(value: Any) -> str:
    """Encrypt a JSON-serializable value; empty dict/list → empty ciphertext."""
    if value is None:
        return ""
    if value == {} or value == []:
        return ""
    return encrypt_field(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def decrypt_json(ciphertext: str, *, default: Any = None) -> Any:
    if ciphertext is None or ciphertext == "":
        return {} if default is None else default
    return json.loads(decrypt_field(ciphertext))
