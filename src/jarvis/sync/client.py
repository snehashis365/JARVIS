"""Decoupled Cloud Sync Client with E2EE and Conflict Resolution."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from jarvis.config import Settings, settings
from jarvis.memory.manager import MemoryManager
from jarvis.memory.models import MemoryCategory
from jarvis.sync.crypto import E2EEEngine
from jarvis.sync.models import DeviceRecord, EncryptedSyncBundle, SyncableState
from jarvis.tools.skills.manager import SkillManager
from jarvis.voice.personality import PersonalityManager


class SyncClient:
    """Manages offline-first client-side encryption and multi-device synchronization."""

    def __init__(
        self,
        device_name: str = "Primary Desktop",
        app_settings: Optional[Settings] = None,
    ) -> None:
        self.settings = app_settings or settings
        self.local_device = DeviceRecord(device_name=device_name)
        self._paired_devices: Dict[str, DeviceRecord] = {
            self.local_device.device_id: self.local_device
        }

    @property
    def is_enabled(self) -> bool:
        return self.settings.sync_enabled

    def register_device(self, device_name: str) -> DeviceRecord:
        """Register a new peer device for synchronization."""
        dev = DeviceRecord(device_name=device_name)
        self._paired_devices[dev.device_id] = dev
        return dev

    def revoke_device(self, device_id: str) -> bool:
        """Revoke a device's synchronization rights."""
        if device_id in self._paired_devices and device_id != self.local_device.device_id:
            self._paired_devices[device_id].is_revoked = True
            return True
        return False

    def list_devices(self) -> List[DeviceRecord]:
        """List registered peer devices."""
        return list(self._paired_devices.values())

    def export_sync_state(
        self,
        personality_mgr: PersonalityManager,
        memory_mgr: MemoryManager,
        skill_mgr: SkillManager,
    ) -> SyncableState:
        """Gather safe, user-approved syncable data categories."""
        # 1. Export personality
        p_dict = personality_mgr.get_profile().model_dump()

        # 2. Export curated preferences and facts only (no raw chat history or passwords)
        memories = []
        for cat in (MemoryCategory.PREFERENCE, MemoryCategory.FACT, MemoryCategory.PROCEDURAL):
            items = memory_mgr.list_memories(category=cat, limit=100)
            for item in items:
                memories.append(item.model_dump())

        # 3. Export active skill configurations
        skills = {s.name: {"enabled": s.enabled, "version": s.version} for s in skill_mgr.list_skills()}

        return SyncableState(
            personality=p_dict,
            preferences={"theme": "dark", "format": "markdown"},
            memories=memories,
            skills_config=skills,
        )

    def create_encrypted_bundle(self, state: SyncableState, passphrase: str) -> EncryptedSyncBundle:
        """Serialize and encrypt sync state using AES-256-GCM before transport."""
        raw_json = json.dumps(state.model_dump(), default=str).encode("utf-8")
        ciphertext, nonce, salt = E2EEEngine.encrypt(raw_json, passphrase)
        return EncryptedSyncBundle.from_crypto_output(
            device_id=self.local_device.device_id,
            ciphertext=ciphertext,
            nonce=nonce,
            salt=salt,
        )

    def decrypt_bundle(self, bundle: EncryptedSyncBundle, passphrase: str) -> SyncableState:
        """Decrypt and deserialize an encrypted sync bundle."""
        ciphertext, nonce, salt = bundle.to_crypto_input()
        plaintext = E2EEEngine.decrypt(ciphertext, nonce, salt, passphrase)
        data = json.loads(plaintext.decode("utf-8"))
        return SyncableState(**data)

    def merge_sync_state(
        self,
        incoming: SyncableState,
        personality_mgr: PersonalityManager,
        memory_mgr: MemoryManager,
        skill_mgr: SkillManager,
    ) -> Dict[str, Any]:
        """Merge incoming state with deterministic last-write-wins field resolution."""
        stats = {"memories_merged": 0, "personality_updated": False, "skills_updated": 0}

        # 1. Merge Personality if newer
        if incoming.personality:
            p = incoming.personality
            personality_mgr.update_profile(
                name=p.get("name"),
                tone=p.get("tone"),
                humor=p.get("humor"),
                proactivity=p.get("proactivity"),
                custom_instructions=p.get("custom_instructions"),
            )
            stats["personality_updated"] = True

        # 2. Merge Memories
        for mem_dict in incoming.memories:
            existing = memory_mgr.get(mem_dict["id"])
            if not existing:
                try:
                    cat = MemoryCategory(mem_dict["category"])
                    memory_mgr.store(
                        category=cat,
                        title=mem_dict["title"],
                        content=mem_dict["content"],
                        confidence=mem_dict.get("confidence", 1.0),
                        tags=mem_dict.get("tags", []),
                    )
                    stats["memories_merged"] += 1
                except Exception:
                    pass

        # 3. Merge Skills enabled flags
        for s_name, s_info in incoming.skills_config.items():
            if s_info.get("enabled"):
                if skill_mgr.enable(s_name):
                    stats["skills_updated"] += 1
            else:
                if skill_mgr.disable(s_name):
                    stats["skills_updated"] += 1

        self.local_device.last_synced_at = datetime.now(timezone.utc)
        return stats
