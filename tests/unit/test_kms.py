"""Envelope encryption round-trip."""
from melp.common.kms import decrypt_blob, encrypt_blob, from_envelope, to_envelope


def test_encrypt_decrypt_roundtrip():
    plaintext = b"top secret evaluation data" * 64
    blob = encrypt_blob(plaintext, aad="dataset=ds_secret")
    assert blob.ciphertext != plaintext
    assert decrypt_blob(blob) == plaintext


def test_envelope_serialise_roundtrip():
    blob = encrypt_blob(b"hello world", aad="aad-value")
    raw = to_envelope(blob)
    parsed = from_envelope(raw)
    assert decrypt_blob(parsed) == b"hello world"


def test_tampered_ciphertext_rejected():
    import pytest

    blob = encrypt_blob(b"hello world")
    blob.ciphertext = blob.ciphertext[:-1] + bytes([blob.ciphertext[-1] ^ 0x01])
    with pytest.raises(Exception):
        decrypt_blob(blob)
