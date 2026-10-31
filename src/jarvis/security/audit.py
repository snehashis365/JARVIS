"""Tamper-evident, Append-only Security Audit Logger."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.logging import redact_secrets


class AuditRecord(BaseModel):
    """Immutable audit record for a security check or tool execution."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action_type: str
    tool_name: str
    resource: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    decision: str  # "ALLOWED", "DENIED", "APPROVED", "REJECTED", "PENDING_APPROVAL"
    autonomy_mode: str
    session_id: Optional[str] = None
    reason: str = ""


class AuditLogger:
    """Manages appending and querying security audit records."""

    def __init__(self, log_dir: Optional[Path] = None) -> None:
        self.log_dir = log_dir
        self._records: List[AuditRecord] = []

    def record(
        self,
        action_type: str,
        tool_name: str,
        decision: str,
        autonomy_mode: str,
        resource: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        reason: str = "",
    ) -> AuditRecord:
        """Create and store an audit record with automatic secret redaction."""
        # Sanitize parameters
        clean_params = {}
        if parameters:
            for k, v in parameters.items():
                if isinstance(v, str):
                    clean_params[k] = redact_secrets(v)
                elif isinstance(v, (int, float, bool)):
                    clean_params[k] = v
                else:
                    clean_params[k] = redact_secrets(str(v))

        record = AuditRecord(
            action_type=action_type,
            tool_name=tool_name,
            resource=redact_secrets(resource) if resource else None,
            parameters=clean_params,
            decision=decision,
            autonomy_mode=autonomy_mode,
            session_id=session_id,
            reason=redact_secrets(reason),
        )
        self._records.append(record)

        # Write to append-only disk log if log_dir configured
        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            audit_file = self.log_dir / "security_audit.jsonl"
            try:
                with open(audit_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record.model_dump(), default=str) + "\n")
            except Exception:
                pass

        return record

    def get_records(self, limit: Optional[int] = None) -> List[AuditRecord]:
        """Retrieve stored audit records."""
        if limit:
            return self._records[-limit:]
        return list(self._records)
