"""Session and Task state models."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.models.messages import ChatMessage, ToolResult


class TaskStatus(str, Enum):
    """Execution status of an orchestrator task."""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskProgress(BaseModel):
    """Real-time progress update for an ongoing task."""
    task_id: str
    step: int
    max_steps: int
    current_action: str
    status: TaskStatus
    message: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskState(BaseModel):
    """Complete state snapshot of a bounded task."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    goal: str
    status: TaskStatus = TaskStatus.PENDING
    current_step: int = 0
    max_steps: int = 10
    tool_results: List[ToolResult] = Field(default_factory=list)
    pending_approval_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionState(BaseModel):
    """Conversation session containing message history and active tasks."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "New Conversation"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    messages: List[ChatMessage] = Field(default_factory=list)
    active_task_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
