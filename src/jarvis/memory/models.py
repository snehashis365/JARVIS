"""Memory Data Models and Category Definitions."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class MemoryCategory(str, Enum):
    """Tiered memory classification categories."""
    WORKING = "working"          # Active task context and short-term buffers
    PREFERENCE = "preference"    # User explicit preferences, tone, formatting choices
    FACT = "fact"                # Stable verified facts about the user or project
    EPISODIC = "episodic"        # Summaries of past completed tasks and outcomes
    PROCEDURAL = "procedural"    # Learned operational patterns and recipes


class MemoryItem(BaseModel):
    """Individual structured memory item."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: MemoryCategory
    title: str
    content: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
