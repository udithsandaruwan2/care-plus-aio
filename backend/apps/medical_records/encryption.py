"""Re-export shared field encryption (Step 34 → Step 68 shared module)."""

from apps.common.encryption import (  # noqa: F401
    FieldEncryptionError,
    decrypt_field,
    decrypt_json,
    encrypt_field,
    encrypt_json,
)
