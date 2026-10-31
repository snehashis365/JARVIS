"""Data Models for Decoupled End-to-End Encrypted Cloud Sync."""

import base64
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DeviceRecord(BaseModel):
    """Registered client device in synchronization network."""
    device_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_name: str
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_synced_at: Optional[datetime] = None
    is_revoked: bool = False


class SyncableState(BaseModel):
    """Encapsulates safe user-approved data categories eligible for synchronization."""
    personality: Dict[str, Any] = Field(default_factory=dict)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    memories: List[Dict[str, Any]] = Field(default_factory=list)
    skills_config: Dict[str, Any] = Field(default_factory=dict)
    updated_at_iso: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EncryptedSyncBundle(BaseModel):
    """Encrypted envelope transmitted to sync relays or peer devices."""
    version: int = 1
    device_id: str
    ciphertext_b64: str
    nonce_b64: str
    salt_b64: str
    timestamp_iso: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def from_crypto_output(
        cls, device_id: str, ciphertext: bytes, nonce: bytes, salt: bytes
    ) -> "EncryptedSyncBundle":
        """Instantiate bundle from raw cryptographic bytes."""
        return cls(
            device_id=device_id,
            ciphertext_b64=base64.b64encode(ciphertext).decode("ascii"),
            nonce_b64=base64.b64encode(nonce).decode("ascii"),
            salt_b64=base64.b64encode(salt).decode("ascii"),
        )

    def to_crypto_input(self) -> tuple[bytes, bytes, bytes]:
        """Decode base64 fields into raw bytes."""
        return (
            base64.b64decode(self.ciphertext_b64.encode("ascii")),
            base64.b64decode(self.nonce_b64.encode("ascii")),
            base64.b64decode(self.salt_b64.encode("ascii")),
        )
