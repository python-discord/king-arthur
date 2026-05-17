import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA3_256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_HKDF_INFO = b"king-arthur-motd-v1"
_NONCE_LEN = 12


def _derive_key(raw_key_hex: str) -> bytes:
    """Derive a 256-bit AES key from the hex-encoded env var value via HKDF-SHA3-256."""
    raw = bytes.fromhex(raw_key_hex)
    return HKDF(
        algorithm=SHA3_256(),
        length=32,
        salt=None,
        info=_HKDF_INFO,
    ).derive(raw)


def encrypt_motd(plaintext: bytes, raw_key_hex: str) -> bytes:
    """Encrypt *plaintext* and return ``nonce || ciphertext+tag``."""
    key = _derive_key(raw_key_hex)
    nonce = os.urandom(_NONCE_LEN)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt_motd(blob: bytes, raw_key_hex: str) -> bytes:
    """Decrypt a blob produced by :func:`encrypt_motd`."""
    key = _derive_key(raw_key_hex)
    nonce, ciphertext = blob[:_NONCE_LEN], blob[_NONCE_LEN:]
    return AESGCM(key).decrypt(nonce, ciphertext, None)
