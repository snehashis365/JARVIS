"""Tool Registry and Execution Runtime."""

from typing import Any, Dict, List, Optional
from jarvis.models.messages import ToolCall, ToolResult
from jarvis.security.permissions import PermissionManager
from jarvis.tools.base import BaseTool
from jarvis.tools.builtin.fs import DeleteFileTool, ListDirectoryTool, ReadFileTool, SearchFilesTool, WriteFileTool
from jarvis.tools.builtin.search import WebFetchTool, WebSearchTool
from jarvis.tools.builtin.system import CalculateExpressionTool, DateTimeNowTool, ExecuteShellCommandTool, SystemDiagnosticsTool


class ToolRegistry:
    """Registry maintaining active tools and coordinating safe permission-gated execution."""

    def __init__(self, permission_manager: Optional[PermissionManager] = None) -> None:
        self.permission_manager = permission_manager or PermissionManager()
        self._tools: Dict[str, BaseTool] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register core built-in workspace, system, and web tools."""
        builtins: List[BaseTool] = [
            ReadFileTool(),
            WriteFileTool(),
            DeleteFileTool(),
            ListDirectoryTool(),
            SearchFilesTool(),
            WebSearchTool(),
            WebFetchTool(),
            SystemDiagnosticsTool(),
            DateTimeNowTool(),
            CalculateExpressionTool(),
            ExecuteShellCommandTool(),
        ]
        for t in builtins:
            self.register(t)

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Retrieve a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Generate OpenAI/standard function-calling schemas for all registered tools."""
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.definition.parameters_schema,
                }
            })
        return schemas

    async def execute_tool(
        self,
        tool_call: ToolCall,
        session_id: Optional[str] = None,
        approval_token: Optional[str] = None,
    ) -> ToolResult:
        """Execute a tool call deterministically through the permission manager."""
        tool = self.get(tool_call.tool_name)
        if not tool:
            return ToolResult(
                tool_call_id=tool_call.id,
                tool_name=tool_call.tool_name,
                status="error",
                output=None,
                error_message=f"Unknown tool '{tool_call.tool_name}'. Registered tools: {list(self._tools.keys())}",
            )

        result = await tool.execute(
            arguments=tool_call.arguments,
            permission_manager=self.permission_manager,
            session_id=session_id,
            approval_token=approval_token,
        )
        result.tool_call_id = tool_call.id
        return result
