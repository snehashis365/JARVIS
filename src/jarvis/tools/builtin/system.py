"""System Diagnostics and Environment Inspection Tool."""

import os
import platform
import sys
from typing import Any, Dict
from jarvis.security.policy import ActionType
from jarvis.tools.base import BaseTool, ToolDefinition


class SystemDiagnosticsTool(BaseTool):
    """Tool to inspect safe local system parameters and resource availability."""

    def __init__(self) -> None:
        super().__init__(
            ToolDefinition(
                name="system_diagnostics",
                description="Retrieve safe host diagnostic metrics: OS, architecture, Python version, CPU count.",
                action_type=ActionType.READ,
                parameters_schema={
                    "type": "object",
                    "properties": {},
                },
            )
        )

    async def run(self, **kwargs: Any) -> Dict[str, Any]:
        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "python_version": sys.version.split()[0],
            "cpu_count": os.cpu_count() or 1,
            "platform_detail": platform.platform(),
        }


class DateTimeNowTool(BaseTool):
    """Tool to retrieve current system date, time, and timezone information."""

    def __init__(self) -> None:
        super().__init__(
            ToolDefinition(
                name="datetime_now",
                description="Get the current date, time, day of the week, and local timezone.",
                action_type=ActionType.READ,
                parameters_schema={
                    "type": "object",
                    "properties": {},
                },
            )
        )

    async def run(self, **kwargs: Any) -> Dict[str, Any]:
        from datetime import datetime, timezone
        now = datetime.now()
        utc_now = datetime.now(timezone.utc)
        return {
            "iso_timestamp": now.isoformat(),
            "utc_timestamp": utc_now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day_of_week": now.strftime("%A"),
            "timezone": str(now.astimezone().tzinfo),
        }


class CalculateExpressionTool(BaseTool):
    """Tool for safe mathematical calculation without unsafe eval."""

    def __init__(self) -> None:
        super().__init__(
            ToolDefinition(
                name="calculate_expression",
                description="Evaluate a mathematical expression safely (e.g. '24 * 365', 'sqrt(144) + 10', '2**16').",
                action_type=ActionType.READ,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Mathematical formula to compute."
                        }
                    },
                    "required": ["expression"],
                },
            )
        )

    async def run(self, expression: str, **kwargs: Any) -> Dict[str, Any]:
        import ast
        import math
        import operator

        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
        }
        allowed_names = {
            "pi": math.pi,
            "e": math.e,
            "sqrt": math.sqrt,
            "abs": abs,
            "round": round,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "log10": math.log10,
        }

        def eval_node(node: Any) -> Any:
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            elif isinstance(node, ast.BinOp):
                op_type = type(node.op)
                if op_type in operators:
                    return operators[op_type](eval_node(node.left), eval_node(node.right))
                raise ValueError(f"Unsupported binary operator: {op_type.__name__}")
            elif isinstance(node, ast.UnaryOp):
                op_type = type(node.op)
                if op_type in operators:
                    return operators[op_type](eval_node(node.operand))
                raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
            elif isinstance(node, ast.Name) and node.id in allowed_names:
                return allowed_names[node.id]
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in allowed_names:
                fn = allowed_names[node.func.id]
                args = [eval_node(a) for a in node.args]
                return fn(*args)
            raise ValueError(f"Unsafe or unsupported expression syntax: {type(node).__name__}")

        try:
            parsed = ast.parse(expression.strip(), mode="eval")
            result = eval_node(parsed.body)
            return {"expression": expression, "result": result}
        except Exception as exc:
            return {"expression": expression, "error": str(exc)}


class ExecuteShellCommandTool(BaseTool):
    """Tool to execute a bounded terminal shell command (requires explicit confirmation)."""

    def __init__(self) -> None:
        super().__init__(
            ToolDefinition(
                name="execute_shell_command",
                description="Execute a bounded shell command within the workspace. Mutating action requiring approval.",
                action_type=ActionType.EXECUTE,
                requires_approval_by_default=True,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Shell command line to execute."
                        },
                        "timeout_seconds": {
                            "type": "number",
                            "description": "Maximum execution time in seconds.",
                            "default": 15.0
                        }
                    },
                    "required": ["command"],
                },
            )
        )

    async def run(self, command: str, timeout_seconds: float = 15.0, **kwargs: Any) -> Dict[str, Any]:
        import asyncio
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
            out_str = stdout.decode("utf-8", errors="replace")[:4000]
            err_str = stderr.decode("utf-8", errors="replace")[:4000]
            return {
                "command": command,
                "exit_code": proc.returncode,
                "stdout": out_str,
                "stderr": err_str,
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {
                "command": command,
                "error": f"Command timed out after {timeout_seconds} seconds.",
                "exit_code": -1,
            }
