"""End-to-End Encryption (E2EE) Engine for Client-Side Sync."""

import os
from typing import Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


class E2EEEngine:
    """Provides AES-256-GCM authenticated encryption and decryption for synchronized data."""

    @staticmethod
    def derive_key(passphrase: str, salt: bytes) -> bytes:
        """Derive 256-bit symmetric key from passphrase using PBKDF2-HMAC-SHA256."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
        )
        return kdf.derive(passphrase.encode("utf-8"))

    @classmethod
    def encrypt(cls, plaintext_bytes: bytes, passphrase: str) -> Tuple[bytes, bytes, bytes]:
        """Encrypt plaintext bytes with AES-256-GCM.
        
        Returns (ciphertext, nonce, salt).
        """
        salt = os.urandom(16)
        key = cls.derive_key(passphrase, salt)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # Standard 96-bit nonce for AES-GCM
        ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)
        return ciphertext, nonce, salt

    @classmethod
    def decrypt(cls, ciphertext: bytes, nonce: bytes, salt: bytes, passphrase: str) -> bytes:
        """Decrypt ciphertext bytes with AES-256-GCM and verify authentication tag."""
        key = cls.derive_key(passphrase, salt)
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)
