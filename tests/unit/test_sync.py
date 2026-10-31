"""Unit tests for Phase 8 Decoupled Cloud Sync and E2EE Continuity.

Verifies AES-256-GCM encryption/decryption, PBKDF2 key derivation,
peer device registration/revocation, state export/merge, and zero-leakage boundaries.
"""

import pytest
from cryptography.exceptions import InvalidTag

from jarvis.config import Settings
from jarvis.memory.manager import MemoryManager
from jarvis.memory.models import MemoryCategory
from jarvis.sync.client import SyncClient
from jarvis.sync.crypto import E2EEEngine
from jarvis.sync.models import EncryptedSyncBundle, SyncableState
from jarvis.tools.skills.manager import SkillManager
from jarvis.voice.personality import PersonalityManager


def test_e2ee_encryption_and_decryption():
    """Verify AES-256-GCM authenticated encryption and key derivation."""
    passphrase = "correct-horse-battery-staple-123"
    message = b"Secret personal assistant payload"

    # Encrypt
    ciphertext, nonce, salt = E2EEEngine.encrypt(message, passphrase)
    assert len(nonce) == 12
    assert len(salt) == 16
    assert ciphertext != message

    # Decrypt with correct passphrase
    decrypted = E2EEEngine.decrypt(ciphertext, nonce, salt, passphrase)
    assert decrypted == message

    # Decryption with incorrect passphrase fails authentication tag verification
    with pytest.raises(Exception):
        E2EEEngine.decrypt(ciphertext, nonce, salt, "wrong-passphrase")


def test_nonce_uniqueness():
    """Verify distinct random nonces and salts are generated per encryption call."""
    passphrase = "test-passphrase"
    data = b"identical payload"

    c1, n1, s1 = E2EEEngine.encrypt(data, passphrase)
    c2, n2, s2 = E2EEEngine.encrypt(data, passphrase)

    assert n1 != n2
    assert s1 != s2
    assert c1 != c2


def test_sync_client_device_lifecycle():
    """Verify local device registration, peer device pairing, and revocation."""
    client = SyncClient(device_name="Workstation")
    assert client.local_device.device_name == "Workstation"
    assert client.local_device.is_revoked is False

    # Register peer device
    phone = client.register_device("Mobile Phone")
    assert phone.device_name == "Mobile Phone"
    assert len(client.list_devices()) == 2

    # Revoke peer device
    assert client.revoke_device(phone.device_id) is True
    revoked_phone = [d for d in client.list_devices() if d.device_id == phone.device_id][0]
    assert revoked_phone.is_revoked is True

    # Primary device cannot be revoked
    assert client.revoke_device(client.local_device.device_id) is False


def test_sync_export_and_merge():
    """Verify exporting syncable state, encrypting bundle, and merging on peer."""
    p_mgr = PersonalityManager()
    p_mgr.update_profile(name="SyncAssistant", tone="warm")
    m_mgr = MemoryManager()
    m_mgr.store(
        category=MemoryCategory.PREFERENCE,
        title="Preferred Language",
        content="User speaks English and French.",
    )
    s_mgr = SkillManager()

    client_a = SyncClient(device_name="Device A")
    passphrase = "shared-user-sync-secret"

    # 1. Export syncable state
    state_a = client_a.export_sync_state(p_mgr, m_mgr, s_mgr)
    assert state_a.personality["name"] == "SyncAssistant"
    assert len(state_a.memories) == 1
    # Verify zero-leakage: raw secrets not exported
    assert "OPENAI_API_KEY" not in str(state_a.model_dump())

    # 2. Encrypt into bundle
    bundle = client_a.create_encrypted_bundle(state_a, passphrase)
    assert isinstance(bundle, EncryptedSyncBundle)
    assert bundle.ciphertext_b64 is not None

    # 3. Simulate Peer Device B receiving and merging bundle
    client_b = SyncClient(device_name="Device B")
    p_mgr_b = PersonalityManager()
    m_mgr_b = MemoryManager()
    s_mgr_b = SkillManager()

    # Decrypt
    decrypted_state = client_b.decrypt_bundle(bundle, passphrase)
    assert decrypted_state.personality["name"] == "SyncAssistant"

    # Merge
    stats = client_b.merge_sync_state(decrypted_state, p_mgr_b, m_mgr_b, s_mgr_b)
    assert stats["personality_updated"] is True
    assert stats["memories_merged"] == 1
    assert p_mgr_b.get_profile().name == "SyncAssistant"
    assert len(m_mgr_b.list_memories()) == 1


def test_offline_mode_independent_from_sync():
    """Verify assistant functions 100% locally when sync is disabled."""
    settings = Settings(JARVIS_SYNC_ENABLED=False)
    client = SyncClient(app_settings=settings)
    assert client.is_enabled is False


@pytest.mark.asyncio
async def test_sync_api_endpoints(async_client):
    """Verify /api/sync/ REST endpoints."""
    # 1. Status
    res = await async_client.get("/api/sync/status")
    assert res.status_code == 200
    status_data = res.json()
    assert "device_id" in status_data
    assert "registered_devices_count" in status_data

    # 2. Devices list
    dev_res = await async_client.get("/api/sync/devices")
    assert dev_res.status_code == 200
    assert len(dev_res.json()) >= 1

    # 3. Register device
    reg_res = await async_client.post("/api/sync/devices", json={"device_name": "Tablet Device"})
    assert reg_res.status_code == 200
    new_dev = reg_res.json()
    assert new_dev["device_name"] == "Tablet Device"

    # 4. Revoke device
    del_res = await async_client.delete(f"/api/sync/devices/{new_dev['device_id']}")
    assert del_res.status_code == 200
    assert del_res.json()["revoked"] is True
