"""Envelope encryption for highly-classified datasets. Phase 3 / §9.4.

Two-key model:
  - The **data encryption key (DEK)** is a fresh per-asset key used for actual
    bytes (AES-256-GCM).
  - The **key-encryption key (KEK)** is held in the corporate KMS / HSM.
    Plaintext DEK never leaves the publishing service; we store
    ``KMS.encrypt(KEK, DEK)`` alongside the asset and re-fetch the plaintext
    DEK by calling ``KMS.decrypt`` whenever the asset is read.

This module ships a **dev KMS** that uses a static key from
``MELP_KMS_DEV_KEY`` (32-byte hex). Production deploys swap the dev backend
for a real one (HashiCorp Vault Transit, AWS KMS, GCP KMS) via the
``MELP_KMS_BACKEND`` env var. The contract is the four methods on ``KMS``.

Datasets opt in via ``classification`` ∈ {``secret``, ``export-controlled``}.
The dataset service refuses to publish those without envelope-encrypted
assets; the runner refuses to read them without a successful KMS decrypt.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Protocol


@dataclass
class EncryptedBlob:
    ciphertext: bytes
    wrapped_dek: bytes
    nonce: bytes
    aad: str = ""


class KMS(Protocol):
    def wrap_dek(self, dek: bytes) -> bytes: ...
    def unwrap_dek(self, wrapped: bytes) -> bytes: ...


# ---------- Dev backend ----------
class DevKMS:
    """Symmetric XOR-wrap with a static key. **Not for prod.** Documented here
    so dev / tests can exercise the encryption path without a real KMS."""

    def __init__(self, master_hex: str | None = None):
        master = bytes.fromhex(
            master_hex or os.environ.get("MELP_KMS_DEV_KEY", "00" * 32)
        )
        if len(master) != 32:
            raise ValueError("MELP_KMS_DEV_KEY must be 32 bytes hex")
        self._master = master

    def wrap_dek(self, dek: bytes) -> bytes:
        return bytes(a ^ b for a, b in zip(dek, _expand(self._master, len(dek)), strict=True))

    def unwrap_dek(self, wrapped: bytes) -> bytes:
        return self.wrap_dek(wrapped)


def _expand(key: bytes, n: int) -> bytes:
    out = b""
    counter = 0
    while len(out) < n:
        out += hmac.new(key, counter.to_bytes(4, "big"), hashlib.sha256).digest()
        counter += 1
    return out[:n]


# ---------- Public API ----------
def get_kms() -> KMS:
    backend = os.environ.get("MELP_KMS_BACKEND", "dev")
    if backend == "dev":
        return DevKMS()
    # Production wiring goes here. Vault / AWS / GCP clients import lazily.
    raise NotImplementedError(f"KMS backend {backend!r} not wired")


def encrypt_blob(plaintext: bytes, *, aad: str = "") -> EncryptedBlob:
    """Generate a fresh DEK, wrap with KEK, encrypt plaintext with the DEK.

    AES-GCM via the ``cryptography`` library if available; falls back to a
    deterministic XOR-based stream when not (dev/test only).
    """
    kms = get_kms()
    dek = os.urandom(32)
    nonce = os.urandom(12)
    ciphertext = _aead_encrypt(dek, nonce, plaintext, aad.encode())
    return EncryptedBlob(
        ciphertext=ciphertext,
        wrapped_dek=kms.wrap_dek(dek),
        nonce=nonce,
        aad=aad,
    )


def decrypt_blob(blob: EncryptedBlob) -> bytes:
    kms = get_kms()
    dek = kms.unwrap_dek(blob.wrapped_dek)
    return _aead_decrypt(dek, blob.nonce, blob.ciphertext, blob.aad.encode())


def to_envelope(blob: EncryptedBlob) -> bytes:
    """Serialise an EncryptedBlob to a single self-describing byte string."""
    payload = {
        "v": 1,
        "n": base64.b64encode(blob.nonce).decode(),
        "k": base64.b64encode(blob.wrapped_dek).decode(),
        "a": blob.aad,
        "c": base64.b64encode(blob.ciphertext).decode(),
    }
    import json

    return ("MELP-ENV1:" + json.dumps(payload, separators=(",", ":"))).encode()


def from_envelope(raw: bytes) -> EncryptedBlob:
    import json

    if not raw.startswith(b"MELP-ENV1:"):
        raise ValueError("not a MELP envelope")
    p = json.loads(raw[len(b"MELP-ENV1:") :])
    return EncryptedBlob(
        ciphertext=base64.b64decode(p["c"]),
        wrapped_dek=base64.b64decode(p["k"]),
        nonce=base64.b64decode(p["n"]),
        aad=p.get("a", ""),
    )


# ---------- AEAD primitives ----------
def _aead_encrypt(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore[import-not-found]

        return AESGCM(key).encrypt(nonce, plaintext, aad)
    except ImportError:
        # Dev-only fallback: stream cipher + HMAC tag.
        stream = _expand(key, len(plaintext))
        ct = bytes(a ^ b for a, b in zip(plaintext, stream, strict=True))
        tag = hmac.new(key, nonce + aad + ct, hashlib.sha256).digest()[:16]
        return ct + tag


def _aead_decrypt(key: bytes, nonce: bytes, ct: bytes, aad: bytes) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore[import-not-found]

        return AESGCM(key).decrypt(nonce, ct, aad)
    except ImportError:
        body, tag = ct[:-16], ct[-16:]
        expected = hmac.new(key, nonce + aad + body, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(tag, expected):
            raise ValueError("envelope tag mismatch")
        stream = _expand(key, len(body))
        return bytes(a ^ b for a, b in zip(body, stream, strict=True))
