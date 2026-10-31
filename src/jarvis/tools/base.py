"""Base Tool Class and Execution Contracts."""

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from jarvis.models.messages import ToolResult
from jarvis.security.permissions import PermissionManager
from jarvis.security.policy import ActionType


class ToolDefinition(BaseModel):
    """Metadata and parameter schema for tool discovery and LLM registration."""
    name: str
    description: str
    action_type: ActionType
    parameters_schema: Dict[str, Any]
    requires_approval_by_default: bool = False
    timeout_seconds: float = 30.0


class BaseTool(ABC):
    """Abstract base class for all tools."""

    def __init__(self, definition: ToolDefinition) -> None:
        self.definition = definition

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def description(self) -> str:
        return self.definition.description

    @property
    def action_type(self) -> ActionType:
        return self.definition.action_type

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        """Internal execution logic implemented by the concrete tool."""
        pass

    async def execute(
        self,
        arguments: Dict[str, Any],
        permission_manager: PermissionManager,
        session_id: Optional[str] = None,
        approval_token: Optional[str] = None,
    ) -> ToolResult:
        """Execute tool safely through deterministic permission manager."""
        start = time.perf_counter()

        # Extract target path if tool deals with filesystem
        target_path = arguments.get("path") or arguments.get("file_path") or arguments.get("directory_path")

        # 1. Deterministic Permission Check
        decision = permission_manager.evaluate_action(
            tool_name=self.name,
            action_type=self.action_type,
            resource_path=target_path,
            parameters=arguments,
            session_id=session_id,
            justification=f"Execution of tool '{self.name}'",
            approval_token=approval_token,
        )

        if not decision.allowed:
            elapsed = (time.perf_counter() - start) * 1000.0
            status = "waiting_approval" if decision.requires_approval else "rejected"
            return ToolResult(
                tool_call_id="",
                tool_name=self.name,
                status=status,
                output=None,
                error_message=decision.reason,
                execution_time_ms=elapsed,
            )

        # 2. Execute with resolved path if available
        exec_args = dict(arguments)
        if decision.resolved_path and target_path:
            # Pass verified canonical path
            if "path" in exec_args:
                exec_args["path"] = decision.resolved_path
            elif "file_path" in exec_args:
                exec_args["file_path"] = decision.resolved_path
            elif "directory_path" in exec_args:
                exec_args["directory_path"] = decision.resolved_path

        try:
            output = await self.run(**exec_args)
            elapsed = (time.perf_counter() - start) * 1000.0
            return ToolResult(
                tool_call_id="",
                tool_name=self.name,
                status="success",
                output=output,
                execution_time_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000.0
            return ToolResult(
                tool_call_id="",
                tool_name=self.name,
                status="error",
                output=None,
                error_message=str(exc),
                execution_time_ms=elapsed,
            )
