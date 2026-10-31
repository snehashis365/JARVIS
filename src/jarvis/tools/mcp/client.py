"""Model Context Protocol (MCP) Client Adapter.

Converts standardized MCP tools into permission-gated Jarvis BaseTool instances.
"""

from typing import Any, Dict, List, Optional
from jarvis.security.policy import ActionType
from jarvis.tools.base import BaseTool, ToolDefinition


class MCPToolAdapter(BaseTool):
    """Wraps an external MCP tool definition and execution."""

    def __init__(
        self,
        mcp_name: str,
        description: str,
        parameters_schema: Dict[str, Any],
        mcp_client: Any,
        action_type: ActionType = ActionType.EXECUTE,
    ) -> None:
        super().__init__(
            ToolDefinition(
                name=f"mcp_{mcp_name}",
                description=description,
                action_type=action_type,
                parameters_schema=parameters_schema,
                requires_approval_by_default=True,
            )
        )
        self.raw_name = mcp_name
        self.mcp_client = mcp_client

    async def run(self, **kwargs: Any) -> Any:
        """Forward invocation to MCP server client."""
        return await self.mcp_client.call_tool(self.raw_name, kwargs)


class MockMCPClient:
    """Mock in-memory MCP client for testing and simulation."""

    def __init__(self, registered_tools: Optional[List[Dict[str, Any]]] = None) -> None:
        self.registered_tools = registered_tools or [
            {
                "name": "sqlite_query",
                "description": "Execute a safe SQL query on an MCP database.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            }
        ]

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools on the MCP server."""
        return self.registered_tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Simulate tool call on the MCP server."""
        return {"status": "mcp_executed", "tool": name, "result": f"Result for {arguments}"}


class MCPManager:
    """Discovers MCP tools and registers them as native Jarvis tools."""

    @staticmethod
    async def create_adapters_from_client(client: Any) -> List[BaseTool]:
        """Convert MCP tool declarations into Jarvis BaseTools."""
        tools = await client.list_tools()
        adapters = []
        for t in tools:
            adapter = MCPToolAdapter(
                mcp_name=t["name"],
                description=t.get("description", ""),
                parameters_schema=t.get("inputSchema", {}),
                mcp_client=client,
            )
            adapters.append(adapter)
        return adapters
