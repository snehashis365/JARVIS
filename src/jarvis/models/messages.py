"""Chat message and tool execution models."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message role definitions."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    """Specification of an invoked tool call."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Result of an executed tool call."""
    tool_call_id: str
    tool_name: str
    status: str = Field(default="success")  # "success", "error", "rejected"
    output: Any = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0


class TokenUsage(BaseModel):
    """Token consumption statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatMessage(BaseModel):
    """Normalized chat message representation."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: MessageRole
    content: str = ""
    name: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    usage: Optional[TokenUsage] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
