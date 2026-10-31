"""Declarative Skill Manifest and Validation Model."""

from typing import List
from pydantic import BaseModel, Field

from jarvis.security.policy import ActionType


class SkillManifest(BaseModel):
    """Specification of an installable and inspectable skill."""
    name: str = Field(..., pattern=r"^[a-zA-Z0-9_\-]+$")
    version: str = "0.1.0"
    description: str
    instructions: str
    required_tools: List[str] = Field(default_factory=list)
    declared_permissions: List[ActionType] = Field(default_factory=list)
    author: str = "Jarvis Assistant"
    enabled: bool = True
